"""Warm Python API comparisons with SciPy, DUCC and cached/planned FFTW."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'

from pathlib import Path
import argparse
import csv
import functools
import hashlib
import importlib
import json
import math
import platform
import random
import statistics
import sys
import time

import numpy as np
import scipy
from scipy import fft
from benchmark import cpu_metadata, parse_shape, process_snapshot, save, selected_shapes, sha

ROOT = Path(__file__).resolve().parent
KEYS = ('h', 'w', 'b', 'contract', 'mode', 'arm')


class FFTWPlan:
    def __init__(self, shape, effort):
        import pyfftw
        self.input = pyfftw.empty_aligned(shape, dtype='float32')
        self.output = pyfftw.empty_aligned(shape, dtype='float32')
        axes = (len(shape)-2, len(shape)-1)
        self.forward_plan = pyfftw.FFTW(self.input, self.output, axes=axes,
            direction=['FFTW_REDFT10']*2, flags=[effort], threads=1)
        self.inverse_plan = pyfftw.FFTW(self.input, self.output, axes=axes,
            direction=['FFTW_REDFT01']*2, flags=[effort], threads=1)
        h, w = shape[-2:]
        base = 1/(2*math.sqrt(h*w))
        self.forward_scale = np.full((h, w), base, dtype=np.float64)
        self.forward_scale[0, :] /= math.sqrt(2)
        self.forward_scale[:, 0] /= math.sqrt(2)
        self.inverse_scale = np.full((h, w), base, dtype=np.float64)
        self.inverse_scale[0, :] *= math.sqrt(2)
        self.inverse_scale[:, 0] *= math.sqrt(2)
        self.forward_scale = self.forward_scale.astype(np.float32)
        self.inverse_scale = self.inverse_scale.astype(np.float32)

    def forward(self, x):
        np.copyto(self.input, x)
        self.forward_plan.execute()
        return np.multiply(self.output, self.forward_scale)

    def inverse(self, x):
        np.multiply(x, self.inverse_scale, out=self.input)
        self.inverse_plan.execute()
        return self.output.copy()


def pair(forward, inverse):
    return lambda x: inverse(forward(x))


def adapters(plan, shape, requested, effort):
    directions = {'bridct': (plan.forward, plan.inverse)}
    if 'scipy' in requested:
        options = dict(type=2, axes=(-2, -1), norm='ortho', workers=1, overwrite_x=False)
        directions['scipy'] = (functools.partial(fft.dctn, **options),
                               functools.partial(fft.idctn, **options))
    if 'ducc' in requested:
        import ducc0
        options = dict(axes=(len(shape)-2, len(shape)-1), inorm=1, nthreads=1)
        directions['ducc'] = (functools.partial(ducc0.fft.dct, type=2, **options),
                              functools.partial(ducc0.fft.dct, type=3, **options))
    if 'pyfftw_cached' in requested:
        from pyfftw.interfaces import scipy_fft, cache
        cache.enable()
        cache.set_keepalive_time(3600)
        options = dict(type=2, axes=(-2, -1), norm='ortho', workers=1,
                       overwrite_x=False, planner_effort=effort)
        directions['pyfftw_cached'] = (functools.partial(scipy_fft.dctn, **options),
                                      functools.partial(scipy_fft.idctn, **options))
    if 'pyfftw_planned' in requested:
        planned = FFTWPlan(shape, effort)
        directions['pyfftw_planned'] = (planned.forward, planned.inverse)
    return {name: (forward, inverse, pair(forward, inverse))
            for name, (forward, inverse) in directions.items()}


def module_metadata(name):
    module = importlib.import_module(name)
    root = Path(module.__file__).resolve()
    directory = root.parent
    binaries = [root] if root.suffix in ('.so', '.pyd', '.dll') else sorted(
        path for path in directory.rglob('*') if path.suffix in ('.so', '.pyd', '.dll'))
    info = dict(version=module.__version__, location=str(root),
                binary_sha256={str(path.relative_to(directory)): sha(path) for path in binaries})
    if name == 'pyfftw':
        info.update(fftw_version=module.fftw_version, simd_alignment=module.simd_alignment)
    return info


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extension', type=Path, default=ROOT/'build')
    parser.add_argument('--session', type=int, default=1)
    parser.add_argument('--blocks', type=int, default=7)
    parser.add_argument('--ms', type=float, default=10)
    shape_options = parser.add_mutually_exclusive_group()
    shape_options.add_argument('--shapes', nargs='+', type=parse_shape)
    shape_options.add_argument('--all-shapes', action='store_true')
    parser.add_argument('--libraries', nargs='+', choices=['scipy','ducc','pyfftw_cached','pyfftw_planned'],
                        default=['scipy','ducc','pyfftw_cached','pyfftw_planned'])
    parser.add_argument('--planning', choices=['FFTW_MEASURE','FFTW_PATIENT'], default='FFTW_MEASURE')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--guard-known-compute', action='store_true')
    parser.add_argument('--environment-description', default='User-managed host; isolation not guaranteed.')
    args = parser.parse_args()
    if sys.flags.optimize:
        parser.error("Run without Python -O/PYTHONOPTIMIZE so validation checks remain active.")
    if args.blocks < 1 or args.session < 1 or not math.isfinite(args.ms) or args.ms <= 0:
        parser.error('Use positive session, blocks and milliseconds.')
    if len(set(args.libraries)) != len(args.libraries):
        parser.error('Duplicate library names.')
    shapes = selected_shapes(args.shapes, args.all_shapes)
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.extension.resolve()))
    import bridct_numpy
    extension = Path(bridct_numpy.__file__).resolve()
    if extension.parent != args.extension.resolve():
        raise RuntimeError('Imported a different extension than requested.')
    arms = ['bridct', *args.libraries]
    modules = {'numpy','scipy'}
    if 'ducc' in arms: modules.add('ducc0')
    if any(name.startswith('pyfftw') for name in arms): modules.add('pyfftw')
    metadata = dict(status='STARTED', session=args.session, blocks=args.blocks,
        calibration_ms=args.ms, started=time.time(), host=platform.platform(), cpu=cpu_metadata(),
        python=sys.version, modules={name: module_metadata(name) for name in sorted(modules)},
        extension_sha256=sha(extension), extension_file=str(extension), runner_sha256=sha(__file__),
        helper_sha256=sha(ROOT/'benchmark.py'), arms=arms, shapes=shapes,
        planning=args.planning, thread_request=1, setup_timed=False, cached_replanning_timed=True, baseline_subtraction=False,
        units='nanoseconds per array; complete allocating Python API calls',
        contracts='Direct 2D for B1; batched (4,H,W) for B4. Every round trip uses separate forward and inverse calls and materializes the orthonormal spectrum. Initial planning and input preparation excluded; any cached-interface replanning is counted and retained in measured time. Dispatch, copies, normalization, allocation and result destruction included.',
        planned_fftw='Aligned MEASURE/PATIENT plans; input copy or input normalization, unnormalized real-to-real execute, output normalization or copy. Returns fresh full output. No FFTW_UNALIGNED flag.',
        environment_description=args.environment_description, host_isolation_guaranteed=False,
        github_actions=os.environ.get('GITHUB_ACTIONS')=='true', github_run_id=os.environ.get('GITHUB_RUN_ID'))
    build = args.extension/'build.json'
    if build.exists():
        metadata['extension_build_manifest'] = json.loads(build.read_text())
        assert metadata['extension_build_manifest']['sha256']['extension'] == metadata['extension_sha256']
    save(args.output/'manifest.json', metadata)
    rng = np.random.default_rng(210920263)
    configurations, checks, rows, plans = [], [], [], []
    audit = None
    try:
        if "pyfftw_cached" in arms:
            import fftw_cache_audit as audit
            audit.install()
            metadata["cache_audit_sha256"] = sha(ROOT/"fftw_cache_audit.py")
        process_snapshot(args.output/'processes-setup.txt', args.guard_known_compute)
        for h,w in shapes:
            plan = bridct_numpy.Plan(h,w); plans.append(plan)
            for batch in (1,4):
                shape = (h,w) if batch == 1 else (batch,h,w)
                contract = 'direct_alloc' if batch == 1 else 'batch_alloc'
                methods = adapters(plan, shape, args.libraries, args.planning)
                x = rng.normal(size=shape).astype(np.float32)
                impulse = np.zeros_like(x); impulse[...,h//3,w//2]=1
                cases = {'signed':x, 'neighbors':(1+np.where(np.indices(shape).sum(axis=0)%2,1.,-1.)*2**-23).astype(np.float32), 'impulse':impulse}
                for mode in range(3):
                    for name, transforms in methods.items():
                        function = transforms[mode]
                        for label, data in cases.items():
                            before = data.copy(); output = function(data)
                            held = output.copy(); other = function(data)
                            reference = data.astype(np.float64) if mode==2 else (fft.dctn if mode==0 else fft.idctn)(data.astype(np.float64), type=2, axes=(-2,-1), norm='ortho', workers=1)
                            error = float(np.linalg.norm(output.astype(np.float64)-reference)/np.linalg.norm(data.astype(np.float64)))
                            passed = bool(output.shape==shape and output.dtype==np.float32 and output.flags.c_contiguous and np.isfinite(output).all() and error<=2e-5 and np.array_equal(before,data) and np.array_equal(output,held) and not np.shares_memory(output,data) and not np.shares_memory(output,other))
                            record = dict(h=h,w=w,b=batch,contract=contract,mode=mode,arm=name,case=label,error=error,passed=passed)
                            checks.append(record)
                            if not passed: raise AssertionError(record)
                        configurations.append(dict(h=h,w=w,b=batch,contract=contract,mode=mode,arm=name,function=function,input=x))
        expected = {(h,w,b,'direct_alloc' if b==1 else 'batch_alloc',m,a) for h,w in shapes for b in (1,4) for m in range(3) for a in arms}
        assert {tuple(c[k] for k in KEYS) for c in configurations} == expected
        assert len(checks)==3*len(expected)
        save(args.output/'validation.json', checks)
        print('VALIDATED',len(checks),'directions',flush=True)
        if args.validate_only:
            metadata.update(status='VALIDATED',validation_records=len(checks));return
        def timed(c, repeats):
            f=c['function'];x=c['input']
            before_plans=audit.count() if audit else 0
            start=time.perf_counter_ns()
            for _ in range(repeats): f(x)
            elapsed=time.perf_counter_ns()-start
            if elapsed<0: raise RuntimeError('Negative elapsed time.')
            return elapsed, (audit.count()-before_plans if audit else 0)
        process_snapshot(args.output/'processes-calibration.txt', args.guard_known_compute)
        for c in configurations:
            timed(c,4);repeats=1
            while timed(c,repeats)[0]<args.ms*1e6:
                repeats*=2
                if repeats>2**32:raise RuntimeError('Calibration exhausted.')
            c['repeats']=repeats
        save(args.output/'calibration.json',[dict(**{k:c[k] for k in KEYS},repeats=c['repeats']) for c in configurations])
        metadata['plan_creations_before_measurement']=audit.count() if audit else 0
        fields=['session','block','order',*KEYS,'repeats','elapsed_ns','ns_array','plan_creations']
        with (args.output/'timing.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
            order=list(range(len(configurations)));randomizer=random.Random(71000+args.session)
            for block in range(args.blocks):
                process_snapshot(args.output/f'processes-{block}.txt',args.guard_known_compute)
                randomizer.shuffle(order)
                for rank,index in enumerate(order):
                    c=configurations[index];elapsed,plan_creations=timed(c,c['repeats'])
                    assert elapsed>0
                    row=dict(session=args.session,block=block,order=rank,**{k:c[k] for k in KEYS},repeats=c['repeats'],elapsed_ns=elapsed,ns_array=elapsed/c['repeats']/c['b'],plan_creations=plan_creations)
                    rows.append(row);writer.writerow(row)
                f.flush();print('BLOCK',block+1,'/',args.blocks,flush=True)
        assert len(rows)==args.blocks*len(expected)
        assert {(r['block'],*(r[k] for k in KEYS)) for r in rows}=={(b,*key) for b in range(args.blocks) for key in expected}
        grouped={}
        for row in rows:
            key=tuple(row[k] for k in KEYS[:-1]);grouped.setdefault(key,{}).setdefault(row['arm'],[]).append(row['ns_array'])
        with (args.output/'comparison.csv').open('w',newline='') as f:
            fields=[*KEYS[:-1],'reference','bridct_ns_array','reference_ns_array','reference_over_bridct']
            writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
            for key,values in sorted(grouped.items()):
                candidate=statistics.median(values['bridct'])
                for name in args.libraries:
                    ref=statistics.median(values[name])
                    writer.writerow(dict(zip(KEYS[:-1],key),reference=name,bridct_ns_array=candidate,reference_ns_array=ref,reference_over_bridct=ref/candidate))
        metadata.update(status='COMPLETE_EXPLORATORY',rows=len(rows),validation_records=len(checks),cached_replanning_total=sum(r['plan_creations'] for r in rows),blocks_with_replanning=sum(r['plan_creations']>0 for r in rows))
    except Exception as error:
        metadata.update(status='FAILED',error=repr(error));save(args.output/'validation.json',checks);raise
    finally:
        if audit: audit.restore()
        for plan in plans:plan.close()
        metadata['finished']=time.time();save(args.output/'manifest.json',metadata)


if __name__=='__main__':
    main()
