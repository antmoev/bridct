#include "bridct.h"
#include "bridct_runtime.h"
#include <stdint.h>

#if BRIDCT_HAS_AVX2
int bridct_small_avx2_f1(int, int, int, const float *, float *, float *, size_t);
#endif

int bridct_small_optimized_f1(int, int, int, const float *, float *, float *, size_t);
int bridct_large_f0(int, int, int, const float *, float *, float *, size_t);
int bridct_large_f1(int, int, int, const float *, float *, float *, size_t);

size_t bridct_workspace_floats(int n)
{
    if (n != 8 && n != 16 && n != 32 && n != 64 && n != 128 && n != 256)
        return 0;

    size_t elements = (size_t)n * n;
    return n <= 16 ? 2 * elements
        : 8 * elements + 2 * 1100 * 4 + 4 * 4 * 256 + 4 * (size_t)n * (4*n + 4);
}

static int overlaps(const void *a, size_t bytes_a, const void *b, size_t bytes_b)
{
    uintptr_t x = (uintptr_t)a;
    uintptr_t y = (uintptr_t)b;
    return x <= y ? y - x < bytes_a : x - y < bytes_b;
}

int bridct_apply(int n, enum bridct_mode mode, const float *input, float *output,
                 float *workspace, size_t workspace_count)
{
    size_t needed = bridct_workspace_floats(n);
    if (!needed || !input || !output || !workspace || (unsigned)mode > BRIDCT_ROUNDTRIP)
        return BRIDCT_INVALID_ARGUMENT;
    if (workspace_count < needed)
        return BRIDCT_WORKSPACE_TOO_SMALL;
    if ((uintptr_t)workspace % 16)
        return BRIDCT_BAD_ALIGNMENT;

    size_t bytes = (size_t)n * n * sizeof(float);
    if (overlaps(input, bytes, output, bytes) ||
        overlaps(input, bytes, workspace, needed * sizeof(float)) ||
        overlaps(output, bytes, workspace, needed * sizeof(float)))
        return BRIDCT_OVERLAPPING_BUFFERS;

#if BRIDCT_HAS_AVX2
    if (n == 8 && bridct_cpu_avx2_fma())
        return bridct_small_avx2_f1(n, 1, mode, input, output,
                                     workspace, workspace_count);
#endif
    if (n <= 16) {
        int variant = n == 8 && mode == BRIDCT_ROUNDTRIP ? 1 : 2;
        return bridct_small_optimized_f1(n, variant, mode, input, output,
                                          workspace, workspace_count);
    }

    int variant;
    if (n == 32)
        variant = 0;
    else if (n == 64)
        variant = mode == BRIDCT_INVERSE ? 5 : 3;
    else if (n == 128)
        variant = 6;
    else
        variant = mode == BRIDCT_INVERSE ? 5 : 6;

#if defined(__x86_64__)
    if (n == 256 && mode == BRIDCT_INVERSE && !bridct_cpu_avx2_fma())
        variant = 6;
#endif

    return (n == 32 || n == 256 ? bridct_large_f1 : bridct_large_f0)
        (n, variant, mode, input, output, workspace, workspace_count);
}
