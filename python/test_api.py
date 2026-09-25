"""Untimed numerical and ownership validation of the optional NumPy interface."""
from pathlib import Path
import argparse
import concurrent.futures
import gc
import hashlib
import importlib
import json
import os
import platform
import sys
import sysconfig
import threading

for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'

import numpy as np
import scipy
from scipy import fft

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--module-dir', type=Path, default=ROOT / 'build')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--all-shapes', action='store_true')
    args = parser.parse_args()
    args.output = args.output or args.module_dir / 'validation.json'
    sys.path.insert(0, str(args.module_dir.resolve()))
    module = importlib.import_module('bridct_numpy')
    checks = []
    required_errors = []

    def rejected(label, func, error):
        try:
            func()
        except error:
            required_errors.append(label)
        else:
            raise AssertionError('Accepted invalid argument: ' + label)

    plan = module.Plan(8, 8)
    x = np.arange(64, dtype=np.float32).reshape(8, 8).copy()
    for label, bad in (
        ('dtype64', x.astype(np.float64)), ('dtype16', x.astype(np.float16)),
        ('int', x.astype(np.int32)), ('byteorder', x.astype(np.dtype('f4').newbyteorder('S'))),
        ('list', x.tolist()), ('masked-subclass', np.ma.array(x)),
    ):
        rejected(label, lambda bad=bad: plan.forward(bad), TypeError)
    for label, bad in (
        ('1d', x.reshape(-1)), ('4d', x.reshape(1, 1, 8, 8)),
        ('different-size', np.zeros((16, 8), np.float32)),
        ('empty-batch', np.zeros((0, 8, 8), np.float32)), ('transpose', x.T),
        ('negative-stride', x[::-1]),
        ('misaligned', np.ndarray((8, 8), np.float32, buffer=bytearray(257), offset=1)),
    ):
        rejected(label, lambda bad=bad: plan.forward(bad), ValueError)
    rejected('overlap', lambda: plan.forward(x, out=x), ValueError)
    storage = np.arange(65, dtype=np.float32)
    rejected('partial-overlap', lambda: plan.forward(storage[:-1].reshape(8, 8), out=storage[1:].reshape(8, 8)), ValueError)
    readonly = np.empty_like(x)
    readonly.flags.writeable = False
    rejected('readonly-output', lambda: plan.forward(x, out=readonly), ValueError)
    rejected('out-dtype', lambda: plan.forward(x, out=np.empty((8, 8))), TypeError)
    rejected('out-batch-shape', lambda: plan.forward(x, out=np.empty((1, 8, 8), np.float32)), ValueError)
    rejected('out-positional', lambda: plan.forward(x, np.empty_like(x)), TypeError)
    rejected('unexpected-keyword', lambda: plan.forward(x, norm='ortho'), TypeError)
    rejected('missing-input', lambda: plan.forward(), TypeError)
    rejected('keyword-input', lambda: plan.forward(input=x), TypeError)
    rejected('reinitialize', lambda: plan.__init__(16, 16), RuntimeError)
    for shape in ((4, 8), (26, 32), (8, 2048), (0, 8), (-8, 8)):
        rejected('invalid-plan-' + str(shape), lambda shape=shape: module.Plan(*shape), ValueError)
    readonly_input = x.copy()
    readonly_input.flags.writeable = False
    assert np.array_equal(plan.forward(readonly_input), plan.forward(x))
    y = plan.forward(x)
    z = plan.forward(x)
    assert y is not z and y.flags.owndata and z.flags.owndata
    assert not np.shares_memory(x, y) and not np.shares_memory(y, z)
    del plan
    gc.collect()
    assert np.isfinite(y).all()
    plan = module.Plan(8, 8)
    plan.close()
    plan.close()
    assert plan.closed and plan.route is None
    rejected('closed', lambda: plan.forward(x), RuntimeError)
    uninitialized = module.Plan.__new__(module.Plan)
    rejected('uninitialized', lambda: uninitialized.forward(x), RuntimeError)
    uninitialized.close()
    lengths = (8, 16, 32, 64, 128, 256, 512, 1024)
    shapes = [(h, w) for h in lengths for w in lengths] if args.all_shapes else (
        [(n, n) for n in lengths] + [(16, 32), (8, 64), (1024, 512), (512, 1024)])
    maximum = 0.0
    for h, w in shapes:
        plan = module.Plan(h, w)
        assert plan.shape == (h, w) and not plan.closed
        for batch in (1, 4):
            shape = (h, w) if batch == 1 else (batch, h, w)
            rng = np.random.default_rng(210920 + h * 1024 + w + batch)
            signed = rng.standard_normal(shape).astype(np.float32)
            impulse = np.zeros(shape, np.float32)
            impulse[..., 1, 2] = 1
            for label, values in (('signed', signed), ('impulse', impulse),
                                  ('near-constant', (1 + signed * 1e-5).astype(np.float32))):
                initial = values.copy()
                for mode, method in enumerate((plan.forward, plan.inverse, plan.roundtrip)):
                    reference = (fft.dctn if mode == 0 else fft.idctn)(
                        values.astype(np.float64), type=2, axes=(-2, -1), norm='ortho', workers=1
                    ) if mode != 2 else values.astype(np.float64)
                    actual = method(values)
                    error = float(np.linalg.norm(actual.astype(np.float64) - reference) /
                                  max(np.linalg.norm(values.astype(np.float64)), np.finfo(float).tiny))
                    maximum = max(maximum, error)
                    assert actual.shape == values.shape and actual.dtype == np.float32
                    assert np.isfinite(actual).all() and error <= 2e-5
                    assert actual.flags.owndata and not np.shares_memory(actual, values)
                    assert np.array_equal(initial, values)
                    guarded = np.full(actual.size + 8, np.float32(-81723))
                    out = guarded[4:-4].reshape(shape)
                    returned = method(values, out=out)
                    assert returned is out and np.array_equal(actual, out)
                    assert np.all(guarded[:4] == -81723) and np.all(guarded[-4:] == -81723)
                    assert np.array_equal(initial, values)
                    if mode == 2:
                        assert np.array_equal(actual, plan.inverse(plan.forward(values)))
                    checks.append(dict(h=h, w=w, batch=batch, case=label, mode=mode, error=error))
        plan.close()

    def independent_worker(seed):
        values = np.random.default_rng(seed).standard_normal((128, 256)).astype(np.float32)
        worker = module.Plan(128, 256)
        actual = worker.roundtrip(values)
        error = float(np.linalg.norm(actual.astype(float) - values) / np.linalg.norm(values))
        assert error <= 2e-5
        worker.close()
        return error

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        threaded = list(pool.map(independent_worker, range(8)))
    shared = module.Plan(1024, 1024)
    values = np.ones((8, 1024, 1024), np.float32)
    barrier = threading.Barrier(2)

    def overlapping_worker():
        barrier.wait()
        try:
            result = shared.roundtrip(values)
            assert np.max(np.abs(result - 1)) < 2e-5
            return 'completed'
        except RuntimeError as error:
            assert 'another thread' in str(error)
            return 'busy-rejected'

    overlap_attempts = []
    for _ in range(3):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(overlapping_worker) for _ in range(2)]
            overlap = [future.result() for future in futures]
        overlap_attempts.append(overlap)
        if 'completed' in overlap and 'busy-rejected' in overlap:
            break
    else:
        raise AssertionError('The scheduler did not expose concurrent execution in three attempts: ' + repr(overlap_attempts))
    shared.close()
    result = {
        'status': 'PASS', 'numerical_cases': len(checks), 'output_contract_checks_per_case': 2,
        'runtime': {'platform': platform.platform(), 'machine': platform.machine(),
                    'python': sys.version, 'executable': sys.executable,
                    'numpy': np.__version__, 'scipy': scipy.__version__,
                    'numpy_file': np.__file__, 'scipy_file': scipy.__file__,
                    'extension_file': module.__file__, 'core_version': module.core_version,
                    'byteorder': sys.byteorder,
                    'gil_disabled': bool(sysconfig.get_config_var('Py_GIL_DISABLED'))},
        'maximum_input_relative_error': maximum, 'threshold': 2e-5,
        'shapes': shapes, 'rejected_inputs': required_errors,
        'independent_thread_cases': threaded, 'shared_plan_overlap': overlap,
        'shared_plan_overlap_attempts': overlap_attempts,
        'sha256': {'extension': sha(module.__file__), 'test': sha(__file__),
                   'source': sha(ROOT / 'bridct_numpy.c')}, 'checks': checks,
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('checks', 'shapes', 'rejected_inputs')}))


if __name__ == '__main__':
    main()
