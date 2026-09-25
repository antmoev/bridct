"""Targeted untimed tests for reentrancy, error cleanup, and interpreter isolation."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import subprocess
import sys

import numpy as np
import scipy
from scipy import fft

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(__doc__)
parser.add_argument('--module-dir', type=Path, default=ROOT / 'build')
parser.add_argument('--output', type=Path)
args = parser.parse_args()
module_dir = args.module_dir.resolve()
args.output = args.output or module_dir / 'hardening-validation.json'
sys.path.insert(0, str(module_dir))
import bridct_numpy as api
import bridct_test_allocator as allocator

events = []


def expect(label, exception, call):
    try:
        call()
    except exception:
        events.append(label)
    else:
        raise AssertionError('Missing expected exception: ' + label)


x = np.ones((8, 8), dtype=np.float32)
empty = api.Plan.__new__(api.Plan)
expect('uninitialized-apply', RuntimeError, lambda: empty.forward(x))
empty.close()
empty.__init__(8, 8)
expect('initialized-reinit', RuntimeError, lambda: empty.__init__(8, 8))
empty.close()
expect('closed-reinit', RuntimeError, lambda: empty.__init__(8, 8))

for action in ('close', 'initialize', 'apply'):
    pending = api.Plan.__new__(api.Plan)

    class Dimension:
        def __index__(self):
            call = (lambda: pending.close()) if action == 'close' else (
                (lambda: pending.__init__(8, 8)) if action == 'initialize' else
                (lambda: pending.forward(x)))
            expect('dimension-reentry-' + action, RuntimeError, call)
            return 8

    pending.__init__(Dimension(), 8)
    assert np.isfinite(pending.forward(x)).all()
    pending.close()

failed = api.Plan.__new__(api.Plan)
expect('failed-init-parse', TypeError, lambda: failed.__init__('8', 8))
expect('failed-init-shape', ValueError, lambda: failed.__init__(26, 8))
failed.__init__(8, 8)
assert np.isfinite(failed.forward(x)).all()
failed.close()

plan = api.Plan(8, 8)
reference = plan.forward(x)
for action in ('close', 'apply', 'initialize'):
    def callback(action=action):
        call = plan.close if action == 'close' else (
            (lambda: plan.forward(x)) if action == 'apply' else
            (lambda: plan.__init__(8, 8)))
        expect('allocator-reentry-' + action, RuntimeError, call)

    result = allocator.run(lambda: plan.forward(x), callback)
    assert np.array_equal(result, reference)
    assert not plan.closed
    del result

def allocation_failure_callback():
    events.append('allocator-failure-callback')

expect('allocation-failure', MemoryError,
       lambda: allocator.run(lambda: plan.forward(x), allocation_failure_callback, True))
assert np.array_equal(plan.forward(x), reference)
events.append('usable-after-allocation-failure')
for label, call in (
    ('invalid-keyword', lambda: plan.forward(x, invalid=True)),
    ('invalid-input', lambda: plan.forward(x.astype(np.float64))),
    ('invalid-output-type', lambda: plan.forward(x, out=[])),
):
    expect(label, TypeError, call)
    assert np.array_equal(plan.forward(x), reference)
for label, call in (
    ('late-output-shape', lambda: plan.forward(x, out=np.empty((1, 8, 8), np.float32))),
    ('late-overlap', lambda: plan.forward(x, out=x)),
):
    expect(label, ValueError, call)
    assert np.array_equal(plan.forward(x), reference)
plan.close()

numerical = []
for shape in ((8, 8), (16, 32), (128, 128), (512, 1024)):
    plan = api.Plan(*shape)
    x = np.random.default_rng(sum(shape)).standard_normal(shape).astype(np.float32)
    for mode, method in enumerate((plan.forward, plan.inverse, plan.roundtrip)):
        expected = (fft.dctn if mode == 0 else fft.idctn)(x.astype(float), norm='ortho') if mode != 2 else x
        result = method(x)
        error = float(np.linalg.norm(result.astype(float) - expected) / np.linalg.norm(x.astype(float)))
        assert error < 2e-5
        assert result.flags.owndata and not np.shares_memory(x, result)
        if mode == 2:
            assert np.array_equal(result, plan.inverse(plan.forward(x)))
        numerical.append({'shape': shape, 'mode': mode, 'error': error})
    plan.close()

subinterpreter_code = '''
import sys
try:
    import _interpreters as interpreters
except ImportError:
    import _xxsubinterpreters as interpreters
sys.path.insert(0, MODULE_DIR)
MAIN_FIRST
interpreter = interpreters.create()
try:
    try:
        failure = interpreters.run_string(interpreter, "import sys; sys.path.insert(0, " + repr(MODULE_DIR) + "); import bridct_numpy")
    except Exception as error:
        failure = error
    if failure is None:
        raise AssertionError('subinterpreter import was accepted')
    assert 'ImportError' in str(failure), str(failure)
    assert 'subinterpreters' in str(failure) or 'main interpreter' in str(failure), str(failure)
    print(str(failure))
finally:
    interpreters.destroy(interpreter)
'''
subinterpreter_outputs = []
for main_first in (False, True):
    code = subinterpreter_code.replace('MODULE_DIR', repr(str(module_dir))).replace(
        'MAIN_FIRST', 'import bridct_numpy' if main_first else '')
    process = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True)
    assert process.returncode == 0, process.stdout + process.stderr
    subinterpreter_outputs.append({'main_import_first': main_first,
                                   'stdout': process.stdout, 'stderr': process.stderr})

report = {
    'status': 'PASS', 'events': events, 'numerical_checks': numerical,
    'runtime': {'platform': platform.platform(), 'machine': platform.machine(),
                'python': sys.version, 'executable': sys.executable,
                'numpy': np.__version__, 'scipy': scipy.__version__,
                'extension_file': api.__file__, 'allocator_file': allocator.__file__,
                'core_version': api.core_version},
    'subinterpreter_checks': subinterpreter_outputs,
    'sha256': {label: hashlib.sha256(path.read_bytes()).hexdigest()
               for label, path in (('source', ROOT / 'bridct_numpy.c'),
                                   ('test', ROOT / 'test_hardening.py'),
                                   ('extension', Path(api.__file__)),
                                   ('allocator', Path(allocator.__file__)))},
}
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'events': len(events),
                  'numerical_checks': len(numerical), 'subinterpreter_checks': len(subinterpreter_outputs)}))
