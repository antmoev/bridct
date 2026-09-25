#include "bridct.h"
#include "bridct_runtime.h"
#include <string.h>

int bridct_small_optimized_f1(int,int,int,const float*,float*,float*,size_t);
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#ifndef __has_feature
#define __has_feature(x) 0
#endif
#if __has_feature(address_sanitizer) || defined(__SANITIZE_ADDRESS__)
#include <sanitizer/asan_interface.h>
#define POISON(p,n) __asan_poison_memory_region((p),(n))
#define UNPOISON(p,n) __asan_unpoison_memory_region((p),(n))
#else
#define POISON(p,n) ((void)0)
#define UNPOISON(p,n) ((void)0)
#endif

static int checks, failures;
static void require(int ok) { checks++; if(!ok) failures++; }
static float *reserve(float **owner, size_t count, unsigned residue)
{
    *owner=malloc((count+32)*sizeof(float));
    if(!*owner) return NULL;
    for(size_t k=0;k<count+32;k++) (*owner)[k]=12345.f;
    uintptr_t address=((uintptr_t)(*owner+1)+63u)&~(uintptr_t)63u;
    return (float *)(address+residue);
}
static int guards(const float *owner, const float *data, size_t count)
{
    size_t start=(size_t)(data-owner);
    for(size_t k=0;k<start;k++) if(owner[k]!=12345.f) return 0;
    for(size_t k=start+count;k<count+32;k++) if(owner[k]!=12345.f) return 0;
    return 1;
}
static void protect(float *owner, float *data, size_t count)
{
    size_t start=(size_t)(data-owner);
    POISON(owner,start*sizeof(float));
    POISON(data+count,(32-start)*sizeof(float));
}
static void unprotect(float *owner, size_t count)
{
    UNPOISON(owner,(count+32)*sizeof(float));
}
static int selected_call(int mode, const float *x, float *y, float *work)
{
    return bridct_small_optimized_f1(16,2,mode,x,y,work,512);
}
int main(void)
{
    const unsigned triples[6][3]={{0,0,0},{16,48,48},{48,16,48},{32,16,0},{4,12,16},{60,4,32}};
    const int impulses[4]={0,1,85,255};
    double c[16][16];
    _Alignas(32) float direct[256];
    for(int k=0;k<16;k++) for(int x=0;x<16;x++)
        c[k][x]=sqrt((k?2.0:1.0)/16)*cos(3.14159265358979323846*(2*x+1)*k/32);
    for(int layout=0;layout<6;layout++) {
        float *ax=NULL,*ay=NULL,*aw=NULL;
        float *x=reserve(&ax,256,triples[layout][0]);
        float *y=reserve(&ay,256,triples[layout][1]);
        float *w=reserve(&aw,512,triples[layout][2]);
        require(x&&y&&w);if(!x||!y||!w) return 1;
        require((uintptr_t)x%64==triples[layout][0]);
        require((uintptr_t)y%64==triples[layout][1]);
        require((uintptr_t)w%64==triples[layout][2]);
        for(int sample=0;sample<4;sample++) for(int mode=0;mode<3;mode++) {
            int impulse=impulses[sample];
            for(int k=0;k<256;k++) { x[k]=k==impulse; y[k]=12345.f; }
            for(int k=0;k<512;k++) w[k]=12345.f;
            protect(ax,x,256);protect(ay,y,256);protect(aw,w,512);
            require(bridct_apply(16,(enum bridct_mode)mode,x,y,w,512)==0);
            unprotect(ax,256);unprotect(ay,256);unprotect(aw,512);
            double error=0;
            for(int r=0;r<16;r++) for(int s=0;s<16;s++) {
                double wanted=mode==2 ? (r*16+s==impulse) : mode==0 ? c[r][impulse/16]*c[s][impulse%16] : c[impulse/16][r]*c[impulse%16][s];
                double d=y[r*16+s]-wanted;error+=d*d;
                require(x[r*16+s]==(r*16+s==impulse));
            }
            require(isfinite(error)&&sqrt(error)<=2e-5);
            require(guards(ax,x,256)&&guards(ay,y,256)&&guards(aw,w,512));
            protect(ax,x,256);protect(aw,w,512);
            require(selected_call(mode,x,direct,w)==0);
            unprotect(ax,256);unprotect(aw,512);
            require(memcmp(y,direct,sizeof direct)==0);
        }
        for(int k=0;k<256;k++) y[k]=12345.f;
        for(int k=0;k<512;k++) w[k]=12345.f;
        protect(ax,x,256);protect(ay,y,256);protect(aw,w,512);
        require(bridct_apply(16,BRIDCT_FORWARD,x,y,w,511)==BRIDCT_WORKSPACE_TOO_SMALL);
        require(bridct_apply(16,(enum bridct_mode)3,x,y,w,512)==BRIDCT_INVALID_ARGUMENT);
        require(bridct_apply(16,BRIDCT_FORWARD,x,x,w,512)==BRIDCT_OVERLAPPING_BUFFERS);
        require(bridct_apply(16,BRIDCT_FORWARD,x,y,w+1,512)==BRIDCT_BAD_ALIGNMENT);
        require(bridct_apply(16,BRIDCT_INVERSE,x,y,w,511)==BRIDCT_WORKSPACE_TOO_SMALL);
        require(bridct_apply(16,BRIDCT_INVERSE,x,x,w,512)==BRIDCT_OVERLAPPING_BUFFERS);
        require(bridct_apply(16,BRIDCT_INVERSE,x,y,w+1,512)==BRIDCT_BAD_ALIGNMENT);
        unprotect(ax,256);unprotect(ay,256);unprotect(aw,512);
        for(int k=0;k<256;k++) require(y[k]==12345.f);
        for(int k=0;k<512;k++) require(w[k]==12345.f);
        require(guards(ax,x,256)&&guards(ay,y,256)&&guards(aw,w,512));
        free(ax);free(ay);free(aw);
    }
    printf("shao_johnson16 checks=%d failures=%d layouts=6 exact_workspace=512\n",checks,failures);
    return failures?1:0;
}
