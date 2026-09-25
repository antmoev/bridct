/* Ooura-derived arithmetic. Original attribution/license in ATTRIBUTION.md. */
#include <stddef.h>
#if EXPLICIT_NEON
#include <arm_neon.h>
typedef float32x4_t T;
#else
typedef float T;
#endif
#define C8_1R   0.49039264020161522456f
#define C8_1I   0.09754516100806413392f
#define C8_2R   0.46193976625564337806f
#define C8_2I   0.19134171618254488586f
#define C8_3R   0.41573480615127261854f
#define C8_3I   0.27778511650980111237f
#define C8_4R   0.35355339059327376220f
#define W8_4R   0.70710678118654752440f
#define C16_1R   0.35185093438159561476f
#define C16_1I   0.03465429229977286565f
#define C16_2R   0.34675996133053686546f
#define C16_2I   0.06897484482073575308f
#define C16_3R   0.33832950029358816957f
#define C16_3I   0.10263113188058934529f
#define C16_4R   0.32664074121909413196f
#define C16_4I   0.13529902503654924610f
#define C16_5R   0.31180625324666780814f
#define C16_5I   0.16666391461943662432f
#define C16_6R   0.29396890060483967924f
#define C16_6I   0.19642373959677554532f
#define C16_7R   0.27330046675043937206f
#define C16_7I   0.22429189658565907106f
#define C16_8R   0.25f
#define W16_4R   0.92387953251128675613f
#define W16_4I   0.38268343236508977173f
#define W16_8R   0.70710678118654752440f
static __attribute__((always_inline)) inline void one_f8(const T*x,T*y){ T v[8];for(int i=0;i<8;i++)v[i]=x[i];
    T x0r, x0i, x1r, x1i, x2r, x2i, x3r, x3i;
    T xr, xi;
    


            x0r = v[0] + v[7];
            x1r = v[0] - v[7];
            x0i = v[2] + v[5];
            x1i = v[2] - v[5];
            x2r = v[4] + v[3];
            x3r = v[4] - v[3];
            x2i = v[6] + v[1];
            x3i = v[6] - v[1];
            xr = x0r + x2r;
            xi = x0i + x2i;
            v[0] = C8_4R * (xr + xi);
            v[4] = C8_4R * (xr - xi);
            xr = x0r - x2r;
            xi = x0i - x2i;
            v[2] = C8_2R * xr - C8_2I * xi;
            v[6] = C8_2R * xi + C8_2I * xr;
            xr = W8_4R * (x1i - x3i);
            x1i = W8_4R * (x1i + x3i);
            x3i = x1i - x3r;
            x1i += x3r;
            x3r = x1r - xr;
            x1r += xr;
            v[1] = C8_1R * x1r - C8_1I * x1i;
            v[7] = C8_1R * x1i + C8_1I * x1r;
            v[3] = C8_3R * x3r - C8_3I * x3i;
            v[5] = C8_3R * x3i + C8_3I * x3r;

for(int i=0;i<8;i++)y[i]=v[i];}
static __attribute__((always_inline)) inline void one_t8(const T*x,T*y){ T v[8];for(int i=0;i<8;i++)v[i]=x[i];
    T x0r, x0i, x1r, x1i, x2r, x2i, x3r, x3i;
    T xr, xi;
    


            x1r = C8_1R * v[1] + C8_1I * v[7];
            x1i = C8_1R * v[7] - C8_1I * v[1];
            x3r = C8_3R * v[3] + C8_3I * v[5];
            x3i = C8_3R * v[5] - C8_3I * v[3];
            xr = x1r - x3r;
            xi = x1i + x3i;
            x1r += x3r;
            x3i -= x1i;
            x1i = W8_4R * (xr + xi);
            x3r = W8_4R * (xr - xi);
            xr = C8_2R * v[2] + C8_2I * v[6];
            xi = C8_2R * v[6] - C8_2I * v[2];
            x0r = C8_4R * (v[0] + v[4]);
            x0i = C8_4R * (v[0] - v[4]);
            x2r = x0r - xr;
            x2i = x0i - xi;
            x0r += xr;
            x0i += xi;
            v[0] = x0r + x1r;
            v[7] = x0r - x1r;
            v[2] = x0i + x1i;
            v[5] = x0i - x1i;
            v[4] = x2r - x3i;
            v[3] = x2r + x3i;
            v[6] = x2i - x3r;
            v[1] = x2i + x3r;

for(int i=0;i<8;i++)y[i]=v[i];}
static __attribute__((always_inline)) inline void one_f16(const T*x,T*y){ T v[16];for(int i=0;i<16;i++)v[i]=x[i];
    T x0r, x0i, x1r, x1i, x2r, x2i, x3r, x3i;
    T x4r, x4i, x5r, x5i, x6r, x6i, x7r, x7i;
    T xr, xi;
    


            x4r = v[0] - v[15];
            xr = v[0] + v[15];
            x4i = v[8] - v[7];
            xi = v[8] + v[7];
            x0r = xr + xi;
            x0i = xr - xi;
            x5r = v[2] - v[13];
            xr = v[2] + v[13];
            x5i = v[10] - v[5];
            xi = v[10] + v[5];
            x1r = xr + xi;
            x1i = xr - xi;
            x6r = v[4] - v[11];
            xr = v[4] + v[11];
            x6i = v[12] - v[3];
            xi = v[12] + v[3];
            x2r = xr + xi;
            x2i = xr - xi;
            x7r = v[6] - v[9];
            xr = v[6] + v[9];
            x7i = v[14] - v[1];
            xi = v[14] + v[1];
            x3r = xr + xi;
            x3i = xr - xi;
            xr = x0r + x2r;
            xi = x1r + x3r;
            v[0] = C16_8R * (xr + xi);
            v[8] = C16_8R * (xr - xi);
            xr = x0r - x2r;
            xi = x1r - x3r;
            v[4] = C16_4R * xr - C16_4I * xi;
            v[12] = C16_4R * xi + C16_4I * xr;
            x0r = W16_8R * (x1i - x3i);
            x2r = W16_8R * (x1i + x3i);
            xr = x0i + x0r;
            xi = x2r + x2i;
            v[2] = C16_2R * xr - C16_2I * xi;
            v[14] = C16_2R * xi + C16_2I * xr;
            xr = x0i - x0r;
            xi = x2r - x2i;
            v[6] = C16_6R * xr - C16_6I * xi;
            v[10] = C16_6R * xi + C16_6I * xr;
            xr = W16_8R * (x6r - x6i);
            xi = W16_8R * (x6i + x6r);
            x6r = x4r - xr;
            x6i = x4i - xi;
            x4r += xr;
            x4i += xi;
            xr = W16_4I * x7r - W16_4R * x7i;
            xi = W16_4I * x7i + W16_4R * x7r;
            x7r = W16_4R * x5r - W16_4I * x5i;
            x7i = W16_4R * x5i + W16_4I * x5r;
            x5r = x7r + xr;
            x5i = x7i + xi;
            x7r -= xr;
            x7i -= xi;
            xr = x4r + x5r;
            xi = x5i + x4i;
            v[1] = C16_1R * xr - C16_1I * xi;
            v[15] = C16_1R * xi + C16_1I * xr;
            xr = x4r - x5r;
            xi = x5i - x4i;
            v[7] = C16_7R * xr - C16_7I * xi;
            v[9] = C16_7R * xi + C16_7I * xr;
            xr = x6r - x7i;
            xi = x7r + x6i;
            v[5] = C16_5R * xr - C16_5I * xi;
            v[11] = C16_5R * xi + C16_5I * xr;
            xr = x6r + x7i;
            xi = x7r - x6i;
            v[3] = C16_3R * xr - C16_3I * xi;
            v[13] = C16_3R * xi + C16_3I * xr;

for(int i=0;i<16;i++)y[i]=v[i];}
static __attribute__((always_inline)) inline void one_t16(const T*x,T*y){ T v[16];for(int i=0;i<16;i++)v[i]=x[i];
    T x0r, x0i, x1r, x1i, x2r, x2i, x3r, x3i;
    T x4r, x4i, x5r, x5i, x6r, x6i, x7r, x7i;
    T xr, xi;
    


            x5r = C16_1R * v[1] + C16_1I * v[15];
            x5i = C16_1R * v[15] - C16_1I * v[1];
            xr = C16_7R * v[7] + C16_7I * v[9];
            xi = C16_7R * v[9] - C16_7I * v[7];
            x4r = x5r + xr;
            x4i = x5i - xi;
            x5r -= xr;
            x5i += xi;
            x7r = C16_5R * v[5] + C16_5I * v[11];
            x7i = C16_5R * v[11] - C16_5I * v[5];
            xr = C16_3R * v[3] + C16_3I * v[13];
            xi = C16_3R * v[13] - C16_3I * v[3];
            x6r = x7r + xr;
            x6i = x7i - xi;
            x7r -= xr;
            x7i += xi;
            xr = x4r - x6r;
            xi = x4i - x6i;
            x4r += x6r;
            x4i += x6i;
            x6r = W16_8R * (xi + xr);
            x6i = W16_8R * (xi - xr);
            xr = x5r + x7i;
            xi = x5i - x7r;
            x5r -= x7i;
            x5i += x7r;
            x7r = W16_4I * x5r + W16_4R * x5i;
            x7i = W16_4I * x5i - W16_4R * x5r;
            x5r = W16_4R * xr + W16_4I * xi;
            x5i = W16_4R * xi - W16_4I * xr;
            xr = C16_4R * v[4] + C16_4I * v[12];
            xi = C16_4R * v[12] - C16_4I * v[4];
            x2r = C16_8R * (v[0] + v[8]);
            x3r = C16_8R * (v[0] - v[8]);
            x0r = x2r + xr;
            x1r = x3r + xi;
            x2r -= xr;
            x3r -= xi;
            x0i = C16_2R * v[2] + C16_2I * v[14];
            x2i = C16_2R * v[14] - C16_2I * v[2];
            x1i = C16_6R * v[6] + C16_6I * v[10];
            x3i = C16_6R * v[10] - C16_6I * v[6];
            xr = x0i - x1i;
            xi = x2i + x3i;
            x0i += x1i;
            x2i -= x3i;
            x1i = W16_8R * (xi + xr);
            x3i = W16_8R * (xi - xr);
            xr = x0r + x0i;
            xi = x0r - x0i;
            v[0] = xr + x4r;
            v[15] = xr - x4r;
            v[8] = xi + x4i;
            v[7] = xi - x4i;
            xr = x1r + x1i;
            xi = x1r - x1i;
            v[2] = xr + x5r;
            v[13] = xr - x5r;
            v[10] = xi + x5i;
            v[5] = xi - x5i;
            xr = x2r + x2i;
            xi = x2r - x2i;
            v[4] = xr + x6r;
            v[11] = xr - x6r;
            v[12] = xi + x6i;
            v[3] = xi - x6i;
            xr = x3r + x3i;
            xi = x3r - x3i;
            v[6] = xr + x7r;
            v[9] = xr - x7r;
            v[14] = xi + x7i;
            v[1] = xi - x7i;

for(int i=0;i<16;i++)y[i]=v[i];}

