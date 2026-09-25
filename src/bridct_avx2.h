#ifndef BRIDCT_WIDE8_OPS_H
#define BRIDCT_WIDE8_OPS_H

#if defined(WIDE8_SCALAR_CHECK)
typedef struct { float lane[8]; } W8;
static inline W8 w8_load(const float *x)
{
    W8 r; for (int k = 0; k < 8; k++) r.lane[k] = x[k]; return r;
}
static inline void w8_store(float *x, W8 a)
{
    for (int k = 0; k < 8; k++) x[k] = a.lane[k];
}
static inline W8 w8_splat(float a)
{
    W8 r; for (int k = 0; k < 8; k++) r.lane[k] = a; return r;
}
static inline W8 w8_add(W8 a, W8 b)
{
    W8 r; for (int k = 0; k < 8; k++) r.lane[k] = a.lane[k] + b.lane[k]; return r;
}
static inline W8 w8_sub(W8 a, W8 b)
{
    W8 r; for (int k = 0; k < 8; k++) r.lane[k] = a.lane[k] - b.lane[k]; return r;
}
static inline W8 w8_mul(W8 a, W8 b)
{
    W8 r; for (int k = 0; k < 8; k++) r.lane[k] = a.lane[k] * b.lane[k]; return r;
}
static inline W8 w8_mul_scalar(W8 a, float b) { return w8_mul(a, w8_splat(b)); }
static inline W8 w8_neg(W8 a)
{
    W8 r; for (int k = 0; k < 8; k++) r.lane[k] = -a.lane[k]; return r;
}
static inline void w8_transpose(W8 rows[8])
{
    W8 copy[8];
    for (int r = 0; r < 8; r++) copy[r] = rows[r];
    for (int r = 0; r < 8; r++)
        for (int c = 0; c < 8; c++) rows[r].lane[c] = copy[c].lane[r];
}
#else
#if !defined(__AVX2__)
#error "The wide8 execution backend requires AVX2; scalar mode is for checks only."
#endif
#include <immintrin.h>
typedef __m256 W8;
static inline W8 w8_load(const float *x) { return _mm256_loadu_ps(x); }
static inline void w8_store(float *x, W8 a) { _mm256_storeu_ps(x, a); }
static inline W8 w8_splat(float a) { return _mm256_set1_ps(a); }
static inline W8 w8_add(W8 a, W8 b) { return _mm256_add_ps(a, b); }
static inline W8 w8_sub(W8 a, W8 b) { return _mm256_sub_ps(a, b); }
static inline W8 w8_mul(W8 a, W8 b) { return _mm256_mul_ps(a, b); }
static inline W8 w8_mul_scalar(W8 a, float b) { return _mm256_mul_ps(a, _mm256_set1_ps(b)); }
static inline W8 w8_neg(W8 a) { return _mm256_xor_ps(a, _mm256_set1_ps(-0.0f)); }

/* Each shuffle stays inside 128-bit halves; the final permutes join rows 0..3
   with rows 4..7. No coefficient arithmetic or memory transpose is involved. */
static inline void w8_transpose(W8 rows[8])
{
    W8 t0 = _mm256_unpacklo_ps(rows[0], rows[1]);
    W8 t1 = _mm256_unpackhi_ps(rows[0], rows[1]);
    W8 t2 = _mm256_unpacklo_ps(rows[2], rows[3]);
    W8 t3 = _mm256_unpackhi_ps(rows[2], rows[3]);
    W8 t4 = _mm256_unpacklo_ps(rows[4], rows[5]);
    W8 t5 = _mm256_unpackhi_ps(rows[4], rows[5]);
    W8 t6 = _mm256_unpacklo_ps(rows[6], rows[7]);
    W8 t7 = _mm256_unpackhi_ps(rows[6], rows[7]);
    W8 s0 = _mm256_shuffle_ps(t0, t2, 0x44);
    W8 s1 = _mm256_shuffle_ps(t0, t2, 0xee);
    W8 s2 = _mm256_shuffle_ps(t1, t3, 0x44);
    W8 s3 = _mm256_shuffle_ps(t1, t3, 0xee);
    W8 s4 = _mm256_shuffle_ps(t4, t6, 0x44);
    W8 s5 = _mm256_shuffle_ps(t4, t6, 0xee);
    W8 s6 = _mm256_shuffle_ps(t5, t7, 0x44);
    W8 s7 = _mm256_shuffle_ps(t5, t7, 0xee);
    rows[0] = _mm256_permute2f128_ps(s0, s4, 0x20);
    rows[1] = _mm256_permute2f128_ps(s1, s5, 0x20);
    rows[2] = _mm256_permute2f128_ps(s2, s6, 0x20);
    rows[3] = _mm256_permute2f128_ps(s3, s7, 0x20);
    rows[4] = _mm256_permute2f128_ps(s0, s4, 0x31);
    rows[5] = _mm256_permute2f128_ps(s1, s5, 0x31);
    rows[6] = _mm256_permute2f128_ps(s2, s6, 0x31);
    rows[7] = _mm256_permute2f128_ps(s3, s7, 0x31);
}
#endif

#endif
