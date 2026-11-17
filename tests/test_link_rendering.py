"""Regression tests for links misidentified in archived conversation text."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tb_chatgpt_export_viewer.py'
spec = importlib.util.spec_from_file_location('viewer_under_test', SCRIPT)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class LinkRenderingTest(unittest.TestCase):
    def test_invalid_relative_markdown_does_not_create_links(self):
        for target in ('Distortion+', 'turn0search11', 'turn0search13', 'turn0search2', r'\d{1,2}', '{img_uri}'):
            rendered = viewer.render_text('Example [text](' + target + ')')
            self.assertNotIn('<a href=', rendered, target)
            self.assertIn(target.replace('{', '{'), rendered)

    def test_valid_external_and_sandbox_links(self):
        self.assertIn('href="https://example.com/page"', viewer.render_text('[Site](https://example.com/page)'))
        viewer.ASSET_NAME_TO_HREF['example.py'] = '../assets/example.py'
        self.assertIn('href="../assets/example.py"', viewer.render_text('[example.py](sandbox:/mnt/data/example.py)'))
        viewer.ASSET_NAME_TO_HREF.clear()

    def test_export_url_ref_keeps_label_but_not_bad_href(self):
        rendered = viewer.render_text('urlYahoo Mapsturn0search11')
        self.assertIn('Yahoo Maps', rendered)
        self.assertNotIn('href="turn0search11"', rendered)
        self.assertIn('href="https://example.org"', viewer.render_text('urlExamplehttps://example.org'))

    def test_generated_html_has_no_bogus_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export = root/'export'; export.mkdir()
            content = ['Effect [x](Distortion+)', 'Unknown urlMapturn0search11', r'Pattern (20\d{2})[年/](\d{1,2})', 'Image [p]({img_uri})', '[Web](https://example.com)']
            messages = {}
            for i, txt in enumerate(content):
                messages[str(i)]={'id':str(i), 'message':{'author':{'role':'user'},'create_time':i+1,'content':{'content_type':'text','parts':[txt]}}}
            (export/'conversations.json').write_text(json.dumps([{'title':'Links','mapping':messages,'create_time':1,'update_time':5}]),encoding='utf-8')
            out=root/'view'
            result = subprocess.run([sys.executable,str(SCRIPT),str(export),'--out',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('broken: 0',result.stdout)
            html=(next((out/'chats').glob('*.html'))).read_text('utf-8')
            for bad in ('Distortion+', 'turn0search11',r'\d{1,2}', '{img_uri}'):
                self.assertNotIn('href="'+bad+'"',html)

if __name__ == '__main__':
    unittest.main()