static inline void transpose(const float *restrict x,float *restrict y,int n){
#if EXPLICIT_NEON
 for(int i=0;i<n;i+=4)for(int j=0;j<n;j+=4){
  float32x4_t a=vld1q_f32(x+i*n+j),b=vld1q_f32(x+(i+1)*n+j),c=vld1q_f32(x+(i+2)*n+j),d=vld1q_f32(x+(i+3)*n+j);
  float32x4x2_t u=vtrnq_f32(a,b),v=vtrnq_f32(c,d);
  vst1q_f32(y+j*n+i,vcombine_f32(vget_low_f32(u.val[0]),vget_low_f32(v.val[0])));
  vst1q_f32(y+(j+1)*n+i,vcombine_f32(vget_low_f32(u.val[1]),vget_low_f32(v.val[1])));
  vst1q_f32(y+(j+2)*n+i,vcombine_f32(vget_high_f32(u.val[0]),vget_high_f32(v.val[0])));
  vst1q_f32(y+(j+3)*n+i,vcombine_f32(vget_high_f32(u.val[1]),vget_high_f32(v.val[1])));
 }
#else
 for(int i=0;i<n;i++)for(int j=0;j<n;j++)y[j*n+i]=x[i*n+j];
#endif
}

static inline void vertical_f8(const float *restrict x,float *restrict y){
#if EXPLICIT_NEON
 for(int col=0;col<8;col+=4){T u[8],v[8];for(int k=0;k<8;k++)u[k]=vld1q_f32(x+k*8+col);one_f8(u,v);for(int k=0;k<8;k++)vst1q_f32(y+k*8+col,v[k]);}
#else
 for(int col=0;col<8;col++){T u[8],v[8];for(int k=0;k<8;k++)u[k]=x[k*8+col];one_f8(u,v);for(int k=0;k<8;k++)y[k*8+col]=v[k];}
#endif
}
static inline void half_f8(const float*x,float*y,float*a,float*b){vertical_f8(x,a);transpose(a,b,8);vertical_f8(b,y);}

