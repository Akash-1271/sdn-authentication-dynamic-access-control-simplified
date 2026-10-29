"""Session behavior and real TCP application exchange, with SDN calls mocked."""
import contextlib
import io
import logging
import socketserver
import threading
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

logging.basicConfig(handlers=[logging.NullHandler()])
import auth_server as auth
import client
import demo_checks as demo
import protected_service
import performance_test as benchmark
from summarize_performance import inspect_results


@contextlib.contextmanager
def listener(handler):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            handler(self.request, self.client_address)
    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
    with Server(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_address[1]
        finally:
            server.shutdown()
            thread.join(2)


class SessionTests(unittest.TestCase):
    def setUp(self):
        auth.sessions.clear()
        auth.failed_attempts.clear()
        auth.locked_until.clear()
        self.allow = self.enterContext(patch.object(auth, "send_allow", return_value="OK"))
        self.revoke = self.enterContext(patch.object(auth, "send_revoke", return_value="OK"))
        self.enterContext(patch.object(auth, "SESSION_LEASE_SECONDS", 60))
        self.enterContext(patch.object(auth, "LOCKOUT_SECONDS", 60))

    def login(self, ip="10.0.0.1", password="123"):
        return auth.handle_request(dict(action="LOGIN", username="alice", password=password), ip)

    def logout(self, token, ip="10.0.0.1"):
        return auth.handle_request(dict(action="LOGOUT", session_id=token), ip)

    def test_login_logout_and_token_ip_binding(self):
        token = self.login()["session_id"]
        self.allow.assert_called_once_with("10.0.0.1", "10.0.0.4", 8080, 60)
        self.assertFalse(self.logout(token, "10.0.0.2")["ok"])
        self.assertTrue(self.logout(token)["ok"])
        self.assertFalse(self.logout(token)["ok"])
        self.revoke.assert_called_once()

    def test_lockout_threshold_recovery_and_other_ip(self):
        with patch.object(auth.time, "monotonic", return_value=100):
            for _ in range(3):
                self.assertFalse(self.login(password="wrong")["ok"])
            self.assertIn("locked", self.login()["error"])
            self.assertTrue(self.login("10.0.0.2")["ok"])
        with patch.object(auth.time, "monotonic", return_value=160):
            self.assertTrue(self.login()["ok"])

    def test_failed_grant_does_not_commit_session(self):
        self.allow.side_effect = OSError("offline")
        self.assertFalse(self.login()["ok"])
        self.assertFalse(auth.sessions)
        self.revoke.assert_called_once()

    def test_failed_logout_can_be_retried(self):
        token = self.login()["session_id"]
        self.revoke.side_effect = OSError("offline")
        self.assertFalse(self.logout(token)["ok"])
        self.assertIn(token, auth.sessions)
        self.revoke.side_effect = None
        self.assertTrue(self.logout(token)["ok"])

    def test_same_ip_logout_preserves_remaining_session(self):
        with patch.object(auth.time, "monotonic", return_value=100):
            first = self.login()["session_id"]
        with patch.object(auth.time, "monotonic", return_value=130):
            second = self.login()["session_id"]
            self.assertTrue(self.logout(second)["ok"])
        self.assertIn(first, auth.sessions)
        self.assertEqual(self.allow.call_args.args[-1], 30)
        self.revoke.assert_not_called()

    def test_expiry_retries_unconfirmed_revoke(self):
        with patch.object(auth.time, "monotonic", return_value=100):
            token = self.login()["session_id"]
        with patch.object(auth.time, "monotonic", return_value=161):
            self.revoke.side_effect = OSError("offline")
            auth.expire_once()
            self.assertIn(token, auth.sessions)
            self.revoke.side_effect = None
            auth.expire_once()
            self.assertNotIn(token, auth.sessions)

    def test_concurrent_sessions_and_logout(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            tokens = [r["session_id"] for r in pool.map(lambda _: self.login(), range(5))]
            results = list(pool.map(self.logout, tokens))
        self.assertEqual(len(set(tokens)), 5)
        self.assertTrue(all(r["ok"] for r in results))
        self.assertFalse(auth.sessions)

    def test_invalid_request_and_log_injection(self):
        for request in [None, [], {}, {"action": "LOGIN", "username": []},
                        {"action": "LOGOUT", "session_id": []}]:
            self.assertFalse(auth.handle_request(request, "10.0.0.1")["ok"])
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        auth.logger.addHandler(handler)
        try:
            auth.handle_request(dict(action="LOGIN", username="bad\nFORGED", password="bad"), "10.0.0.2")
        finally:
            auth.logger.removeHandler(handler)
        self.assertEqual(len(output.getvalue().splitlines()), 1)

    def test_client_and_demo_over_real_tcp(self):
        with listener(auth.handle_client) as auth_port, listener(protected_service.handle_client) as service_port:
            with patch.multiple(client, AUTH_HOST="127.0.0.1", AUTH_PORT=auth_port,
                                SERVICE_HOST="127.0.0.1", SERVICE_PORT=service_port):
                client.main()
                self.assertEqual(demo.concurrent(), 0)
                with patch.object(auth, "LOCKOUT_SECONDS", 1):
                    self.assertEqual(demo.lockout(recover=True), 0)
                self.allow.side_effect = OSError("offline")
                self.assertEqual(demo.controller_down(), 0)
        self.assertFalse(auth.sessions)

    def test_benchmark_over_real_tcp_records_both_modes_and_logs_out(self):
        with tempfile.TemporaryDirectory() as folder, \
             listener(auth.handle_client) as auth_port, \
             listener(protected_service.handle_client) as service_port, \
             patch.multiple(benchmark, AUTH_HOST="127.0.0.1", AUTH_PORT=auth_port,
                            SERVICE_HOST="127.0.0.1", SERVICE_PORT=service_port,
                            TRIALS=2, RESULTS_FILE=Path(folder) / "fresh.csv"):
            benchmark.run_dynamic()
            benchmark.run_static()
            result = inspect_results(benchmark.RESULTS_FILE, expected_trials=2)
            self.assertEqual(result["rows"], 4)
            self.assertFalse(auth.sessions)
            self.assertEqual(self.revoke.call_count, 2)

    def test_demo_concurrency_cleans_successful_sessions_after_partial_failure(self):
        responses = [{"ok": True, "session_id": f"test-{i}"} for i in range(4)] + [{"ok": False}]
        with patch.object(demo, "login", side_effect=responses), patch.object(demo, "logout") as cleanup:
            with self.assertRaises(RuntimeError):
                demo.concurrent()
        self.assertEqual(cleanup.call_count, 4)


if __name__ == "__main__":
    unittest.main()
