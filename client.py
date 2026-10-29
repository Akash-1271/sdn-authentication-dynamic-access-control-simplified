"""Demonstrate TCP login, protected-service access, and logout."""
import json

from net_protocol import decode_json, exchange_line

AUTH_HOST, AUTH_PORT = "10.0.0.3", 9000
SERVICE_HOST, SERVICE_PORT = "10.0.0.4", 8080


def send_auth_request(request):
    frame = exchange_line((AUTH_HOST, AUTH_PORT),
                          json.dumps(request).encode("utf-8") + b"\n", timeout=5)
    response = decode_json(frame)
    if not isinstance(response, dict):
        raise ValueError("Expected a JSON object response")
    return response


def access_protected_service():
    return exchange_line((SERVICE_HOST, SERVICE_PORT), b"GET_SECRET\n", timeout=3)


def main():
    token = None
    success = False
    try:
        response = send_auth_request({"action": "LOGIN", "username": "alice", "password": "123"})
        if not response.get("ok"):
            raise RuntimeError(f"Login rejected: {response.get('error')}")
        token = response["session_id"]
        print("[PASS] Login successful")

        result = access_protected_service()
        print(result)
        if not result.startswith("ACCESS GRANTED"):
            raise RuntimeError("Unexpected protected-service response")
        print("[PASS] Protected service access succeeded")
        success = True
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[FAIL] {exc}")
    finally:
        if token:
            try:
                response = send_auth_request({"action": "LOGOUT", "session_id": token})
                if not response.get("ok"):
                    raise RuntimeError("Logout/revocation was not confirmed")
                print("[PASS] Logout successful")
            except (OSError, ValueError, RuntimeError) as exc:
                success = False
                print(f"[FAIL] Logout failed: {exc}")
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
