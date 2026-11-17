"""CLI default input is an extracted directory relative to the caller's cwd."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tb_chatgpt_export_viewer.py'

class DefaultInputTest(unittest.TestCase):
    def test_default_extracted_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            inp = cwd / 'chatgpt_export_work'
            inp.mkdir()
            (inp / 'conversations.json').write_text(json.dumps([
                {'title': 'Test default', 'create_time': 1, 'update_time': 2,
                 'mapping': {'u': {'id': 'u', 'message': {'author': {'role': 'user'},
                 'create_time': 1, 'content': {'content_type': 'text', 'parts': ['Hello']}}}}}
            ]), encoding='utf-8')
            result = subprocess.run([sys.executable, str(SCRIPT), '--show-internal'],
                                    cwd=cwd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((cwd / 'chatgpt_export_viewer' / 'index.html').exists())
            self.assertTrue((inp / 'conversations.json').exists())

    def test_missing_default_input_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(SCRIPT), '--show-internal'],
                                    cwd=directory, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Input path does not exist', result.stderr)
            self.assertIn('chatgpt_export_work', result.stderr)
            self.assertFalse((Path(directory) / 'chatgpt_export_viewer_tmp').exists())

if __name__ == '__main__':
    unittest.main()
