/* Extracted by tools/extract.py; provenance in ORIGIN.json. */
#include <stddef.h>
#include <math.h>
#include <stdint.h>
#include "bridct_simd.h"
typedef float K;
typedef float32x4_t T;
static inline T zero(void){return vdupq_n_f32(0.f);}
static inline T add(T a,T b){return vaddq_f32(a,b);}
static inline T neg(T a){return vnegq_f32(a);}
static inline T mul(T a,K b){return vmulq_n_f32(a,b);}
#include "tables.inc"
#include "sj_body.inc"
static void transpose4(const float*restrict x,float*restrict y,int n,const float*scale){
 for(int i=0;i<n;i+=4)for(int j=0;j<n;j+=4){
  T a=vld1q_f32(x+i*n+j),b=vld1q_f32(x+(i+1)*n+j),c=vld1q_f32(x+(i+2)*n+j),d=vld1q_f32(x+(i+3)*n+j);
  float32x4x2_t u=vtrnq_f32(a,b),v=vtrnq_f32(c,d);
  T z[4]={vcombine_f32(vget_low_f32(u.val[0]),vget_low_f32(v.val[0])),vcombine_f32(vget_low_f32(u.val[1]),vget_low_f32(v.val[1])),vcombine_f32(vget_high_f32(u.val[0]),vget_high_f32(v.val[0])),vcombine_f32(vget_high_f32(u.val[1]),vget_high_f32(v.val[1]))};
  for(int k=0;k<4;k++){if(scale)z[k]=vmulq_f32(z[k],vld1q_f32(scale+(j+k)*n+i));vst1q_f32(y+(j+k)*n+i,z[k]);}
 }
}
static void vertical_f8(const float*restrict x,float*restrict y){T u[8],v[8];for(int col=0;col<8;col+=4){for(int k=0;k<8;k++)u[k]=vld1q_f32(x+k*8+col);one_f8(u,v);for(int k=0;k<8;k++)vst1q_f32(y+k*8+col,v[k]);}}
static void half_f8(const float*restrict x,float*restrict y,float*restrict a,float*restrict b){vertical_f8(x,a);transpose4(a,b,8,NULL);vertical_f8(b,y);}
static void vertical_t8(const float*restrict x,float*restrict y){T u[8],v[8];for(int col=0;col<8;col+=4){for(int k=0;k<8;k++)u[k]=vld1q_f32(x+k*8+col);one_t8(u,v);for(int k=0;k<8;k++)vst1q_f32(y+k*8+col,v[k]);}}
static void half_t8(const float*restrict x,float*restrict y,float*restrict a,float*restrict b){vertical_t8(x,a);transpose4(a,b,8,NULL);vertical_t8(b,y);}
static void vertical_f16(const float*restrict x,float*restrict y){T u[16],v[16];for(int col=0;col<16;col+=4){for(int k=0;k<16;k++)u[k]=vld1q_f32(x+k*16+col);one_f16(u,v);for(int k=0;k<16;k++)vst1q_f32(y+k*16+col,v[k]);}}
static void half_f16(const float*restrict x,float*restrict y,float*restrict a,float*restrict b){vertical_f16(x,a);transpose4(a,b,16,NULL);vertical_f16(b,y);}
static void vertical_t16(const float*restrict x,float*restrict y){T u[16],v[16];for(int col=0;col<16;col+=4){for(int k=0;k<16;k++)u[k]=vld1q_f32(x+k*16+col);one_t16(u,v);for(int k=0;k<16;k++)vst1q_f32(y+k*16+col,v[k]);}}
static void half_t16(const float*restrict x,float*restrict y,float*restrict a,float*restrict b){vertical_t16(x,a);transpose4(a,b,16,NULL);vertical_t16(b,y);}

int NAME(int n,int variant,int mode,const float*x,float*y,float*w,size_t count){
 (void)count;size_t m=(size_t)n*n;
 float*a=w,*b=a+m,*c=b+m,*d=c+m;T*A=(T*)w;T*B=A+m;T*C=B+m;T*D=C+m;(void)D;
if(n==8){
  if(variant==0){if(mode==0){half_f8(x,a,b,c);transpose4(a,y,8,norm_sj8);}else if(mode==1){for(size_t k=0;k<m;k+=4)vst1q_f32(a+k,vmulq_f32(vld1q_f32(x+k),vld1q_f32(norm_sj8+k)));half_t8(a,b,c,d);transpose4(b,y,8,NULL);}else{half_f8(x,a,b,c);for(size_t k=0;k<m;k+=4)vst1q_f32(a+k,vmulq_f32(vld1q_f32(a+k),vld1q_f32(corr_sj8+k)));half_t8(a,y,b,c);}return 0;}
}
if(n==16){
  if(variant==0){if(mode==0){half_f16(x,a,b,c);transpose4(a,y,16,norm_sj16);}else if(mode==1){for(size_t k=0;k<m;k+=4)vst1q_f32(a+k,vmulq_f32(vld1q_f32(x+k),vld1q_f32(norm_sj16+k)));half_t16(a,b,c,d);transpose4(b,y,16,NULL);}else{half_f16(x,a,b,c);for(size_t k=0;k<m;k+=4)vst1q_f32(a+k,vmulq_f32(vld1q_f32(a+k),vld1q_f32(corr_sj16+k)));half_t16(a,y,b,c);}return 0;}
}
return -1;
}
