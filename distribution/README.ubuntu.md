# Ubuntu — extract and run

Target: Ubuntu 22.04/24.04, Intel/AMD x86-64, CPython 3.10–3.14 with GIL. Internet is needed for pinned public Python wheels. Extract all files, open a terminal in `bridct`, then:

```sh
bash distribution/run_ubuntu.sh --preflight
bash distribution/run_ubuntu.sh --quick
```

The script requests permission before installing missing system tools with apt. It creates an isolated Python environment, builds C11/Clang and the NumPy extension, validates the sources and numerical outputs, and then runs two short sessions. Use `--no-system-install` to forbid system installation, `--python /path/to/python` to select Python, `--jobs 2` to limit build concurrency, or `--full` for all 64 shapes and 21 blocks calibrated to 30 ms.

The default quick screen uses ten shapes, two sessions of seven blocks calibrated to 10 ms. Comparisons: OpenCV/SciPy/DUCC/pyFFTW in Python, Ooura in C. All correctness checks run before timing. No GPU, account or automatic upload is needed. The legacy `--confirm-dev5` option is unsupported for this snapshot and intentionally fails.

Read `results/ubuntu-.../status.txt`, the summary and logs; keep the matching `.tar.gz`, including on failure. Successful output says `exit_code=0` and `last_stage=complete`. A returned archive alone proves nothing. Close heavy applications, use mains power and run only one campaign at a time. Results include CPU/RAM/OS, compiler and dependency metadata; logs may contain local paths or hostnames, so review them before public sharing.

This source snapshot is dev.7. Earlier independent Ubuntu returns used an older release; the supplement retains their technical lessons, not final-release timing claims. A fresh dev.7 Ubuntu evaluation is pending. See `docs/PLATFORMS.md` and `docs/RESULTS_MAP.md`.
