# Simplified candidate — Ubuntu results, 26 October 2026

**Ready for a presentation rehearsal. Keep the original fallback.** These are new measurements against this candidate, not inherited pass counts. No mark guarantee or production-security claim.

## Actual gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Transfer integrity | 57/57 manifest hashes match; ZIP CRC valid | Original handoff manifest |
| Compact suite | 26 passed, zero skipped, exit 0 | compact-final.log |
| Full isolated regression | 75 passed, zero skipped, exit 0 | regression-final.log |
| Normal Mininet run | 80 recorded checkpoints passed, runner exit 0 | normal/results.json and commands.json |
| Additional controller/master run | 122 recorded checkpoints passed, runner exit 0 | master-retry/results.json and commands.json |
| New demo CLI | Service, denial, login/logout, default expiry, concurrency, 60-second lockout recovery, controller-down exercised; runner exit 0 | demo/topology.log, commands.json and flow tables |
| Performance | 20 unique dynamic + 20 unique static final-source trials | data/performance_results_current.csv |
| Cleanup | Owned processes stopped; final deny/normal table, no owned bridge or management link | per-run ovs-after, final-state.json |

The master count includes repeated normal checks, not that many independent unit tests. A denial/expiry probe exit 2 remains INCONCLUSIVE by itself; it is accepted only with successful h_srv access, priority-100 deny, and no priority-200 grant. Existing grants persisted during controller failure until finite hard timeout. Final source CSV is from the preselected successful additional run; the first successful normal-run batch is also preserved, without selecting on performance.

## Reproduction commands

From `/home/akash/sdn-authentication-simplified`:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv311/bin/python -B -m unittest discover -s tests -v
.venv311/bin/python -B summarize_performance.py data/performance_results_current.csv --label "Simplified candidate: runtime manifest SHA256 48090f05076c89b21ee5ac3d2184274a975f2c28209ca587a27001987b5ac299" --output /tmp/choose-new-unused-summary.md
```

From `/home/akash/sdn-simplification-verification`:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv311/bin/python -B -m unittest discover -v
sudo env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B audit_live.py --output-dir /home/akash/CHOOSE-NEW-EVIDENCE-DIRECTORY
```

The second run adds `--master` and uses another fresh directory. Never use the stale-removal flag. Inspect resources first; keep the fallback demo stopped normally. The automated CLI rehearsal uses a verification-only driver around the documented topology entrypoint, starts controller as akash, then services. It adds exit markers, flow capture and PID verification around the documented commands; shutdown sends the same TERM/exit/interrupt actions. It is not a manual human rehearsal. See DEMO.md for presentation commands.

## Performance (milliseconds)

| Metric | Mean | Median |
| --- | ---: | ---: |
| dynamic login_ms | 89.1809 | 68.7180 |
| dynamic service_rtt_ms | 17.5641 | 16.9745 |
| dynamic login_to_access_ms | 106.8042 | 85.6560 |
| static service_rtt_ms | 14.3079 | 12.5385 |

Compare dynamic/static service transaction time (connect + request + response), not login-to-access versus static service. Login/control time is separate authorization overhead. All observations retained; see data/PERFORMANCE.md for maxima and >100 ms observations. VM scheduling, cache, sequential mode order and load can affect these results; one batch cannot demonstrate universal speed superiority or isolate SDN's causal overhead. The VM was heavily loaded during validation; no application performance threshold is asserted.

## Requirement-to-evidence

| Requirement | Current evidence |
| --- | --- |
| TCP authentication | Compact real loopback exchange; live test_auth and client login/access/logout |
| Concurrent users | Five-client legacy test plus new demo concurrent, distinct tokens and logout |
| Sessions/timeouts | IP-bound tokens, compact expiry/retry; short live expiry and demo default 60-second expiry flow |
| Dynamic allow/revoke | Signed commands, priority-200 exact source grant, barrier checks, strict cookie deletion, master unrelated-rule retention and revoke retry |
| Logs | Candidate auth/security and protected-service logs; sanitized copies in evidence |
| Unauthorized access | Healthy service + timeout + deny/no matching grant; peer/HMAC/replay rejection |
| Robustness | Invalid/oversized/slow/disconnected TCP, capacity/recovery, controller outage, key mismatch and restart cases |
| Performance comparison | Fresh 20+20 CSV, strict unique-trial validation, mean/median and unfiltered outliers |

