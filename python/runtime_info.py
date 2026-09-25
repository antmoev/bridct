"""Record the actually imported Python, NumPy, SciPy, and BRiDCT environment."""
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import platform
import sys
import sysconfig

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(__doc__)
parser.add_argument('--module-dir', type=Path, default=ROOT / 'build')
parser.add_argument('--output', type=Path)
args = parser.parse_args()
module_dir = args.module_dir.resolve()
args.output = args.output or module_dir / 'import-diagnostics.json'
sys.path.insert(0, str(module_dir))
record = {
    'status': 'STARTED', 'platform': platform.platform(), 'machine': platform.machine(),
    'python': sys.version, 'executable': sys.executable, 'implementation': sys.implementation.name,
    'byteorder': sys.byteorder, 'pointer_bytes': __import__('struct').calcsize('P'),
    'extension_suffix': sysconfig.get_config_var('EXT_SUFFIX'),
    'gil_disabled': bool(sysconfig.get_config_var('Py_GIL_DISABLED')),
    'requested_module_directory': str(module_dir), 'imports': {},
}
failed = False
for name in ('numpy', 'scipy', 'bridct_numpy'):
    try:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        item = {'file': str(path), 'version': getattr(module, '__version__', None)}
        if name == 'bridct_numpy':
            if path.parent != module_dir:
                raise RuntimeError('Imported a different extension from the requested build directory.')
            item.update(core_version=module.core_version,
                        core_version_source='Compile-time bridct.h; the linked archive hash identifies the implementation.',
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        record['imports'][name] = item
    except Exception as error:
        failed = True
        record['imports'][name] = {'error': repr(error)}
record['status'] = 'FAILED' if failed else 'PASS'
args.output.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
raise SystemExit(1 if failed else 0)
