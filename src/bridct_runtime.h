#ifndef BRIDCT_RUNTIME_H
#define BRIDCT_RUNTIME_H

#ifndef BRIDCT_COMPILED_AVX2
#define BRIDCT_COMPILED_AVX2 0
#endif

#if BRIDCT_COMPILED_AVX2 && defined(__x86_64__) && \
    (defined(__GNUC__) || defined(__clang__)) && !defined(SIMDE_NO_NATIVE)
#define BRIDCT_HAS_AVX2 1
#else
#define BRIDCT_HAS_AVX2 0
#endif

/* CPU detection must be compiled without the ISA that it is detecting. */
static inline int bridct_cpu_avx2_fma(void)
{
#if defined(BRIDCT_TESTING) && defined(BRIDCT_TEST_DISABLE_AVX2)
    return 0;
#elif BRIDCT_HAS_AVX2
    return __builtin_cpu_supports("avx2") && __builtin_cpu_supports("fma");
#else
    return 0;
#endif
}

static inline int bridct_avx2_plan_shape(int height, int width)
{
    return (height == 256 && width == 256) ||
        ((height == 512 || height == 1024) &&
         (width == 512 || width == 1024));
}

#endif
