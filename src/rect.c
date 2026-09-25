/* BRiDCT rectangular extension: unchanged blocked 1D cores; independent axis lengths. */
#include <string.h>
#include "rect_generated.inc"
#include "rect_generated_meta.h"
static void vertical(int h,int w,int s,int inv,const float*x,float*y,T*ws){
 for(int c=0;c<w;c+=4)col(h,inv,x+c,y+c,ws,s);
}
static void bands(int h,int w,int s,int so,int inv,const float*x,float*y,const float*norm,T*work){
 T*u=work,*v=u+w,*ws=v+w;
 for(int r=0;r<h;r+=4){
  for(int c=0;c<w;c+=4){float32x4x4_t q;for(int k=0;k<4;k++)q.val[k]=vld1q_f32(x+(size_t)(r+k)*s+c);vst4q_f32((float*)(u+c),q);}
  col(w,inv,(const float*)u,(float*)v,ws,4);
  for(int c=0;c<w;c+=4){float32x4x4_t q=vld4q_f32((const float*)(v+c));for(int k=0;k<4;k++){T t=q.val[k];if(norm)t=vmulq_f32(t,vld1q_f32(norm+(size_t)(r+k)*w+c));vst1q_f32(y+(size_t)(r+k)*so+c,t);}}
 }
}
int NAME(int h,int w,int pad,int mode,const float*x,float*y,const float*norm,const float*corr,float*work){
 if((h<8||h>1024||(h&(h-1)))||(w<8||w>1024||(w&(w-1)))||(pad!=0&&pad!=4)||mode<0||mode>2)return -1;
 int s=w+pad;size_t m=(size_t)h*s;float*a=work,*b=a+m;T*ws=(T*)(b+m);
 for(int r=0;r<h;r++)for(int c=0;c<w;c+=4){T t=vld1q_f32(x+(size_t)r*w+c);if(mode==1)t=vmulq_f32(t,vld1q_f32(norm+(size_t)r*w+c));vst1q_f32(a+(size_t)r*s+c,t);}
 if(mode==0){vertical(h,w,s,0,a,b,ws);bands(h,w,s,w,0,b,y,norm,ws);}
 else{if(mode==2){vertical(h,w,s,0,a,b,ws);bands(h,w,s,s,0,b,a,corr,ws);}bands(h,w,s,s,1,a,b,NULL,ws);vertical(h,w,s,1,b,a,ws);for(int r=0;r<h;r++)memcpy(y+(size_t)r*w,a+(size_t)r*s,(size_t)w*sizeof(float));}
 return 0;
}
