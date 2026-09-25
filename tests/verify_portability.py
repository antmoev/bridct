"""Check a C runner against independent references, including translated binaries."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys
import numpy as np
from scipy.fft import dctn, idctn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'dataset'))
from corpus import matrix
from verify import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runner', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execution', required=True,
                        help='Describe native or translated execution; this is not a timing test.')
    parser.add_argument('--library', type=Path, action='append', default=[],
                        help='Shared library loaded by the runner; record its hash as well.')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory')
    args.output.mkdir(parents=True)
    verify()
    executable = args.runner.resolve()
    rows = []
    with (args.output / 'stderr.log').open('wb') as errors:
        proc = subprocess.Popen([str(executable)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=errors)
        def check(x, expected, mode, case, domain):
            x = np.ascontiguousarray(x, dtype=np.float32)
            h, w = x.shape
            proc.stdin.write(struct.pack('=4I', 0x42524443, h, w, mode))
            proc.stdin.write(x.tobytes())
            proc.stdin.flush()
            reply = proc.stdout.read(16)
            if len(reply) != 16:
                raise RuntimeError('Runner terminated; inspect stderr.log')
            magic, rc, guards, immutable = struct.unpack('=4I', reply)
            output = proc.stdout.read(x.nbytes)
            if len(output) != x.nbytes or magic != 0x42524443:
                raise RuntimeError('Incomplete runner response')
            y = np.frombuffer(output, dtype=np.float32).reshape(h, w)
            finite = bool(np.isfinite(y).all())
            norm = float(np.linalg.norm(x.astype(np.float64)))
            delta = float(np.linalg.norm(y.astype(np.float64) - expected)) if finite else None
            error = delta / norm if norm and finite else delta
            passed = bool(rc == 0 and guards and immutable and finite and error <= 2e-5)
            rows.append(dict(h=h, w=w, case=case, domain=domain, mode=mode,
                             error=error, finite=finite, guards=bool(guards),
                             unchanged=bool(immutable), return_code=rc, passed=passed))
        try:
            rng = np.random.default_rng(202609201)
            for h in (8, 16, 32, 64, 128, 256, 512, 1024):
                for w in (8, 16, 32, 64, 128, 256, 512, 1024):
                    noise = rng.normal(size=(h,w)).astype(np.float32)
                    alt = np.where(np.indices((h,w)).sum(axis=0) % 2, 1., -1.)
                    impulse = np.zeros((h,w), np.float32)
                    impulse[h//3,w//2] = 1
                    cases = [('zero',np.zeros_like(impulse)), ('impulse',impulse),
                             ('random',noise), ('neighbors',(1+alt*2**-23).astype(np.float32)),
                             ('tiny',noise*2.**-70), ('large',noise*2.**50)]
                    for name,x in cases:
                        xd = x.astype(np.float64)
                        for mode,ref in enumerate((dctn(xd,type=2,norm='ortho'),
                                                   idctn(xd,type=2,norm='ortho'),xd)):
                            check(x,ref,mode,name,'shapes')
            manifest = json.loads((ROOT/'dataset/manifest.json').read_text())
            with np.load(ROOT/'dataset/inputs.npz',allow_pickle=False) as data:
                for n in manifest['sizes']:
                    q = matrix(n)
                    assert np.max(np.abs(q@q.T-np.eye(n))) < 1e-12
                    for case in (c for c in manifest['cases'] if c['N']==n):
                        x=data[case['id']];xd=x.astype(np.float64)
                        for mode,ref in enumerate((q@xd@q.T,q.T@xd@q,xd)):
                            check(x,ref,mode,case['id'],case['domain'])
            proc.stdin.close()
            if proc.wait(timeout=30) != 0:
                raise RuntimeError('Runner returned nonzero')
        finally:
            if proc.poll() is None:
                proc.terminate();proc.wait(timeout=30)
    with (args.output/'checks.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    required=[r for r in rows if r['domain'] in ('shapes','core')]
    boundary=[r for r in rows if r['domain'] not in ('shapes','core')]
    structural=all(r['guards'] and r['unchanged'] and r['return_code']==0 for r in rows)
    result=dict(status='PASS' if structural and all(r['passed'] for r in required) else 'FAIL',
                execution=args.execution,host=platform.platform(),host_machine=platform.machine(),package_version=(ROOT/'VERSION').read_text().strip(),
                runner_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                shared_libraries={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in args.library},
                shapes=64,shape_checks=sum(r['domain']=='shapes' for r in rows),
                corpus_core_checks=sum(r['domain']=='core' for r in rows),
                boundary_checks=len(boundary),boundary_failures=sum(not r['passed'] for r in boundary),
                required_failures=sum(not r['passed'] for r in required),
                max_required_error=max(r['error'] for r in required if r['error'] is not None),
                guards_and_input_preservation=structural,
                scope='Correctness only; no execution-time measurements or native CPU performance claims.')
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));assert result['status']=='PASS'

if __name__=='__main__':
    main()
