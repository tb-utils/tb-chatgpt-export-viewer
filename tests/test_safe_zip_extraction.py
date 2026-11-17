"""ZIP extraction must never destroy a previously extracted export on failure."""
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import importlib.util

SCRIPT = Path(__file__).resolve().parents[1] / 'tb_chatgpt_export_viewer.py'
spec = importlib.util.spec_from_file_location('viewer', SCRIPT)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


def make_zip(path, content=None):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('conversations.json', json.dumps(content if content is not None else []))
        z.writestr('ads.json', '{}')


class SafeZipExtractionTest(unittest.TestCase):
    def test_success_replaces_work_and_removes_old_files(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            work = base / 'chatgpt_export_work'
            work.mkdir()
            (work / 'old-only.txt').write_text('old')
            z = base / 'export.zip'
            make_zip(z)
            result = viewer.prepare_input(z, base / 'viewer', str(work))
            self.assertEqual(result, work)
            self.assertFalse((work / 'old-only.txt').exists())
            self.assertTrue((work / 'conversations.json').exists())
            self.assertFalse(list(base.glob('chatgpt_export_work_extract_*')))
            self.assertFalse(list(base.glob('chatgpt_export_work_backup_*')))

    def test_broken_zip_leaves_previous_work_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            work = base / 'chatgpt_export_work'
            work.mkdir()
            (work / 'ads.json').write_text('existing data')
            z = base / 'broken.zip'
            z.write_text('not a ZIP')
            with self.assertRaises(SystemExit):
                viewer.prepare_input(z, base / 'viewer', str(work))
            self.assertEqual((work / 'ads.json').read_text(), 'existing data')
            self.assertFalse(list(base.glob('chatgpt_export_work_extract_*')))

    def test_missing_conversations_json_leaves_work_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            work = base / 'chatgpt_export_work'
            work.mkdir()
            (work / 'old').write_text('old')
            z = base / 'wrong.zip'
            with zipfile.ZipFile(z, 'w') as archive:
                archive.writestr('ads.json', '[]')
            with self.assertRaises(SystemExit):
                viewer.prepare_input(z, base / 'viewer', str(work))
            self.assertEqual((work / 'old').read_text(), 'old')

    def test_denied_rename_preserves_existing_work(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            work = base / 'chatgpt_export_work'
            work.mkdir()
            (work / 'ads.json').write_text('original')
            z = base / 'export.zip'
            make_zip(z)
            real_rename = Path.rename
            def refuse_original(self, target):
                if self == work:
                    raise PermissionError('simulated locked file')
                return real_rename(self, target)
            with patch.object(Path, 'rename', refuse_original):
                with self.assertRaises(SystemExit) as cm:
                    viewer.prepare_input(z, base / 'viewer', str(work))
            self.assertIn('existing data was not changed', str(cm.exception))
            self.assertEqual((work / 'ads.json').read_text(), 'original')
            self.assertFalse(list(base.glob('chatgpt_export_work_extract_*')))

    def test_staging_install_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            work = base / 'chatgpt_export_work'
            work.mkdir()
            (work / 'ads.json').write_text('original')
            z = base / 'export.zip'
            make_zip(z)
            real_rename = Path.rename
            def refuse_staging(self, target):
                if self.name.startswith('chatgpt_export_work_extract_'):
                    raise PermissionError('simulated blocked install')
                return real_rename(self, target)
            with patch.object(Path, 'rename', refuse_staging):
                with self.assertRaises(SystemExit) as cm:
                    viewer.prepare_input(z, base / 'viewer', str(work))
            self.assertIn('previous directory was restored', str(cm.exception))
            self.assertEqual((work / 'ads.json').read_text(), 'original')
            self.assertFalse(list(base.glob('chatgpt_export_work_backup_*')))

    def test_zip_inside_work_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            work = base / 'chatgpt_export_work'
            work.mkdir()
            z = work / 'export.zip'
            make_zip(z)
            with self.assertRaises(SystemExit) as cm:
                viewer.prepare_input(z, base / 'viewer', str(work))
            self.assertIn('must not be inside', str(cm.exception))
            self.assertTrue(z.exists())

    def test_cli_failure_does_not_create_empty_output_tmp(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            work = base / 'chatgpt_export_work'
            work.mkdir()
            (work / 'ads.json').write_text('old')
            bad_zip = base / 'broken.zip'
            bad_zip.write_text('bad')
            result = subprocess.run([sys.executable, str(SCRIPT), str(bad_zip),
                                     '--work', str(work), '--out', str(base / 'viewer')],
                                     capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((work / 'ads.json').read_text(), 'old')
            self.assertFalse((base / 'viewer_tmp').exists())


if __name__ == '__main__':
    unittest.main()
