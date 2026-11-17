"""Regression tests for generated-page local-link validation."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tb_chatgpt_export_viewer.py"
spec = importlib.util.spec_from_file_location("tb_chatgpt_export_viewer", SCRIPT)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class LocalLinkValidationTest(unittest.TestCase):
    def test_ignores_html_stored_as_user_attachment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "chats").mkdir()
            (out / "assets").mkdir()
            (out / "index.html").write_text('<a href="chats/test.html">Open</a>', encoding="utf-8")
            (out / "chats" / "test.html").write_text('<a href="../assets/photo.png">Photo</a>', encoding="utf-8")
            (out / "assets" / "photo.png").write_bytes(b"PNG placeholder")
            # A copied uploaded HTML may contain its own obsolete relative links.
            (out / "assets" / "previous_viewer.html").write_text(
                '<a href="../assets/nonexistent.dat">Old link</a>', encoding="utf-8"
            )
            checked, missing = viewer.validate_local_links(out)
            self.assertEqual(checked, 2)
            self.assertEqual(missing, [])

    def test_ignores_link_like_strings_in_message_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "chats").mkdir()
            (out / "index.html").write_text('<a href="chats/test.html">Open</a>', encoding="utf-8")
            # These look like links to a regex but are not HTML link attributes.
            (out / "chats" / "test.html").write_text(
                '<pre>&lt;a href="turn0search11"&gt;link&lt;/a&gt;</pre>'
                '<code>href="Distortion+"</code>'
                '<p>src="{img_uri}" and href="\\d{1,2}" are examples.</p>'
                '<a href="../index.html">Index</a>', encoding="utf-8"
            )
            checked, missing = viewer.validate_local_links(out)
            self.assertEqual(checked, 2)
            self.assertEqual(missing, [])

    def test_skips_external_and_anchor_links_but_checks_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "chats").mkdir()
            (out / "index.html").write_text(
                '<a href="https://example.org/">External</a>'
                '<a href="#top">Top</a>'
                '<script src="search_data.js"></script>', encoding="utf-8"
            )
            (out / "search_data.js").write_text("window.SEARCH_DATA = {};",encoding="utf-8")
            checked, missing = viewer.validate_local_links(out)
            self.assertEqual(checked, 1)
            self.assertEqual(missing, [])

    def test_still_reports_broken_links_in_generated_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "chats").mkdir()
            (out / "index.html").write_text('<a href="chats/test.html">Open</a>', encoding="utf-8")
            (out / "chats" / "test.html").write_text(
                '<a href="../assets/missing.png">Missing</a>', encoding="utf-8"
            )
            checked, missing = viewer.validate_local_links(out)
            self.assertEqual(checked, 2)
            self.assertEqual(len(missing), 1)
            self.assertIn('chats', missing[0])
            self.assertIn('missing.png', missing[0])


if __name__ == "__main__":
    unittest.main()
