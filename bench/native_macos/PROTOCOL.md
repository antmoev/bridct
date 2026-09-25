# Final BRiDCT dev.7 native confirmation

Frozen before timing. BRiDCT is the public `bridct_plan_create` / `bridct_plan_apply` API, version 0.2.0-dev.7, with its shipped policy. No candidate selection or kernel tuning in this experiment.

All calls transform one natural row-major float32 array into one natural row-major array, orthonormal forward DCT-II, inverse, or normalized identity round trip. A four-array input pool rotates between iterations; this is not a batch-four API. Plans, memory allocation, normalization calibration, and FFTW planning are excluded. Each timed iteration includes a common input copy, the complete API call, all wrapper copies, output normalization, and a consumed output value. Python only orchestrates; the timed loop is C. Nothing is subtracted.

Comparators: Apple Accelerate vDSP separable wrapper; single-precision FFTW 3.3.11 PATIENT with a one-second cap per plan; general Ooura mechanically adapted to float32; libjxl/Highway exact floating DCT for square axes through 256; libjpeg-turbo floating forward 8x8; public specialized Ooura float32, local Ooura NEON, and its argument-check-free control for 8x8 and 16x16. Integer JPEG approximations are not included in exact-transform comparisons. The libjxl wrapper is reused with its batch acceptance widened to one; its transform loop and scaling are unchanged. vDSP is absent when either axis is 8. Unavailable routes are recorded, never assigned infinite times.

Dimensions: squares 8,16,32,64,128,256,512,1024; rectangles 128x256,256x128,256x512,512x256,512x1024,1024x512,128x1024,1024x128,16x32,32x16,8x64,64x8; unsupported BRiDCT axes 32x26 and 26x32 retained as explicit availability probes. FFTW can evaluate these last shapes; no BRiDCT speed ratio is computed there.

Validation precedes timing: eight deterministic structured families, SciPy float64 oracle, direct cosine-matrix oracle on small arrays, input preservation and output guards. Threshold: input-relative Frobenius error <=2e-5. This smoke coverage complements the full release corpus; it does not replace it.

Two independent sessions. Each has 21 randomized blocks; each arm is calibrated to at least 30 ms using doubling repetitions. Report every available route, session medians separately, and reference/BRiDCT ratios only within the same shape, mode and session. No fastest-session selection. Record calibration counts, every raw block, runtime route, compiler/build/source/library hashes, FFTW plans, and machine/OS identity. Abort on detected simultaneous compiler or benchmark processes. Run sessions serially with all other validation/compilation work stopped.

Historical wrappers: `2026-09-20_large-rectangles/harness.c`, `2026-09-19_libjxl-baseline/wrapper.cc`, and release `bench/controls/`. Original records remain unchanged. Libraries are used under their upstream licenses and attributed as external references, never as BRiDCT kernels.

Clock resolution: a zero elapsed duration is allowed only while doubling calibration repetitions; nonfinite or negative durations abort. Every recorded block must have strictly positive elapsed time. The initial one-iteration calibration failure is preserved separately and contributed no timing blocks.
