import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_api.model import FINISH, ModelReply, ScriptedModel, Step, TaskView  # noqa: E402

VIEW = TaskView("Cari mouse", ("Buka toko",), (), (), "")


class ScriptedModelTest(unittest.TestCase):
    def test_replays_plan_and_calls(self):
        model = ScriptedModel({"steps": ["a"]}, [{"tool": "tab_read", "args": {}}], cost=3)
        self.assertEqual(model.plan("x"), ModelReply({"steps": ["a"]}, 3))
        self.assertEqual(model.act(VIEW), ModelReply({"tool": "tab_read", "args": {}}, 3))
        self.assertEqual(model.act(VIEW).output, {"tool": "finish", "args": {"report": "selesai"}})
        self.assertEqual(model.act(VIEW).output, FINISH)
        self.assertEqual(model.views, [VIEW, VIEW, VIEW])
        self.assertEqual(model.instructions, ["x"])

    def test_raises_scripted_errors(self):
        with self.assertRaises(TimeoutError):
            ScriptedModel({}, [TimeoutError("lambat")]).act(VIEW)

        with self.assertRaises(ConnectionError):
            ScriptedModel(ConnectionError("putus"), []).plan("x")

    def test_the_script_is_not_shared_between_models(self):
        calls = [{"tool": "tab_read", "args": {}}]
        ScriptedModel({}, calls).act(VIEW)
        self.assertEqual(len(calls), 1)

    def test_views_and_steps_are_immutable(self):
        with self.assertRaises(Exception):
            VIEW.instruction = "y"

        with self.assertRaises(Exception):
            Step("tab_read", "allow", None, "ok").outcome = "block"


if __name__ == "__main__":
    unittest.main()
