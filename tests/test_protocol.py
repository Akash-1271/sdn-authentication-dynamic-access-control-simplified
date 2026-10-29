"""Message framing, replay protection, deadlines and benchmark failures."""
import json
import secrets
import socket
import unittest
from unittest.mock import patch

import control_security as security
import demo_checks as demo
import performance_test as benchmark
from net_protocol import decode_json, receive_line


class ProtocolTests(unittest.TestCase):
    def test_signed_command_and_tampering(self):
        key = secrets.token_bytes(32)
        challenge = security.new_challenge()
        command = "ALLOW 10.0.0.1 10.0.0.4 8080 60"
        request = security.sign_request(command, challenge, key)
        self.assertEqual(security.verify_request(request, challenge, key), command)
        self.assertIsNone(security.verify_request(dict(request, command=command+"0"), challenge, key))
        self.assertIsNone(security.verify_request(request, challenge, secrets.token_bytes(32)))

    def test_replay_and_expired_challenge(self):
        key = secrets.token_bytes(32)
        challenge = security.new_challenge()
        request = security.sign_request("REVOKE 10.0.0.1 10.0.0.4 8080", challenge, key)
        self.assertIsNone(security.verify_request(request, security.new_challenge(), key))
        with patch.object(security.time, "time", return_value=challenge["ts"] + 31):
            self.assertIsNone(security.verify_request(request, challenge, key))

    def test_json_rejects_ambiguous_fields(self):
        for frame in ['{"v":1,"v":2}', r'{"v":1,"\u0076":1}', '{"x":NaN}', '{"x":Infinity}']:
            with self.assertRaises(ValueError):
                decode_json(frame)

    def test_frame_boundaries_eof_and_coalescing(self):
        for frame, expected in [(b"hello\n", "hello"), (b"first\nsecond\n", "first"), (b"", None)]:
            left, right = socket.socketpair()
            try:
                right.sendall(frame)
                right.shutdown(socket.SHUT_WR)
                self.assertEqual(receive_line(left, 20, 1), expected)
            finally:
                left.close()
                right.close()
        for frame in [b"x"*21+b"\n", b"incomplete", b"\xff\n"]:
            left, right = socket.socketpair()
            try:
                right.sendall(frame)
                right.shutdown(socket.SHUT_WR)
                with self.assertRaises(ValueError):
                    receive_line(left, 20, 1)
            finally:
                left.close()
                right.close()

    def test_slow_bytes_do_not_reset_deadline(self):
        clock, timeouts = [100.0], []
        class SlowSocket:
            def settimeout(self, value):
                timeouts.append(value)
            def recv(self, size):
                clock[0] += 0.06
                return b"x"
        with patch("net_protocol.time.monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(TimeoutError):
                receive_line(SlowSocket(), 100, 0.2)
        self.assertLess(timeouts[-1], timeouts[0])

    def test_benchmark_does_not_record_failed_logout(self):
        with patch.object(benchmark, "TRIALS", 1), patch.object(benchmark, "service_request", return_value=1), \
             patch.object(benchmark, "auth_request", side_effect=[{"ok": True, "session_id": "test"}, {"ok": False}]), \
             patch.object(benchmark, "append_result") as append:
            with self.assertRaises(RuntimeError):
                benchmark.run_dynamic()
        append.assert_not_called()

    def test_expiry_demo_always_cleans_token(self):
        with patch.object(demo, "login", return_value={"ok": True, "session_id": "test", "lease_seconds": 1}), \
             patch.object(demo, "service"), patch.object(demo.time, "sleep"), \
             patch.object(demo, "denied", return_value=2), patch.object(demo, "logout") as logout:
            self.assertEqual(demo.expiry(), 2)
        logout.assert_called_once_with("test", allow_expired=True)

    def test_reachable_service_is_not_reported_as_denied(self):
        with patch.object(demo, "access_protected_service", return_value="ACCESS GRANTED"):
            with self.assertRaises(RuntimeError):
                demo.denied()
        with patch.object(demo, "access_protected_service", side_effect=socket.timeout):
            self.assertEqual(demo.denied(), 2)


if __name__ == "__main__":
    unittest.main()
