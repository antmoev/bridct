#define _POSIX_C_SOURCE 200809L
#include <stddef.h>
#include <stdint.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif

typedef int (*Kernel)(int,int,int,const float *,float *,float *,size_t);
static uint64_t ns(void)
{
#ifdef _WIN32
    LARGE_INTEGER value,frequency;
    if(!QueryPerformanceCounter(&value)||!QueryPerformanceFrequency(&frequency))return 0;
    return (uint64_t)((double)value.QuadPart*1e9/(double)frequency.QuadPart);
#else
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC,&t)) return 0;
    return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
#endif
}

double kernel_time(Kernel kernel,int n,int variant,int mode,
                   const float *x,float *y,float *workspace,size_t workspace_count,
                   int batch,uint64_t repeats)
{
    if (!kernel || n<1 || batch<1 || !repeats) return -1.;
    size_t count=(size_t)n*n;
    uint64_t begin=ns();
    for (uint64_t r=0;r<repeats;r++)
        for (int b=0;b<batch;b++)
            if (kernel(n,variant,mode,x+(size_t)b*count,y+(size_t)b*count,
                       workspace,workspace_count)) return -1.;
    uint64_t end=ns();
    return end>=begin?(double)(end-begin):-1.;
}
