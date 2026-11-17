"""Regression: a reasoning recap may be a child, not a parent, of an answer."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tb_chatgpt_export_viewer.py"
spec = importlib.util.spec_from_file_location("viewer", SCRIPT)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class ChildRecapTest(unittest.TestCase):
    def test_child_recap_and_parent_thoughts_both_before_assistant(self):
        def node(parent, kind, timestamp, role="assistant", text=""):
            return {"parent": parent, "message": {
                "author": {"role": role}, "create_time": timestamp,
                "content": {"content_type": kind, "parts": [text]} if kind == "text"
                           else {"content_type": kind, "content": "duration"},
            }}
        # Main and alternate share a user. Main has its own answer and recap.
        mapping = {
            "user": node(None, "text", 1, "user", "question"),
            "main_thought": node("user", "thoughts", 5),
            "main_answer": node("main_thought", "text", 3, text="main reply"),
            "main_recap": node("main_answer", "reasoning_recap", 6),
            "alt_thought": node("user", "thoughts", 14),
            "alt_answer": node("alt_thought", "text", 12, text="alternate reply"),
            "alt_recap": node("alt_answer", "reasoning_recap", 18),
        }
        conv = {"current_node": "main_recap", "mapping": mapping}
        actual = viewer.walk_messages(conv, show_internal=True)
        ids = [m["_node_id"] for m in actual]
        for prefix, answer in [("main", "main_answer"), ("alt", "alt_answer")]:
            index = ids.index(answer)
            self.assertEqual(ids[index-2:index], [prefix+"_thought", prefix+"_recap"])
            self.assertEqual(actual[index-1]["_branch"], actual[index]["_branch"])

if __name__ == "__main__":
    unittest.main()
