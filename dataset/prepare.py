"""Regenerate the reference corpus without changing its recorded manifest."""
from pathlib import Path
import hashlib, json, shutil, tempfile
from corpus import save
from verify import verify, ROOT

if (ROOT / 'inputs.npz').exists():
    print(json.dumps(verify(), indent=2))
else:
    recorded = json.loads((ROOT / 'manifest.json').read_text())
    assert hashlib.sha256((ROOT / 'corpus.py').read_bytes()).hexdigest() == recorded['generator_sha256']
    with tempfile.TemporaryDirectory(prefix='bridct-corpus-') as temp:
        generated = save(temp)
        if generated['archive_sha256'] != recorded['archive_sha256']:
            raise RuntimeError('Regeneration differs from the reference bytes. Use the published dataset archive; do not replace the expected hash.')
        shutil.copyfile(Path(temp) / 'inputs.npz', ROOT / 'inputs.npz')
    print(json.dumps(verify(), indent=2))
