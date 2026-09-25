#include <stddef.h>
#include "bridct_simd.h"
typedef float K;
typedef float32x4_t T;
static inline T zero(void) { return vdupq_n_f32(0.f); }
static inline T add(T a, T b) { return vaddq_f32(a, b); }
static inline T neg(T a) { return vnegq_f32(a); }
static inline T mul(T a, K b) { return vmulq_n_f32(a, b); }
#include "tables.inc"
#include "sj_body.inc"
#ifndef NAME
#define NAME bridct_small_optimized_f1
#endif

static inline __attribute__((always_inline)) void tr4(T a, T b, T c, T d, T *z)
{
    float32x4x2_t u = vtrnq_f32(a, b), v = vtrnq_f32(c, d);
    z[0] = vcombine_f32(vget_low_f32(u.val[0]), vget_low_f32(v.val[0]));
    z[1] = vcombine_f32(vget_low_f32(u.val[1]), vget_low_f32(v.val[1]));
    z[2] = vcombine_f32(vget_high_f32(u.val[0]), vget_high_f32(v.val[0]));
    z[3] = vcombine_f32(vget_high_f32(u.val[1]), vget_high_f32(v.val[1]));
}

static inline __attribute__((always_inline)) void pass_f8(
    const float *restrict x, float *restrict y,
    const float *scale_in, const float *scale_out, int transpose)
{
    T u[8], v[8], z[4];
    for (int col = 0; col < 8; col += 4) {
        for (int k = 0; k < 8; k++) {
            u[k] = vld1q_f32(x + k*8 + col);
            if (scale_in)
                u[k] = vmulq_f32(u[k], vld1q_f32(scale_in + k*8 + col));
        }
        one_f8(u, v);
        if (transpose) {
            for (int row = 0; row < 8; row += 4) {
                tr4(v[row], v[row+1], v[row+2], v[row+3], z);
                for (int k = 0; k < 4; k++) {
                    T a = z[k];
                    if (scale_out)
                        a = vmulq_f32(a, vld1q_f32(scale_out + (col+k)*8 + row));
                    vst1q_f32(y + (col+k)*8 + row, a);
                }
            }
        } else {
            for (int k = 0; k < 8; k++) {
                T a = v[k];
                if (scale_out)
                    a = vmulq_f32(a, vld1q_f32(scale_out + k*8 + col));
                vst1q_f32(y + k*8 + col, a);
            }
        }
    }
}

static inline __attribute__((always_inline)) void pass_t8(
    const float *restrict x, float *restrict y,
    const float *scale_in, const float *scale_out, int transpose)
{
    T u[8], v[8], z[4];
    for (int col = 0; col < 8; col += 4) {
        for (int k = 0; k < 8; k++) {
            u[k] = vld1q_f32(x + k*8 + col);
            if (scale_in)
                u[k] = vmulq_f32(u[k], vld1q_f32(scale_in + k*8 + col));
        }
        one_t8(u, v);
        if (transpose) {
            for (int row = 0; row < 8; row += 4) {
                tr4(v[row], v[row+1], v[row+2], v[row+3], z);
                for (int k = 0; k < 4; k++) {
                    T a = z[k];
                    if (scale_out)
                        a = vmulq_f32(a, vld1q_f32(scale_out + (col+k)*8 + row));
                    vst1q_f32(y + (col+k)*8 + row, a);
                }
            }
        } else {
            for (int k = 0; k < 8; k++) {
                T a = v[k];
                if (scale_out)
                    a = vmulq_f32(a, vld1q_f32(scale_out + k*8 + col));
                vst1q_f32(y + k*8 + col, a);
            }
        }
    }
}

static void fused8(int mode, const float *restrict x,
                    float *restrict y, float *restrict w)
{
    float *a = w, *b = w + 64;
    if (mode == 0) {
        pass_f8(x, a, NULL, NULL, 1);
        pass_f8(a, y, NULL, norm_sj8, 1);
    } else if (mode == 1) {
        pass_t8(x, a, norm_sj8, NULL, 1);
        pass_t8(a, y, NULL, NULL, 1);
    }
}

