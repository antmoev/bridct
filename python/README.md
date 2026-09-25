# Optional NumPy interface

The standalone BRiDCT C library remains independent of Python. This optional C11 extension supplies a reusable NumPy interface with newly allocated output by default and `out=` for reusable output storage.

From the repository root, first build the core normally, then the extension:

```sh
make
make -C python PYTHON=python3
PYTHONPATH=python/build python3 -c "from bridct_numpy import Plan; print(Plan(16, 32).shape)"
make -C python check PYTHON=python3
```

Requirements: GIL-enabled CPython >= 3.10, NumPy headers, and a C11 compiler (Clang by default). Supply `CC` to select another compiler. The extension and core archive must target the same processor. Validation scope is documented in [platform support](../docs/PLATFORMS.md). A successful build does not imply support for every CPU, compiler, free-threaded Python, or MSVC. Windows users must select the same CPython interpreter used to install NumPy.

The builder prioritizes the active interpreter's NumPy headers, records the actual inclusion paths and checks import/plan creation before reporting success. This prevents a reproduced system-NumPy/venv-NumPy header collision. `build.json`, `build.log` and `import-check.log` retain diagnostics. Rebuild the extension when changing Python or NumPy; this is not a portable binary wheel.

```python
import numpy as np
from bridct_numpy import Plan

x = np.random.default_rng(0).standard_normal((16, 32)).astype(np.float32)
plan = Plan(16, 32)
y = plan.forward(x)
z = plan.inverse(y)
pair = plan.roundtrip(x)
out = np.empty_like(x)
plan.forward(x, out=out)
plan.close()
```

A plan accepts `(H, W)` or `(B, H, W)` arrays, where both axes are powers of two from 8 to 1024 and B >= 1. All transforms are orthonormal; the forward is DCT-II and the inverse DCT-III. The round-trip materializes each image's normalized spectrum before its inverse, and never uses the fused identity route.

Input must be an exact NumPy ndarray, native-endian float32, C contiguous, and float aligned. Read-only input is allowed. Subclasses, implicit conversions, unsupported shapes, and strided inputs are rejected. The input remains unchanged. Each allocating call returns a distinct owning ndarray; `out=` returns the supplied writable ndarray, which must match the input shape and have no overlapping storage.

Use one plan per concurrent worker. A busy plan rejects nested calls or closure, including reentrant allocator callbacks. Calls with >=16384 elements release the GIL; callers must not modify their array buffers concurrently. Main-interpreter imports only are supported and subinterpreter imports are rejected. Free-threaded Python builds are rejected at compile time. This is not a stable-ABI binary wheel.

Plan creation and workspace allocation occur once; include them separately when reporting startup costs. Steady-state Python calls include dispatch, validation, output allocation unless `out=` is supplied, and all computation/stores. Do not subtract an estimated empty-call time. Compare allocating APIs with allocating APIs and supplied-output APIs with supplied-output APIs.

`make check-full` verifies all 64 shapes in two batches, three input families, and three directions with allocated and guarded supplied outputs. `build/build.json` records compiler and binary hashes. `build/import-diagnostics.json` records the Python executable, OS, architecture, NumPy/SciPy versions and imported paths, and the actual extension hash. Validation reports are also written inside the selected build directory, so running checks does not alter the reviewed source manifest. They repeat runtime provenance and retain the shared-plan concurrency attempts. These are correctness checks, not speed benchmarks. The main experiment preserves the already-executed validation and benchmark evidence. The test-only allocator helper exercises lifecycle failure/reentrancy paths and is not part of the normal extension. Interpreter isolation tests select the available CPython subinterpreter test API; the previously executed version used CPython 3.13.

```sh
cd python
make check-hardening PYTHON=python3
```

Code license: the repository's BSD-3-Clause license. No NumPy or CPython implementation source is copied into this directory; their installed public C APIs are used.

The extension is compiled in C11 with pedantic diagnostics. The core keeps all its existing strict flags. CPython's module-slot interface represents its execution callback as `void *`; only that initializer has a GCC-local `-Wpedantic` suppression for the API-required function-pointer conversion. This does not relax diagnostics elsewhere or change the generated transform kernels.

## Optional OpenCV comparison

OpenCV is needed only for this comparison, never for the C library or its numerical tests. After installing an OpenCV Python package in the chosen Python environment, run from the repository root:

```sh
python3 python/benchmark.py --output build/python-screen1 --session 1 --blocks 7 --ms 20
python3 python/benchmark.py --output build/python-screen2 --session 2 --blocks 21 --ms 30
```

`--validate-only` performs numerical/ownership checks without calibration or timing: 520 records for the default ten shapes, or 52 per selected shape. `--extension` selects another extension build directory. Every output directory must be new; incomplete or failed sessions are retained. Completed sessions require the complete expected key set for the selected shapes: 13 contract comparisons, 26 arms, and 52 admission checks per shape. They end with `COMPLETE_EXPLORATORY`. `comparison.csv` gives within-session median nanoseconds per array and OpenCV/BRiDCT ratios.

The default ten shapes remain the eight squares from 8 to 1024 plus 16×32 and 8×64, for 130 comparisons. Select a smaller confirmation set with `--shapes`, or all 64 supported height/width pairs with `--all-shapes`; these options are mutually exclusive. Duplicate shapes and dimensions that are not powers of two in `[8, 1024]` are rejected, including 32×26. The manifest records the chosen shapes, selection mode, and derived expected counts.

```sh
python3 python/benchmark.py --output build/python-small --shapes 8x8 16x16 --blocks 21 --ms 30
python3 python/benchmark.py --output build/python-rectangles --shapes 16x32 32x16 8x64 64x8 --blocks 7 --ms 20
python3 python/benchmark.py --output build/python-all --all-shapes --blocks 7 --ms 20
python3 python/benchmark.py --self-test
```

The last command runs eight lightweight parser/completeness tests using only Python's standard library. It executes no DCT, compilation, calibration, or timing, and does not require NumPy, SciPy, OpenCV, or the BRiDCT extension.

Each shape's comparisons distinguish B1/B4 allocating batches, direct 2D allocation, supplied output, and round-trip through two allocating calls. A batch gain can include replacing OpenCV's Python loop with a C loop. A one-call round-trip can include avoiding Python dispatch and intermediate allocation. Those advantages are reported separately from direct 2D and two-call round-trips. Both implementations compute complete orthonormal outputs; input copying/conversion is not silently omitted from one side. No empty-call adjustment is applied.

These are warmed end-to-end API timings, including output destruction; imports, plan construction, input creation, and calibration are outside measured intervals. `--guard-known-compute` can reject a small list of observed compiler/test processes, but neither that guard nor a process snapshot establishes host isolation. The manifest records this limitation, the CPU model when queryable, imported versions, compiler/link command, extension/core hashes, OpenCV build information, and GitHub run ID when present.

The workflow's `performance_screen` input defaults to false. When enabled, it installs the pinned comparator and runs one short Python screen followed by the separate C small-block/Ooura screen, sequentially and only on Ubuntu Clang/auto. Shared CI runners execute native code on real CPUs, but their uncontrolled load makes these results exploratory. Repeat on an identified, controlled machine before drawing hardware performance conclusions; no universal speed threshold is asserted in CI.
