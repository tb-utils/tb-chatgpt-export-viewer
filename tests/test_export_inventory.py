import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('viewer_under_test', ROOT / 'tb_chatgpt_export_viewer.py')
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class ExportInventoryTests(unittest.TestCase):
    def test_zip_metadata_nested_files_and_renamed_dat_link(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            exported = base / 'extracted'
            assets = base / 'output' / 'assets'
            exported.mkdir()
            assets.mkdir(parents=True)
            source = exported / 'file_abcdef123456.dat'
            source.write_bytes(b'abcdef')
            (exported / 'sites').mkdir()
            (exported / 'sites' / 'export_manifest.json').write_text('{}')
            archive = base / 'my_export.zip'
            archive.write_bytes(b'zipfake')
            restored = assets / '日本語 サンプル.txt'
            restored.write_bytes(b'abcdef')
            recs = {'file_abcdef123456': {'asset_name': restored.name}}
            result = viewer.build_export_manifest_html(exported, archive, recs, assets, '2026-11-13 20:00:00')
            for expected in ['my_export.zip', '7 bytes', 'file_abcdef123456.dat', 'sites/export_manifest.json',
                             '日本語 サンプル.txt', 'assets/%E6%97%A5%E6%9C%AC%E8%AA%9E%20%E3%82%B5%E3%83%B3%E3%83%97%E3%83%AB.txt',
                             '2026-11-13 20:00:00', 'tb_chatgpt_export_viewer.py', viewer.PROGRAM_VERSION, '6']:
                self.assertIn(expected, result)

    def test_extracted_input_has_no_zip_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'conversations.json').write_text('[]')
            text = viewer.build_export_manifest_html(root, root, {}, root, 'now')
            self.assertIn('conversations.json', text)
            self.assertNotIn('Source ZIP:', text)

    def test_missing_dat_not_linked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'file_123abc.dat').write_bytes(b'x')
            text = viewer.build_export_manifest_html(root, root, {'file_123abc': {'asset_name': 'missing.txt'}}, root, 'now')
            self.assertIn('(not found)', text)
            self.assertNotIn('<a href="assets/missing.txt"', text)


if __name__ == '__main__':
    unittest.main()
