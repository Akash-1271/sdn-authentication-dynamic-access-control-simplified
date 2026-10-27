"""OpenFlow policy: default deny, temporary source-IP grants, confirmed revoke."""
import ipaddress
import json
import os
import time

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, DEAD_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.lib import hub
from os_ken.lib.hub import StreamServer
from os_ken.ofproto import ofproto_v1_3

from control_security import MAX_ENVELOPE_BYTES, load_secret, new_challenge, verify_request
from net_protocol import decode_json, receive_line

CONTROL_HOST = os.environ.get("SDN_CONTROL_HOST", "10.0.0.254")
CONTROL_PORT = int(os.environ.get("SDN_CONTROL_PORT", "9999"))
CONTROL_ALLOWED_PEER = os.environ.get("SDN_CONTROL_ALLOWED_PEER", "10.0.0.3")
PROTECTED_SERVER_IP = os.environ.get("PROTECTED_SERVER_IP", "10.0.0.4")
PROTECTED_SERVER_PORT = int(os.environ.get("PROTECTED_SERVER_PORT", "8080"))
DENY_PRIORITY, ALLOW_PRIORITY = 100, 200
ALLOW_COOKIE = 0x53444E4155544801
COOKIE_MASK = 0xFFFFFFFFFFFFFFFF
MAX_LEASE_SECONDS = 3600
BARRIER_TIMEOUT_SECONDS = 3
CONTROL_MAX_CONNECTIONS, CONTROL_MESSAGE_SECONDS = 32, 5