## Source identity and environment

Runtime manifest SHA256 `48090f05076c89b21ee5ac3d2184274a975f2c28209ca587a27001987b5ac299`; 11 runtime Python modules plus requirements are byte-identical between app and verification and unchanged from transfer through both benchmarks. Documentation/test-harness changes after/between runs do not change measured application code. The return bundle's source manifest additionally hashes final docs, tests and data.

Ubuntu 26.04 LTS, Linux 7.0.0-38-generic; system Python 3.14.4, existing controller interpreter 3.11.13; OS-Ken 3.1.1, Eventlet 0.41.2, Mininet 2.3.0, OVS 3.7.1. Existing dependency check passed without package changes. Eventlet deprecation/unpatched-RLock startup warnings remain recorded.

## Failures, repairs and limitations


1. Legacy CSV tests assumed an omitted historical CSV. Replaced with disposable explicitly synthetic 40-row fixture; expected mean 51, median 1, maximum 1001. These numbers are test inputs, never benchmark results. Original failure: 75 discovered, 10 subtest errors from missing fixture.
2. Wire test sent a barrier reply before setting a local thread event; main thread could observe successful acknowledgement before event scheduling. Replaced immediate is_set assertion with bounded wait(1), retaining all switch-message assertions. First repaired run: 75 discovered, one failure. Final full suite: 75 passed, exit 0, 13.903 seconds.
3. Additional live run hit five-second auth-server startup deadline while VM load average was 13.33 with ~1.9 GB swap used. Server later logged ready. Run exited 1 and cleaned up; no benchmark taken. Extended only verification runner startup allowance to 30 seconds. Application deadlines and leases remain unchanged.

Compact final suite: 26 passed, zero skipped, exit 0, 3.568 seconds. pip check exit 0. Syntax parsed for app and verification. Normal live run exit 0: 80 recorded checkpoints, 20+20 fresh trials, final deny/normal rules only and no bridge after teardown. Outage first no-grant observation 58.653 seconds after stopping controller; grant age predates stop. Immediate fail-closed for existing sessions is not claimed.

Documentary changes: use correct venv for all compact tests, prevent bytecode writes, private log directory and recorded server PID shutdown instructions. Candidate key lives outside source at /home/akash/.local/state/sdn-simplified/control.key and is excluded from the return bundle.

Human presentation is still required. Single trusted VM, plaintext demo credentials/tokens, source-IP-based policy, shared filesystem/trusted administrators, unsigned control replies, volatile sessions, bounded rather than immediate outage revocation, Eventlet deprecation warning, and workload-sensitive performance remain limitations.


The failed additional run is retained under master-failed; no benchmark was collected in it. Existing grants are not immediately revoked when the controller dies. Direct administrator/key-holder access and shared namespace files remain trusted lab assumptions. No original source, private key, historical evidence, package or GitHub repository was modified. Windows publication/submission and human demo/viva remain Akash's actions.

## Verification runner provenance

Application runtime identity above is the same for every run. Verification driver hashes differ only for the recorded startup-wait repair.

| Driver / runs | SHA256 |
| --- | --- |
| audit_live.py — normal and failed master | `43fe644549234378b04a1c5bc73dec981ac30192e37332e244e40722cffd317a` |
| audit_live.py — successful master retry | `91b0310675eaefe6f384a0a1e47fdf09e80a36d986b1190225495334a240122e` |
| Documented CLI rehearsal driver | `aebd97c877392db3ec173544f099398b97034a38741b037f15e6c0a3771dd0bb` |

Fallback preservation: 11,728 original files, including installed environments, rehashed with zero changed, missing or new files. Final listeners 6653/9999/9000/8080 absent; no candidate interfaces or OVS bridge. No stage, commit, remote change, push or publication was performed.

## Publication — 27 October 2026

This separate repository publishes the validated simplified source. The VM report above records the earlier verification stage. Only documentation and packaging changed for publication; runtime hashes remain unchanged. Raw machine logs and the complete VM return remain in the local evidence bundle. The optional public verification toolkit is in verification/; it contains the regression and live-runner source, not private runtime logs or keys.
