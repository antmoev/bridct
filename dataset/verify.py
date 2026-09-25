"""Verify immutable dataset bytes, metadata and array layout."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np

ROOT = Path(__file__).resolve().parent

def verify(directory=ROOT):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    archive = directory / 'inputs.npz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['archive_sha256'], 'Archive hash mismatch'
    assert len(manifest['cases']) == 474
    ids = [case['id'] for case in manifest['cases']]
    assert len(ids) == len(set(ids))
    with np.load(archive, allow_pickle=False) as arrays:
        assert set(arrays.files) == set(ids)
        for case in manifest['cases']:
            x = arrays[case['id']]
            assert x.shape == (case['N'], case['N']) and x.dtype == np.dtype('<f4')
            assert np.isfinite(x).all()
            digest = hashlib.sha256(x.tobytes(order='C')).hexdigest()
            assert digest == case['sha256'], case['id']
    result = {'status': 'PASS', 'arrays': len(ids),
              'core': sum(c['domain'] == 'core' for c in manifest['cases']),
              'boundary': sum(c['domain'] != 'core' for c in manifest['cases']),
              'archive_sha256': manifest['archive_sha256']}
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT)
    print(json.dumps(verify(parser.parse_args().directory), indent=2))
