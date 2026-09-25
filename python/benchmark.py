"""Exploratory end-to-end Python/OpenCV comparison with 13 contracts per selected shape."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'

from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import platform
import random
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
LENGTHS = (8, 16, 32, 64, 128, 256, 512, 1024)
DEFAULT_SHAPES = [(n, n) for n in LENGTHS] + [(16, 32), (8, 64)]
CONTRACT_BATCHES = (('batch_alloc', 1), ('batch_alloc', 4), ('direct_alloc', 1),
                    ('direct_out', 1), ('roundtrip_two_calls', 1))
IDENTITY_KEYS = ('h', 'w', 'b', 'contract', 'mode', 'arm')


def load_dependencies():
    global cv2, np, scipy, dctn, idctn
    import cv2
    import numpy as np
    import scipy
    from scipy.fft import dctn, idctn
    cv2.setNumThreads(1)


def parse_shape(value):
    match = re.fullmatch(r'([0-9]+)[xX×]([0-9]+)', value)
    if not match:
        raise argparse.ArgumentTypeError('Use HxW, for example 8x8 or 16x32.')
    shape = tuple(map(int, match.groups()))
    if any(length not in LENGTHS for length in shape):
        raise argparse.ArgumentTypeError('Each axis must be a power of two from 8 through 1024.')
    return shape


def selected_shapes(explicit=None, all_shapes=False):
    if explicit is not None and all_shapes:
        raise ValueError('--shapes and --all-shapes are mutually exclusive.')
    shapes = [(height, width) for height in LENGTHS for width in LENGTHS] if all_shapes else (
        list(explicit) if explicit is not None else list(DEFAULT_SHAPES))
    if not shapes or any(len(shape) != 2 or any(length not in LENGTHS for length in shape) for shape in shapes):
        raise ValueError('At least one valid supported shape is required.')
    if len(set(shapes)) != len(shapes):
        raise ValueError('Duplicate shapes are not allowed.')
    return shapes


def expected_arms(shapes):
    return {(height, width, batch, contract, mode, arm)
            for height, width in shapes
            for contract, batch in CONTRACT_BATCHES
            for mode in ((2,) if contract == 'roundtrip_two_calls' else range(3))
            for arm in ('bridct', 'opencv')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def cpu_metadata():
    data = {'machine': platform.machine(), 'processor': platform.processor(),
            'logical_cpu_count': os.cpu_count()}
    try:
        if sys.platform == 'darwin':
            data['model'] = subprocess.check_output(
                ['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
        elif sys.platform == 'win32':
            data['model'] = subprocess.check_output(
                ['powershell', '-NoProfile', '-Command',
                 '(Get-CimInstance Win32_Processor).Name'], text=True).strip()
        elif Path('/proc/cpuinfo').is_file():
            data['model'] = next((line.split(':', 1)[1].strip()
                                  for line in Path('/proc/cpuinfo').read_text().splitlines()
                                  if line.startswith('model name')), None)
    except (OSError, subprocess.SubprocessError) as error:
        data['model_query_error'] = repr(error)
    return data


def process_snapshot(path, guard):
    if sys.platform == 'win32':
        command = ['tasklist', '/FO', 'CSV', '/NH']
    else:
        command = ['ps', '-axo', 'pid,ppid,pcpu,comm']
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        path.write_text(result.stdout)
    except (OSError, subprocess.SubprocessError) as error:
        path.write_text('Process snapshot unavailable: ' + repr(error) + '\n')
        if guard:
            raise RuntimeError('Requested process guard could not inspect processes.') from error
        return
    if not guard:
        return
    forbidden = {'clang', 'cc1', 'clang++', 'gcc', 'g++', 'bench', 'check_memory', 'test_runner'}
    if sys.platform == 'win32':
        names = [Path(row[0]).stem.lower() for row in csv.reader(result.stdout.splitlines()) if row]
    else:
        names = [line.split()[-1].split('/')[-1] for line in result.stdout.splitlines()[1:] if line.split()]
    conflicts = sorted(set(names) & forbidden)
    if conflicts:
        raise RuntimeError('Known concurrent compute process observed: ' + ', '.join(conflicts))


def functions(plan, x, mode, contract):
    forward, inverse = plan.forward, plan.inverse
    method = (forward, inverse, plan.roundtrip)[mode]
    cv_forward, cv_inverse = cv2.dct, cv2.idct
    if contract == 'batch_alloc':
        allocate = np.empty_like
        if mode == 2:
            def opencv(a):
                output = allocate(a)
                for i in range(len(a)):
                    cv_inverse(cv_forward(a[i]), output[i])
                return output
        else:
            cv_method = (cv_forward, cv_inverse)[mode]
            def opencv(a):
                output = allocate(a)
                for i in range(len(a)):
                    cv_method(a[i], output[i])
                return output
        return {'bridct': method, 'opencv': opencv}, None
    if contract == 'direct_alloc':
        opencv = cv_forward if mode == 0 else cv_inverse if mode == 1 else lambda a: cv_inverse(cv_forward(a))
        return {'bridct': method, 'opencv': opencv}, None
    if contract == 'direct_out':
        temporary = np.empty_like(x)
        output = np.empty_like(x)
        if mode == 2:
            opencv = lambda a: cv_inverse(cv_forward(a, temporary), output)
        else:
            cv_method = (cv_forward, cv_inverse)[mode]
            opencv = lambda a: cv_method(a, output)
        return {'bridct': lambda a: method(a, out=output), 'opencv': opencv}, output
    if contract == 'roundtrip_two_calls':
        return {'bridct': lambda a: inverse(forward(a)),
                'opencv': lambda a: cv_inverse(cv_forward(a))}, None
    raise ValueError(contract)


def verify_complete(configurations, checks, rows, blocks, shapes):
    expected = expected_arms(shapes)
    configured = {tuple(item[key] for key in IDENTITY_KEYS) for item in configurations}
    if len(configurations) != len(expected) or configured != expected:
        raise AssertionError(f'Expected exactly {len(expected)} distinct arms for the selected shapes.')
    validation_keys = {tuple(item[key] for key in IDENTITY_KEYS) + (item['case'],) for item in checks}
    expected_checks = {key + (case,) for key in expected for case in ('signed', 'neighbors')}
    if len(checks) != len(expected_checks) or validation_keys != expected_checks or not all(item['passed'] for item in checks):
        raise AssertionError(f'Expected exactly {len(expected_checks)} passing, distinct validation records.')
    if rows is None:
        return
    actual = {(item['block'],) + tuple(item[key] for key in IDENTITY_KEYS) for item in rows}
    expected_rows = {(block,) + key for block in range(blocks) for key in expected}
    if len(rows) != len(expected) * blocks or actual != expected_rows:
        raise AssertionError('Timing rows do not match the complete expected key set.')
    if not all(item['elapsed_ns'] > 0 and item['repeats'] > 0 and
               math.isfinite(item['ns_array']) and item['ns_array'] > 0 for item in rows):
        raise AssertionError('Invalid timing value.')


def summarize(rows, path):
    grouped = {}
    for row in rows:
        key = tuple(row[name] for name in IDENTITY_KEYS[:-1])
        grouped.setdefault(key, {}).setdefault(row['arm'], []).append(row['ns_array'])
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=[*IDENTITY_KEYS[:-1], 'bridct_ns_array',
                                                    'opencv_ns_array', 'opencv_over_bridct'])
        writer.writeheader()
        for key, arms in sorted(grouped.items()):
            bridct = statistics.median(arms['bridct'])
            opencv = statistics.median(arms['opencv'])
            writer.writerow(dict(zip(IDENTITY_KEYS[:-1], key), bridct_ns_array=bridct,
                                 opencv_ns_array=opencv, opencv_over_bridct=opencv / bridct))


def argument_parser():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--extension', type=Path, default=ROOT / 'build')
    parser.add_argument('--session', type=int, default=1)
    parser.add_argument('--blocks', type=int, default=7)
    parser.add_argument('--ms', type=float, default=20)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--guard-known-compute', action='store_true')
    parser.add_argument('--environment-description', default='User-managed host; isolation not established by this script.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--shapes', nargs='+', type=parse_shape, metavar='HxW')
    group.add_argument('--all-shapes', action='store_true', help='All 64 supported height/width pairs.')
    parser.add_argument('--self-test', action='store_true', help='Test parsing and completeness logic without transforms or timing.')
    return parser


def self_test():
    import contextlib
    import io
    import unittest
    from unittest.mock import patch
    from types import SimpleNamespace

    class ShapeContracts(unittest.TestCase):
        def test_valid_shapes(self):
            for text, expected in [('8x8', (8, 8)), ('16x32', (16, 32)),
                                   ('8X64', (8, 64)), ('1024×512', (1024, 512))]:
                self.assertEqual(parse_shape(text), expected)

        def test_invalid_shapes(self):
            for text in ('', '8', '8x8x8', '8x26', '4x8', '2048x8', '-8x8', '0x8', '8.0x8'):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_shape(text)

        def test_defaults(self):
            self.assertEqual(selected_shapes(), DEFAULT_SHAPES)
            self.assertEqual(len(expected_arms(selected_shapes())), 260)

        def test_all_shapes(self):
            shapes = selected_shapes(all_shapes=True)
            self.assertEqual(len(shapes), 64)
            self.assertEqual(len(expected_arms(shapes)), 1664)

        def test_duplicate_and_empty(self):
            for shapes in ([], [(8, 8), (8, 8)], [(8, 26)]):
                with self.assertRaises(ValueError):
                    selected_shapes(shapes)

        def test_exclusive_flags(self):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                argument_parser().parse_args(['--shapes', '8x8', '--all-shapes'])
            with self.assertRaises(ValueError):
                selected_shapes([(8, 8)], True)

        def test_selected_order(self):
            args = argument_parser().parse_args(['--shapes', '16x32', '8x8'])
            self.assertEqual(selected_shapes(args.shapes), [(16, 32), (8, 8)])

        def test_complete_contracts(self):
            shapes = [(8, 8), (16, 32)]
            configurations = [dict(zip(IDENTITY_KEYS, key)) for key in expected_arms(shapes)]
            checks = [dict(item, case=case, passed=True) for item in configurations
                      for case in ('signed', 'neighbors')]
            rows = [dict(item, block=block, elapsed_ns=100, repeats=1, ns_array=100)
                    for block in range(2) for item in configurations]
            verify_complete(configurations, checks, None, 2, shapes)
            verify_complete(configurations, checks, rows, 2, shapes)
            for broken_configurations, broken_checks, broken_rows in (
                (configurations[:-1], checks, rows),
                (configurations[:-1] + [configurations[0]], checks, rows),
                (configurations, checks[:-1], rows),
                (configurations, checks[:-1] + [dict(checks[-1], case='unexpected')], rows),
                (configurations, checks, rows[:-1]),
                (configurations, checks, rows[:-1] + [dict(rows[-1], elapsed_ns=0)]),
            ):
                with self.assertRaises(AssertionError):
                    verify_complete(broken_configurations, broken_checks, broken_rows, 2, shapes)

        def test_comparator_closures(self):
            class Array:
                def __init__(self, count=2):
                    self.images = [object() for _ in range(count)]
                def __len__(self):
                    return len(self.images)
                def __getitem__(self, index):
                    return self.images[index]

            events = []
            def record(name):
                def transform(input_array, out=None):
                    events.append(name)
                    return out if out is not None else Array()
                return transform

            plan = SimpleNamespace(forward=record('br-forward'), inverse=record('br-inverse'),
                                   roundtrip=record('br-pair'))
            cv = SimpleNamespace(dct=record('cv-forward'), idct=record('cv-inverse'))
            fake_numpy = SimpleNamespace(empty_like=lambda value: Array(len(value)))
            with patch.dict(globals(), cv2=cv, np=fake_numpy):
                for contract in ('batch_alloc', 'direct_alloc', 'direct_out', 'roundtrip_two_calls'):
                    for mode in ((2,) if contract == 'roundtrip_two_calls' else range(3)):
                        values = Array()
                        arms, output = functions(plan, values, mode, contract)
                        events.clear()
                        result = arms['opencv'](values)
                        expected = ['cv-forward', 'cv-inverse'] if mode == 2 else [
                            'cv-forward' if mode == 0 else 'cv-inverse']
                        self.assertEqual(events, expected * (2 if contract == 'batch_alloc' else 1))
                        if output is not None:
                            self.assertIs(result, output)
                        events.clear()
                        result = arms['bridct'](values)
                        expected = ['br-forward', 'br-inverse'] if contract == 'roundtrip_two_calls' else [
                            ('br-forward', 'br-inverse', 'br-pair')[mode]]
                        self.assertEqual(events, expected)
                        if output is not None:
                            self.assertIs(result, output)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ShapeContracts))
    print(json.dumps({'status': 'PASS' if result.wasSuccessful() else 'FAILED',
                      'tests': result.testsRun, 'numerical_transforms_executed': 0, 'timings_executed': 0}))
    return 0 if result.wasSuccessful() else 1


def main():
    if sys.flags.optimize:
        raise RuntimeError("Run without Python -O/PYTHONOPTIMIZE so validation checks remain active.")
    parser = argument_parser()
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(self_test())
    if args.output is None:
        parser.error('--output is required unless --self-test is selected.')
    try:
        shapes = selected_shapes(args.shapes, args.all_shapes)
    except ValueError as error:
        parser.error(str(error))
    if args.blocks < 1 or not math.isfinite(args.ms) or args.ms <= 0 or args.session < 1:
        parser.error('session and blocks must be positive integers; ms must be positive and finite.')
    load_dependencies()
    args.output.mkdir(parents=True, exist_ok=False)
    extension_dir = args.extension.resolve()
    sys.path.insert(0, str(extension_dir))
    import bridct_numpy
    extension = Path(bridct_numpy.__file__).resolve()
    if extension.parent != extension_dir:
        raise RuntimeError('Imported a different BRiDCT extension than requested.')
    opencv_root = Path(cv2.__file__).parent
    opencv_binaries = sorted({path for pattern in ('*.so', '*.pyd', '*.dll')
                              for path in opencv_root.rglob(pattern)})
    meta = {
        'status': 'STARTED', 'scope': 'Exploratory warmed end-to-end Python API comparison; not a universal ranking.',
        'session': args.session, 'host': platform.platform(), 'cpu': cpu_metadata(),
        'python': sys.version, 'python_executable': sys.executable,
        'numpy': np.__version__, 'scipy': scipy.__version__, 'opencv': cv2.__version__,
        'opencv_threads_reported': cv2.getNumThreads(), 'opencv_thread_request': 1,
        'blocks': args.blocks, 'calibration_ms': args.ms, 'started': time.time(),
        'extension_file': str(extension), 'extension_sha256': sha(extension),
        'opencv_binary_sha256': {str(path.relative_to(opencv_root)): sha(path) for path in opencv_binaries},
        'opencv_python_file': str(Path(cv2.__file__).resolve()),
        'runner_sha256': sha(__file__), 'baseline_subtraction': False,
        'units': 'nanoseconds per array; Python calls, validation, and declared allocations included',
        'environment_description': args.environment_description,
        'github_actions': os.environ.get('GITHUB_ACTIONS') == 'true',
        'github_run_id': os.environ.get('GITHUB_RUN_ID'),
        'host_isolation_guaranteed': False, 'process_guard_requested': args.guard_known_compute,
        'setup_timed': False, 'output_deallocation_timed': True,
        'shapes': shapes, 'shape_selection': 'all' if args.all_shapes else 'explicit' if args.shapes else 'default',
        'expected_contracts': len(expected_arms(shapes)) // 2,
        'expected_arms': len(expected_arms(shapes)),
        'expected_validation_records': 2 * len(expected_arms(shapes)),
    }
    build = extension_dir / 'build.json'
    if build.is_file():
        meta['extension_build_manifest'] = json.loads(build.read_text())
        meta['extension_build_manifest_sha256'] = sha(build)
        if meta['extension_build_manifest']['sha256']['extension'] != meta['extension_sha256']:
            raise RuntimeError('Extension hash does not match its build manifest.')
    else:
        meta['extension_build_manifest'] = None
    (args.output / 'opencv_build.txt').write_text(cv2.getBuildInformation())
    save(args.output / 'manifest.json', meta)
    configurations, checks, rows, plans = [], [], [], []
    rng = np.random.default_rng(9021026)
    try:
        process_snapshot(args.output / 'processes-setup.txt', args.guard_known_compute)
        for height, width in shapes:
            plan = bridct_numpy.Plan(height, width)
            plans.append(plan)
            for contract, batch in CONTRACT_BATCHES:
                shape = (batch, height, width) if contract == 'batch_alloc' else (height, width)
                x = rng.normal(size=shape).astype(np.float32)
                cases = {'signed': x, 'neighbors': (1 + np.where(np.indices(shape).sum(axis=0) % 2,
                                                                1., -1.) * 2**-23).astype(np.float32)}
                for mode in ([2] if contract == 'roundtrip_two_calls' else range(3)):
                    callables, expected_output = functions(plan, x, mode, contract)
                    for arm, operation in callables.items():
                        for case, values in cases.items():
                            before = values.copy()
                            result = operation(values)
                            values64 = values.astype(np.float64)
                            reference = values64 if mode == 2 else (dctn if mode == 0 else idctn)(
                                values64, type=2, norm='ortho', axes=(-2, -1), workers=1)
                            error = float(np.linalg.norm(result.astype(np.float64) - reference) /
                                          np.linalg.norm(values64))
                            passed = bool(error <= 2e-5 and np.isfinite(result).all() and
                                          result.shape == values.shape and result.dtype == np.float32 and
                                          result.flags.c_contiguous and np.array_equal(values, before) and
                                          not np.shares_memory(result, values))
                            if expected_output is not None:
                                passed = passed and result is expected_output
                            else:
                                other = operation(values)
                                passed = passed and result.flags.owndata and not np.shares_memory(result, other)
                            checks.append(dict(h=height, w=width, b=batch, contract=contract, mode=mode,
                                               arm=arm, case=case, error=error, passed=bool(passed)))
                            if not passed:
                                raise AssertionError(checks[-1])
                        configurations.append(dict(h=height, w=width, b=batch, contract=contract,
                                                   mode=mode, arm=arm, fn=operation, x=x))
        verify_complete(configurations, checks, None, args.blocks, shapes)
        save(args.output / 'validation.json', checks)
        print('VALIDATED', len(checks), 'records across', len(configurations) // 2, 'contracts', flush=True)
        if args.validate_only:
            meta.update(status='VALIDATED', contracts=len(configurations) // 2, validation_records=len(checks))
            return

        def timed(configuration, repetitions):
            function = configuration['fn']
            values = configuration['x']
            start = time.perf_counter_ns()
            for _ in range(repetitions):
                function(values)
            elapsed = time.perf_counter_ns() - start
            if elapsed < 0:
                raise RuntimeError('Negative elapsed time.')
            return elapsed

        process_snapshot(args.output / 'processes-calibration.txt', args.guard_known_compute)
        for configuration in configurations:
            timed(configuration, 4)
            repetitions = 1
            while True:
                elapsed = timed(configuration, repetitions)
                if elapsed >= args.ms * 1e6:
                    break
                repetitions = max(repetitions + 1, min(repetitions * 8,
                    int(repetitions * args.ms * 1e6 / max(elapsed, 1) * 1.1)))
                if repetitions > 2**32:
                    raise RuntimeError('Calibration exhausted.')
            configuration['repeats'] = repetitions
        save(args.output / 'calibration.json', [
            {key: value for key, value in item.items() if key not in ('fn', 'x')} for item in configurations])
        fields = ['session', 'block', 'order', *IDENTITY_KEYS, 'repeats', 'elapsed_ns', 'ns_array']
        with (args.output / 'timing.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
            writer.writeheader()
            order = list(range(len(configurations)))
            randomizer = random.Random(88800 + args.session)
            for block in range(args.blocks):
                process_snapshot(args.output / f'processes-block{block}.txt', args.guard_known_compute)
                randomizer.shuffle(order)
                for rank, index in enumerate(order):
                    configuration = configurations[index]
                    elapsed = timed(configuration, configuration['repeats'])
                    if elapsed <= 0:
                        raise RuntimeError('Nonpositive measured block duration.')
                    row = dict(session=args.session, block=block, order=rank,
                               **{key: configuration[key] for key in IDENTITY_KEYS},
                               repeats=configuration['repeats'], elapsed_ns=elapsed,
                               ns_array=elapsed / configuration['repeats'] / configuration['b'])
                    rows.append(row)
                    writer.writerow(row)
                stream.flush()
                print('BLOCK', block + 1, '/', args.blocks, flush=True)
        process_snapshot(args.output / 'processes-finished.txt', args.guard_known_compute)
        verify_complete(configurations, checks, rows, args.blocks, shapes)
        summarize(rows, args.output / 'comparison.csv')
        meta.update(status='COMPLETE_EXPLORATORY', rows=len(rows), contracts=len(configurations) // 2,
                    validation_records=len(checks))
    except Exception as error:
        meta.update(status='FAILED', error=repr(error))
        save(args.output / 'validation.json', checks)
        raise
    finally:
        for plan in plans:
            plan.close()
        meta['finished'] = time.time()
        save(args.output / 'manifest.json', meta)


if __name__ == '__main__':
    main()
