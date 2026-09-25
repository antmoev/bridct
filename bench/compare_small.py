"""Compare the current C kernels/API with attributed Ooura controls."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import argparse,csv,ctypes as C,hashlib,json,math,platform,random,subprocess,time,sys
from build_small_controls import build
import numpy as np
from scipy.fft import dctn,idctn
R=Path(__file__).resolve().parent
FP=C.POINTER(C.c_float)
Kernel=C.CFUNCTYPE(C.c_int,C.c_int,C.c_int,C.c_int,FP,FP,FP,C.c_size_t)

def ptr(x):return x.ctypes.data_as(FP)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,data):path.write_text(json.dumps(data,indent=2)+'\n')
def guard(out,tag):
    if os.name=='nt':
        proc=subprocess.run(['tasklist','/FO','CSV'],capture_output=True,text=True,check=True)
        (out/f'processes-{tag}.txt').write_text(proc.stdout)
        return
    proc=subprocess.run(['ps','-axo','pid,ppid,pcpu,comm'],capture_output=True,text=True,check=True)
    (out/f'processes-{tag}.txt').write_text(proc.stdout)
    conflicts=[]
    for line in proc.stdout.splitlines()[1:]:
        name=line.split()[-1].split('/')[-1]
        if name in ('clang','cc1','clang++','gcc','g++','bench','check_memory','test_runner'):
            conflicts.append(line)
    if conflicts:raise RuntimeError('Concurrent compute: '+repr(conflicts))

def main():
    if sys.flags.optimize:
        raise RuntimeError("Run without Python -O/PYTHONOPTIMIZE so validation checks remain active.")
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--session',type=int,required=True)
    ap.add_argument('--blocks',type=int,default=7);ap.add_argument('--ms',type=float,default=10)
    ap.add_argument('--batches',type=int,nargs='+',default=[1,4]);ap.add_argument('--select',type=Path)
    ap.add_argument('--validate-only',action='store_true')
    ap.add_argument('--library',type=Path,default=R.parent/'build/libbridct.a')
    ap.add_argument('--cc',default=os.environ.get('CC','/Library/Developer/CommandLineTools/usr/bin/clang' if sys.platform=='darwin' else 'clang'))
    ap.add_argument('--extra-flags',default='')
    ap.add_argument('--control-build',type=Path,help='Reuse an existing control build without recompilation')
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    if a.blocks<1 or a.ms<=0 or any(b<1 for b in a.batches):ap.error('positive blocks, duration and batches required')
    suffix='.dll' if os.name=='nt' else '.dylib' if sys.platform=='darwin' else '.so'
    build_dir=a.control_build.resolve() if a.control_build else a.output.resolve()/'build'
    if not a.control_build:build(build_dir,a.library.resolve(),a.cc,a.extra_flags)

    paths={name:build_dir/(name+suffix) for name in ('controls','kernel_timer')}
    libs={name:C.CDLL(str(path)) for name,path in paths.items()}
    timer=libs['kernel_timer'].kernel_time
    timer.argtypes=[Kernel,C.c_int,C.c_int,C.c_int,FP,FP,FP,C.c_size_t,C.c_int,C.c_uint64];timer.restype=C.c_double
    arms=[]
    for name in ('baseline_f1','selected_kernel','selected_api','ooura_public_f1','ooura_scalar_f1','ooura_auto_f1','ooura_neon_f1','ooura_trusted_f1'):
        kind='current_api' if name=='selected_api' else 'four_lane_fallback_kernel' if name=='selected_kernel' else 'baseline' if name=='baseline_f1' else 'ooura_public_float' if name=='ooura_public_f1' else 'ooura_local_adaptation'
        arms.append(dict(name=name,kind=kind,func=Kernel((name,libs['controls'])),variant=1 if name in ('ooura_neon_f1','ooura_trusted_f1') else 0,sizes=[8,16]))
    metadata={'status':'STARTED','session':a.session,'blocks':a.blocks,'calibration_ms':a.ms,'batches':a.batches,'host':platform.platform(),'started':time.time(),'hashes':{name:sha(path) for name,path in paths.items()},'build_manifest':json.loads((build_dir/'build.json').read_text()),'architecture':platform.machine(),'cpu':platform.processor(),'isolation':'Process inventory only; shared CI CPU isolation is not guaranteed','runner_sha256':sha(__file__),'arms':[{k:v for k,v in arm.items() if k!='func'} for arm in arms],'units':'ns per complete array; C loop; no overhead subtraction'}
    save(a.output/'manifest.json',metadata)
    selected=json.loads(a.select.read_text()) if a.select else None
    configs=[];checks=[];rng=np.random.default_rng(21092026)
    try:
        guard(a.output,'start')
        for n in (8,16):
            for b in a.batches:
                x=rng.normal(size=(b,n,n)).astype(np.float32);y=np.empty_like(x)
                ws=np.full(16*n*n+8,12345,dtype=np.float32);work=ws[4:-4]
                cases={'random':x,'constant':np.ones_like(x),'neighbors':(1+np.where(np.indices(x.shape).sum(axis=0)%2,1.,-1.)*2**-23).astype(np.float32)}
                impulse=np.zeros_like(x);impulse[:,n//3,n//2]=1;cases['impulse']=impulse
                for mode in range(3):
                    for arm in arms:
                        if n not in arm['sizes']:continue
                        if selected and arm['name'] not in selected[f'{n}:{b}:{mode}']:continue
                        for label,case in cases.items():
                            before=case.copy();out=np.full(b*n*n+8,12345,dtype=np.float32);dst=out[4:-4].reshape(case.shape)
                            for i in range(b):
                                assert arm['func'](n,arm['variant'],mode,ptr(case[i]),ptr(dst[i]),ptr(work),len(work))==0
                            xd=case.astype(np.float64)
                            ref=xd if mode==2 else (dctn if mode==0 else idctn)(xd,type=2,norm='ortho',axes=(-2,-1),workers=1)
                            error=float(np.linalg.norm(dst.astype(np.float64)-ref)/np.linalg.norm(xd))
                            passed=bool(error<=2e-5 and np.isfinite(dst).all() and np.array_equal(case,before) and np.all(out[:4]==12345) and np.all(out[-4:]==12345) and np.all(ws[:4]==12345) and np.all(ws[-4:]==12345))
                            checks.append(dict(n=n,b=b,mode=mode,arm=arm['name'],case=label,error=error,passed=passed))
                            if not passed:raise AssertionError(checks[-1])
                        configs.append(dict(n=n,b=b,mode=mode,arm=arm,x=x,y=y,work=work))
        save(a.output/'validation.json',checks)
        print('VALIDATED',len(checks),'directions',flush=True)
        if a.validate_only:metadata['status']='VALIDATED';return
        def timed(c,reps):
            ns=timer(c['arm']['func'],c['n'],c['arm']['variant'],c['mode'],ptr(c['x']),ptr(c['y']),ptr(c['work']),len(c['work']),c['b'],reps)
            if not math.isfinite(ns) or ns<0:raise RuntimeError('invalid elapsed')
            return ns
        guard(a.output,'calibration')
        for c in configs:
            timed(c,4);r=1
            while timed(c,r)<a.ms*1e6:
                r*=2
                if r>2**32:raise RuntimeError('calibration exhausted')
            c['repeats']=r
        save(a.output/'calibration.json',[{'n':c['n'],'b':c['b'],'mode':c['mode'],'arm':c['arm']['name'],'repeats':c['repeats']} for c in configs])
        fields=['session','block','order','n','b','mode','arm','kind','repeats','elapsed_ns','ns_array','checksum']
        with (a.output/'timing.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
            order=list(range(len(configs)));randomizer=random.Random(41000+a.session)
            for block in range(a.blocks):
                guard(a.output,f'b{block}');randomizer.shuffle(order)
                for rank,i in enumerate(order):
                    c=configs[i];elapsed=timed(c,c['repeats'])
                    assert elapsed>0 and np.isfinite(c['y']).all()
                    writer.writerow(dict(session=a.session,block=block,order=rank,n=c['n'],b=c['b'],mode=c['mode'],arm=c['arm']['name'],kind=c['arm']['kind'],repeats=c['repeats'],elapsed_ns=elapsed,ns_array=elapsed/c['repeats']/c['b'],checksum=float(c['y'].sum(dtype=np.float64))))
                f.flush();print('BLOCK',block+1,'/',a.blocks,flush=True)
        metadata.update(status='COMPLETE_EXPLORATORY',rows=len(configs)*a.blocks)
    except Exception as e:metadata.update(status='FAILED',error=repr(e));save(a.output/'validation.json',checks);raise
    finally:metadata['finished']=time.time();save(a.output/'manifest.json',metadata)

if __name__=='__main__':main()
