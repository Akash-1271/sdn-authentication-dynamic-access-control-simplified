# Performance evaluation

Batch label: Final simplified candidate: runtime manifest SHA256 a65454260fecde78bead6593957a274d29a637d6c1b9ceb747db74b6d4a888bf

Input SHA-256: `51173309df2e7da02cadfbe49f78322412cd7ba54f0599cd705a47f2b3e131f8`

Validated rows: 40. All observations retained.

| Mode | Metric (ms) | Trials | Mean | Median | Minimum | Maximum |
|---|---|---:|---:|---:|---:|---:|
| dynamic | login_ms | 20 | 6.6608 | 5.9155 | 2.8250 | 13.1550 |
| dynamic | service_rtt_ms | 20 | 154.8531 | 2.5200 | 0.9060 | 1045.5770 |
| dynamic | login_to_access_ms | 20 | 161.5195 | 9.0790 | 5.1240 | 1050.2950 |
| static | service_rtt_ms | 20 | 1.3555 | 0.9955 | 0.6970 | 2.8890 |

Service transaction time includes TCP connection setup and application response.
Compare service_rtt_ms across modes. Static login/total fields are not applicable.
Login/control and login-to-access measure additional dynamic authorization work.
A mean or median from one ordered VM batch does not establish a general speed advantage.
The caller-provided batch label is not proof of the tested source version; retain its manifest.

## Observations over 100 ms (retained, not discarded)

- dynamic, trial 5, service_rtt_ms: 1045.577 ms
- dynamic, trial 5, login_to_access_ms: 1050.295 ms
- dynamic, trial 11, service_rtt_ms: 1007.280 ms
- dynamic, trial 11, login_to_access_ms: 1010.109 ms
- dynamic, trial 19, service_rtt_ms: 1010.669 ms
- dynamic, trial 19, login_to_access_ms: 1013.502 ms
