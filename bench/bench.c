#define _POSIX_C_SOURCE 200809L
#include "bridct.h"
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif

static double nanoseconds_per_tick = 1.0;

static uint64_t ticks(void)
{
#ifdef _WIN32
    LARGE_INTEGER value;
    if (!QueryPerformanceCounter(&value))
        exit(EXIT_FAILURE);
    return (uint64_t)value.QuadPart;
#else
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value))
        exit(EXIT_FAILURE);
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
#endif
}

static int integer(const char *text, int low, int high)
{
    char *end;
    errno = 0;
    long value = strtol(text, &end, 10);
    return errno || end == text || *end || value < low || value > high ? -1 : (int)value;
}

static double measure(bridct_plan *plan, enum bridct_mode mode, const float *input,
                      float *output, size_t count, int batch, uint64_t iterations)
{
    uint64_t start = ticks();
    for (uint64_t iteration = 0; iteration < iterations; iteration++)
        for (int image = 0; image < batch; image++)
            if (bridct_plan_apply(plan, mode, input + (size_t)image * count,
                                  output + (size_t)image * count) != BRIDCT_OK)
                return -1.0;
    uint64_t end = ticks();
    if (end < start)
        return -1.0;
    return (double)(end - start) * nanoseconds_per_tick;
}

int main(int argc, char **argv)
{
    int h = 16, w = 16, batch = 4, mode = 0, blocks = 7, target_ms = 10;
    if (argc == 7) {
        h = integer(argv[1], 8, 1024);
        w = integer(argv[2], 8, 1024);
        batch = integer(argv[3], 1, 64);
        mode = integer(argv[4], 0, 2);
        blocks = integer(argv[5], 1, 1000);
        target_ms = integer(argv[6], 1, 1000);
    }
    if ((argc != 1 && argc != 7) || !bridct_supported(h, w) || batch < 1 ||
        mode < 0 || blocks < 1 || target_ms < 1) {
        fprintf(stderr, "usage: %s [height width batch mode blocks target_ms]\n"
                "mode: 0 forward, 1 inverse, 2 identity round trip; batch 1..64\n", argv[0]);
        return EXIT_FAILURE;
    }
#ifdef _WIN32
    LARGE_INTEGER frequency;
    if (!QueryPerformanceFrequency(&frequency) || frequency.QuadPart <= 0)
        return EXIT_FAILURE;
    nanoseconds_per_tick = 1e9 / (double)frequency.QuadPart;
#endif
#if defined(__aarch64__)
    const char *arch = "aarch64";
#elif defined(__x86_64__)
    const char *arch = "x86_64";
#else
    const char *arch = "other";
#endif
#if defined(SIMDE_NO_NATIVE)
    const char *backend = "SIMDe-no-native";
#elif defined(BRIDCT_USE_SIMDE) || !defined(__aarch64__)
    const char *backend = "SIMDe";
#else
    const char *backend = "NEON";
#endif
    fprintf(stderr,"BRiDCT %s; target=%s; backend=%s; compiler=%s\n",
            BRIDCT_VERSION,arch,backend,__VERSION__);
    size_t count = (size_t)h * w, total = count * (size_t)batch;
    float *input = malloc(total * sizeof(float));
    float *output = malloc(total * sizeof(float));
    bridct_plan *plan = bridct_plan_create(h, w);
    int status = EXIT_FAILURE;
    if (!input || !output || !plan)
        goto cleanup;
    uint32_t state = UINT32_C(20260921);
    for (size_t i = 0; i < total; i++) {
        state ^= state << 13;
        state ^= state >> 17;
        state ^= state << 5;
        input[i] = (float)(state >> 8) * 0x1p-24f - 0.5f;
    }
    if (measure(plan, (enum bridct_mode)mode, input, output, count, batch, 4) < 0)
        goto cleanup;
    uint64_t iterations = 1;
    double elapsed;
    for (;;) {
        elapsed = measure(plan, (enum bridct_mode)mode, input, output, count, batch, iterations);
        if (elapsed < 0)
            goto cleanup;
        if (elapsed >= target_ms * 1e6)
            break;
        if (iterations >= (UINT64_C(1) << 32))
            goto cleanup;
        iterations *= 2;
    }
    const char *names[] = {"forward", "inverse", "roundtrip"};
    puts("version,height,width,batch,mode,block,iterations,elapsed_ns,ns_per_array,checksum");
    for (int block = 0; block < blocks; block++) {
        elapsed = measure(plan, (enum bridct_mode)mode, input, output, count, batch, iterations);
        if (!(elapsed > 0) || !isfinite(elapsed))
            goto cleanup;
        double checksum = 0;
        for (size_t i = 0; i < total; i++) {
            if (!isfinite(output[i]))
                goto cleanup;
            checksum += output[i];
        }
        printf("%s,%d,%d,%d,%s,%d,%" PRIu64 ",%.3f,%.6f,%.9g\n",
               BRIDCT_VERSION,h,w,batch,names[mode],block,iterations,elapsed,
               elapsed / ((double)iterations * batch),checksum);
    }
    status = ferror(stdout) ? EXIT_FAILURE : EXIT_SUCCESS;
cleanup:
    bridct_plan_destroy(plan);
    free(output);
    free(input);
    return status;
}
