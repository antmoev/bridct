"""Build the test-only NumPy allocation hook using the extension's compiler command."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sysconfig

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(__doc__)
parser.add_argument('--build-dir', type=Path, default=ROOT / 'build')
args = parser.parse_args()
build = args.build_dir.resolve()
config = json.loads((build / 'build.json').read_text())
source = ROOT / 'test_allocator.c'
target = build / ('bridct_test_allocator' + sysconfig.get_config_var('EXT_SUFFIX'))
command = [str(source) if item == str(ROOT / 'bridct_numpy.c') else
           str(target) if item == config['output'] else item
           for item in config['command'] if item != config['library']]
result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(build / 'test-allocator-build.log').write_text(result.stdout)
record = {'status': 'PASS' if result.returncode == 0 else 'FAILED', 'command': command,
          'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
if not result.returncode:
    record['binary_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
(build / 'test-allocator-build.json').write_text(json.dumps(record, indent=2) + '\n')
print(result.stdout or record['status'])
raise SystemExit(result.returncode)
