#include <stddef.h>
#include "wide8_ops.h"
typedef float K;
typedef W8 T;
static inline T zero(void) { return w8_splat(0.f); }
static inline T add(T a, T b) { return w8_add(a, b); }
static inline T neg(T a) { return w8_neg(a); }
static inline T mul(T a, K b) { return w8_mul_scalar(a, b); }
#include "tables.inc"
#include "sj_body.inc"
#if defined(WIDE8_AAN4)
#include "aan4_body.inc"
#include "aan4_tables.inc"
#define FORWARD8 aan4_f8
#define INVERSE8 aan4_t8
#define NORM8 norm_aan8
#define CORR8 corr_aan8
#else
#define FORWARD8 one_f8
#define INVERSE8 one_t8
#define NORM8 norm_sj8
#define CORR8 corr_sj8
#endif
#ifndef NAME
#define NAME bridct_wide_small
#endif

static inline void pass_f(int n, const float *restrict x, float *restrict y,
                          const float *scale, int transpose)
{
    T u[16], v[16];
    for (int col = 0; col < n; col += 8) {
        for (int k = 0; k < n; k++) u[k] = w8_load(x + k*n + col);
        if (n == 8) FORWARD8(u, v);
        else one_f16(u, v);
        if (transpose) {
            for (int row = 0; row < n; row += 8) {
                w8_transpose(v + row);
                for (int k = 0; k < 8; k++) {
                    int offset = (col+k)*n+row;
                    T value = v[row+k];
                    if (scale) value = w8_mul(value, w8_load(scale + offset));
                    w8_store(y + offset, value);
                }
            }
        } else {
            for (int k = 0; k < n; k++) {
                int offset = k*n+col;
                T value = v[k];
                if (scale) value = w8_mul(value, w8_load(scale + offset));
                w8_store(y + offset, value);
            }
        }
    }
}

static inline void pass_t(int n, const float *restrict x, float *restrict y,
                          const float *scale, int transpose)
{
    T u[16], v[16];
    for (int col = 0; col < n; col += 8) {
        for (int k = 0; k < n; k++) {
            int offset = k*n+col;
            u[k] = w8_load(x + offset);
            if (scale) u[k] = w8_mul(u[k], w8_load(scale + offset));
        }
        if (n == 8) INVERSE8(u, v);
        else one_t16(u, v);
        if (transpose) {
            for (int row = 0; row < n; row += 8) {
                w8_transpose(v + row);
                for (int k = 0; k < 8; k++)
                    w8_store(y + (col+k)*n+row, v[row+k]);
            }
        } else {
            for (int k = 0; k < n; k++) w8_store(y + k*n+col, v[k]);
        }
    }
}

static inline void registers8(int mode, const float *restrict x, float *restrict y)
{
    T u[8], v[8];
    for (int k = 0; k < 8; k++) {
        u[k] = w8_load(x + 8*k);
        if (mode == 1) u[k] = w8_mul(u[k], w8_load(NORM8 + 8*k));
    }
    if (mode == 0) {
        FORWARD8(u, v);
        w8_transpose(v);
        FORWARD8(v, u);
        w8_transpose(u);
        for (int k = 0; k < 8; k++) u[k] = w8_mul(u[k], w8_load(NORM8 + 8*k));
    } else if (mode == 1) {
        INVERSE8(u, v);
        w8_transpose(v);
        INVERSE8(v, u);
        w8_transpose(u);
    } else {
        FORWARD8(u, v);
        w8_transpose(v);
        FORWARD8(v, u);
        for (int k = 0; k < 8; k++) u[k] = w8_mul(u[k], w8_load(CORR8 + 8*k));
        INVERSE8(u, v);
        w8_transpose(v);
        INVERSE8(v, u);
    }
    for (int k = 0; k < 8; k++) w8_store(y + 8*k, u[k]);
}

int NAME(int n, int variant, int mode, const float *x, float *y,
         float *workspace, size_t count)
{
    if ((n != 8 && n != 16) || (unsigned)mode > 2 || !x || !y || !workspace ||
        count < (size_t)2*n*n) return -1;
    if (variant == 1 && n == 8) {
        registers8(mode, x, y);
        return 0;
    }
    if (variant != 2) return -1;
    const float *norm = n == 8 ? NORM8 : norm_sj16;
    const float *corr = n == 8 ? CORR8 : corr_sj16;
    float *a = workspace, *b = workspace+n*n;
    if (mode == 0) {
        pass_f(n, x, a, NULL, 1);
        pass_f(n, a, y, norm, 1);
    } else if (mode == 1) {
        pass_t(n, x, a, norm, 1);
        pass_t(n, a, y, NULL, 1);
    } else {
        pass_f(n, x, a, NULL, 1);
        pass_f(n, a, b, NULL, 0);
        pass_t(n, b, a, corr, 1);
        pass_t(n, a, y, NULL, 0);
    }
    return 0;
}
