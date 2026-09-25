#ifndef BRIDCT_H
#define BRIDCT_H

#include <stddef.h>

#if defined(_WIN32)
#if defined(BRIDCT_BUILD)
#define BRIDCT_API __declspec(dllexport)
#else
#define BRIDCT_API
#endif
#elif defined(__GNUC__)
#define BRIDCT_API __attribute__((visibility("default")))
#else
#define BRIDCT_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define BRIDCT_VERSION "0.2.0-dev.7"

enum bridct_mode {
    BRIDCT_FORWARD = 0,
    BRIDCT_INVERSE = 1,
    BRIDCT_ROUNDTRIP = 2
};

enum bridct_status {
    BRIDCT_OK = 0,
    BRIDCT_INVALID_ARGUMENT = -1,
    BRIDCT_WORKSPACE_TOO_SMALL = -2,
    BRIDCT_BAD_ALIGNMENT = -3,
    BRIDCT_OVERLAPPING_BUFFERS = -4
};

typedef struct bridct_plan bridct_plan;

BRIDCT_API int bridct_supported(int height, int width);
BRIDCT_API bridct_plan *bridct_plan_create(int height, int width);
BRIDCT_API void bridct_plan_destroy(bridct_plan *plan);
BRIDCT_API const char *bridct_plan_route(const bridct_plan *plan);
BRIDCT_API int bridct_plan_apply(bridct_plan *plan, enum bridct_mode mode,
                                const float *input, float *output);

BRIDCT_API size_t bridct_workspace_floats(int size);
BRIDCT_API int bridct_apply(int size, enum bridct_mode mode,
                           const float *input, float *output,
                           float *workspace, size_t workspace_count);

#ifdef __cplusplus
}
#endif
#endif
