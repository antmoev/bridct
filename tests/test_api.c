#include "bridct.h"
#include "bridct_alloc.h"
#include <math.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define REQUIRE(condition) do { if (!(condition)) { \
    fprintf(stderr, "FAIL at line %d: %s\n", __LINE__, #condition); return 1; \
} } while (0)

static int check_shape(int height, int width)
{
    size_t count = (size_t)height * width;
    float *input = malloc(count * sizeof(float));
    float *saved = malloc(count * sizeof(float));
    float *output = malloc(count * sizeof(float));
    bridct_plan *plan = bridct_plan_create(height, width);
    REQUIRE(input && saved && output && plan);
    for (size_t k = 0; k < count; k++)
        input[k] = (float)sin((double)k * 0.017);
    memcpy(saved, input, count * sizeof(float));
    for (int mode = 0; mode < 3; mode++) {
        REQUIRE(bridct_plan_apply(plan, (enum bridct_mode)mode, input, output) == BRIDCT_OK);
        REQUIRE(memcmp(input, saved, count * sizeof(float)) == 0);
        for (size_t k = 0; k < count; k++) {
            REQUIRE(isfinite(output[k]));
            if (mode == BRIDCT_ROUNDTRIP)
                REQUIRE(fabsf(output[k] - input[k]) < 2e-5f);
        }
    }
    REQUIRE(bridct_plan_apply(plan, BRIDCT_FORWARD, input, input) == BRIDCT_OVERLAPPING_BUFFERS);
    REQUIRE(bridct_plan_apply(plan, BRIDCT_FORWARD, input, input + 1) == BRIDCT_OVERLAPPING_BUFFERS);
    REQUIRE(bridct_plan_apply(plan, (enum bridct_mode)-1, input, output) == BRIDCT_INVALID_ARGUMENT);
    REQUIRE(bridct_plan_apply(plan, BRIDCT_FORWARD, NULL, output) == BRIDCT_INVALID_ARGUMENT);
    REQUIRE(strcmp(bridct_plan_route(plan), height == width && height <= 256 ? "paper8-square" : "blocked-extension") == 0);
    bridct_plan_destroy(plan);
    free(output);
    free(saved);
    free(input);
    return 0;
}

static int check_workspace(void)
{
    size_t count = bridct_workspace_floats(8);
    float input[64] = {0}, output[64];
    REQUIRE(bridct_alloc_floats(0) == NULL);
    REQUIRE(bridct_alloc_floats(SIZE_MAX) == NULL);
    bridct_free_floats(NULL);
    float *workspace = bridct_alloc_floats(count);
    REQUIRE(workspace);
    REQUIRE((uintptr_t)workspace % 16 == 0);
    REQUIRE(bridct_apply(8, BRIDCT_FORWARD, input, output, workspace, count) == BRIDCT_OK);
    REQUIRE(bridct_apply(8, BRIDCT_FORWARD, input, output, workspace, count-1) == BRIDCT_WORKSPACE_TOO_SMALL);
    REQUIRE(bridct_apply(8, BRIDCT_FORWARD, input, output, workspace+1, count) == BRIDCT_BAD_ALIGNMENT);
    REQUIRE(bridct_apply(8, BRIDCT_FORWARD, input, input, workspace, count) == BRIDCT_OVERLAPPING_BUFFERS);
    REQUIRE(bridct_apply(8, BRIDCT_FORWARD, input, workspace, workspace, count) == BRIDCT_OVERLAPPING_BUFFERS);
    REQUIRE(bridct_apply(8, (enum bridct_mode)9, input, output, workspace, count) == BRIDCT_INVALID_ARGUMENT);
    REQUIRE(bridct_apply(8, BRIDCT_FORWARD, NULL, output, workspace, count) == BRIDCT_INVALID_ARGUMENT);
    REQUIRE(bridct_workspace_floats(26) == 0);
    REQUIRE(bridct_workspace_floats(-8) == 0);
    bridct_free_floats(workspace);
    return 0;
}

static void *worker(void *argument)
{
    int *status = argument;
    *status = 0;
    for (int repeat = 0; repeat < 10; repeat++) {
        if (check_shape(16, 32) || check_shape(32, 32)) {
            *status = 1;
            break;
        }
    }
    return NULL;
}

int main(void)
{
    const int shapes[][2] = {
        {8,8}, {16,16}, {32,32}, {64,64}, {128,128}, {256,256},
        {16,32}, {8,64}, {32,16}, {512,512}, {1024,1024}, {512,1024}
    };
    REQUIRE(check_workspace() == 0);
    for (size_t k = 0; k < sizeof(shapes) / sizeof(shapes[0]); k++)
        REQUIRE(check_shape(shapes[k][0], shapes[k][1]) == 0);
    REQUIRE(!bridct_supported(32,26) && !bridct_plan_create(32,26));
    REQUIRE(!bridct_supported(-8,16) && !bridct_supported(2048,8));
    REQUIRE(bridct_plan_route(NULL) == NULL);
    REQUIRE(bridct_plan_apply(NULL, BRIDCT_FORWARD, NULL, NULL) == BRIDCT_INVALID_ARGUMENT);
    bridct_plan_destroy(NULL);
    pthread_t threads[4];
    int status[4];
    for (int i = 0; i < 4; i++)
        REQUIRE(pthread_create(&threads[i], NULL, worker, &status[i]) == 0);
    for (int i = 0; i < 4; i++) {
        REQUIRE(pthread_join(threads[i], NULL) == 0);
        REQUIRE(status[i] == 0);
    }
    puts("PASS: 12 shapes, workspace/argument/overlap checks, four threads with independent plans.");
    return 0;
}
