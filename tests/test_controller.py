"""OpenFlow message checks using OS-Ken and a fake switch. Run in the Ubuntu venv."""
import logging
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

try:
    import controller
    from os_ken.ofproto import ofproto_v1_3 as ofp
    from os_ken.ofproto import ofproto_v1_3_parser as parser
except ModuleNotFoundError as exc:
    if not exc.name.startswith("os_ken"):
        raise
    controller = None


class Datapath:
    def __init__(self, number=1):
        self.id, self.xid = number, 0
        self.messages = []
        self.ofproto, self.ofproto_parser = ofp, parser
    def set_xid(self, message):
        self.xid += 1
        message.xid = self.xid
    def send_msg(self, message):
        self.messages.append(message)


@unittest.skipIf(controller is None, "OS-Ken controller checks require the Ubuntu environment")
class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.app = controller.AuthAccessController.__new__(controller.AuthAccessController)
        self.app.logger = logging.getLogger("controller-test")
        self.dp = Datapath()
        self.app.datapaths = {1: self.dp}
        self.app.pending_operations = {}
        self.app._finish_operation = Mock(return_value="OK")

    def test_default_policy_and_reconnect_cleanup(self):
        self.app.switch_features_handler(SimpleNamespace(msg=SimpleNamespace(datapath=self.dp)))
        clear, deny, normal = self.dp.messages
        self.assertEqual(clear.cookie, controller.ALLOW_COOKIE)
        self.assertEqual(clear.cookie_mask, controller.COOKIE_MASK)
        self.assertEqual(clear.command, ofp.OFPFC_DELETE)
        self.assertEqual(deny.priority, 100)
        self.assertEqual(deny.instructions, [])
        self.assertEqual(normal.priority, 0)

    def test_temporary_source_specific_allow(self):
        self.assertEqual(self.app.process_command("ALLOW 10.0.0.1 10.0.0.4 8080 60"), "OK")
        message = self.dp.messages[0]
        self.assertEqual(message.priority, 200)
        self.assertEqual(message.hard_timeout, 60)
        self.assertEqual(dict(message.match.items()), dict(eth_type=2048, ip_proto=6,
                         ipv4_src="10.0.0.1", ipv4_dst="10.0.0.4", tcp_dst=8080))

    def test_revoke_is_strict_and_cookie_scoped(self):
        self.assertEqual(self.app.process_command("REVOKE 10.0.0.1 10.0.0.4 8080"), "OK")
        message = self.dp.messages[0]
        self.assertEqual(message.command, ofp.OFPFC_DELETE_STRICT)
        self.assertEqual(message.priority, 200)
        self.assertEqual(message.cookie_mask, controller.COOKIE_MASK)

    def test_failed_allow_rolls_back(self):
        self.app._finish_operation.side_effect = ["ERR timed out", "OK"]
        self.assertTrue(self.app.apply_allow("10.0.0.1", "10.0.0.4", 8080, 60).startswith("ERR"))
        self.assertEqual(self.dp.messages[-1].command, ofp.OFPFC_DELETE_STRICT)
        self.assertFalse(self.app.pending_operations)

    def test_revoke_continues_after_one_switch_fails(self):
        second = Datapath(2)
        self.app.datapaths[2] = second
        self.app._finish_operation.side_effect = ["ERR offline", "OK"]
        self.assertTrue(self.app.apply_revoke("10.0.0.1", "10.0.0.4", 8080).startswith("ERR"))
        self.assertTrue(second.messages)

    def test_invalid_commands_and_no_switch(self):
        for command in ["", "ALLOW a b x y", "ALLOW ::1 10.0.0.4 8080 60",
                        "ALLOW 10.0.0.1 10.0.0.5 8080 60", "ALLOW 10.0.0.1 10.0.0.4 8081 60",
                        "ALLOW 10.0.0.1 10.0.0.4 8080 0"]:
            self.assertTrue(self.app.process_command(command).startswith("ERR"))
        self.assertFalse(self.dp.messages)
        self.app.datapaths.clear()
        self.assertEqual(self.app.apply_allow("10.0.0.1", "10.0.0.4", 8080, 60), "ERR no switch connected")

    def test_barrier_and_error_ids_are_correlated(self):
        operation = self.app._begin_operation(self.dp)
        operation.update(event=Mock(), barrier_xid=17, flow_xids={12})
        for xid in [16, 17]:
            self.app.barrier_reply_handler(SimpleNamespace(msg=SimpleNamespace(datapath=self.dp, xid=xid)))
        operation["event"].set.assert_called_once()
        for xid in [11, 12]:
            self.app.error_msg_handler(SimpleNamespace(msg=SimpleNamespace(datapath=self.dp, xid=xid, type=5, code=0)))
        self.assertEqual(len(operation["errors"]), 1)

    def test_disconnect_wakes_pending_operation(self):
        operation = self.app._begin_operation(self.dp)
        operation["event"] = Mock()
        self.app.switch_state_handler(SimpleNamespace(datapath=self.dp, state=controller.DEAD_DISPATCHER))
        self.assertFalse(self.app.datapaths)
        operation["event"].set.assert_called_once()
        self.assertTrue(operation["errors"])


if __name__ == "__main__":
    unittest.main()
