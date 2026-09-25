"""Verify every supported height/width pair against float64 SciPy, without timing."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import argparse,ctypes as C,csv,hashlib,json
import numpy as np
from scipy.fft import dctn,idctn
R=Path(__file__).resolve().parents[1];F=C.POINTER(C.c_float)
def ptr(x):return x.ctypes.data_as(F)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,default=R/'build/libbridct.dylib');ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
 if args.output.exists():ap.error('Choose a new directory')
 args.output.mkdir(parents=True)
 lib=C.CDLL(str(args.library.resolve()))
 create=lib.bridct_plan_create;create.argtypes=[C.c_int,C.c_int];create.restype=C.c_void_p
 destroy=lib.bridct_plan_destroy;destroy.argtypes=[C.c_void_p]
 apply=lib.bridct_plan_apply;apply.argtypes=[C.c_void_p,C.c_int,F,F];apply.restype=C.c_int
 route=lib.bridct_plan_route;route.argtypes=[C.c_void_p];route.restype=C.c_char_p
 raw=lib.bridct_apply;raw.argtypes=[C.c_int,C.c_int,F,F,F,C.c_size_t]
 need=lib.bridct_workspace_floats;need.argtypes=[C.c_int];need.restype=C.c_size_t
 rng=np.random.default_rng(202609201);rows=[];routes={}
 for h in [8,16,32,64,128,256,512,1024]:
  for w in [8,16,32,64,128,256,512,1024]:
   p=create(h,w);assert p;routes[f'{h}x{w}']=route(p).decode()
   random=rng.normal(size=(h,w)).astype(np.float32)
   alt=np.where(np.indices((h,w)).sum(axis=0)%2,1.,-1.).astype(np.float32)
   impulse=np.zeros((h,w),np.float32);impulse[h//3,w//2]=1
   cases=[('zero',np.zeros_like(impulse)),('impulse',impulse),('random',random),('neighbors',(1+alt*2**-23).astype(np.float32)),('tiny',random*2.**-70),('large',random*2.**50)]
   count=need(h) if h==w and h<=256 else 0
   scratch=np.zeros(count,np.float32) if count else None
   for name,x in cases:
    xd=x.astype(np.float64);norm=float(np.linalg.norm(xd));before=x.view(np.uint32).copy()
    yr=np.full(h*w+8,12345,np.float32);y=yr[4:-4].reshape(h,w)
    for mode in range(3):
     rc=apply(p,mode,ptr(x),ptr(y));ref=dctn(xd,type=2,norm='ortho') if mode==0 else idctn(xd,type=2,norm='ortho') if mode==1 else xd
     err=float(np.linalg.norm(y.astype(np.float64)-ref));err=err/norm if norm else err
     gate=bool(rc==0 and np.isfinite(y).all() and err<2e-5 and np.array_equal(x.view(np.uint32),before) and np.all(yr[:4]==12345) and np.all(yr[-4:]==12345))
     same=None;legacy_error=None;bitwise_required=bool(count and h<=128)
     if count:
      other=np.empty_like(y);assert raw(h,mode,ptr(x),ptr(other),ptr(scratch),count)==0;same=bool(np.array_equal(y.view(np.uint32),other.view(np.uint32)))
      legacy_error=float(np.linalg.norm(other.astype(np.float64)-ref));legacy_error=legacy_error/norm if norm else legacy_error
      gate=gate and bool(np.isfinite(other).all() and legacy_error<2e-5) and (same or not bitwise_required)
     rows.append(dict(h=h,w=w,case=name,mode=mode,error=err,pass_check=gate,square_dispatch_bitwise=same,square_dispatch_bitwise_required=bitwise_required,legacy_error=legacy_error))
   destroy(p)
 assert not create(32,26) and not create(-8,32) and not create(2048,8)
 with (args.output/'checks.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
 result={'status':'PASS' if all(r['pass_check'] for r in rows) else 'FAIL','shapes':64,'directions':len(rows),'max_input_relative_error':max(r['error'] for r in rows),'square_dispatch_bitwise_checks':sum(r['square_dispatch_bitwise'] is True for r in rows),'required_square_dispatch_bitwise_checks':sum(r['square_dispatch_bitwise_required'] for r in rows),'routes':routes,'lib_sha256':hashlib.sha256(args.library.read_bytes()).hexdigest(),'scope':'Numerical validation across all supported shapes; no timings. Plan and legacy calls are both checked against float64 at square sizes. Bit identity is required through 128; at 256 it is diagnostic because the runtime plan may select a different validated backend.'}
 (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='routes'},indent=2));assert result['status']=='PASS'
if __name__=='__main__':main()
