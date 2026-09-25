from pathlib import Path
import json, shutil, sys, tempfile, unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'dataset'))
from verify import verify
from evaluate import error_norm

class DatasetContract(unittest.TestCase):
    def test_reference(self):
        self.assertEqual(verify()['arrays'], 474)

    def test_corrupt_archive_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            shutil.copyfile(ROOT/'dataset/manifest.json', target/'manifest.json')
            payload = bytearray((ROOT/'dataset/inputs.npz').read_bytes())
            payload[-10] ^= 1
            (target/'inputs.npz').write_bytes(payload)
            with self.assertRaises(AssertionError):
                verify(target)

    def test_duplicate_case_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            shutil.copyfile(ROOT/'dataset/inputs.npz', target/'inputs.npz')
            manifest = json.loads((ROOT/'dataset/manifest.json').read_text())
            manifest['cases'][1] = manifest['cases'][0]
            (target/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(AssertionError):
                verify(target)

    def test_tiny_signal_not_hidden(self):
        expected = np.array([1e-30], dtype=np.float64)
        self.assertEqual(error_norm(np.zeros(1), expected, 1e-30), 1.0)

    def test_zero_and_nonfinite(self):
        self.assertEqual(error_norm(np.zeros(2), np.zeros(2), 0.0), 0.0)
        self.assertIsNone(error_norm(np.ones(2), np.zeros(2), 0.0))
        self.assertIsNone(error_norm(np.array([np.inf]), np.zeros(1), 1.0))

if __name__ == '__main__':
    unittest.main()
