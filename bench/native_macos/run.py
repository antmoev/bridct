"""Validate first, then run one matched native C timing session on explicit request."""
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
from pathlib import Path
import argparse,ctypes as C,csv,hashlib,json,math,platform,random,subprocess,time
import numpy as np
from scipy.fft import dctn,idctn
R=Path(__file__).resolve().parent
SHAPES=[(n,n) for n in (8,16,32,64,128,256,512,1024)]+[(128,256),(256,128),(256,512),(512,256),(512,1024),(1024,512),(128,1024),(1024,128),(16,32),(32,16),(8,64),(64,8),(32,26),(26,32)]
LABEL=['bridct_dev7_plan','apple_vdsp','fftw_patient_1s','ooura_general_float','libjxl_highway','libjpeg_turbo_float','ooura_specialized_float','ooura_neon','ooura_neon_trusted']
FP=C.POINTER(C.c_float)
def ptr(x):return x.ctypes.data_as(FP)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
lib=C.CDLL(str(R/'build/native.dylib'))
lib.rect_plan.argtypes=[C.c_int,C.c_int];lib.rect_plan.restype=C.c_void_p
lib.rect_free.argtypes=[C.c_void_p]
lib.rect_available.argtypes=[C.c_void_p,C.c_int];lib.rect_available.restype=C.c_int
lib.rect_route.argtypes=[C.c_void_p];lib.rect_route.restype=C.c_char_p
lib.rect_print_fftw.argtypes=[C.c_void_p]
lib.rect_apply.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_int,FP,FP];lib.rect_apply.restype=C.c_int
lib.rect_time.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_int,FP,C.c_int,FP,C.c_uint64];lib.rect_time.restype=C.c_double
def arms(p):return [(b,m) for b in range(9) if lib.rect_available(p,b) for m in ([0] if b==5 else range(3))]
def fixtures(h,w):
 rng=np.random.default_rng(90820+h*1024+w);rr,cc=np.indices((h,w))
 yield 'zero',np.zeros((h,w),np.float32)
 yield 'random',rng.standard_normal((h,w)).astype(np.float32)
 a=np.zeros((h,w),np.float32);a[h//3,w//5]=1;yield 'impulse',a
 yield 'constant',np.full((h,w),-.7,np.float32)
 yield 'alternating',np.where((rr+cc)%2,1.,-1.).astype(np.float32)
 yield 'offset_ulp',(np.float32(1)+((rr+cc)%3-1)*np.float32(2**-23)).astype(np.float32)
 yield 'tiny',(rng.standard_normal((h,w))*2**-70).astype(np.float32)
 yield 'large',(rng.standard_normal((h,w))*2**50).astype(np.float32)
def validate(out):
 out.mkdir(exist_ok=False);rows=[];availability=[];fails=[]
 for h,w in SHAPES:
  p=lib.rect_plan(h,w);assert p,(h,w)
  availability.extend(dict(h=h,w=w,backend=b,name=LABEL[b],available=bool(lib.rect_available(p,b)),bridct_route=lib.rect_route(p).decode()) for b in range(9))
  for case,x in fixtures(h,w):
   before=x.copy();xf=x.astype(np.float64);refs=[dctn(xf,norm='ortho',workers=1),idctn(xf,norm='ortho',workers=1),xf]
   if max(h,w)<=64:
    def q(n):
     a=np.cos(np.pi*np.arange(n)[:,None]*(np.arange(n)[None,:]+.5)/n)*np.sqrt(2/n);a[0]/=np.sqrt(2);return a
    for mode,z in enumerate([q(h)@xf@q(w).T,q(h).T@xf@q(w)]):
     assert np.max(np.abs(z-refs[mode]))<=1e-12*max(float(np.max(np.abs(xf))),1e-300)*h*w
   den=float(np.linalg.norm(xf)) or 1.
   for b,m in arms(p):
    raw=np.full(h*w+32,np.float32(12345));y=raw[16:-16].reshape(h,w)
    rc=lib.rect_apply(p,b,0,m,0,ptr(x),ptr(y));err=float(np.linalg.norm(y.astype(np.float64)-refs[m]))/den
    ok=rc==0 and np.isfinite(y).all() and err<=2e-5 and np.array_equal(x,before) and np.all(raw[:16]==12345) and np.all(raw[-16:]==12345)
    row=dict(h=h,w=w,case=case,backend=b,name=LABEL[b],mode=m,error=err,passed=bool(ok));rows.append(row)
    if not ok:fails.append(row)
  lib.rect_free(p);print('validated',h,w,'checks',len(rows),'failures',len(fails),flush=True)
 with (out/'checks.csv').open('w') as f:
  wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
 save(out/'availability.json',availability)
 save(out/'verification.json',dict(status='PASS' if not fails else 'FAIL',checks=len(rows),max_error=max(x['error'] for x in rows),threshold=2e-5,failures=fails,library_sha256=sha(R/'build/native.dylib'),runner_sha256=sha(Path(__file__)),protocol_sha256=sha(R/'PROTOCOL.md'),oracle='SciPy PocketFFT float64 plus explicit float64 matrices for axes <=64'))
 if fails:raise RuntimeError(f'{len(fails)} numerical checks failed')
def guard(out,tag):
 text=subprocess.check_output(['ps','-axo','pid,ppid,pcpu,comm'],text=True);(out/f'processes-{tag}.txt').write_text(text)
 conflicts=[s for s in text.splitlines()[1:] if s.split()[-1].split('/')[-1] in ('clang','clang++','cc1','gcc','g++','test_runner','test_api','bench')]
 if conflicts:raise RuntimeError('Concurrent compute: '+repr(conflicts))
def timing(out,session,verification):
 v=json.loads((verification/'verification.json').read_text());assert v['status']=='PASS' and v['library_sha256']==sha(R/'build/native.dylib') and v['runner_sha256']==sha(Path(__file__)) and v['protocol_sha256']==sha(R/'PROTOCOL.md')
 out.mkdir(exist_ok=False);guard(out,'start');plans={};pools={};outputs={};configs=[];rng=np.random.default_rng(72026)
 for h,w in SHAPES:
  p=lib.rect_plan(h,w);assert p;plans[h,w]=p;lib.rect_print_fftw(p)
  pools[h,w]=rng.standard_normal((4,h,w)).astype(np.float32);outputs[h,w]=np.empty((h,w),np.float32)
  configs.extend((h,w,b,m) for b,m in arms(p))
 meta=dict(status='RUNNING',session=session,shapes=SHAPES,arms=len(configs),blocks=21,target_seconds=.03,pool=4,array_calls_per_iteration=1,units='ns per complete array',layout='natural row-major',normalization='orthonormal',modes=['forward','inverse','identity_roundtrip'],setup='excluded; FFTW PATIENT capped at one second per plan',copy='common input copy included, all wrapper copies and normalization included',overhead_subtraction=False,library_sha256=sha(R/'build/native.dylib'),runner_sha256=sha(Path(__file__)),protocol_sha256=sha(R/'PROTOCOL.md'),platform=platform.platform(),machine=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),start_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),routes={f'{h}x{w}':lib.rect_route(p).decode() for (h,w),p in plans.items()})
 save(out/'manifest.json',meta)
 def timed(a,n):
  h,w,b,m=a;t=lib.rect_time(plans[h,w],b,0,m,0,ptr(pools[h,w]),4,ptr(outputs[h,w]),n);
  if not math.isfinite(t) or t<0:raise RuntimeError(f"Invalid timer result {t} for {a}, iterations={n}")
  return t
 try:
  counts={};guard(out,'calibration')
  for a in configs:
   n=1;timed(a,4)
   while timed(a,n)<.03:
    n*=2
    if n>2**40:raise RuntimeError(f"Calibration exhausted for {a}")
   counts[a]=n
  save(out/'calibration.json',[dict(h=a[0],w=a[1],backend=a[2],mode=a[3],iterations=n) for a,n in counts.items()])
  rr=random.Random(900+session)
  with (out/'timing.csv').open('w') as f:
   wr=csv.writer(f);wr.writerow(['h','w','backend','name','mode','block','order','iterations','seconds','ns_per_array'])
   for block in range(21):
    guard(out,f'block-{block}');order=configs.copy();rr.shuffle(order)
    for rank,a in enumerate(order):
     t=timed(a,counts[a]);assert t>0,(a,counts[a],t);wr.writerow([a[0],a[1],a[2],LABEL[a[2]],a[3],block,rank,counts[a],t,t*1e9/counts[a]])
    f.flush();print('block',block+1,'/21',flush=True)
  meta.update(status='COMPLETE',rows=len(configs)*21,timing_sha256=sha(out/'timing.csv'))
 except Exception as e:meta.update(status='FAILED',error=repr(e));raise
 finally:
  for p in plans.values():lib.rect_free(p)
  meta['end_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());save(out/'manifest.json',meta)
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['validate','timing']);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--session',type=int,default=1);ap.add_argument('--verification',type=Path,default=R/'validation');a=ap.parse_args()
 if a.action=='validate':validate(a.output)
 else:timing(a.output,a.session,a.verification)
