"""Regression tests for search query preservation on Reload and Back/Forward."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tb_chatgpt_export_viewer.py'
spec = importlib.util.spec_from_file_location('viewer_query_reload', SCRIPT)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class QueryReloadTests(unittest.TestCase):
    def test_index_persists_query_on_input_and_reloads(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            viewer.build_index(
                [{'title':'Search test', 'file':'test.html', 'create':'', 'update':'', 'message_count':1}],
                out, [{'conv':0,'id':0,'text':'persistent keyword'}])
            html = (out / 'index.html').read_text(encoding='utf-8')
            self.assertIn("'tb-chatgpt-export-viewer:query:' + location.pathname", html)
            self.assertIn('sessionStorage.setItem(queryStateKey', html)
            self.assertIn('sessionStorage.getItem(queryStateKey', html)
            self.assertIn('history.replaceState(combined', html)
            self.assertIn('saveQueryState();\n    clearTimeout(debounce);', html)
            self.assertIn("window.addEventListener('pageshow', () => {\n    restorePanelState();\n    restoreQueryState();", html)
            self.assertIn("window.addEventListener('beforeunload', () => { saveQueryState(); savePanelState(); });", html)
            self.assertIn('  restoreQueryState();\n\n  // On Back/Forward', html)


if __name__ == '__main__':
    unittest.main()
