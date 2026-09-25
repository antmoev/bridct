#include "bridct.h"
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define REQUIRE(condition) do { if (!(condition)) { \
    fprintf(stderr, "FAIL at line %d: %s\n", __LINE__, #condition); return 1; \
} } while (0)

static void reference(int n, int mode, const float *input, double *output)
{
    double q[256], temporary[256];
    for (int k = 0; k < n; k++)
        for (int j = 0; j < n; j++)
            q[k*n+j] = sqrt((k ? 2.0 : 1.0) / n) *
                cos(3.14159265358979323846 * (2*j+1) * k / (2*n));
    if (mode == BRIDCT_ROUNDTRIP) {
        for (int k = 0; k < n*n; k++)
            output[k] = input[k];
        return;
    }
    for (int row = 0; row < n; row++) {
        for (int col = 0; col < n; col++) {
            double sum = 0;
            for (int k = 0; k < n; k++)
                sum += q[mode == BRIDCT_FORWARD ? row*n+k : k*n+row] * input[k*n+col];
            temporary[row*n+col] = sum;
        }
    }
    for (int row = 0; row < n; row++) {
        for (int col = 0; col < n; col++) {
            double sum = 0;
            for (int k = 0; k < n; k++)
                sum += temporary[row*n+k] * q[mode == BRIDCT_FORWARD ? col*n+k : k*n+col];
            output[row*n+col] = sum;
        }
    }
}

static int check_rejections(int base_n)
{
    struct storage {
        _Alignas(16) float input[272], output[272], workspace[528];
    } buffers, saved;
    size_t needed = 2*(size_t)base_n*base_n;
    for (int scenario = 0; scenario < 24; scenario++) {
        memset(&buffers, 0, sizeof(buffers));
        for (size_t k = 0; k < 272; k++) {
            buffers.input[k] = 321.25f;
            buffers.output[k] = -912.5f;
        }
        for (size_t k = 0; k < 528; k++)
            buffers.workspace[k] = 313.75f;
        int n = base_n, mode = 0, expected = BRIDCT_INVALID_ARGUMENT;
        const float *input = buffers.input+8;
        float *output = buffers.output+8, *workspace = buffers.workspace+8;
        size_t count = needed;
        switch (scenario) {
            case 0: n = 0; break;
            case 1: n = 7; break;
            case 2: n = 26; break;
            case 3: n = INT_MIN; break;
            case 4: n = INT_MAX; break;
            case 5: mode = -1; break;
            case 6: mode = 3; break;
            case 7: input = NULL; break;
            case 8: output = NULL; break;
            case 9: workspace = NULL; break;
            case 10: count = 0; expected = BRIDCT_WORKSPACE_TOO_SMALL; break;
            case 11: count--; expected = BRIDCT_WORKSPACE_TOO_SMALL; break;
            case 12: workspace++; expected = BRIDCT_BAD_ALIGNMENT; break;
            case 13: output = buffers.input+8; break;
            case 14: output = buffers.input+9; break;
            case 15: input = buffers.output+9; break;
            case 16: workspace = buffers.input+8; break;
            case 17: workspace = buffers.input+12; break;
            case 18: workspace = buffers.output+8; break;
            case 19: workspace = buffers.output+12; break;
            case 20: input = buffers.workspace+8; break;
            case 21: output = buffers.workspace+8; break;
            case 22: input = buffers.workspace+12; break;
            case 23: output = buffers.workspace+12; break;
        }
        if (scenario >= 13)
            expected = BRIDCT_OVERLAPPING_BUFFERS;
        memcpy(&saved, &buffers, sizeof(buffers));
        REQUIRE(bridct_apply(n, (enum bridct_mode)mode, input, output,
                             workspace, count) == expected);
        REQUIRE(memcmp(&saved, &buffers, sizeof(buffers)) == 0);
    }
    return 0;
}

static int check_size(int n)
{
    _Alignas(16) float input_storage[272], output_storage[272], workspace_storage[528];
    float saved[256];
    double expected[256];
    float *input = input_storage + 8;
    float *output = output_storage + 8;
    float *workspace = workspace_storage + 8;
    size_t elements = (size_t)n*n, count = bridct_workspace_floats(n);
    REQUIRE(count == 2*elements);
    for (size_t trial = 0; trial < elements + 4; trial++) {
        for (size_t k = 0; k < elements; k++) {
            if (trial < elements)
                input[k] = k == trial ? 1.f : 0.f;
            else if (trial == elements)
                input[k] = 0.f;
            else if (trial == elements + 1)
                input[k] = 1.f;
            else if (trial == elements + 2)
                input[k] = k % 2 ? 1.f : nextafterf(1.f, 2.f);
            else
                input[k] = (float)sin((double)k * .23) * (k % 2 ? -128.f : 128.f);
        }
        memcpy(saved, input, elements*sizeof(float));
        for (int mode = 0; mode < 3; mode++) {
            for (size_t k = 0; k < elements; k++)
                output[k] = -913.25f;
            for (size_t k = 0; k < count; k++)
                workspace[k] = 731.5f;
            for (int k = 0; k < 8; k++) {
                input_storage[k] = input[elements+k] = 117.75f;
                output_storage[k] = output[elements+k] = -913.25f;
                workspace_storage[k] = workspace[count+k] = 731.5f;
            }
            REQUIRE(bridct_apply(n, (enum bridct_mode)mode, input, output,
                                 workspace, count) == BRIDCT_OK);
            REQUIRE(memcmp(input, saved, elements*sizeof(float)) == 0);
            for (int k = 0; k < 8; k++) {
                REQUIRE(input_storage[k] == 117.75f && input[elements+k] == 117.75f);
                REQUIRE(output_storage[k] == -913.25f && output[elements+k] == -913.25f);
                REQUIRE(workspace_storage[k] == 731.5f && workspace[count+k] == 731.5f);
            }
            reference(n, mode, input, expected);
            double error = 0, norm = 0;
            for (size_t k = 0; k < elements; k++) {
                REQUIRE(isfinite(output[k]));
                double delta = output[k] - expected[k];
                error += delta*delta;
                norm += (double)input[k]*input[k];
            }
            REQUIRE(norm ? sqrt(error/norm) <= 2e-5 : error == 0);
        }
    }
    REQUIRE(check_rejections(n) == 0);
    return 0;
}

int main(void)
{
    REQUIRE(check_size(8) == 0);
    REQUIRE(check_size(16) == 0);
    puts("PASS: 984 small directional checks, exact scratch sizes, guards and 48 public rejections without writes.");
    return 0;
}
