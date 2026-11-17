import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'tb_chatgpt_export_viewer.py'
spec = importlib.util.spec_from_file_location('viewer', SOURCE)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


def node(parent, role, content_type, text, t):
    contents = {'content_type': content_type}
    if content_type == 'text':
        contents['parts'] = [text]
    elif content_type == 'reasoning_recap':
        contents['content'] = text
    else:
        contents['thoughts'] = []
    return {'parent': parent, 'message': {'author': {'role': role}, 'create_time': t, 'content': contents}}


class BranchInternalTests(unittest.TestCase):
    def test_internal_before_own_answer_not_other_branch(self):
        c = {'current_node': 'mainanswer', 'mapping': {
            'question': node(None, 'user', 'text', 'question', 1),
            'mainthought': node('question', 'assistant', 'thoughts', '', 5),
            'mainrecap': node('mainthought', 'assistant', 'reasoning_recap', 'main recap', 5.1),
            'mainanswer': node('mainrecap', 'assistant', 'text', 'main answer', 2),
            'altthought': node('question', 'assistant', 'thoughts', '', 6),
            'altrecap': node('altthought', 'assistant', 'reasoning_recap', 'alternative recap', 6.1),
            'altanswer': node('altrecap', 'assistant', 'text', 'alternative answer', 2.1),
        }}
        msgs = viewer.walk_messages(c, show_internal=True)
        ids = [m['_node_id'] for m in msgs]
        self.assertEqual(ids, ['question', 'mainthought', 'mainrecap', 'mainanswer',
                               'altthought', 'altrecap', 'altanswer'])
        self.assertEqual([m['_branch'] for m in msgs[1:4]], ['main'] * 3)
        self.assertEqual(len(set(m['_branch'] for m in msgs[4:])), 1)
        self.assertEqual(len(viewer.walk_messages(c, show_internal=False)), 3)

    def test_fallback_does_not_cross_branches(self):
        ms = [
            {'_branch': 'main', '_node_id': 'a', 'author': {'role': 'assistant'}},
            {'_branch': 1, '_node_id': 'b', '_internal_type': 'thoughts'},
        ]
        self.assertEqual(viewer.reorder_internal_blocks_before_assistant(ms), ms)


class MarkdownTableTests(unittest.TestCase):
    def test_standard_table(self):
        raw = '| Name | Value |\n|---|---|\n| **A** | `1` |\n| B | 2 |'
        output = viewer.render_text(raw)
        self.assertIn('<table', output)
        self.assertEqual(output.count('<tr>'), 3)
        self.assertIn('<strong>A</strong>', output)
        self.assertIn('<code>1</code>', output)

    def test_alignment_and_escaped_pipe(self):
        raw = 'Topic | Formula | Result\n:--- | :---: | ---:\nA | `x|y` | left\\|right'
        output = viewer.render_text(raw)
        self.assertIn('text-align:center', output)
        self.assertIn('text-align:right', output)
        self.assertIn('<code>x|y</code>', output)
        self.assertIn('left|right', output)

    def test_non_table_and_fenced_code_unchanged(self):
        self.assertNotIn('<table', viewer.render_text('foo | bar\nnot a separator'))
        self.assertNotIn('<table', viewer.render_text('```markdown\n| x | y |\n|---|---|\n```'))
        self.assertIn('<pre class="code">', viewer.render_text('```markdown\n| x | y |\n|---|---|\n```'))

    def test_table_followed_by_normal_paragraph(self):
        output = viewer.render_text('| A | B |\n|---|---|\n| x | y |\nAn explanation follows.')
        self.assertIn('</table>', output)
        self.assertIn('<p>An explanation follows.</p>', output)


if __name__ == '__main__':
    unittest.main()
