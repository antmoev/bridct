#include "bridct.h"
#include "bridct_alloc.h"
#include "bridct_runtime.h"
#include "bridct_avx2_workspace.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int bridct_test_plan_uses_avx2(const bridct_plan *);
size_t bridct_test_plan_workspace(const bridct_plan *);
int bridct_small_optimized_f1(int, int, int, const float *, float *, float *, size_t);
#if BRIDCT_HAS_AVX2
int bridct_small_avx2_f1(int, int, int, const float *, float *, float *, size_t);
#endif

static int failures, checks;

static void require(int condition, const char *name)
{
    checks++;
    if (!condition) {
        fprintf(stderr, "FAIL: %s\n", name);
        failures++;
    }
}

static double basis8(int k, int x)
{
    return sqrt((k ? 2.0 : 1.0) / 8.0) *
        cos(3.14159265358979323846 * (2*x+1) * k / 16.0);
}

static void reference8(int mode, const float *x, double *y)
{
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            double sum = 0;
            if (mode == BRIDCT_ROUNDTRIP) {
                y[8*r+c] = x[8*r+c];
                continue;
            }
            for (int a = 0; a < 8; a++)
                for (int b = 0; b < 8; b++)
                    sum += x[8*a+b] *
                        (mode == BRIDCT_FORWARD ? basis8(r,a)*basis8(c,b)
                                                : basis8(a,r)*basis8(b,c));
            y[8*r+c] = sum;
        }
    }
}

static void small_route(void)
{
    float storage_x[66], storage_y[67], direct[64];
    float *x = storage_x+1, *y = storage_y+2;
    float *allocation = bridct_alloc_floats(136);
    require(allocation != NULL, "small workspace allocation");
    if (!allocation) return;
    float *work = (uintptr_t)allocation % 32 ? allocation : allocation+4;
    require((uintptr_t)work % 32 == 16, "workspace is 16-byte, not 32-byte aligned");
    for (int sample = 0; sample < 4; sample++) {
        for (int k = 0; k < 64; k++) {
            x[k] = sample == 0 ? (float)((k*17)%61-30)/32.f :
                sample == 1 ? 1.f : sample == 2 ? (k == 9 ? 1.f : 0.f) :
                (k%2 ? 1.f : -1.00000011920928955078125f);
        }
        for (int mode = 0; mode < 3; mode++) {
            double expected[64], squared_error = 0, squared_input = 0;
            reference8(mode, x, expected);
            storage_y[0] = storage_y[1] = storage_y[66] = 12345.f;
            require(bridct_apply(8, (enum bridct_mode)mode, x, y, work, 128) == 0,
                    "small public application");
#if BRIDCT_HAS_AVX2
            if (bridct_cpu_avx2_fma())
                require(bridct_small_avx2_f1(8, 1, mode, x, direct, work, 128) == 0,
                        "selected eight-lane private application");
            else
#endif
                require(bridct_small_optimized_f1(8, mode == 2 ? 1 : 2, mode,
                                                  x, direct, work, 128) == 0,
                        "selected four-lane private application");
            require(memcmp(y, direct, sizeof direct) == 0, "public dispatch matches selected kernel");
            require(storage_y[0] == 12345.f && storage_y[1] == 12345.f &&
                    storage_y[66] == 12345.f, "small output guards");
            for (int k = 0; k < 64; k++) {
                double d = (double)y[k] - expected[k];
                squared_error += d*d;
                squared_input += (double)x[k]*x[k];
            }
            require(isfinite(squared_error) &&
                    sqrt(squared_error / squared_input) <= 2e-5,
                    "small independent orthonormal reference");
        }
    }
    for (int k = 0; k < 64; k++) y[k] = 12345.f;
    require(bridct_apply(8, BRIDCT_FORWARD, x, y, work, 127) == BRIDCT_WORKSPACE_TOO_SMALL,
            "public insufficient workspace rejected before runtime dispatch");
    require(bridct_apply(8, (enum bridct_mode)3, x, y, work, 128) == BRIDCT_INVALID_ARGUMENT,
            "public invalid mode rejected before runtime dispatch");
    require(bridct_apply(8, BRIDCT_FORWARD, x, x, work, 128) == BRIDCT_OVERLAPPING_BUFFERS,
            "public overlap rejected before runtime dispatch");
    require(bridct_apply(8, BRIDCT_FORWARD, x, y, work+1, 128) == BRIDCT_BAD_ALIGNMENT,
            "public bad alignment rejected before runtime dispatch");
    int untouched = 1;
    for (int k = 0; k < 64; k++) untouched &= y[k] == 12345.f;
    require(untouched, "public rejection does not write output");
    bridct_free_floats(allocation);
}

