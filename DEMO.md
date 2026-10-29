# A 10–15 minute demonstration

**This candidate passed fresh Ubuntu validation on 29 October 2026.** Keep the validated project as your fallback. Everything below runs in **Ubuntu**, not Windows.

The tested application is in `/home/akash/sdn-final-simplified-20261029`, with `.venv311` linked to the working OS-Ken environment. Keep both earlier projects unchanged.

## 1. Prepare once — Ubuntu terminal

```bash
cd /home/akash/sdn-final-simplified-20261029
mkdir -p /home/akash/.local/state/sdn-final-simplified-20261029
chmod 700 /home/akash/.local/state/sdn-final-simplified-20261029
test -f /home/akash/.local/state/sdn-final-simplified-20261029/control.key || python3 control_security.py --generate-key /home/akash/.local/state/sdn-final-simplified-20261029/control.key
mkdir -p logs
chmod 700 logs
```

Keep the key private and out of GitHub. Before starting, ensure the original demonstration is stopped normally. The candidate uses the same network names and ports, so both cannot run together. If startup says an interface or bridge already exists, inspect it; do not blindly run `mn -c`.

## 2. Terminal A — create the network

```bash
cd /home/akash/sdn-final-simplified-20261029
sudo env PYTHONDONTWRITEBYTECODE=1 python3 -B topology.py
```

Leave the `mininet>` prompt open. A controller connection warning at this point is expected: start the controller next.

## 3. Terminal B — start the controller

```bash
cd /home/akash/sdn-final-simplified-20261029
PYTHONDONTWRITEBYTECODE=1 SDN_CONTROL_SECRET_FILE=/home/akash/.local/state/sdn-final-simplified-20261029/control.key .venv311/bin/osken-manager --ofp-listen-host 127.0.0.1 --ofp-tcp-listen-port 6653 controller.py
```

Wait for the switch connection message. Say: “The controller installs a default deny rule for the protected service.”

## 4. Terminal A — start both servers

Paste these at `mininet>`, without typing the prompt itself:

```text
h_auth env SDN_CONTROL_SECRET_FILE=/home/akash/.local/state/sdn-final-simplified-20261029/control.key AUTH_LOG_FILE=/home/akash/sdn-final-simplified-20261029/logs/security.log sh -c 'echo $$ > logs/h_auth.pid; exec python3 -B -u auth_server.py' > logs/auth-console.log 2>&1 &
h_srv sh -c 'echo $$ > logs/h_srv.pid; exec python3 -B -u protected_service.py' > logs/service.log 2>&1 &
h_srv python3 -B demo_checks.py service
```

The last command must report service success. If not, inspect the logs before proceeding. If a login times out, its outcome is uncertain: the server may have installed a temporary grant without the client receiving its token. Stop the scenario, allow outstanding requests and leases to settle, and inspect the flow table before retrying. A timeout is not proof that access was never granted.

## 5. Show blocked → allowed → blocked

At `mininet>`:

```text
h1 python3 -B demo_checks.py denied
h1 python3 -B client.py
h1 python3 -B demo_checks.py denied
h_srv python3 -B demo_checks.py service
sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

The denial probe deliberately prints **INCONCLUSIVE** for a timeout. Combine that with a working service and a priority-100 drop rule with no priority-200 grant for h1.

`client.py` must show successful login, protected-service access and logout. Say: “A correct password causes a temporary network permission. Logout removes it.”

## 6. Show the temporary rule and expiry

At `mininet>`:

```text
h1 python3 -B demo_checks.py expiry
```

During its 60-second wait, use **Terminal C**:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

Point out priority 200, source `10.0.0.1`, destination `10.0.0.4`, TCP port 8080 and the hard timeout. After the wait, check the flows again and confirm service health from h_srv. Say: “The permission is temporary, even if the user forgets to log out.”

## 7. Show concurrency and failed-login protection

At `mininet>`:

```text
h1 python3 -B demo_checks.py concurrent
h2 python3 -B demo_checks.py lockout --recover
```

The second command waits about a minute to prove recovery. Explain that the lockout is per source IP, while session tokens identify individual logins. The concurrency check logs out all successfully created sessions.

If time is short, show either concurrency or lockout and use the recorded VM results for the other.

## Optional controller-failure check

After the preceding checks have logged out or expired their sessions, press Ctrl+C in Terminal B. At `mininet>` run:

```text
h1 python3 -B demo_checks.py controller-down
h_srv python3 -B demo_checks.py service
sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

New login must fail. This does not establish immediate revocation of an existing grant: existing flows can persist until their finite hard timeout. Restart Terminal B using step 3 if continuing the demo; otherwise finish below.

## 8. Explain the performance comparison

Show the **fresh VM results** in [data/PERFORMANCE.md](data/PERFORMANCE.md). Compare service transaction time across dynamic and static modes. Dynamic login/control time is separate authorization overhead; the static baseline has no login step.

Do not run a new benchmark during a short presentation. Do not claim SDN is always faster based on a single VM batch.

## 9. Finish

At `mininet>`, stop only the two servers launched above, using their recorded PIDs:

```text
h_auth kill -TERM $(cat logs/h_auth.pid)
h_srv kill -TERM $(cat logs/h_srv.pid)
exit
```

Use these PID files only for this running demo; do not reuse old PID files after a restart. The `exit` command stops this topology. In Terminal B, press Ctrl+C to stop this controller. Do not terminate unrelated processes or modify the original project.

For the viva, start with the five central files in README. You do not need to explain every test method unless asked.