static inline __attribute__((always_inline)) void pass_f16(
    const float *restrict x, float *restrict y,
    const float *scale_in, const float *scale_out, int transpose)
{
    T u[16], v[16], z[4];
    for (int col = 0; col < 16; col += 4) {
        for (int k = 0; k < 16; k++) {
            u[k] = vld1q_f32(x + k*16 + col);
            if (scale_in)
                u[k] = vmulq_f32(u[k], vld1q_f32(scale_in + k*16 + col));
        }
        one_f16(u, v);
        if (transpose) {
            for (int row = 0; row < 16; row += 4) {
                tr4(v[row], v[row+1], v[row+2], v[row+3], z);
                for (int k = 0; k < 4; k++) {
                    T a = z[k];
                    if (scale_out)
                        a = vmulq_f32(a, vld1q_f32(scale_out + (col+k)*16 + row));
                    vst1q_f32(y + (col+k)*16 + row, a);
                }
            }
        } else {
            for (int k = 0; k < 16; k++) {
                T a = v[k];
                if (scale_out)
                    a = vmulq_f32(a, vld1q_f32(scale_out + k*16 + col));
                vst1q_f32(y + k*16 + col, a);
            }
        }
    }
}

static inline __attribute__((always_inline)) void pass_t16(
    const float *restrict x, float *restrict y,
    const float *scale_in, const float *scale_out, int transpose)
{
    T u[16], v[16], z[4];
    for (int col = 0; col < 16; col += 4) {
        for (int k = 0; k < 16; k++) {
            u[k] = vld1q_f32(x + k*16 + col);
            if (scale_in)
                u[k] = vmulq_f32(u[k], vld1q_f32(scale_in + k*16 + col));
        }
        one_t16(u, v);
        if (transpose) {
            for (int row = 0; row < 16; row += 4) {
                tr4(v[row], v[row+1], v[row+2], v[row+3], z);
                for (int k = 0; k < 4; k++) {
                    T a = z[k];
                    if (scale_out)
                        a = vmulq_f32(a, vld1q_f32(scale_out + (col+k)*16 + row));
                    vst1q_f32(y + (col+k)*16 + row, a);
                }
            }
        } else {
            for (int k = 0; k < 16; k++) {
                T a = v[k];
                if (scale_out)
                    a = vmulq_f32(a, vld1q_f32(scale_out + k*16 + col));
                vst1q_f32(y + k*16 + col, a);
            }
        }
    }
}

#if defined(__aarch64__) && defined(__clang__)
static inline __attribute__((always_inline)) void pass_t16_inverse(
    const float *restrict x, float *restrict y,
    const float *scale_in, const float *scale_out, int transpose)
{
    T u[16], v[16], z[4];
    #pragma clang loop unroll(full)
    for (int col = 0; col < 16; col += 4) {
        for (int k = 0; k < 16; k++) {
            u[k] = vld1q_f32(x + k*16 + col);
            if (scale_in)
                u[k] = vmulq_f32(u[k], vld1q_f32(scale_in + k*16 + col));
        }
        one_t16(u, v);
        if (transpose) {
            for (int row = 0; row < 16; row += 4) {
                tr4(v[row], v[row+1], v[row+2], v[row+3], z);
                for (int k = 0; k < 4; k++) {
                    T a = z[k];
                    if (scale_out)
                        a = vmulq_f32(a, vld1q_f32(scale_out + (col+k)*16 + row));
                    vst1q_f32(y + (col+k)*16 + row, a);
                }
            }
        } else {
            for (int k = 0; k < 16; k++) {
                T a = v[k];
                if (scale_out)
                    a = vmulq_f32(a, vld1q_f32(scale_out + k*16 + col));
                vst1q_f32(y + k*16 + col, a);
            }
        }
    }
}

#else
#define pass_t16_inverse pass_t16
#endif

