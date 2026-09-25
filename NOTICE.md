# Attribution and licenses

BRiDCT 0.2.0-dev.7 uses the Shao–Johnson factorization on every library path. The current Makefile does not link Ooura. Original implementation code, generators, tests and documentation are BSD-3-Clause (LICENSE). Verification arrays and dataset metadata are CC BY 4.0 (dataset/LICENSE); executable Python files remain BSD-3-Clause (dataset/SOFTWARE_LICENSE).

The mathematical basis is Xuancheng Shao and Steven G. Johnson, “Type-II/III DCT/DST algorithms with reduced number of arithmetic operations,” Signal Processing 88(6), 1553–1564 (2008), DOI https://doi.org/10.1016/j.sigpro.2008.01.004. BRiDCT contributes implementation and evaluation, not ownership of that factorization. Authors: Antoine Moevus and Max Mignotte, Université de Montréal.

SIMDe 0.8.2 headers in third_party/simde are separately MIT-licensed. Preserve COPYING, UPSTREAM.json and individual notices. Native ARM64 uses the compiler's NEON intrinsics; supported other builds use SIMDe and separately compiled x86 kernels.

bench/controls contains Takuya Ooura's original small DCT and an explicitly identified adaptation used only for optional comparisons. Preserve bench/controls/NOTICE.md and all upstream notices. Their permission is not replaced by BRiDCT's BSD license. Historical Ooura library paths from earlier revisions are not included in this export.

NumPy, SciPy, OpenCV, DUCC, pyFFTW, Python, MSYS2 and compilation tools are installed separately under their own terms. Their binaries are not included. Package hashes are recorded in new benchmark results.

The optional bench/native_macos helper contains an attributed Ooura general float32 adaptation and wrappers for separately obtained FFTW, libjxl/Highway, libjpeg-turbo and Apple Accelerate. See its NOTICE.md for the upstream terms; no comparator implementation is linked into libbridct.
