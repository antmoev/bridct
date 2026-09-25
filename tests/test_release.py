"""Verify archive determinism, platform identity and rejection of source drift."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT / 'distribution/build_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'
            release.build(ROOT, a)
            release.build(ROOT, b)
            platforms = []
            for path in sorted(a.glob('*.zip')):
                self.assertEqual(path.read_bytes(), (b / path.name).read_bytes())
                with zipfile.ZipFile(path) as z:
                    files = {n.split('/', 1)[1]: z.read(n) for n in z.namelist()}
                for line in files['SHA256SUMS'].decode().splitlines():
                    sha, name = line.split(maxsplit=1)
                    self.assertEqual(sha, hashlib.sha256(files[name]).hexdigest(), name)
                if 'SOURCES.json' in files:
                    m = json.loads(files['SOURCES.json'])
                    for name, sha in m['sha256'].items():
                        self.assertEqual(sha, hashlib.sha256(files[name]).hexdigest(), name)
                    platforms.append(files)
            self.assertEqual(len(platforms), 3)
            for name in platforms[0]:
                if name not in ('START_HERE.md', 'SOURCES.json', 'SHA256SUMS'):
                    self.assertTrue(all(p[name] == platforms[0][name] for p in platforms), name)
            with self.assertRaises(FileExistsError):
                release.build(ROOT, a)

    def test_drift_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in json.loads((ROOT / 'distribution/files.json').read_text()):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, path)
            kernel = root / 'src/bridct.c'
            kernel.write_bytes(kernel.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'Paper source changed'):
                release.source_files(root)
            shutil.copyfile(ROOT / 'src/bridct.c', kernel)
            corpus = root / 'dataset/inputs.npz'
            corpus.write_bytes(corpus.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'Paper source changed|Verification corpus differs'):
                release.source_files(root)


if __name__ == '__main__':
    unittest.main()
