# BRiDCT on macOS

Extract the archive, open Terminal, and enter the extracted `bridct` directory.
Use a native terminal and native 64-bit CPython 3.10–3.14 with the GIL enabled.
Apple Silicon and Intel Mac builds use the same source package; performance on
one processor is not a prediction for another. Rosetta execution is rejected.

## First run

Install Apple Command Line Tools yourself if needed (`xcode-select --install`),
and install a native Python from python.org or your package manager. The launcher
never installs system software. Then run:

```sh
bash distribution/run_macos.sh --preflight
bash distribution/run_macos.sh --verify
```

Select a different Python with `--python /path/to/python3`. Each run creates a new
virtual environment under `.macos-work/`, installs the pinned dependencies from
`distribution/requirements-ubuntu.txt` into it, and keeps build outputs separate
from the source. Despite its historical filename, this requirements file also
provides the macOS dependencies. A missing binary wheel causes a logged failure;
it is not replaced silently with a different version or a source build.

`--verify` is the default and runs source integrity checks, generated-source
checks, C tests, Python API and hardening tests, the numerical corpus, and native
Ooura comparison validation. It collects **no benchmark timings**. Boundary
inputs intentionally expose floating-point limitations; read their diagnostics
separately from required core-test failures.

## Optional measurements

```sh
bash distribution/run_macos.sh --quick
bash distribution/run_macos.sh --full
```

Both profiles repeat all checks before collecting two sequential sessions.
`--quick` uses ten shapes and seven blocks with a 10 ms calibration target;
`--full` uses all 64 supported shapes and 21 blocks with a 30 ms target. Actual
block durations are retained. `--jobs 2` controls compilation only. Close other
CPU-heavy applications and connect the Mac to power. A process check cannot
guarantee CPU isolation or a fixed thermal state.

Python comparisons include OpenCV, SciPy, DUCC and pyFFTW, with the declared call
and allocation costs retained. Native C comparisons cover Ooura and the study's
attributed adaptations at 8×8 and 16×16. These are different timing contracts;
do not mix their results or subtract an estimated Python overhead. To reproduce
the final native campaign against Apple Accelerate/vDSP, FFTW, Ooura and codec
routines, follow `bench/native_macos/README.md`. That optional helper uses the
same BRiDCT kernels and requires the additional reference-library sources.

## Results and failures

The launcher prints the path of a `.tar.gz` results archive even when a stage
fails. Read `status.txt`, `SUMMARY.fr.md`, `host.txt`, the logs, and the numerical
reports before interpreting timings. The archive records CPU model, CPU counts,
RAM, macOS, compiler, Python and package versions, source/build hashes and raw
measurements. It does not deliberately collect serial numbers, hardware UUIDs,
network addresses or the login name; runtime paths in logs can nevertheless
contain your home-directory name. Inspect the archive before sharing it.

Use `--output /path/to/new-results` to choose a new results directory. Existing
outputs are never overwritten. Build work remains in `.macos-work/`; delete a
completed run's work directory when no longer needed. The launcher rejects a
second run in the same package. After an interrupted process, remove a stale
`.macos-run.lock` directory only after confirming no run remains active.

## Offline validation

```sh
bash distribution/run_macos.sh --verify --offline --python /path/to/python3
```

Offline mode creates a new venv with `--system-site-packages`. It inherits the
chosen Python installation's packages (including an explicitly selected existing
venv, whose package directories are recorded in a `.pth` file), checks the same pinned requirements and
runs `pip check`, with network access disabled for dependency installation. It
fails if a required version is unavailable. This is less isolated than the
normal fresh environment; the mode and installed versions are recorded.
