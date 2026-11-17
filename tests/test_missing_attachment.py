import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from zipfile import ZipFile

import tb_chatgpt_export_viewer as viewer


class MissingAttachmentTests(unittest.TestCase):
    def test_missing_audio_retains_reference(self):
        ref = {"content_type": "audio_asset_pointer", "asset_pointer": "sediment://file_abc", "format": "wav"}
        html = viewer.render_attachment_record({"ref": ref, "fid": "file_unknown", "name": "Attachment", "path": None, "original_name": None}, Path('.'), Path('.'))
        self.assertIn('Audio (WAV)', html)
        self.assertIn('sediment://file_abc', html)
        self.assertIn('source file not found', html)
        self.assertNotIn('href=', html)

    def test_missing_named_document_keeps_name_and_id(self):
        ref = {"id": "file-abc", "name": "Example.docx", "mime_type": "application/test"}
        html = viewer.render_attachment_record({"ref": ref, "fid": "file-abc", "name": "Example.docx", "path": None, "original_name": "Example.docx"}, Path('.'), Path('.'))
        self.assertIn('Example.docx', html)
        self.assertIn('file-abc', html)
        self.assertNotIn('href=', html)

    def test_missing_metadata_is_escaped(self):
        ref = {"content_type": "audio_asset_pointer", "asset_pointer": 'sediment://<script>alert(1)</script>', "format": "wav"}
        html = viewer.render_attachment_record({"ref": ref, "fid": "file_unknown", "name": "Attachment", "path": None}, Path('.'), Path('.'))
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_zip_extraction_prints_start_and_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'export.zip'
            with ZipFile(archive, 'w') as z:
                z.writestr('conversations.json', '[]')
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = viewer.prepare_input(archive, root / 'out', str(root / 'work'))
            self.assertEqual(result, root / 'work')
            self.assertTrue((result / 'conversations.json').exists())
            self.assertIn('ZIP extraction started', buf.getvalue())
            self.assertIn('ZIP extraction completed', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
