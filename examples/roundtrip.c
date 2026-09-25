#include "bridct.h"
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static int dimension(const char *text)
{
    char *end;
    errno = 0;
    long value = strtol(text, &end, 10);
    return errno || *end || value < 8 || value > 1024 ? 0 : (int)value;
}

int main(int argc, char **argv)
{
    int height = argc > 1 ? dimension(argv[1]) : 16;
    int width = argc > 2 ? dimension(argv[2]) : 32;
    if (argc > 3 || !bridct_supported(height, width)) {
        fprintf(stderr, "usage: %s [height width], power-of-two axes 8..1024\n", argv[0]);
        return EXIT_FAILURE;
    }

    size_t count = (size_t)height * width;
    float *input = malloc(count * sizeof(float));
    float *coefficients = malloc(count * sizeof(float));
    float *reconstructed = malloc(count * sizeof(float));
    bridct_plan *plan = bridct_plan_create(height, width);
    int status = EXIT_FAILURE;
    if (!input || !coefficients || !reconstructed || !plan)
        goto cleanup;

    for (int row = 0; row < height; row++)
        for (int col = 0; col < width; col++)
            input[(size_t)row * width + col] = (float)(sin(row * 0.17) + cos(col * 0.13));

    if (bridct_plan_apply(plan, BRIDCT_FORWARD, input, coefficients) != BRIDCT_OK ||
        bridct_plan_apply(plan, BRIDCT_INVERSE, coefficients, reconstructed) != BRIDCT_OK)
        goto cleanup;

    double error = 0.0, norm = 0.0;
    for (size_t k = 0; k < count; k++) {
        double delta = (double)input[k] - reconstructed[k];
        error += delta * delta;
        norm += (double)input[k] * input[k];
    }
    double relative_error = sqrt(error / norm);
    printf("BRiDCT %s: %dx%d, %s, relative round-trip error %.3g\n",
           BRIDCT_VERSION, height, width, bridct_plan_route(plan), relative_error);
    status = isfinite(relative_error) && relative_error < 2e-5 ? EXIT_SUCCESS : EXIT_FAILURE;

cleanup:
    bridct_plan_destroy(plan);
    free(reconstructed);
    free(coefficients);
    free(input);
    return status;
}
