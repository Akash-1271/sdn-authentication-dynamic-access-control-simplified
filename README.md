# SDN Authentication and Dynamic Access Control

**Simplified edition · Python TCP sockets · Mininet · OpenFlow 1.3 · OS-Ken**

[Architecture](PROJECT_GUIDE.md) · [Demo steps](DEMO.md) · [Validation](RESULTS.md) · [Performance](data/PERFORMANCE.md)

A small networking lab: a host logs in over TCP, and an SDN controller temporarily permits that host to reach a protected service. Logout or expiry removes the permission.

**Validated in Ubuntu on 26 October 2026.** The [original project](https://github.com/Akash-1271/sdn-authentication-dynamic-access-control) remains unchanged.

| Validation | Result |
| --- | --- |
| Compact tests | 26 passed, no skips |
| Separate regression suite | 75 passed, no skips |
| Normal / extended live runs | 80 / 122 checkpoint verdicts passed |
| Performance comparison | 20 dynamic + 20 static trials |

Live checkpoints overlap; they are not independent unit-test counts. See [RESULTS.md](RESULTS.md) for scope and limitations.

## How it works

```text
h1 / h2 ── TCP login ──> h_auth (authentication server)
                              │ signed ALLOW / REVOKE
                              ▼
                       OS-Ken controller
                              │ OpenFlow 1.3
                              ▼
                         s1 (OVS switch)
                              │ permitted TCP traffic
                              ▼
                       h_srv (protected service)
```

1. The switch initially drops TCP traffic to `10.0.0.4:8080`.
2. A client sends a username and password to `10.0.0.3:9000`.
3. After valid credentials, the authentication server asks the controller to install a source-IP-specific grant.
4. The controller waits for a switch barrier reply before acknowledging the update.
5. The server returns an IP-bound session token. The client can now access the service.
6. Logout removes the grant, unless another active session on the same IP still needs it. Sessions expire after 60 seconds by default.

The switch uses three priorities: **200 = temporary allow**, **100 = protected-service deny**, **0 = normal forwarding for other traffic**. A finite OpenFlow hard timeout limits access even if the authentication server stops.

## Files to understand first

| File | Responsibility |
| --- | --- |
| `topology.py` | Creates four Mininet hosts, one OVS switch, and a controller management link. |
| `auth_server.py` | Checks credentials, maintains sessions, handles logout/expiry and failed-login lockout. |
| `controller.py` | Turns authenticated ALLOW/REVOKE commands into OpenFlow rules. |
| `client.py` | Demonstrates login, service access and logout. |
| `protected_service.py` | Replies to a TCP request; the switch controls who can reach it. |

Three supporting modules keep repeated code separate: `controller_client.py` sends control commands; `control_security.py` signs them with HMAC-SHA256; `net_protocol.py` reads bounded newline-delimited messages and serves concurrent connections.

`demo_checks.py` contains the demonstration scenarios. `performance_test.py` measures dynamic access and a static-rule baseline; `summarize_performance.py` summarizes the CSV. Three files under `tests/` check application behavior, protocol handling, and controller logic.

## Run and demonstrate

Use the existing Ubuntu Mininet environment. For a fresh checkout on an already provisioned Ubuntu machine:

```bash
git clone https://github.com/Akash-1271/sdn-authentication-dynamic-access-control-simplified.git
cd sdn-authentication-dynamic-access-control-simplified
python3.11 -m venv .venv311
.venv311/bin/python -m pip install -r requirements.txt
.venv311/bin/python -m pip check
```

The demo uses the existing VM path `/home/akash/sdn-authentication-simplified`; substitute your checkout path when using a fresh clone. Fresh-machine provisioning has not been independently validated. The full optional regression/live tooling is provided in [verification/](verification/README.md), separately from the 14 Python application/test files.

 See [DEMO.md](DEMO.md) for terminal-by-terminal commands and [RESULTS.md](RESULTS.md) for verified status.

Run the compact tests from this directory:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv311/bin/python -B -m unittest discover -s tests -v
```

Controller tests need the OS-Ken environment (`requirements.txt` pins the version). Windows can run the portable tests but cannot demonstrate Mininet forwarding. Do not install or upgrade packages in the original VM project's environment as part of this copy.

## Important implementation choices

- TCP is a byte stream, so messages end in a newline and have size/deadline limits.
- Worker threads accept concurrent clients; one state-transition lock serializes session changes and their switch updates.
- Three wrong passwords lock that source IP for 60 seconds. A different host can still authenticate.
- HMAC proves a control command came from a holder of the shared key. A fresh challenge binds the command to its connection. HMAC does not encrypt it.
- Switch errors, barrier timeouts and disconnects cause failed updates to be reported. Failed grants trigger best-effort rollback; unconfirmed revocations can be retried.
- Logs record authentication and access changes without printing session tokens or the private control key.

## Scope and limitations

This is a trusted lab prototype, not a production identity system. The public demo accounts are `alice / 123` and `bob / 456`. Login credentials and tokens travel without TLS. Sessions are held in memory. Network permission is per source IP, so sessions on one host share access; it is not per-process isolation. IP/ARP spoofing prevention is outside this implementation.

Control replies are not signed, and a lost acknowledgement is not an atomic transaction. Existing finite grants may remain until timeout during a controller outage. The experiment measures a local VM workload, not Internet-scale performance.

The simplified copy retains the rubric's TCP service, concurrent clients, sessions/timeouts, dynamic rules, logs, failure scenarios and performance comparison. Actual marks depend on the demonstrated behavior, report and viva.
