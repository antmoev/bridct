# Platform scope of this snapshot

The kernels, public API, precision, normalization and immutable dataset are common across all three downloads. No platform ZIP is a different mathematical algorithm.

- **macOS ARM64:** native NEON on Apple Silicon. The manuscript's main timing results use one Apple M3 Max. The archive is freshly compiled and validated after extraction; the final native and Python campaigns use the same ARM object code.
- **Ubuntu 22.04/24.04 x86-64:** baseline SIMDe with runtime AVX2/FMA selection where available. An earlier independent Ubuntu return used dev.5; it is not a final-release evaluation. The current package must be checked on the recipient's machine.
- **Windows x86-64:** private MSYS2 CLANG64 and CPython. Dev.7 completed required native and Python checks on an Intel i9-9820X running Windows 11; short exploratory timings retained losses at large sizes. Packaging checks on a Mac do not constitute a new Windows run.

MSVC, Windows ARM and Linux ARM64 are not validated by these launchers. Windows uses a child-process PowerShell execution-policy override, not a persistent machine policy change. Corporate restrictions may prevent downloads or execution and are reported rather than bypassed.

The software does not support non-power-of-two axes such as 26. Padding the input would compute a different DCT and is not an equivalent fallback. Do not add fast-math flags when comparing the stated accuracy contract.
