#ifndef BRIDCT_ALLOC_H
#define BRIDCT_ALLOC_H

#include <stdint.h>
#include <stdlib.h>
#ifdef _WIN32
#include <malloc.h>
#endif

static inline float *bridct_alloc_floats(size_t count)
{
    if (!count || count > (SIZE_MAX - 15) / sizeof(float))
        return NULL;
    size_t bytes = (count * sizeof(float) + 15) & ~(size_t)15;
#ifdef _WIN32
    return _aligned_malloc(bytes, 16);
#else
    return aligned_alloc(16, bytes);
#endif
}

static inline void bridct_free_floats(float *memory)
{
    /* Windows aligned allocations must be paired with _aligned_free. */
#ifdef _WIN32
    _aligned_free(memory);
#else
    free(memory);
#endif
}

#endif
