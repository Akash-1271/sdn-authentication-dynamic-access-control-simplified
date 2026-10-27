"""Small live demonstrations. Run from the host named in DEMO.md."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import socket
import time

from client import access_protected_service, send_auth_request


def login(password="123"):
    return send_auth_request({"action": "LOGIN", "username": "alice", "password": password})


def logout(token, allow_expired=False):
    result = send_auth_request({"action": "LOGOUT", "session_id": token})
    expired = allow_expired and result.get("error") in {"Invalid session", "Session expired"}
    if not result.get("ok") and not expired:
        raise RuntimeError("Logout/revocation was not confirmed")


def service():
    result = access_protected_service()
    if not result.startswith("ACCESS GRANTED"):
        raise RuntimeError("Unexpected service reply")
    print(result)


def denied():
    try:
        access_protected_service()
    except socket.timeout:
        print("[INCONCLUSIVE] Timeout. Pair with service self-access and deny/no-grant flows.")
        return 2
    except OSError:
        print("[INCONCLUSIVE] Connection error. Check service health and switch flows.")
        return 2
    raise RuntimeError("Service was reachable without the expected permission")


def expiry():
    result = login()
    if not result.get("ok"):
        raise RuntimeError("Login failed; check services, controller and lockout")
    try:
        service()
        wait = result["lease_seconds"] + 2
        print(f"Service worked. Waiting {wait}s; inspect the active rule in another terminal.", flush=True)
        time.sleep(wait)
        return denied()
    finally:
        logout(result["session_id"], allow_expired=True)


def lockout(recover=False):
    for attempt in range(1, 4):
        result = login("incorrect-demo-password")
        error = result.get("error", "").lower()
        expected = "invalid credentials" if attempt < 3 else "locked"
        if result.get("ok") or expected not in error:
            raise RuntimeError("Unexpected lockout state; start with an unlocked host")
        print(f"[PASS] Incorrect password {attempt} rejected")
    result = login()
    if result.get("ok") or "locked" not in result.get("error", "").lower():
        if result.get("ok"):
            logout(result["session_id"])
        raise RuntimeError("Correct credentials were not blocked during lockout")
    print("[PASS] Correct credentials rejected during IP lockout")
    if recover:
        match = re.search(r"retry in (\d+) seconds", result["error"])
        if not match:
            raise RuntimeError("Server did not advertise a lockout retry interval")
        wait = int(match[1]) + 1
        print(f"Waiting {wait}s for lockout recovery...", flush=True)
        time.sleep(wait)
        result = login()
        if not result.get("ok"):
            raise RuntimeError("Login did not recover after lockout")
        logout(result["session_id"])
        print("[PASS] Login and logout succeeded after recovery")
    return 0


def concurrent():
    tokens, failures = [], []
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            jobs = [pool.submit(login) for _ in range(5)]
            for job in as_completed(jobs):
                try:
                    result = job.result()
                    if result.get("ok"):
                        tokens.append(result["session_id"])
                    else:
                        failures.append("login rejected")
                except (OSError, ValueError):
                    failures.append("login connection failed")
    finally:
        for token in tokens:
            try:
                logout(token)
            except (OSError, ValueError, RuntimeError):
                failures.append("logout unconfirmed")
    if failures or len(tokens) != 5 or len(set(tokens)) != 5:
        raise RuntimeError("Concurrent login/unique-token/cleanup check failed")
    print("[PASS] Five concurrent logins, unique tokens, and confirmed logout")
    return 0


def controller_down():
    result = login()
    if result.get("ok"):
        logout(result["session_id"])
        raise RuntimeError("Login succeeded; the controller may still be running")
    if "controller unavailable" not in result.get("error", "").lower():
        raise RuntimeError("Login failed for a different reason")
    print("[PASS] New login rejected while controller was unavailable")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["service", "denied", "expiry", "lockout", "concurrent", "controller-down"])
    parser.add_argument("--recover", action="store_true", help="Also wait for lockout recovery")
    args = parser.parse_args()
    checks = {"service": service, "denied": denied, "expiry": expiry,
              "lockout": lambda: lockout(args.recover), "concurrent": concurrent,
              "controller-down": controller_down}
    try:
        return checks[args.mode]() or 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[FAIL] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