static void fused16(int mode, const float *restrict x,
                    float *restrict y, float *restrict w)
{
    float *a = w, *b = w + 256;
    if (mode == 0) {
        pass_f16(x, a, NULL, NULL, 1);
        pass_f16(a, y, NULL, norm_sj16, 1);
    } else if (mode == 1) {
        pass_t16_inverse(x, a, norm_sj16, NULL, 1);
        pass_t16_inverse(a, y, NULL, NULL, 1);
    } else {
        pass_f16(x, a, NULL, NULL, 1);
        pass_f16(a, b, NULL, NULL, 0);
        pass_t16(b, a, corr_sj16, NULL, 1);
        pass_t16(a, y, NULL, NULL, 0);
    }
}

static void registers8_2(const float *restrict x, float *restrict y)
{
    T a[2][8], b[2][8], z[4];
    a[0][0] = vld1q_f32(x + 0);
    a[0][1] = vld1q_f32(x + 8);
    a[0][2] = vld1q_f32(x + 16);
    a[0][3] = vld1q_f32(x + 24);
    a[0][4] = vld1q_f32(x + 32);
    a[0][5] = vld1q_f32(x + 40);
    a[0][6] = vld1q_f32(x + 48);
    a[0][7] = vld1q_f32(x + 56);
    a[1][0] = vld1q_f32(x + 4);
    a[1][1] = vld1q_f32(x + 12);
    a[1][2] = vld1q_f32(x + 20);
    a[1][3] = vld1q_f32(x + 28);
    a[1][4] = vld1q_f32(x + 36);
    a[1][5] = vld1q_f32(x + 44);
    a[1][6] = vld1q_f32(x + 52);
    a[1][7] = vld1q_f32(x + 60);
    one_f8(a[0], b[0]);
    one_f8(a[1], b[1]);
    tr4(b[0][0], b[0][1], b[0][2], b[0][3], z);
    a[0][0] = z[0];
    a[0][1] = z[1];
    a[0][2] = z[2];
    a[0][3] = z[3];
    tr4(b[1][0], b[1][1], b[1][2], b[1][3], z);
    a[0][4] = z[0];
    a[0][5] = z[1];
    a[0][6] = z[2];
    a[0][7] = z[3];
    tr4(b[0][4], b[0][5], b[0][6], b[0][7], z);
    a[1][0] = z[0];
    a[1][1] = z[1];
    a[1][2] = z[2];
    a[1][3] = z[3];
    tr4(b[1][4], b[1][5], b[1][6], b[1][7], z);
    a[1][4] = z[0];
    a[1][5] = z[1];
    a[1][6] = z[2];
    a[1][7] = z[3];
    one_f8(a[0], b[0]);
    one_f8(a[1], b[1]);
    a[0][0] = b[0][0];
    a[1][0] = b[1][0];
    a[0][1] = b[0][1];
    a[1][1] = b[1][1];
    a[0][2] = b[0][2];
    a[1][2] = b[1][2];
    a[0][3] = b[0][3];
    a[1][3] = b[1][3];
    a[0][4] = b[0][4];
    a[1][4] = b[1][4];
    a[0][5] = b[0][5];
    a[1][5] = b[1][5];
    a[0][6] = b[0][6];
    a[1][6] = b[1][6];
    a[0][7] = b[0][7];
    a[1][7] = b[1][7];
    a[0][0] = vmulq_f32(a[0][0], vld1q_f32(corr_sj8 + 0));
    a[1][0] = vmulq_f32(a[1][0], vld1q_f32(corr_sj8 + 4));
    a[0][1] = vmulq_f32(a[0][1], vld1q_f32(corr_sj8 + 8));
    a[1][1] = vmulq_f32(a[1][1], vld1q_f32(corr_sj8 + 12));
    a[0][2] = vmulq_f32(a[0][2], vld1q_f32(corr_sj8 + 16));
    a[1][2] = vmulq_f32(a[1][2], vld1q_f32(corr_sj8 + 20));
    a[0][3] = vmulq_f32(a[0][3], vld1q_f32(corr_sj8 + 24));
    a[1][3] = vmulq_f32(a[1][3], vld1q_f32(corr_sj8 + 28));
    a[0][4] = vmulq_f32(a[0][4], vld1q_f32(corr_sj8 + 32));
    a[1][4] = vmulq_f32(a[1][4], vld1q_f32(corr_sj8 + 36));
    a[0][5] = vmulq_f32(a[0][5], vld1q_f32(corr_sj8 + 40));
    a[1][5] = vmulq_f32(a[1][5], vld1q_f32(corr_sj8 + 44));
    a[0][6] = vmulq_f32(a[0][6], vld1q_f32(corr_sj8 + 48));
    a[1][6] = vmulq_f32(a[1][6], vld1q_f32(corr_sj8 + 52));
    a[0][7] = vmulq_f32(a[0][7], vld1q_f32(corr_sj8 + 56));
    a[1][7] = vmulq_f32(a[1][7], vld1q_f32(corr_sj8 + 60));
    one_t8(a[0], b[0]);
    one_t8(a[1], b[1]);
    tr4(b[0][0], b[0][1], b[0][2], b[0][3], z);
    a[0][0] = z[0];
    a[0][1] = z[1];
    a[0][2] = z[2];
    a[0][3] = z[3];
    tr4(b[1][0], b[1][1], b[1][2], b[1][3], z);
    a[0][4] = z[0];
    a[0][5] = z[1];
    a[0][6] = z[2];
    a[0][7] = z[3];
    tr4(b[0][4], b[0][5], b[0][6], b[0][7], z);
    a[1][0] = z[0];
    a[1][1] = z[1];
    a[1][2] = z[2];
    a[1][3] = z[3];
    tr4(b[1][4], b[1][5], b[1][6], b[1][7], z);
    a[1][4] = z[0];
    a[1][5] = z[1];
    a[1][6] = z[2];
    a[1][7] = z[3];
    one_t8(a[0], b[0]);
    one_t8(a[1], b[1]);
    a[0][0] = b[0][0];
    a[1][0] = b[1][0];
    a[0][1] = b[0][1];
    a[1][1] = b[1][1];
    a[0][2] = b[0][2];
    a[1][2] = b[1][2];
    a[0][3] = b[0][3];
    a[1][3] = b[1][3];
    a[0][4] = b[0][4];
    a[1][4] = b[1][4];
    a[0][5] = b[0][5];
    a[1][5] = b[1][5];
    a[0][6] = b[0][6];
    a[1][6] = b[1][6];
    a[0][7] = b[0][7];
    a[1][7] = b[1][7];
    vst1q_f32(y + 0, a[0][0]);
    vst1q_f32(y + 4, a[1][0]);
    vst1q_f32(y + 8, a[0][1]);
    vst1q_f32(y + 12, a[1][1]);
    vst1q_f32(y + 16, a[0][2]);
    vst1q_f32(y + 20, a[1][2]);
    vst1q_f32(y + 24, a[0][3]);
    vst1q_f32(y + 28, a[1][3]);
    vst1q_f32(y + 32, a[0][4]);
    vst1q_f32(y + 36, a[1][4]);
    vst1q_f32(y + 40, a[0][5]);
    vst1q_f32(y + 44, a[1][5]);
    vst1q_f32(y + 48, a[0][6]);
    vst1q_f32(y + 52, a[1][6]);
    vst1q_f32(y + 56, a[0][7]);
    vst1q_f32(y + 60, a[1][7]);
}

/* Internal: n=8/16, mode=0..2 and variant follow the validated public dispatch.
   The caller supplies disjoint n*n input/output arrays and a 16-byte-aligned
   workspace of at least 2*n*n floats; this entry point does not validate them. */
int NAME(int n, int variant, int mode, const float *x, float *y,
         float *w, size_t count)
{
    if (n == 8 && variant == 1 && mode == 2) {
        registers8_2(x, y);
        return 0;
    }
    if (variant == 2) {
        if (n == 8 && mode != 2) {
            fused8(mode, x, y, w);
            return 0;
        }
        if (n == 16) {
            fused16(mode, x, y, w);
            return 0;
        }
    }
    return -1;
}
