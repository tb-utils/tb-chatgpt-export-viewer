import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tb_chatgpt_export_viewer.py'
spec = importlib.util.spec_from_file_location('viewer_v109', SCRIPT)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)

class GeneratedFilesAndProgress(unittest.TestCase):
    def tearDown(self):
        viewer.ASSET_NAME_TO_HREF.clear()

    def test_generated_file_uses_filename_and_keeps_label(self):
        viewer.ASSET_NAME_TO_HREF['sakutaro_ver13_kyuji_complete.html'] = '../assets/sakutaro_ver13_kyuji_complete.html'
        result = viewer.render_text('[Ver.13（旧字異字一覧ベース広域変換版）](sandbox:/mnt/data/sakutaro_ver13_kyuji_complete.html)')
        self.assertIn('>sakutaro_ver13_kyuji_complete.html</a>', result)
        self.assertIn('Ver.13（旧字異字一覧ベース広域変換版）', result)
        self.assertIn('href="../assets/sakutaro_ver13_kyuji_complete.html"', result)

    def test_missing_file_is_not_an_anchor_but_keeps_name_label(self):
        result = viewer.render_text('[Ver.11](sandbox:/mnt/data/sakutaro_ver11_kyujitai_full.html)')
        self.assertIn('sakutaro_ver11_kyujitai_full.html', result)
        self.assertIn('(Ver.11)', result)
        self.assertIn('not found in assets', result)
        self.assertNotIn('<a href=', result)

    def test_matching_label_not_repeated(self):
        viewer.ASSET_NAME_TO_HREF['file.py'] = '../assets/file.py'
        result = viewer.render_text('[file.py](sandbox:/mnt/data/file.py)')
        self.assertNotIn('(file.py)', result)

    def test_pre_copy_reports_progress(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)/'export'; root.mkdir()
            for i in range(26):
                (root/f'file_{i:032x}.dat').write_bytes(b'abc')
            output = Path(td)/'assets'
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                r = viewer.pre_copy_all_dat_assets(root, output, {}, {})
            text = buf.getvalue()
            self.assertIn('0/26', text)
            self.assertIn('25/26', text)
            self.assertIn('26/26', text)
            self.assertEqual(len(r), 26)

if __name__ == '__main__':
    unittest.main()
