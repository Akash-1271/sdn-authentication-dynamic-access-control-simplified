# Optional extended verification toolkit

The main project has 11 runtime Python modules and 3 compact test files. This archive retains the larger regression/integration tooling used to verify it. It is separate supporting test code, not extra application functionality.

Extract validation-toolkit.zip into a NEW directory outside the application checkout. The archive includes copies of the exact validated runtime so the original test imports and runner paths remain reproducible. Compare those files against ../candidate-runtime-manifest.json (the files mapping) before testing. Do not modify or overwrite the original fallback.

On the tested Ubuntu VM, create a .venv311 link in the new validation directory to the existing working controller environment, without reinstalling packages. From that directory:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv311/bin/python -B -m unittest discover -v
sudo env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B audit_live.py --output-dir /tmp/sdn-validation-UNIQUE
```

Replace UNIQUE with an unused directory name. Check existing bridges/interfaces/listeners first and stop your own demonstration normally. Never use the stale-removal flag or broad cleanup. The live runner creates an owned Mininet topology, runs checks, measures 20 dynamic and 20 static trials, and cleans up its resources. Add --master for the extended run with a different fresh output directory. Keep generated keys/logs outside GitHub.

Candidate runtime passed fresh Ubuntu validation; actual counts and limitations are in ../RESULTS.md. Compact tests remain directly available in ../tests/. This toolkit includes the documented synthetic CSV fixture, bounded thread-event wait and startup-wait repair; application deadlines were unchanged.
