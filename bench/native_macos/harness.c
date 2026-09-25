#define _POSIX_C_SOURCE 200809L
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <arm_neon.h>
#include <Accelerate/Accelerate.h>
#include "fftw3.h"
#include <stdint.h>
#include "bridct.h"
typedef struct Plan Plan;
void *jx_create(int,int,int);
void jx_free(void*);
int jx_run(void*,int,const float*,float*);
void jpeg_fdct_float(float*);
int ooura_neon_f1(int,int,int,const float*,float*,float*,size_t);
int ooura_public_f1(int,int,int,const float*,float*,float*,size_t);
int ooura_trusted_f1(int,int,int,const float*,float*,float*,size_t);
#define PI 3.14159265358979323846
int f0_rect(int,int,int,int,const float*,float*,const float*,const float*,float*);
int f1_rect(int,int,int,int,const float*,float*,const float*,const float*,float*);
void ddct(int,int,float*,int*,float*);
struct Plan{int h,w,available[9];size_t m;float*norm[9],*inv[9],*corr[9],*a,*b,*c,*copy,*work;vDSP_DFT_Setup vf[2],vt[2];fftwf_plan ff,ft;int*ip[2];float*tw[2];bridct_plan*bridct;void*jxl;};
static float* allocf(size_t n){return fftwf_alloc_real(n);}
static double sjscale(int n,int k){if(n<=4)return 1.;k%=n/4;return sjscale(n/4,k)*(k<=n/8?cos(2*PI*k/n):sin(2*PI*k/n));}
static void one(Plan*p,int b,int axis,int inverse,const float*x,float*y){int n=axis?p->w:p->h;if(b==1)vDSP_DCT_Execute(inverse?p->vt[axis]:p->vf[axis],x,y);else{memcpy(y,x,(size_t)n*sizeof(float));ddct(n,inverse?1:-1,y,p->ip[axis],p->tw[axis]);}}
void rect_free(Plan*p){if(!p)return;bridct_plan_destroy(p->bridct);jx_free(p->jxl);for(int b=0;b<9;b++){fftwf_free(p->norm[b]);fftwf_free(p->inv[b]);fftwf_free(p->corr[b]);}for(int a=0;a<2;a++){if(p->vf[a])vDSP_DFT_DestroySetup(p->vf[a]);if(p->vt[a])vDSP_DFT_DestroySetup(p->vt[a]);free(p->ip[a]);free(p->tw[a]);}if(p->ff)fftwf_destroy_plan(p->ff);if(p->ft)fftwf_destroy_plan(p->ft);fftwf_free(p->a);fftwf_free(p->b);fftwf_free(p->c);fftwf_free(p->copy);fftwf_free(p->work);free(p);}
Plan*rect_plan(int h,int w){
 if(h<8||h>1024||w<8||w>1024)return NULL;
 Plan*p=calloc(1,sizeof(*p));if(!p)return NULL;p->h=h;p->w=w;p->m=(size_t)h*w;p->available[0]=!(h&(h-1))&&!(w&(w-1));p->available[3]=p->available[0];p->available[2]=1;
 p->bridct=bridct_plan_create(h,w);p->available[0]=p->bridct!=NULL;
 p->available[4]=h==w&&h<=256; if(p->available[4]){p->jxl=jx_create(9,h,1);if(!p->jxl)goto fail;}
 p->available[5]=h==8&&w==8;
 p->available[6]=p->available[7]=p->available[8]=h==w&&(h==8||h==16);
 p->a=allocf(p->m);p->b=allocf(p->m);p->c=allocf(p->m);p->copy=allocf(p->m);p->work=allocf(16*(size_t)h*(w+4)+8192);
 if(!p->a||!p->b||!p->c||!p->copy||!p->work)goto fail;
 for(int b=0;b<9;b++){p->norm[b]=allocf(p->m);p->inv[b]=allocf(p->m);p->corr[b]=allocf(p->m);if(!p->norm[b]||!p->inv[b]||!p->corr[b])goto fail;}
 for(int a=0;a<2;a++){int n=a?w:h;if(n>=16&&!(n&(n-1))){p->vf[a]=vDSP_DCT_CreateSetup(NULL,n,vDSP_DCT_II);p->vt[a]=vDSP_DCT_CreateSetup(NULL,n,vDSP_DCT_III);}p->ip[a]=calloc(2+2*n,sizeof(int));p->tw[a]=calloc(4*n,sizeof(float));if(!p->ip[a]||!p->tw[a])goto fail;}
 p->available[1]=p->vf[0]&&p->vf[1]&&p->vt[0]&&p->vt[1];
 /* Public FFTW PATIENT planner with explicit one-second budget per plan; setup excluded. */
 fftwf_set_timelimit(1.0);
 p->ff=fftwf_plan_r2r_2d(h,w,p->a,p->b,FFTW_REDFT10,FFTW_REDFT10,FFTW_PATIENT);
 p->ft=fftwf_plan_r2r_2d(h,w,p->a,p->b,FFTW_REDFT01,FFTW_REDFT01,FFTW_PATIENT);
 if(!p->ff||!p->ft)goto fail;
 for(int b=0;b<9;b++){
  if(!p->available[b]||b==0||b>=4)continue;
  double d2[2][1024],d3[2][1024];float x[1024],y[1024];
  for(int a=0;a<2;a++){int n=a?w:h;
   if(b==0){for(int k=0;k<n;k++){double norm=sjscale(4*n,k)*sqrt((k?2.:1.)/n);d2[a][k]=1./norm;d3[a][k]=1./norm;}}
   else if(b==2){for(int k=0;k<n;k++){double alpha=sqrt((k?2.:1.)/n);d2[a][k]=2./alpha;d3[a][k]=(k?2.:1.)/alpha;}}
   else{memset(x,0,(size_t)n*sizeof(float));x[0]=1;one(p,b,a,0,x,y);for(int k=0;k<n;k++)d2[a][k]=y[k]/(sqrt((k?2.:1.)/n)*cos(PI*k*.5/n));for(int j=0;j<n;j++){memset(x,0,(size_t)n*sizeof(float));x[j]=1;one(p,b,a,1,x,y);d3[a][j]=y[0]/(sqrt((j?2.:1.)/n)*cos(PI*j*.5/n));}}
  }
  for(int i=0;i<h;i++)for(int j=0;j<w;j++){size_t k=(size_t)i*w+j;double nf=1./(d2[0][i]*d2[1][j]),ni=1./(d3[0][i]*d3[1][j]);p->norm[b][k]=(float)nf;p->inv[b][k]=(float)ni;p->corr[b][k]=(float)(nf*ni);}
 }
 if(p->available[5]){float e[64]={0},z[64];e[0]=1;memcpy(z,e,sizeof(z));jpeg_fdct_float(z);for(int i=0;i<8;i++)for(int j=0;j<8;j++){double q=sqrt((i?2.:1.)/8)*cos(PI*i/16)*sqrt((j?2.:1.)/8)*cos(PI*j/16);p->norm[5][i*8+j]=(float)(q/z[i*8+j]);}}
 return p;
 fail:rect_free(p);return NULL;
}
static void raw(Plan*p,int b,int inverse,const float*x,float*y){
 if(b==2){fftwf_execute_r2r(inverse?p->ft:p->ff,(float*)x,y);return;}
 int h=p->h,w=p->w;
 for(int r=0;r<h;r++)one(p,b,1,inverse,x+(size_t)r*w,p->b+(size_t)r*w);
 vDSP_mtrans(p->b,1,p->c,1,w,h);
 for(int r=0;r<w;r++)one(p,b,0,inverse,p->c+(size_t)r*h,p->b+(size_t)r*h);
 vDSP_mtrans(p->b,1,y,1,h,w);
}
static void mult(const float*x,const float*n,float*y,size_t m){for(size_t k=0;k<m;k+=4)vst1q_f32(y+k,vmulq_f32(vld1q_f32(x+k),vld1q_f32(n+k)));}
int rect_apply(Plan*p,int b,int pad,int mode,int fma,const float*x,float*y){
 if(!p||!x||!y||b<0||b>8||mode<0||mode>2)return -1;
 if(!p->available[b])return -2;
 if(b==0)return bridct_plan_apply(p->bridct,(enum bridct_mode)mode,x,y);
 if(b==4)return jx_run(p->jxl,mode,x,y);
 if(b==5){if(mode)return -2;memcpy(y,x,64*sizeof(float));jpeg_fdct_float(y);mult(y,p->norm[5],y,64);return 0;}
 if(b>=6){int (*f)(int,int,int,const float*,float*,float*,size_t)=b==6?ooura_public_f1:b==7?ooura_neon_f1:ooura_trusted_f1;return f(p->h,b==6?0:1,mode,x,y,p->work,16*(size_t)p->h*(p->w+4)+8192);}
 if(mode==0){raw(p,b,0,x,p->a);mult(p->a,p->norm[b],y,p->m);}
 else if(mode==1){mult(x,p->inv[b],p->a,p->m);raw(p,b,1,p->a,y);}
 else{raw(p,b,0,x,p->a);mult(p->a,p->corr[b],p->a,p->m);raw(p,b,1,p->a,y);}
 return 0;
}
static volatile double sink;
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+1e-9*t.tv_nsec;}
double rect_time(Plan*p,int b,int pad,int mode,int fma,const float*pool,int pool_count,float*y,uint64_t reps){
 if(!p||pool_count<1||!reps)return -1;double s=0,start=now();for(uint64_t i=0;i<reps;i++){memcpy(p->copy,pool+(i%(uint64_t)pool_count)*p->m,p->m*sizeof(float));if(rect_apply(p,b,pad,mode,fma,p->copy,y))return -1;s+=y[i%p->m];}double dt=now()-start;sink=s;return isfinite(s)?dt:-1;
}

int rect_available(Plan*p,int backend){return p&&backend>=0&&backend<9?p->available[backend]:0;}

const char*rect_route(Plan*p){return p&&p->bridct?bridct_plan_route(p->bridct):"unsupported";}
void rect_print_fftw(Plan*p){fftwf_fprint_plan(p->ff,stderr);fputc(10,stderr);fftwf_fprint_plan(p->ft,stderr);fputc(10,stderr);}
