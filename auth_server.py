"""TCP login/logout server: credentials -> session -> temporary switch access."""
import json
import logging
import math
import os
import secrets
import socket
import threading
import time

from control_security import load_secret
from controller_client import ControllerError, send_allow, send_revoke
from net_protocol import decode_json, receive_line as read_frame, serve_threaded

HOST, PORT = "10.0.0.3", 9000
PROTECTED_SERVER_IP, PROTECTED_SERVER_PORT = "10.0.0.4", 8080
SESSION_LEASE_SECONDS = int(os.environ.get("AUTH_LEASE_SECONDS", "60"))
LOCKOUT_SECONDS = int(os.environ.get("AUTH_LOCKOUT_SECONDS", "60"))
MAX_FAILED_ATTEMPTS = 3
DEMO_USERS = {"alice": "123", "bob": "456"}  # Public lab accounts only.

sessions = {}         # token -> username, client_ip, expires_at
failed_attempts = {}  # source IP -> consecutive incorrect passwords
locked_until = {}     # source IP -> lockout expiry
# One lock covers state AND its switch updates: login/logout/expiry cannot race.
transition_lock = threading.RLock()
logging.basicConfig(filename=os.environ.get("AUTH_LOG_FILE", "security.log"),
                    level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("auth_server")
CONTROL_ERRORS = (OSError, ValueError, ControllerError)


def remaining_lockout(client_ip):
    until = locked_until.get(client_ip, 0)
    remaining = until - time.monotonic()
    if until and remaining <= 0:
        locked_until.pop(client_ip, None)
        failed_attempts.pop(client_ip, None)
        logger.info("IP_LOCKOUT_EXPIRED client_ip=%s", client_ip)
    return max(0, remaining)


def register_failure(client_ip, username):
    count = failed_attempts.get(client_ip, 0) + 1
    failed_attempts[client_ip] = count
    # repr escapes newlines so a supplied username cannot forge log records.
    logger.warning("LOGIN_FAILURE username=%r client_ip=%s count=%s",
                   username[:128], client_ip, count)
    if count >= MAX_FAILED_ATTEMPTS:
        locked_until[client_ip] = time.monotonic() + LOCKOUT_SECONDS
        logger.warning("IP_LOCKOUT client_ip=%s seconds=%s", client_ip, LOCKOUT_SECONDS)
        return True
    return False


def end_session(session, reason):
    """Keep remaining same-IP sessions' access, or revoke if none remain.

    Callers hold transition_lock and restore a removed session if this fails.
    """
    client_ip = session["client_ip"]
    now = time.monotonic()
    remaining = [item["expires_at"] - now for item in sessions.values()
                 if item["client_ip"] == client_ip and item["expires_at"] > now]
    try:
        if remaining:
            lease = min(3600, max(1, math.ceil(max(remaining))))
            send_allow(client_ip, PROTECTED_SERVER_IP, PROTECTED_SERVER_PORT, lease)
        else:
            send_revoke(client_ip, PROTECTED_SERVER_IP, PROTECTED_SERVER_PORT)
        logger.info("ACCESS_UPDATED reason=%s client_ip=%s remaining_sessions=%s",
                    reason, client_ip, len(remaining))
        return True
    except CONTROL_ERRORS:
        logger.error("ACCESS_UPDATE_UNCONFIRMED reason=%s client_ip=%s", reason, client_ip)
        return False


def login(request, client_ip):
    username, password = request.get("username"), request.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return {"ok": False, "error": "Invalid request fields"}
    remaining = remaining_lockout(client_ip)
    if remaining:
        return {"ok": False, "error": f"IP locked; retry in {math.ceil(remaining)} seconds"}
    if username not in DEMO_USERS or DEMO_USERS[username] != password:
        locked = register_failure(client_ip, username)
        error = "IP locked after consecutive failed attempts" if locked else "Invalid credentials"
        return {"ok": False, "error": error}

    failed_attempts.pop(client_ip, None)
    token = secrets.token_urlsafe(32)
    session = {"username": username, "client_ip": client_ip,
               "expires_at": time.monotonic() + SESSION_LEASE_SECONDS}
    try:
        send_allow(client_ip, PROTECTED_SERVER_IP, PROTECTED_SERVER_PORT, SESSION_LEASE_SECONDS)
    except CONTROL_ERRORS:
        # A reply may be lost after installation. Best-effort cleanup also
        # restores an older same-IP session's remaining permission.
        end_session(session, "ALLOW_FAILED")
        return {"ok": False, "error": "Controller unavailable; access not granted"}

    sessions[token] = session  # Commit only after the switch grant is confirmed.
    logger.info("LOGIN_SUCCESS username=%s client_ip=%s", username, client_ip)
    return {"ok": True, "message": "Authentication successful", "username": username,
            "session_id": token, "lease_seconds": SESSION_LEASE_SECONDS}


def logout(request, client_ip):
    token = request.get("session_id")
    if not isinstance(token, str) or not token:
        return {"ok": False, "error": "Missing session_id"}
    session = sessions.get(token)
    if session is None or session["client_ip"] != client_ip:
        return {"ok": False, "error": "Invalid session"}

    expired = session["expires_at"] <= time.monotonic()
    del sessions[token]
    if not end_session(session, "EXPIRED" if expired else "LOGOUT"):
        sessions[token] = session
        return {"ok": False, "error": "Network revocation unconfirmed; retry logout"}
    if expired:
        return {"ok": False, "error": "Session expired"}
    return {"ok": True, "message": "Logged out successfully"}


def handle_request(request, client_ip):
    with transition_lock:
        if not isinstance(request, dict):
            return {"ok": False, "error": "Expected a JSON object"}
        if request.get("action") == "LOGIN":
            return login(request, client_ip)
        if request.get("action") == "LOGOUT":
            return logout(request, client_ip)
        return {"ok": False, "error": "Unsupported action"}


def expire_once():
    with transition_lock:
        now = time.monotonic()
        expired = [token for token, item in sessions.items() if item["expires_at"] <= now]
        for token in expired:
            session = sessions.pop(token)
            if not end_session(session, "EXPIRED"):
                sessions[token] = session  # Retry on the next sweep.


def expire_sessions():
    while True:
        time.sleep(1)
        expire_once()


def receive_line(conn):
    return read_frame(conn, 4096, 10)


def handle_client(conn, address):
    with conn:
        try:
            frame = receive_line(conn)
            if frame is None:
                return
            try:
                response = handle_request(decode_json(frame), address[0])
            except (ValueError, RecursionError):
                response = {"ok": False, "error": "Invalid JSON"}
            conn.settimeout(2)
            conn.sendall(json.dumps(response).encode("utf-8") + b"\n")
        except (OSError, ValueError) as exc:
            logger.warning("CLIENT_ERROR client_ip=%s reason=%s", address[0], type(exc).__name__)


def main():
    if not 1 <= SESSION_LEASE_SECONDS <= 3600 or LOCKOUT_SECONDS <= 0:
        raise ValueError("Lease must be 1..3600; lockout must be positive")
    load_secret()
    threading.Thread(target=expire_sessions, daemon=True).start()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        print(f"Authentication server listening on {HOST}:{PORT}", flush=True)
        print(f"Session lease: {SESSION_LEASE_SECONDS}s; lockout: {LOCKOUT_SECONDS}s", flush=True)
        try:
            serve_threaded(server, handle_client, max_connections=32,
                           busy_response=b'{"ok":false,"error":"Server busy"}\n')
        except KeyboardInterrupt:
            print("Authentication server stopped")


if __name__ == "__main__":
    main()
