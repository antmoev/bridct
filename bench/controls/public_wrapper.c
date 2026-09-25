/* T. Ooura, fft2d/shrtdct.c; see control_manifest.json for source hash and conversion. */
#include <stddef.h>
#include <string.h>
#define CAT_(a,b) a##b
#define CAT(a,b) CAT_(a,b)
#define public8 CAT(NAME,_8)
#define public16 CAT(NAME,_16)
#include "ooura_public_float.c"
int NAME(int n,int variant,int mode,const float*x,float*y,float*w,size_t count)
{
    (void)variant;(void)w;(void)count;
    if ((n!=8 && n!=16) || mode<0 || mode>2) return -1;
    memcpy(y,x,(size_t)n*n*sizeof(float));
    float *rows[16];for(int r=0;r<n;r++) rows[r]=y+(size_t)r*n;
    if (mode!=1) { if(n==8)public8(-1,rows);else public16(-1,rows); }
    if (mode!=0) { if(n==8)public8(1,rows);else public16(1,rows); }
    return 0;
}