static void plan_routes(void)
{
    const int sides[] = {8,16,32,64,128,256,512,1024};
    int selected = 0;
    for (int hi = 0; hi < 8; hi++) {
        for (int wi = 0; wi < 8; wi++) {
            int h = sides[hi], w = sides[wi];
            int eligible = (h == 256 && w == 256) ||
                ((h == 512 || h == 1024) && (w == 512 || w == 1024));
            int expected = eligible && bridct_cpu_avx2_fma();
            bridct_plan *plan = bridct_plan_create(h, w);
            require(plan != NULL, "supported plan created");
            if (!plan) continue;
            int actual = bridct_test_plan_uses_avx2(plan);
            selected += actual;
            require(actual == expected, "64-shape runtime selection matrix");
            int square = h == w && h <= 256;
            require(strcmp(bridct_plan_route(plan), square ? "paper8-square" :
                           "blocked-extension") == 0, "compatible public route label");
            if (expected)
                require(bridct_test_plan_workspace(plan) == wide8_workspace_count(h,w,4),
                        "selected plan has eight-lane workspace and alignment headroom");
            if (eligible) {
                size_t n = (size_t)h*w;
                float *x = malloc((n+2)*sizeof(float));
                float *y = malloc((n+2)*sizeof(float));
                require(x && y, "plan test buffers allocated");
                if (x && y) {
                    for (int mode = 0; mode < 3; mode++) {
                        for (size_t k = 0; k < n; k++)
                            x[k+1] = mode == BRIDCT_INVERSE ? 0.f : 1.f;
                        if (mode == BRIDCT_INVERSE) x[1] = (float)sqrt((double)n);
                        x[0] = x[n+1] = y[0] = y[n+1] = 12345.f;
                        require(bridct_plan_apply(plan,(enum bridct_mode)mode,x+1,y+1) == 0,
                                "runtime plan application");
                        double squared_error = 0;
                        for (size_t k = 0; k < n; k++) {
                            double value = mode == BRIDCT_FORWARD ?
                                (k ? 0.0 : sqrt((double)n)) : 1.0;
                            double d = y[k+1]-value;
                            squared_error += d*d;
                        }
                        require(isfinite(squared_error) && sqrt(squared_error/n) <= 2e-5,
                                "plan constant/DC reference");
                        require(x[0] == 12345.f && x[n+1] == 12345.f &&
                                y[0] == 12345.f && y[n+1] == 12345.f,
                                "plan input/output guards");
                    }
                    require(bridct_plan_apply(plan,BRIDCT_FORWARD,x+1,x+1) == BRIDCT_OVERLAPPING_BUFFERS,
                            "plan overlap rejected");
                    require(bridct_plan_apply(plan,(enum bridct_mode)3,x+1,y+1) == BRIDCT_INVALID_ARGUMENT,
                            "plan invalid mode rejected");
                }
                free(x);
                free(y);
            }
            bridct_plan_destroy(plan);
        }
    }
    require(selected == (bridct_cpu_avx2_fma() ? 5 : 0), "exactly five plan shapes accelerated");
}

int main(void)
{
    small_route();
    plan_routes();
    printf("runtime_simd=%d checks=%d failures=%d\n", bridct_cpu_avx2_fma(), checks, failures);
    return failures ? 1 : 0;
}