static inline void vertical_t8(const float *restrict x,float *restrict y){
#if EXPLICIT_NEON
 for(int col=0;col<8;col+=4){T u[8],v[8];for(int k=0;k<8;k++)u[k]=vld1q_f32(x+k*8+col);one_t8(u,v);for(int k=0;k<8;k++)vst1q_f32(y+k*8+col,v[k]);}
#else
 for(int col=0;col<8;col++){T u[8],v[8];for(int k=0;k<8;k++)u[k]=x[k*8+col];one_t8(u,v);for(int k=0;k<8;k++)y[k*8+col]=v[k];}
#endif
}
static inline void half_t8(const float*x,float*y,float*a,float*b){vertical_t8(x,a);transpose(a,b,8);vertical_t8(b,y);}

static inline void vertical_f16(const float *restrict x,float *restrict y){
#if EXPLICIT_NEON
 for(int col=0;col<16;col+=4){T u[16],v[16];for(int k=0;k<16;k++)u[k]=vld1q_f32(x+k*16+col);one_f16(u,v);for(int k=0;k<16;k++)vst1q_f32(y+k*16+col,v[k]);}
#else
 for(int col=0;col<16;col++){T u[16],v[16];for(int k=0;k<16;k++)u[k]=x[k*16+col];one_f16(u,v);for(int k=0;k<16;k++)y[k*16+col]=v[k];}
#endif
}
static inline void half_f16(const float*x,float*y,float*a,float*b){vertical_f16(x,a);transpose(a,b,16);vertical_f16(b,y);}

