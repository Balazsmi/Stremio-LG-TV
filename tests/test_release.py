"""Release gates must reject a mismatched tag before writing any artifacts."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_mismatched_tag_cannot_build_release(self):
        existing = {path.name: path.read_bytes() for path in (ROOT / 'dist').glob('*') if path.is_file()}
        result = subprocess.run(
            [sys.executable, str(ROOT / 'tools' / 'build_ipk.py'), '--tag', 'v999999.0.0'],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        version = json.loads((ROOT / 'appinfo.json').read_text(encoding='utf-8'))['version']
        self.assertIn(f'must match appinfo.json: v{version}', result.stderr)
        after = {path.name: path.read_bytes() for path in (ROOT / 'dist').glob('*') if path.is_file()}
        self.assertEqual(after, existing)


if __name__ == '__main__':
    unittest.main()
