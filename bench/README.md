# Portable C timing harness

This measures **BRiDCT alone**, not a ranking against external libraries. Validate a new compiler/architecture with `tests/verify_portability.py` before interpreting times.

Build and record two fresh-process sessions:

```sh
make -j2 bench
python bench/run.py --binary build/bench --output /tmp/bridct-native-timing \
  --execution native --height 256 --width 256 --batch 4 --mode 0
```

On Windows use `build/bench.exe`. When executing an x86 binary through Rosetta, use `--execution translated`; those times cannot be reported as Intel/AMD performance. Run only one benchmark at a time, on an otherwise idle machine. Record CPU model and power settings alongside the machine/compiler metadata; they are not inferred by this launcher.

The C executable also runs directly:

```sh
./build/bench 256 256 4 0 21 30
```

Arguments are height, width, physical array count, mode (0 forward, 1 inverse, 2 normalized identity round trip), number of measured blocks and calibration target in milliseconds. The optional defaults are 16×16, four arrays, forward, seven blocks and 10 ms. Axes are powers of two from 8 through 1024. Batch counts range from 1 through 64.

## Measurement contract

One plan/workspace and disjoint row-major float32 inputs/outputs are allocated before timing. Seeded inputs and output buffers are reused. Each repetition visits every physical array once through the ordinary C plan API, serially. Timer boundaries include C dispatch, internal copies, normalization and output stores. Setup, input generation, allocation, warmup, calibration, checksum and printing are excluded. There is no Python crossing inside the measured region. The round trip uses the plan API's identity-pair route, not the materialized Python round trip in the article.

The timer is `CLOCK_MONOTONIC` on POSIX and `QueryPerformanceCounter` on Windows. Calibration doubles repetitions until the requested duration is reached; measured blocks keep that repetition count. A later block can be shorter than the calibration target and is retained/reported. Elapsed nanoseconds are divided by **repetitions × physical array count**. No baseline or empty-call time is subtracted. Results represent warmed repeated calls, not streaming or first-call execution. B1 and larger pools expose different working sets, not a pure SIMD batching effect.

The launcher preserves both CSV files, compiler/target/backend stderr, executable SHA256, build configuration, host platform, explicit native/translated label and actual block durations. `COMPLETE` means both sessions have valid timer/accounting records, not that correctness was independently established or that the host was uncontended. Failed/partial runs are retained without a ranking. Start with a new output directory.

## Current validation


## Attributed small-block comparison

With NumPy and SciPy installed, build the library normally, then run:

```sh
python bench/compare_small.py --output build/small-screen1 --session 1 --blocks 7 --ms 20
python bench/compare_small.py --output build/small-screen2 --session 2 --blocks 21 --ms 20 --batches 1 4 16 --control-build build/small-screen1/build
```

The first command compiles the controls; the second reuses their exact binaries. Supply `--cc gcc` or `--extra-flags` when matching a nondefault library build. `--validate-only` compiles and checks correctness without timing. The harness supports Clang/GCC on ARM64 and x86 through the same vendored SIMD compatibility header. Windows uses QueryPerformanceCounter; Unix uses a monotonic clock.

The 8×8/16×16 test covers forward, inverse and normalized identity round trip. Float32 precision, natural row-major input/output, complete writes, identical batches and one native C timing loop are common to all arms. Preparation/allocation are outside timings. Results distinguish the current private kernel, checked public API, previous SJ implementation, mechanically float-converted public Ooura source, and the study’s scalar/automatic/explicit SIMD Ooura adaptations. A trusted Ooura control removes argument checks only. No unsafe control is an application API. The Ooura round trip retains its intermediate orientation in the explicit SIMD control; no identity shortcut is used.

Every run retains numerical checks, source/compiler/binary hashes, process snapshots, repetitions, raw times and output checksums. `COMPLETE_EXPLORATORY` means the run finished; it does not itself establish a performance claim. Compare full repeated sessions with fixed choices. Process inspection does not reserve a shared CI CPU. Source grants and modifications are documented in `controls/NOTICE.md`.
