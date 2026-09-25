"""Evaluate one BRiDCT build on every published input and retain boundary failures."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
from pathlib import Path
import argparse, collections, ctypes, csv, hashlib, json, platform, sys
import numpy as np
from corpus import matrix
from verify import verify, ROOT

THRESHOLD = 2e-5
FLOAT_POINTER = ctypes.POINTER(ctypes.c_float)

def pointer(x):
    return x.ctypes.data_as(FLOAT_POINTER)

def error_norm(actual, expected, input_norm):
    if not np.isfinite(actual).all():
        return None
    error = float(np.linalg.norm(actual.astype(np.float64) - expected))
    return error / input_norm if input_norm else (0.0 if error == 0.0 else None)

def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory; archived checks are never overwritten.')
    args.output.mkdir(parents=True)
    dataset = verify()
    library = args.library.resolve()
    lib = ctypes.CDLL(str(library))
    create = lib.bridct_plan_create
    create.argtypes = [ctypes.c_int, ctypes.c_int]
    create.restype = ctypes.c_void_p
    destroy = lib.bridct_plan_destroy
    destroy.argtypes = [ctypes.c_void_p]
    apply = lib.bridct_plan_apply
    apply.argtypes = [ctypes.c_void_p, ctypes.c_int, FLOAT_POINTER, FLOAT_POINTER]
    apply.restype = ctypes.c_int
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    rows, faults = [], collections.defaultdict(lambda: [0, 0])
    with np.load(ROOT / 'inputs.npz', allow_pickle=False) as arrays:
        for n in manifest['sizes']:
            q = matrix(n)
            assert np.max(np.abs(q @ q.T - np.eye(n))) < 1e-12
            plan = create(n, n)
            if not plan:
                raise RuntimeError(f'Cannot create plan {n}x{n}')
            try:
                for case in [c for c in manifest['cases'] if c['N'] == n]:
                    x = arrays[case['id']]
                    original = x.view(np.uint32).copy()
                    xd = x.astype(np.float64)
                    norm = float(np.linalg.norm(xd))
                    targets = (q @ xd @ q.T, q.T @ xd @ q, xd)
                    guard = np.full(n*n + 8, 531.25, dtype=np.float32)
                    y = guard[4:-4].reshape(n, n)
                    for mode, expected in enumerate(targets):
                        y.fill(np.nan)
                        rc = apply(plan, mode, pointer(x), pointer(y))
                        error = error_norm(y, expected, norm)
                        finite = bool(np.isfinite(y).all())
                        preserved = bool(np.array_equal(x.view(np.uint32), original))
                        sentinels = bool(np.all(guard[:4] == 531.25) and np.all(guard[-4:] == 531.25))
                        ac_error = None
                        if mode == 0 and finite:
                            ac_error = error_norm(y.ravel()[1:], expected.ravel()[1:], float(np.linalg.norm(expected.ravel()[1:])))
                        passed = bool(rc == 0 and preserved and sentinels and error is not None and error < THRESHOLD)
                        rows.append(dict(id=case['id'],N=n,domain=case['domain'],mode=mode,return_code=rc,
                                         finite=finite,error=error,ac_relative_error=ac_error,input_unchanged=preserved,
                                         sentinels=sentinels,pass_check=passed))
                        if case['domain'] == 'core':
                            mutations = {'scale': expected*1.01, 'transpose': expected.T,
                                         'sign': -expected, 'zero': np.zeros_like(expected)}
                            if mode == 0:
                                lost = np.zeros_like(expected); lost[0,0] = expected[0,0]
                                mutations['lost_ac'] = lost
                            for fault, changed in mutations.items():
                                e = error_norm(changed, expected, norm)
                                record = faults[(n,mode,fault)]
                                record[0] += int(e is None or e >= THRESHOLD)
                                record[1] += 1
            finally:
                destroy(plan)
    write_csv(args.output/'checks.csv', rows)
    mutation_rows = [dict(N=n,mode=m,fault=f,detected=d,total=t) for (n,m,f),(d,t) in sorted(faults.items())]
    write_csv(args.output/'mutations.csv', mutation_rows)
    core = [r for r in rows if r['domain'] == 'core']
    boundary = [r for r in rows if r['domain'] != 'core']
    summary = dict(status='PASS' if all(r['pass_check'] for r in core) and all(r['detected'] for r in mutation_rows) else 'FAIL',
                   core_checks=len(core),core_failures=sum(not r['pass_check'] for r in core),
                   boundary_checks=len(boundary),boundary_failures=sum(not r['pass_check'] for r in boundary),
                   boundary_nonfinite=sum(not r['finite'] for r in boundary),
                   max_core_error=max(r['error'] for r in core if r['error'] is not None),
                   max_core_ac_error=max(r['ac_relative_error'] for r in core if r['ac_relative_error'] is not None),
                   max_offset_ulp_ac_error=max(r['ac_relative_error'] for r in core if 'offset_ulp' in r['id'] and r['mode']==0),
                   fault_scenarios=len(mutation_rows),fault_scenarios_detected=sum(r['detected']>0 for r in mutation_rows),
                   dataset=dataset,library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                   host=platform.platform(),python=sys.version,numpy=np.__version__,threshold=THRESHOLD,
                   scope='Current release policies; not the historical multi-variant audit of 11760 core checks.')
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,indent=2,allow_nan=False))
    if summary['status'] != 'PASS':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
