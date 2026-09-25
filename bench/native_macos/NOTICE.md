# Optional native comparator attribution

BRiDCT's transform library and original helper code retain BSD-3-Clause. This folder is an optional comparator harness; none of its external transform implementations enters `libbridct`.

`vendor/ooura_float.c` is a mechanically adapted single-precision version of Takuya Ooura's `fft4g.c`, from his FFT package. Its upstream algorithm and source documentation are retained. Copyright Takuya Ooura, 1996–2001. The [official package notice](https://www.kurims.kyoto-u.ac.jp/~ooura/fft.html) permits use, modification and distribution for any purpose without fee, and asks modified distributions to acknowledge the package. This file remains under those upstream terms, rather than BRiDCT's BSD license. The first source comment refers to the earlier benchmark in which the mechanical conversion was made; it is not a BRiDCT implementation claim. Specialized Ooura controls and their adaptation notice are in `../controls/`.

External dependencies are obtained separately. Keep their license files with their source trees and any redistribution:

- FFTW 3.3.11: upstream `COPYING` (GNU GPL). Linking FFTW into this optional benchmark does not relicense the independently built BRiDCT library. Do not label the combined comparator binary BSD-only.
- libjxl revision recorded in `DEPENDENCIES.json`: upstream `LICENSE` (BSD-3-Clause), with upstream third-party notices retained.
- Google Highway revision recorded in `DEPENDENCIES.json`: upstream `LICENSE` and `LICENSE-BSD3` (Apache-2.0 / BSD-3-Clause choice).
- libjpeg-turbo 3.2.0: upstream `LICENSE.md`, covering IJG, modified BSD and zlib terms for its components.
- Apple Accelerate: supplied by the macOS SDK/runtime; not redistributed here.

The libjxl wrapper invokes upstream `ComputeScaledDCT` and `ComputeScaledIDCT` and adapts their coefficient layout and scale. Its acceptance of one input array is the only change from the earlier batch-capable wrapper. The benchmark source records the exact wrappers used for the final measurements; the separate build helper resolves user-supplied dependency paths.
