#include "bridct.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

int main(void)
{
    /* Binary pipes must not translate float bytes as Windows text. */
#ifdef _WIN32
    if (_setmode(_fileno(stdin), _O_BINARY) == -1 ||
        _setmode(_fileno(stdout), _O_BINARY) == -1)
        return 7;
#endif
    uint32_t request[4];
    size_t bytes;
    while ((bytes = fread(request, 1, sizeof(request), stdin)) != 0) {
        if (bytes != sizeof(request) || request[0] != UINT32_C(0x42524443) ||
            !bridct_supported((int)request[1], (int)request[2]) || request[3] > 2)
            return 2;
        size_t count = (size_t)request[1] * request[2];
        float *input = malloc((count + 8) * sizeof(float));
        float *output = malloc((count + 8) * sizeof(float));
        float *saved = malloc(count * sizeof(float));
        bridct_plan *plan = bridct_plan_create((int)request[1], (int)request[2]);
        if (!input || !output || !saved || !plan)
            return 3;
        for (size_t i = 0; i < count + 8; i++)
            input[i] = output[i] = 12345.f;
        if (fread(input + 4, sizeof(float), count, stdin) != count)
            return 4;
        memcpy(saved, input + 4, count * sizeof(float));
        int rc = bridct_plan_apply(plan, (enum bridct_mode)request[3], input + 4, output + 4);
        uint32_t intact = 1;
        for (size_t i = 0; i < 4; i++)
            intact &= input[i] == 12345.f && output[i] == 12345.f &&
                input[count + 4 + i] == 12345.f && output[count + 4 + i] == 12345.f;
        uint32_t reply[4] = {request[0], (uint32_t)rc, intact,
            memcmp(saved, input + 4, count * sizeof(float)) == 0};
        if (fwrite(reply, sizeof(reply), 1, stdout) != 1 ||
            fwrite(output + 4, sizeof(float), count, stdout) != count || fflush(stdout))
            return 5;
        bridct_plan_destroy(plan);
        free(saved);
        free(output);
        free(input);
    }
    return ferror(stdin) ? 6 : 0;
}
