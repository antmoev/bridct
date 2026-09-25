"""Check the versioned source package byte for byte, without compiling."""
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]

def verify():
    manifest = json.loads((ROOT/'SOURCES.json').read_text())
    assert manifest['version'] == (ROOT/'VERSION').read_text().strip()
    for name, digest in manifest['sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
    data = manifest['generated_dataset']
    if (ROOT/data['path']).exists():
        assert hashlib.sha256((ROOT/data['path']).read_bytes()).hexdigest() == data['sha256']
    print(f"PASS: {len(manifest['sha256'])} package files match SOURCES.json")
    return manifest

if __name__ == '__main__':
    verify()
