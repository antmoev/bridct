"""Deterministic float32 adversarial DCT test data. No training or optimization data."""
from pathlib import Path
import hashlib, io, json, zipfile
import numpy as np

VERSION = 'dct-adversarial-v1'
SEEDS = (910193, 2718281, 3141593, 1618033)
SIZES = (8, 16, 32, 64, 128, 256)

def matrix(n):
    k = np.arange(n, dtype=np.float64)
    return np.cos(np.pi*k[:, None]*(k[None, :]+.5)/n)*np.sqrt(np.where(k == 0, 1., 2.)/n)[:, None]

def cases(n):
    result = []
    r, c = np.indices((n,n))
    checker = np.where((r+c)%2, -1., 1.)
    def put(name, x, domain='core', seed=None):
        x = np.broadcast_to(x, (n,n)).astype('<f4').copy()
        result.append((dict(id=f'n{n}_{name}', N=n, family=name.split('__')[0], domain=domain, seed=seed,
                            sha256=hashlib.sha256(x.tobytes(order='C')).hexdigest()), x))
    put('zero', 0.)
    put('signed_zero', np.copysign(np.zeros((n,n)), checker))
    for exponent in (-100,-30,0,30,90):
        a = np.float32(2.**exponent)
        put(f'constant__e{exponent}', a)
        put(f'negative_constant__e{exponent}', -a)
        put(f'alternating__e{exponent}', a*checker)
        put(f'row_stripes__e{exponent}', a*np.where(r%2,-1,1))
    for exponent in (-70,0,70):
        a = np.float32(2.**exponent)
        b = np.nextafter(a, np.float32(np.inf))
        put(f'adjacent_positive__e{exponent}', np.where((r+2*c)%3, a, b))
        put(f'adjacent_negative__e{exponent}', -np.where((r+2*c)%3, a, b))
        put(f'near_opposites__e{exponent}', np.where((r+c)%2, -a, b))
        # Perturbations are created with representable ULPs, not lost in input conversion.
        ulp = np.float64(b)-np.float64(a)
        put(f'offset_ulp__e{exponent}', np.float64(a)+ulp*((3*r+5*c)%17-8))
    for (rr,cc) in ((0,0),(n-1,n-1),(n//2,n//3),(1,n-2)):
        x = np.zeros((n,n)); x[rr,cc] = 1.
        put(f'impulse__r{rr}_c{cc}', x)
    x=np.zeros((n,n)); x[1,2]=1.; x[n-2,n-1]=-np.nextafter(np.float32(1.),np.float32(0.))
    put('sparse_cancellation', x)
    q=matrix(n)
    for k,l in ((0,1),(1,0),(1,2),(n//2,n//3),(n-1,n-2)):
        put(f'spatial_mode__k{k}_l{l}', np.outer(q[k],q[l]))
        x=np.zeros((n,n));x[k,l]=1.
        put(f'coefficient_mode__k{k}_l{l}',x)
    put('asymmetric_ramp', (3*r-7*c+.25*r*c)/n)
    for seed in SEEDS:
        rng=np.random.Generator(np.random.PCG64(seed+n))
        z=rng.uniform(-1.,1.,size=(n,n))
        for exponent in (-100,0,90):
            put(f'random_uniform__seed{seed}_e{exponent}', z*2.**exponent, seed=seed)
        put(f'random_normal__seed{seed}', rng.standard_normal((n,n)), seed=seed)
        exponents=rng.integers(-90,91,size=(n,n))
        put(f'dynamic_range__seed{seed}', np.ldexp(z,exponents), seed=seed)
    for exponent in (-149,-140,-126):
        put(f'tiny_alternating__e{exponent}', checker*2.**exponent,'subnormal_diagnostic')
    for exponent in (110,120,126):
        put(f'boundary_constant__e{exponent}', 2.**exponent,'range_diagnostic')
        put(f'boundary_alternating__e{exponent}', checker*2.**exponent,'range_diagnostic')
    return result

def save(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    manifest=[]
    # Fixed ZIP timestamps and NPY payloads give a reproducible compressed archive.
    path=output/'inputs.npz'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n in SIZES:
            for item,x in cases(n):
                b=io.BytesIO();np.lib.format.write_array(b,x,allow_pickle=False)
                info=zipfile.ZipInfo(item['id']+'.npy',date_time=(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,b.getvalue(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
                manifest.append(item)
    result=dict(version=VERSION,seeds=SEEDS,sizes=SIZES,numpy=np.__version__,
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cases=manifest)
    (output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(Path(__file__).parent/'dataset'))
    args=p.parse_args();m=save(args.output);print(f'{len(m["cases"])} inputs; {m["archive_sha256"]}')
