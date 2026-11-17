import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'tb_chatgpt_export_viewer.py'
spec = importlib.util.spec_from_file_location('viewer', SOURCE)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


def node(parent, text='', role='assistant', t=1):
    return {'parent': parent, 'message': {'author': {'role': role}, 'create_time': t,
            'content': {'content_type': 'text', 'parts': [text]}}}

class BranchTests(unittest.TestCase):
    def test_main_and_alternate_subtree(self):
        conv = {'title': 'Test', 'current_node': 'end', 'mapping': {
            'start': node(None, 'question', 'user', 1),
            'answer': node('start', 'chosen answer', t=2),
            'end': node('answer', 'followup', 'user', 4),
            'other': node('start', 'other answer', t=2.1),
            'child': node('other', 'other child', t=3),
        }}
        main, branch_ids, origins = viewer.classify_branches(conv)
        self.assertEqual(main, {'start', 'answer', 'end'})
        self.assertEqual(branch_ids['other'], branch_ids['child'])
        self.assertEqual(origins[branch_ids['other']], 'start')
        messages = viewer.walk_messages(conv)
        alternate = [m for m in messages if isinstance(m['_branch'], int)]
        self.assertEqual(len(alternate), 2)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'chats' / 'test.html'
            output.parent.mkdir()
            viewer.build_chat_page(conv, messages, output, root, root / 'assets', {}, {}, {})
            html = output.read_text('utf-8')
            self.assertIn('Conversation paths', html)
            self.assertIn('branch-label alt', html)
            self.assertIn('Diverged from #m0', html)
            self.assertIn('Main (3)', html)
            self.assertIn('Branch 1 (2)', html)

    def test_multiple_siblings_and_current_node(self):
        conv = {'current_node':'selected','mapping': {
            'root': node(None,'hello','user',1),
            'selected': node('root','selected',t=4),
            'alt1': node('root','alt1',t=2),
            'alt2': node('root','alt2',t=3),
        }}
        main, others, parents = viewer.classify_branches(conv)
        self.assertIn('selected', main)
        self.assertNotEqual(others['alt1'], others['alt2'])
        self.assertEqual(set(parents.values()), {'root'})

    def test_missing_current_node_safe(self):
        conv = {'mapping': {'a': node(None, 'hello')}}
        self.assertEqual(viewer.classify_branches(conv), (set(), {}, {}))
        self.assertIsNone(viewer.walk_messages(conv)[0]['_branch'])

if __name__=='__main__': unittest.main()
