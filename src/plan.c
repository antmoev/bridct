#include "bridct.h"
#include "bridct_alloc.h"
#include "bridct_runtime.h"
#if BRIDCT_HAS_AVX2
#include "bridct_avx2_workspace.h"
#endif
#include "generated/rect_generated_meta.h"
#include <math.h>
#include <stdint.h>
#include <stdlib.h>

struct bridct_plan {
    int height, width, square;
#if BRIDCT_HAS_AVX2
    int avx2;
#endif
    size_t elements, workspace_count;
    float *workspace, *normalization, *correction;
};

int bridct_rect_f0(int, int, int, int, const float *, float *, const float *, const float *, float *);
int bridct_rect_f1(int, int, int, int, const float *, float *, const float *, const float *, float *);

#if BRIDCT_HAS_AVX2
int bridct_rect_avx2_f0(int, int, int, int, const float *, float *, const float *, const float *, float *);
int bridct_rect_avx2_f1(int, int, int, int, const float *, float *, const float *, const float *, float *);
#endif

static const int policies[][5] = {
#include "generated/rect_policy.inc"
};

int bridct_supported(int height, int width)
{
    return height >= 8 && height <= 1024 && width >= 8 && width <= 1024 &&
        !(height & (height - 1)) && !(width & (width - 1));
}

/* Shao–Johnson recursive scale; the DCT core of length n uses scale(4*n,k). */
static double sj_scale(int n, int k)
{
    if (n <= 4)
        return 1.0;
    k %= n / 4;
    double angle = 2 * 3.14159265358979323846 * k / n;
    return sj_scale(n / 4, k) * (k <= n / 8 ? cos(angle) : sin(angle));
}

void bridct_plan_destroy(bridct_plan *plan)
{
    if (plan) {
        bridct_free_floats(plan->correction);
        bridct_free_floats(plan->normalization);
        bridct_free_floats(plan->workspace);
        free(plan);
    }
}

bridct_plan *bridct_plan_create(int height, int width)
{
    if (!bridct_supported(height, width))
        return NULL;

    bridct_plan *plan = calloc(1, sizeof(*plan));
    if (!plan)
        return NULL;
    plan->height = height;
    plan->width = width;
    plan->elements = (size_t)height * width;
    plan->square = height == width && height <= 256;
#if BRIDCT_HAS_AVX2
    plan->avx2 = bridct_avx2_plan_shape(height, width) && bridct_cpu_avx2_fma();
    if (plan->avx2)
        plan->square = 0;
#endif
    plan->workspace_count = plan->square ? bridct_workspace_floats(height)
        : 2 * (size_t)height * (width + 4) + EXTRA_FLOATS;
#if BRIDCT_HAS_AVX2
    if (plan->avx2)
        plan->workspace_count = wide8_workspace_count(height, width, 4);
#endif
    plan->workspace = bridct_alloc_floats(plan->workspace_count);
    if (!plan->workspace)
        goto fail;

    if (!plan->square) {
        plan->normalization = bridct_alloc_floats(plan->elements);
        plan->correction = bridct_alloc_floats(plan->elements);
        if (!plan->normalization || !plan->correction)
            goto fail;

        double inverse_scale[2][1024];
        for (int axis = 0; axis < 2; axis++) {
            int n = axis ? width : height;
            for (int k = 0; k < n; k++) {
                double scale = sj_scale(4*n, k) * sqrt((k ? 2.0 : 1.0) / n);
                inverse_scale[axis][k] = 1.0 / scale;
            }
        }
        for (int row = 0; row < height; row++) {
            for (int col = 0; col < width; col++) {
                size_t k = (size_t)row * width + col;
                double scale = 1.0 / (inverse_scale[0][row] * inverse_scale[1][col]);
                plan->normalization[k] = (float)scale;
                /* U = E H, so the identity pair H^T E^2 H folds two scales. */
                plan->correction[k] = (float)(scale * scale);
            }
        }
    }
    return plan;

fail:
    bridct_plan_destroy(plan);
    return NULL;
}

const char *bridct_plan_route(const bridct_plan *plan)
{
#if BRIDCT_HAS_AVX2
    if (plan && plan->height == 256 && plan->width == 256)
        return "paper8-square";
#endif
    return !plan ? NULL : plan->square ? "paper8-square" : "blocked-extension";
}

int bridct_plan_apply(bridct_plan *plan, enum bridct_mode mode,
                      const float *input, float *output)
{
    if (!plan || !input || !output || (unsigned)mode > BRIDCT_ROUNDTRIP)
        return BRIDCT_INVALID_ARGUMENT;

    uintptr_t a = (uintptr_t)input;
    uintptr_t b = (uintptr_t)output;
    if ((a <= b ? b-a : a-b) < plan->elements * sizeof(float))
        return BRIDCT_OVERLAPPING_BUFFERS;
    if (plan->square)
        return bridct_apply(plan->height, mode, input, output,
                            plan->workspace, plan->workspace_count);

    int padding = 4, fma = 0;
    for (size_t k = 0; k < sizeof(policies) / sizeof(policies[0]); k++) {
        if (policies[k][0] == plan->height && policies[k][1] == plan->width &&
            policies[k][2] == (int)mode) {
            padding = policies[k][3];
            fma = policies[k][4];
            break;
        }
    }
#if BRIDCT_HAS_AVX2
    if (plan->avx2) {
        if (plan->height == 256 && plan->width == 256) {
            padding = 4;
            fma = 1;
        }
        return (fma ? bridct_rect_avx2_f1 : bridct_rect_avx2_f0)
            (plan->height, plan->width, padding, mode, input, output,
             plan->normalization, plan->correction, plan->workspace);
    }
#endif
    return (fma ? bridct_rect_f1 : bridct_rect_f0)
        (plan->height, plan->width, padding, mode, input, output,
         plan->normalization, plan->correction, plan->workspace);
}

#ifdef BRIDCT_TESTING
int bridct_test_plan_uses_avx2(const bridct_plan *plan)
{
#if BRIDCT_HAS_AVX2
    return plan && plan->avx2;
#else
    (void)plan;
    return 0;
#endif
}

size_t bridct_test_plan_workspace(const bridct_plan *plan)
{
    return plan ? plan->workspace_count : 0;
}
#endif
