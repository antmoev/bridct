"""Build only the optional CPython extension against an existing BRiDCT library."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import sysconfig

import numpy as np

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'build')
    parser.add_argument('--cc', default=os.environ.get('CC'))
    parser.add_argument('--extra-cflags', default='')
    args = parser.parse_args()
    core = args.core.resolve()
    library = args.library.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    compiler = args.cc or ('/Library/Developer/CommandLineTools/usr/bin/clang'
                          if sys.platform == 'darwin' else 'clang')
    target = output / ('bridct_numpy' + sysconfig.get_config_var('EXT_SUFFIX'))
    source = ROOT / 'bridct_numpy.c'
    command = [compiler, '-std=c11', '-pedantic-errors', '-O3', '-Wall', '-Wextra',
               '-fvisibility=hidden', '-fPIC', '-H', '-I' + np.get_include(),
               '-I' + str(core / 'include'),
               '-isystem', sysconfig.get_paths()['include'],
               *shlex.split(args.extra_cflags)]
    link_python = []
    if sys.platform == 'darwin':
        command += ['-arch', platform.machine(), '-isysroot',
                    '/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk',
                    '-bundle', '-undefined', 'dynamic_lookup']
    elif sys.platform == 'win32':
        base = Path(sys.base_prefix)
        command += ['-shared']
        link_python = ['-L' + str(base / 'libs'),
                       '-lpython' + str(sys.version_info.major) + str(sys.version_info.minor)]
    else:
        command += ['-shared']
    command += [str(source), str(library), *link_python, '-lm', '-o', str(target)]
    if library.suffix in ('.so', '.dylib'):
        command += ['-Wl,-rpath,' + str(library.parent)]
    manifest = {
        'status': 'BUILDING', 'python': sys.version, 'numpy': np.__version__,
        'platform': platform.platform(), 'command': command,
        'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'core': str(core), 'library': str(library),
        'numpy_include': str(Path(np.get_include()).resolve()),
        'sha256': {'source': digest(source), 'header': digest(core / 'include/bridct.h'),
                   'library': digest(library), 'builder': digest(__file__)},
        'output': str(target),
    }
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output / 'build.log').write_text(result.stdout)
    headers = sorted({str(Path(match.group(1)).resolve())
                      for line in result.stdout.splitlines()
                      if (match := re.match(r'^\.+ (.+)$', line))
                      and Path(match.group(1)).is_file()
                      and 'numpy' in Path(match.group(1)).parts})
    expected = Path(np.get_include()).resolve()
    manifest['numpy_headers'] = headers
    headers_ok = (str(expected / 'numpy/arrayobject.h') in headers
                  and all(Path(name).is_relative_to(expected) for name in headers))
    manifest['header_audit'] = 'PASS' if headers_ok else 'FAILED'
    code = result.returncode
    if not code and not headers_ok:
        code = 1
        print('NumPy header mismatch: see build.json and build.log.')
    if not code:
        probe = subprocess.run([
            sys.executable, '-c',
            'import importlib.util, sys; '
            's=importlib.util.spec_from_file_location("bridct_numpy", sys.argv[1]); '
            'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
            'p=m.Plan(8,8); p.close(); print("PASS: import and plan creation")',
            str(target)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / 'import-check.log').write_text(probe.stdout)
        manifest['import_check'] = 'PASS' if probe.returncode == 0 else 'FAILED'
        code = probe.returncode
    manifest['status'] = 'BUILT' if code == 0 else 'FAILED'
    if result.returncode == 0:
        manifest['sha256']['extension'] = digest(target)
    (output / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'status': manifest['status'], 'output': str(target)}))
    if code:
        print(result.stdout)
        if (output / 'import-check.log').exists():
            print((output / 'import-check.log').read_text())
        raise SystemExit(code)



if __name__ == '__main__':
    main()
