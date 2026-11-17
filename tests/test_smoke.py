"""Minimal local smoke test with synthetic data only."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tb_chatgpt_export_viewer.py"

class SmokeTest(unittest.TestCase):
    def test_export_conversion(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            input_dir = root / "export_input"
            input_dir.mkdir()
            messages = [
                {"id": "u", "message": {"author": {"role": "user"}, "create_time": 1,
                 "content": {"content_type": "text", "parts": ["Alpha needle"]}}},
                {"id": "a", "message": {"author": {"role": "assistant"}, "create_time": 2,
                 "content": {"content_type": "text", "parts": ["Beta needle"]}}},
            ]
            data = [{"title": "Test conversation", "create_time": 1, "update_time": 2,
                     "mapping": {x["id"]: x for x in messages}}]
            (input_dir / "conversations.json").write_text(json.dumps(data), encoding="utf-8")
            output = root / "viewer_dir"
            result = subprocess.run([sys.executable, str(SCRIPT), str(input_dir), "--out", str(output)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((output / "index.html").exists())
            self.assertTrue((output / "search_data.js").exists())
            self.assertIn("needle", (output / "search_data.js").read_text(encoding="utf-8"))
            self.assertIn("broken: 0", result.stdout)

if __name__ == "__main__":
    unittest.main()
