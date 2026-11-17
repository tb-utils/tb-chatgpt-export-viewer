"""Regression test: index keeps its export panels expanded after browser Back."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tb_chatgpt_export_viewer.py'
spec = importlib.util.spec_from_file_location('viewer_panel_restore', SCRIPT)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class PanelRestoreTest(unittest.TestCase):
    def test_export_sections_have_stable_keys_and_restore_logic(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            export = root / 'export'
            export.mkdir()
            (export / 'conversations.json').write_text('[]')
            section = viewer.build_export_manifest_html(export, export, {}, root, 'now')
            self.assertIn('data-restore-key="export-info"', section)
            self.assertIn('data-restore-key="export-files"', section)
            viewer.build_index([], root, [], section)
            html = (root / 'index.html').read_text(encoding='utf-8')
            self.assertIn("window.addEventListener('pagehide', () => { saveQueryState(); savePanelState(); })", html)
            self.assertIn("window.addEventListener('pageshow'", html)
            self.assertIn('sessionStorage.setItem(panelStateKey', html)
            self.assertIn('history.replaceState(combined', html)
            self.assertIn('restorePanelState();', html)
            self.assertIn("inventoryScroll.addEventListener('scroll', scheduleScrollSave", html)
            self.assertIn("window.addEventListener('beforeunload', () => { saveQueryState(); savePanelState(); })", html)
            self.assertLess(html.index('sessionStorage.getItem(panelStateKey'), html.index('const state = history.state;', html.index('sessionStorage.getItem(panelStateKey')))


if __name__ == '__main__':
    unittest.main()
