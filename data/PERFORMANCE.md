# Performance evaluation

Batch label: Simplified candidate: runtime manifest SHA256 48090f05076c89b21ee5ac3d2184274a975f2c28209ca587a27001987b5ac299

Input SHA-256: `63a7d1ffa0897f784a8a67121e2ec14186c6f595a416b2f7af3f5bea9d4e7414`

Validated rows: 40. All observations retained.

| Mode | Metric (ms) | Trials | Mean | Median | Minimum | Maximum |
|---|---|---:|---:|---:|---:|---:|
| dynamic | login_ms | 20 | 89.1809 | 68.7180 | 24.0440 | 335.4490 |
| dynamic | service_rtt_ms | 20 | 17.5641 | 16.9745 | 1.1480 | 44.1590 |
| dynamic | login_to_access_ms | 20 | 106.8042 | 85.6560 | 25.2030 | 345.7230 |
| static | service_rtt_ms | 20 | 14.3079 | 12.5385 | 2.5960 | 34.6370 |

Service transaction time includes TCP connection setup and application response.
Compare service_rtt_ms across modes. Static login/total fields are not applicable.
Login/control and login-to-access measure additional dynamic authorization work.
A mean or median from one ordered VM batch does not establish a general speed advantage.
The caller-provided batch label is not proof of the tested source version; retain its manifest.

## Observations over 100 ms (retained, not discarded)

- dynamic, trial 1, login_ms: 335.449 ms
- dynamic, trial 1, login_to_access_ms: 345.723 ms
- dynamic, trial 5, login_ms: 129.027 ms
- dynamic, trial 5, login_to_access_ms: 139.866 ms
- dynamic, trial 6, login_ms: 126.176 ms
- dynamic, trial 6, login_to_access_ms: 140.022 ms
- dynamic, trial 7, login_ms: 108.006 ms
- dynamic, trial 7, login_to_access_ms: 126.104 ms
- dynamic, trial 9, login_ms: 121.592 ms
- dynamic, trial 9, login_to_access_ms: 165.769 ms
- dynamic, trial 10, login_ms: 156.369 ms
- dynamic, trial 10, login_to_access_ms: 176.314 ms
- dynamic, trial 11, login_ms: 108.666 ms
- dynamic, trial 11, login_to_access_ms: 118.394 ms
- dynamic, trial 13, login_to_access_ms: 103.136 ms