static inline void vertical_t16(const float *restrict x,float *restrict y){
#if EXPLICIT_NEON
 for(int col=0;col<16;col+=4){T u[16],v[16];for(int k=0;k<16;k++)u[k]=vld1q_f32(x+k*16+col);one_t16(u,v);for(int k=0;k<16;k++)vst1q_f32(y+k*16+col,v[k]);}
#else
 for(int col=0;col<16;col++){T u[16],v[16];for(int k=0;k<16;k++)u[k]=x[k*16+col];one_t16(u,v);for(int k=0;k<16;k++)y[k*16+col]=v[k];}
#endif
}
static inline void half_t16(const float*x,float*y,float*a,float*b){vertical_t16(x,a);transpose(a,b,16);vertical_t16(b,y);}

int NAME(int n,int retain,int mode,const float*x,float*y,float*w,size_t count){if(!x||!y||!w||(n!=8&&n!=16)||retain<0||retain>1||mode<0||mode>2)return -1;size_t m=(size_t)n*n;if(count<4*m)return -2;float*a=w,*b=a+m,*c=b+m,*d=c+m;
if(n==8){if(mode==0){half_f8(x,a,b,c);transpose(a,y,8);}else if(mode==1){half_t8(x,a,b,c);transpose(a,y,8);}else if(retain){half_f8(x,a,b,c);half_t8(a,y,b,c);}else{half_f8(x,a,b,c);transpose(a,b,8);half_t8(b,a,c,d);transpose(a,y,8);}}
if(n==16){if(mode==0){half_f16(x,a,b,c);transpose(a,y,16);}else if(mode==1){half_t16(x,a,b,c);transpose(a,y,16);}else if(retain){half_f16(x,a,b,c);half_t16(a,y,b,c);}else{half_f16(x,a,b,c);transpose(a,b,16);half_t16(b,a,c,d);transpose(a,y,16);}}
return 0;}
