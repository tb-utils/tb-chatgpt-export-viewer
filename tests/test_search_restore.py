"""Regression checks for search restoration after browser Back/Forward navigation."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tb_chatgpt_export_viewer.py'
spec = importlib.util.spec_from_file_location('viewer_search_restore', SCRIPT)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class SearchRestoreTests(unittest.TestCase):
    def test_generated_index_searches_on_pageshow(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d)
            conversation = {'title': 'Scale study', 'file': 'scale.html', 'create': '2026-01-01',
                            'update': '2026-01-02', 'message_count': 1}
            viewer.build_index([conversation], output, [
                {'conv': 0, 'id': 0, 'text': 'musical scale'}
            ])
            html = (output / 'index.html').read_text(encoding='utf-8')
            self.assertIn("input.addEventListener('input'", html)
            self.assertIn("window.addEventListener('pageshow'", html)
            self.assertIn("clearTimeout(debounce);\n    search();", html)
            self.assertIn("  search();\n})();", html)
            self.assertTrue((output / 'search_data.js').is_file())


if __name__ == '__main__':
    unittest.main()