class AuthAccessController(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.control_key = load_secret()
        if not self.valid_ipv4(CONTROL_HOST) or CONTROL_HOST == "0.0.0.0":
            raise ValueError("Use a specific IPv4 management address")
        if not self.valid_ipv4(CONTROL_ALLOWED_PEER):
            raise ValueError("Control peer must be an IPv4 address")
        self.datapaths = {}
        self.pending_operations = {}
        self.command_lock = hub.Semaphore(1)
        self.control_slots = hub.Semaphore(CONTROL_MAX_CONNECTIONS)
        self.control_server = StreamServer((CONTROL_HOST, CONTROL_PORT), self.handle_control_client)
        hub.spawn(self.control_server.serve_forever)
        self.logger.info("Control listener: %s:%s", CONTROL_HOST, CONTROL_PORT)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, event):
        datapath = event.msg.datapath
        self.datapaths[datapath.id] = datapath
        parser, ofp = datapath.ofproto_parser, datapath.ofproto
        # Reconnect removes only our old grants, then restores baseline policy.
        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath, command=ofp.OFPFC_DELETE,
            cookie=ALLOW_COOKIE, cookie_mask=COOKIE_MASK, table_id=0,
            out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY, match=parser.OFPMatch()))
        self.add_flow(datapath, DENY_PRIORITY, self.protected_match(datapath))
        self.add_flow(datapath, 0, parser.OFPMatch(), [parser.OFPActionOutput(ofp.OFPP_NORMAL, 0)])
        self.logger.info("Switch %s connected; default protected-service deny installed", datapath.id)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def switch_state_handler(self, event):
        datapath = event.datapath
        if event.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif event.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            operation = self.pending_operations.get(datapath.id)
            if operation:
                operation["errors"].append("Switch disconnected")
                operation["event"].set()

    @set_ev_cls(ofp_event.EventOFPBarrierReply, MAIN_DISPATCHER)
    def barrier_reply_handler(self, event):
        operation = self.pending_operations.get(event.msg.datapath.id)
        if operation and event.msg.xid == operation["barrier_xid"]:
            operation["event"].set()

    @set_ev_cls(ofp_event.EventOFPErrorMsg, [CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def error_msg_handler(self, event):
        operation = self.pending_operations.get(event.msg.datapath.id)
        if operation and event.msg.xid in operation["flow_xids"]:
            operation["errors"].append(f"type={event.msg.type}, code={event.msg.code}")

    def protected_match(self, datapath, client_ip=None):
        fields = dict(eth_type=0x0800, ip_proto=6,
                      ipv4_dst=PROTECTED_SERVER_IP, tcp_dst=PROTECTED_SERVER_PORT)
        if client_ip is not None:
            fields["ipv4_src"] = client_ip
        return datapath.ofproto_parser.OFPMatch(**fields)

    def _send_flow_message(self, datapath, message):
        operation = self.pending_operations.get(datapath.id)
        if operation:
            datapath.set_xid(message)
            operation["flow_xids"].add(message.xid)
        datapath.send_msg(message)

    def add_flow(self, datapath, priority, match, actions=None, hard_timeout=0, cookie=0):
        parser, ofp = datapath.ofproto_parser, datapath.ofproto
        instructions = []  # No forwarding instruction means drop.
        if actions is not None:
            instructions = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        self._send_flow_message(datapath, parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match,
            instructions=instructions, hard_timeout=hard_timeout, cookie=cookie))

    def _begin_operation(self, datapath):
        operation = dict(event=hub.Event(), flow_xids=set(), errors=[], barrier_xid=None)
        self.pending_operations[datapath.id] = operation
        return operation

    def _wait_for_switch(self, datapath, operation):
        barrier = datapath.ofproto_parser.OFPBarrierRequest(datapath)
        datapath.set_xid(barrier)
        operation["barrier_xid"] = barrier.xid
        datapath.send_msg(barrier)
        timer = hub.Timeout(BARRIER_TIMEOUT_SECONDS)
        try:
            operation["event"].wait()
        except hub.Timeout:
            return "ERR switch confirmation timed out"
        finally:
            timer.cancel()
        return "ERR switch rejected flow update" if operation["errors"] else "OK"

    def _finish_operation(self, datapath, operation):
        try:
            return self._wait_for_switch(datapath, operation)
        finally:
            if self.pending_operations.get(datapath.id) is operation:
                del self.pending_operations[datapath.id]

    @staticmethod
    def valid_ipv4(address):
        try:
            return ipaddress.ip_address(address).version == 4
        except (TypeError, ValueError):
            return False

    def _validate_target(self, client_ip, server_ip, port):
        if not self.valid_ipv4(client_ip):
            return "ERR invalid client IP"
        if not self.valid_ipv4(server_ip) or server_ip != PROTECTED_SERVER_IP:
            return "ERR unexpected server IP"
        if port != PROTECTED_SERVER_PORT:
            return "ERR unexpected service port"
        return None

    def _update_rules(self, client_ip, lease=None):
        """Add a finite grant, or delete it when lease is None."""
        datapaths = list(self.datapaths.values())
        if not datapaths:
            return "ERR no switch connected"
        failures = []
        for datapath in datapaths:
            parser, ofp = datapath.ofproto_parser, datapath.ofproto
            operation = self._begin_operation(datapath)
            try:
                match = self.protected_match(datapath, client_ip)
                if lease is None:
                    self._send_flow_message(datapath, parser.OFPFlowMod(
                        datapath=datapath, command=ofp.OFPFC_DELETE_STRICT,
                        cookie=ALLOW_COOKIE, cookie_mask=COOKIE_MASK, table_id=0,
                        priority=ALLOW_PRIORITY, out_port=ofp.OFPP_ANY,
                        out_group=ofp.OFPG_ANY, match=match))
                else:
                    self.add_flow(datapath, ALLOW_PRIORITY, match,
                                  [parser.OFPActionOutput(ofp.OFPP_NORMAL, 0)],
                                  hard_timeout=lease, cookie=ALLOW_COOKIE)
                result = self._finish_operation(datapath, operation)
            except Exception:
                result = "ERR switch update failed"
            finally:
                if self.pending_operations.get(datapath.id) is operation:
                    del self.pending_operations[datapath.id]
            if result != "OK":
                failures.append(result)
                if lease is not None:
                    break  # Failed ALLOW is rolled back on all connected switches.
        return failures[0] if failures else "OK"

    def apply_allow(self, client_ip, server_ip, port, lease):
        error = self._validate_target(client_ip, server_ip, port)
        if error:
            return error
        if type(lease) is not int or not 1 <= lease <= MAX_LEASE_SECONDS:
            return "ERR invalid lease"
        result = self._update_rules(client_ip, lease)
        if result != "OK":
            rollback = self.apply_revoke(client_ip, server_ip, port)
            self.logger.warning("ALLOW failed; rollback=%s", rollback)
        else:
            self.logger.info("ALLOW confirmed client=%s lease=%s", client_ip, lease)
        return result

    def apply_revoke(self, client_ip, server_ip, port):
        error = self._validate_target(client_ip, server_ip, port)
        if error:
            return error
        result = self._update_rules(client_ip)
        self.logger.info("REVOKE client=%s result=%s", client_ip, result)
        return result

    def process_command(self, line):
        fields = line.split()
        try:
            if len(fields) == 5 and fields[0] == "ALLOW":
                return self.apply_allow(fields[1], fields[2], int(fields[3]), int(fields[4]))
            if len(fields) == 4 and fields[0] == "REVOKE":
                return self.apply_revoke(fields[1], fields[2], int(fields[3]))
        except ValueError:
            return "ERR invalid numeric field"
        return "ERR malformed command"

    def handle_control_client(self, conn, address):
        acquired = self.control_slots.acquire(blocking=False)
        with conn:
            try:
                conn.settimeout(0.1)
                if not acquired:
                    conn.sendall(b"ERR busy\n")
                    return
                if address[0] != CONTROL_ALLOWED_PEER:
                    conn.sendall(b"ERR unauthorized peer\n")
                    return
                deadline = time.monotonic() + CONTROL_MESSAGE_SECONDS
                challenge = new_challenge()
                conn.settimeout(CONTROL_MESSAGE_SECONDS)
                conn.sendall(json.dumps(challenge, separators=(",", ":")).encode() + b"\n")
                frame = receive_line(conn, MAX_ENVELOPE_BYTES,
                                     CONTROL_MESSAGE_SECONDS, deadline=deadline)
                if frame is None:
                    return
                try:
                    command = verify_request(decode_json(frame), challenge, self.control_key)
                except (ValueError, TypeError):
                    command = None
                if command is None:
                    response = "ERR authentication failed"
                else:
                    with self.command_lock:
                        response = self.process_command(command)
                conn.settimeout(1)
                conn.sendall(response.encode() + b"\n")
            except (OSError, ValueError) as exc:
                self.logger.warning("Control request closed: %s", type(exc).__name__)
            except Exception:
                self.logger.error("Internal control request failure")
            finally:
                if acquired:
                    self.control_slots.release()
