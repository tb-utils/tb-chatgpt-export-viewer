"""Regression tests for file-service:// image pointers in ChatGPT exports."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tb_chatgpt_export_viewer as viewer


class FileServiceAssetIDTests(unittest.TestCase):
    FILE_IDS = (
        'file-4YgTmy7ojE4Hjh1qMwNYRX',
        'file-WUxLPCUHjXnwrAihnV7XDV',
    )

    def test_two_real_reported_pointers_resolve_to_file_ids(self):
        for fid in self.FILE_IDS:
            with self.subTest(fid=fid):
                self.assertEqual(
                    viewer.attachment_file_id(
                        {'content_type': 'image_asset_pointer',
                         'asset_pointer': f'file-service://{fid}'}, None), fid)

    def test_standard_ids_and_explicit_id_still_work(self):
        for fid in ('file_000000000000abcd', 'file-AbC_123-xy'):
            with self.subTest(fid=fid):
                self.assertEqual(viewer.attachment_file_id({'id': fid}, None), fid)

    def test_invalid_service_pointer_can_fall_back_to_source_filename(self):
        fid = self.FILE_IDS[0]
        self.assertEqual(viewer.attachment_file_id(
            {'asset_pointer': 'file-service://unidentified'}, Path(fid + '.dat')), fid)

    def test_pointers_reuse_pre_copied_assets_without_copying_raw_dat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            assets = root / 'assets'
            sources = {}
            for fid in self.FILE_IDS:
                source = root / f'{fid}.dat'
                source.write_bytes(b'PNG fixture data')
                sources[fid] = source
            original_names = {fid: 'タイトルなし.png' for fid in self.FILE_IDS}
            pre_copied = viewer.pre_copy_all_dat_assets(root, assets, {}, original_names)
            self.assertEqual(len(pre_copied), 2)
            with patch.object(viewer, 'copy_asset', side_effect=AssertionError('unexpected re-copy')):
                for fid, source in sources.items():
                    ref = {'content_type': 'image_asset_pointer',
                           'asset_pointer': f'file-service://{fid}'}
                    self.assertEqual(viewer.attachment_file_id(ref, source), fid)
                    rendered = viewer.render_attachment(ref, root, assets,
                        {fid: source}, original_names, pre_copied)
                    self.assertIn('.png', rendered)
                    self.assertIn('href=', rendered)
            self.assertFalse(list(assets.glob('*.dat')))


if __name__ == '__main__':
    unittest.main()
