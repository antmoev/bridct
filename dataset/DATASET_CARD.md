# Dataset card: DCT adversarial verification corpus v1

**Creators:** Antoine Moevus and Max Mignotte. **Data license:** CC BY 4.0. **Generator/tool license:** BSD-3-Clause. **Status:** immutable corpus version 1; no DOI assigned.

## Purpose and contents

The corpus checks numerical and implementation correctness of single-precision, orthonormal DCT-II, inverse DCT and identity round trips. It was not used for training, arithmetic-graph search or timing-policy selection. All 474 arrays are synthetic; there are no personal data, third-party images or acquisition labels.

There are 79 arrays at each square sizes 8, 16, 32, 64, 128, 256: 70 core cases and 9 boundary diagnostics. The core/diagnostic split predates result inspection. Rectangles and sizes 512/1024 belong to the package’s separate procedural shape tests; they are not silently included in this fixed corpus version.

Families cover signed zero, positive and negative constants, alternating signs, row stripes, adjacent representable positive/negative values, nearly opposite values, offsets with ULP-scale perturbations, sparse impulses and cancellation, spatial cosine modes, coefficient impulses, an asymmetric ramp, uniform/normal random fields and signed dynamic ranges. Inputs are converted to float32 **before** reference evaluation. Neighboring values use `nextafter`, so intended perturbations are representable.

The core samples amplitudes approximately 2^-100 through 2^90. Diagnostics use tiny alternating inputs at 2^-149, 2^-140, 2^-126 and constant/alternating amplitudes 2^110, 2^120, 2^126. This is a finite selection, not an admissible-range theorem. The random generator is PCG64 with seed + size; base seeds are 910193, 2718281, 3141593, 1618033.

## Files and schema

- `inputs.npz`: losslessly compressed NPY arrays, loaded with `allow_pickle=False`.
- `manifest.json`: corpus version, NumPy version, seeds, sizes, generator hash, archive hash, and case records.
- Case record: `id`, `N`, `family`, `domain`, `seed` or null, and SHA256 of little-endian row-major float32 bytes.
- `corpus.py`: exact generator from the article’s artifact, retained without editing its arithmetic or bytes.

ZIP timestamps are fixed. Local regeneration reproduces the archive byte for byte. Across software environments, transcendental or compression differences can change bytes; the distributed arrays and their hashes remain the reference. No external download is needed to use the data archive.

## Independent oracle and criterion

For `Q[k,j] = sqrt((k==0 ? 1 : 2)/N) cos(pi*k*(j+1/2)/N)`, the float64 matrix oracle computes `Q X Q.T`, `Q.T X Q`, and `X`. Its orthogonality is checked at 1e-12. It is independent of the SIMD recursion, generated constants and execution order, but is not an exact-arithmetic certificate.

The primary error is `||computed-reference||F / ||float32_input||F` with threshold 2e-5. The denominator is not floored at 1. Exact-zero input must produce exact-zero output. This matters for tiny inputs: a floor-at-one score can conceal a completely lost signal. NaN/nonfinite results fail the criterion. The gate applies to core inputs; boundary failures are retained and counted separately.

For forward transforms, an AC-only error excludes the DC coefficient. It reveals weak-detail loss on an offset. For mathematically constant inputs, the float64 oracle can have tiny residual AC values: their relative errors are ill-conditioned and must not be interpreted as meaningful signal loss. The summary therefore reports the offset-plus-ULP subset separately.

## Results, failures and interpretation

The final BRiDCT 0.2.0-dev.7 Mac build passes all 1260 core directions on the same 474 arrays, with maximum input-relative Frobenius error 2.250789485770909e-7. It retains 90 failures among 162 boundary directions: 54 nonfinite results and 36 finite results exceeding the criterion. These counts describe this tested library, not every compatible implementation.

Each new evaluation writes its actual counts, worst errors and library hash into the requested output directory. The separate measurements archive contains the fresh final-library numerical records. Procedural tests of all 64 supported shapes are recorded separately from this six-size square corpus.

Internal unnormalized operations can overflow before final normalization even when a final result would be representable. Underflow can cause large relative error. Weak AC components can lose relative accuracy while the full normwise gate passes. The observed maximum is a sample statistic, not a universal bound. Input immutability/sentinels do not prove memory safety; the package has separate ASan/UBSan tests.

The evaluator injects 1% scale errors, transposition, sign reversal, zero output and deletion of AC coefficients into the independent reference. There are 78 size×direction×fault scenarios, each detected by at least one core input. These are **seeded faults**, not 78 naturally discovered bugs, and no claim is made that every case detects every fault.

## Intended reuse and limits

Use the corpus to validate compatible transform implementations, compare diagnostics and expose normalization/orientation/range defects. Do not use its passing core gate as a certificate for all float32 arrays, a natural-image quality claim, a performance benchmark, a Poisson-solver check or a training-performance estimate. Keep the diagnostic cases and report failures. Change the dataset version when changing inputs; do not silently regenerate and overwrite the reference manifest.
