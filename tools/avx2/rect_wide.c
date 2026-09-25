#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "rect_wide_generated.inc"
#include "workspace.h"

#define WIDE_CAT_(a, b) a##b
#define WIDE_CAT(a, b) WIDE_CAT_(a, b)

size_t WIDE_CAT(NAME, _workspace_floats)(int h, int w, int pad)
{
    return wide8_workspace_count(h, w, pad);
}

void WIDE_CAT(NAME, _transpose_check)(const float *x, float *y)
{
    T rows[8];
    for (int r = 0; r < 8; r++) rows[r] = w8_load(x + 8*r);
    w8_transpose(rows);
    for (int r = 0; r < 8; r++) w8_store(y + 8*r, rows[r]);
}

static void vertical(int h, int w, int stride, int inverse,
                     const float *x, float *y, T *scratch)
{
    for (int c = 0; c < w; c += 8) col(h, inverse, x+c, y+c, scratch, stride);
}

static void bands(int h, int w, int stride, int output_stride, int inverse,
                  const float *x, float *y, const float *norm, T *scratch)
{
    T *u = scratch, *v = u+w, *work = v+w;
    for (int r = 0; r < h; r += 8) {
        for (int c = 0; c < w; c += 8) {
            T rows[8];
            for (int k = 0; k < 8; k++) rows[k] = w8_load(x+(size_t)(r+k)*stride+c);
            w8_transpose(rows);
            for (int k = 0; k < 8; k++) u[c+k] = rows[k];
        }
        col(w, inverse, (const float *)u, (float *)v, work, 8);
        for (int c = 0; c < w; c += 8) {
            T rows[8];
            for (int k = 0; k < 8; k++) rows[k] = v[c+k];
            w8_transpose(rows);
            for (int k = 0; k < 8; k++) {
                T value = rows[k];
                if (norm) value = w8_mul(value, w8_load(norm+(size_t)(r+k)*w+c));
                w8_store(y+(size_t)(r+k)*output_stride+c, value);
            }
        }
    }
}

int NAME(int h, int w, int pad, int mode, const float *x, float *y,
         const float *norm, const float *corr, float *work)
{
    if (!wide8_workspace_count(h, w, pad) || mode < 0 || mode > 2) return -1;
    int stride = w+pad;
    size_t elements = (size_t)h*stride;
    float *a = work, *b = a+elements;
    /* Images may be only float-aligned; vector temporaries require 32 bytes. */
    T *scratch = (T *)(((uintptr_t)(b+elements)+31u) & ~(uintptr_t)31u);
    for (int r = 0; r < h; r++) {
        for (int c = 0; c < w; c += 8) {
            T value = w8_load(x+(size_t)r*w+c);
            if (mode == 1) value = w8_mul(value, w8_load(norm+(size_t)r*w+c));
            w8_store(a+(size_t)r*stride+c, value);
        }
    }
    if (mode == 0) {
        vertical(h, w, stride, 0, a, b, scratch);
        bands(h, w, stride, w, 0, b, y, norm, scratch);
    } else {
        if (mode == 2) {
            vertical(h, w, stride, 0, a, b, scratch);
            bands(h, w, stride, stride, 0, b, a, corr, scratch);
        }
        bands(h, w, stride, stride, 1, a, b, NULL, scratch);
        vertical(h, w, stride, 1, b, a, scratch);
        for (int r = 0; r < h; r++)
            memcpy(y+(size_t)r*w, a+(size_t)r*stride, (size_t)w*sizeof(float));
    }
    return 0;
}
