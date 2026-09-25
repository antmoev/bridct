# Ooura benchmark controls

Copyright Takuya Ooura, 1996–2001. These comparator files retain their upstream terms rather than the BRiDCT BSD-3-Clause license. The [official package and permission](https://www.kurims.kyoto-u.ac.jp/~ooura/fft.html) permit use, modification and redistribution, including commercially and without payment, with acknowledgment of the package when modifying its code.

`shrtdct_original.c` is the frozen public double-precision source. The benchmark mechanically converts its declarations/constants to float32 for a same-precision comparison. `ooura_local.c` is an explicitly local adaptation: extracted 1D arithmetic, float constants, SIMD lanes and 4×4 register permutations. It is a stronger additional control, not an independent official SIMD implementation. Compilation replaces only its NEON include with the same BRiDCT compatibility layer. A trusted variant additionally omits precondition checks already guaranteed by the harness. All transformations and hashes are recorded.

None of these files is compiled into libbridct or used by its default transform implementation.
