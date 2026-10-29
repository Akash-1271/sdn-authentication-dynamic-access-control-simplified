# Validation and requirement coverage

Fresh Ubuntu validation completed on 29 October 2026 for this further-simplified candidate. Both previous projects and their environments are preserved. No GitHub writes or publication occurred. These results are newly executed; Windows logs and earlier-source CSVs remain reference evidence.

## Executed gates

| Gate | Actual result | Evidence in return bundle |
|---|---|---|
| Compact application suite | 27 passed, zero skips, exit 0 | evidence/compact-ubuntu.log |
| Original regression suite | 75 passed, zero skips, exit 0 | evidence/regression-ubuntu.log |
| Normal Mininet audit | 80 checkpoint verdicts passed, runner exit 0 | evidence/normal/ |
| Extended Mininet audit | 122 checkpoint verdicts passed, runner exit 0 | evidence/master/ |
| Automated documented CLI rehearsal | All scenarios completed, runner exit 0; topology exit 0 | evidence/demo/ |
| Final-source benchmark | 20 unique dynamic and 20 unique static trials | data/performance_results_current.csv |
| Cleanup and preservation | No candidate bridge/interfaces/listeners; both protected project hashes unchanged | evidence/cleanup-verification.json and preservation.json |

Counts overlap; the extended run repeats normal cases. The isolated suites and normal audit completed before the VM reboot; the resumed extended audit and automated rehearsal completed afterward against identical runtime source. The Linux port-reuse test failed in the supplied Windows attempt but passed unchanged in the complete Ubuntu suite. No application runtime fixes were required. The supplied rehearsal driver was adapted to the new app, private key and evidence paths, with polling for the active flow and documented PID-based CLI teardown. No tests were removed or weakened. A VM reboot interrupted the first extended run; its partial evidence is retained separately and is not counted as a completed run.

## Requirement → evidence

| Requirement | Current evidence |
|---|---|
| Architecture and objectives | README diagram; observed topology, hosts and priority 200/100/0 rules |
| TCP authentication and framing | Compact real TCP and protocol checks; legacy bounded-response tests; live login/access/logout |
| Concurrent clients | Five distinct-token logins and confirmed logout in legacy and new demo checks |
| Sessions and timeouts | IP binding/shared-IP tests; short automated expiry plus default 60-second demo expiry with active/expired flows |
| Dynamic allow/revoke | Signed control, barrier/error tests, exact-source grants, strict deletion, unrelated-rule retention and revoke retry |
| Logs | Sanitized authentication/access and protected-service logs |
| Unauthorized access/robustness | Healthy service + deny/no-grant corroboration; malformed/slow/oversized/disconnected/capacity cases; outage/replay/key-rotation recovery |
| Performance comparison | Fresh 20+20 CSV with mean, median and all outliers |
| Reproducible configuration/tests | DEMO commands, pinned OS-Ken, compact tests and refreshed verification toolkit |
| Submission and viva | Human rehearsal, viva and course submission remain Akash's actions |

A denial or expiry exit 2 is INCONCLUSIVE alone. Live evidence pairs it with successful service self-access, priority-100 drop and absence of a matching priority-200 grant. New logins fail during controller outage; existing grants may persist to hard timeout. First no-grant observation 60.271s after stop. This is an observation after stopping the controller, not a guarantee of immediate revocation or an exact lease-start measurement.

## Performance, milliseconds

| Metric | Mean | Median |
|---|---:|---:|
| dynamic login_ms | 6.6608 | 5.9155 |
| dynamic service_rtt_ms | 154.8531 | 2.5200 |
| dynamic login_to_access_ms | 161.5195 | 9.0790 |
| static service_rtt_ms | 1.3555 | 0.9955 |

[data/PERFORMANCE.md](data/PERFORMANCE.md) includes raw CSV hash, extrema and observations above 100 ms. Compare service transaction time across modes; login/control is separate authorization overhead. All outliers remain. The mean includes long stalls; the median describes the middle trial. One ordered VM batch cannot establish universal speed superiority or isolate causal SDN overhead. The earlier normal-run batch is preserved separately. The final extended-run batch was selected before seeing its values.

Runtime manifest SHA256: `a65454260fecde78bead6593957a274d29a637d6c1b9ceb747db74b6d4a888bf`. [data/runtime_source_manifest.json](data/runtime_source_manifest.json) identifies all 11 runtime modules and requirements. Its files mapping matches candidate-runtime-manifest.json and both workspaces. Runtime was unchanged from supplied candidate throughout tests and both measurements. Final documentation/toolkit changes are independently covered by SOURCE_SHA256_MANIFEST.csv retained in the VM return bundle; the public runtime manifest covers the application modules and requirements.

## Reproduce and interpret

```bash
PYTHONDONTWRITEBYTECODE=1 .venv311/bin/python -B -m unittest discover -s tests -v
```

Extract the refreshed verification/validation-toolkit.zip to a new workspace, link the existing controller environment, then run `PYTHONDONTWRITEBYTECODE=1 .venv311/bin/python -B -m unittest discover -v`. Review audit_live.py and use a fresh output directory for each normal or --master run. Never use broad cleanup or stale removal. Follow DEMO.md for the topology → controller → servers startup and owned-resource teardown. The recorded rehearsal was automated, not performed by a human presenter.

Environment observed: Ubuntu 26.04 LTS, kernel 7.0.0-38-generic; system Python 3.14.4, controller Python 3.11.13, OS-Ken 3.1.1, Eventlet 0.41.2, Mininet 2.3.0, OVS 3.7.1. Dependency check passed; no packages were installed or upgraded. Eventlet deprecation/RLock warnings remain recorded. Fresh-machine provisioning was not independently tested.

This trusted educational lab uses plaintext demo credentials/tokens, volatile sessions and source-IP permissions; host users share network access. It has no IP/ARP anti-spoofing, TLS or signed control replies. Administrators and key holders are trusted. Barriers/rollback do not provide atomic transactions. Finite existing grants may survive component outages. A client authentication timeout means the outcome is unknown: serialized server work and switch confirmation can complete after the client has stopped waiting. A finite grant may therefore remain without a received token; inspect flows and let outstanding requests/leases settle before retrying a scenario. This is part of the non-atomic acknowledgement limitation. Passing these cases does not establish production security, exhaustive fuzz/DoS coverage or guaranteed evaluator marks.

## GitHub publication — 29 October 2026

The final verified runtime, compact tests, documentation, raw performance data and optional verification toolkit are published in this separate simplified repository. Windows verified ZIP/member integrity, source identity, test logs, flow evidence and benchmark statistics before publication. Only documentation wording and setup guidance changed after the Ubuntu return; application runtime and tests remain byte-identical. The original repository and both protected VM project directories remain preserved. The earlier statements about pending publication describe the VM validation stage.

## Development and commit history

The implementation and Ubuntu tests were completed locally before the validated source was uploaded to GitHub. The initial upload records that source snapshot. Later commits group the actual TCP refactor, client/test changes, documentation cleanup and new Ubuntu results. Their timestamps record when those changes were committed to this repository; they are not a diary of every local coding step. Existing commits and dates have been preserved.
