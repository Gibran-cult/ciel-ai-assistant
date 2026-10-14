import ast
import hashlib
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
SOURCE = APP_PATH.read_text(encoding="utf-8")
N_MESSAGES = 10  # Agent memory window in the flow (5 question/answer turns)


def load(**constants):
    namespace = {"hashlib": hashlib, "TABLE_PREVIEW_ROWS": 20, **constants}
    for node in ast.parse(SOURCE).body:
        if isinstance(node, ast.FunctionDef) and node.name in (
            "project_signature", "project_context_due", "build_payload",
        ):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace


def app_constant(name):
    for node in ast.parse(SOURCE).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return ast.literal_eval(node.value)
    raise KeyError(name)


class ProjectContextTest(unittest.TestCase):

    def setUp(self):
        self.app = load(
            MAX_CONTEXT_CHARS=app_constant("MAX_CONTEXT_CHARS"),
            PROJECT_CONTEXT_REFRESH_TURNS=app_constant("PROJECT_CONTEXT_REFRESH_TURNS"),
        )
        self.files = [{"name": "proposal.md", "text": "isi proposal " * 1000}]

    def payload_for(self, chat, turn, files=None):
        files = self.files if files is None else files
        due = self.app["project_context_due"](chat, files, turn)
        payload = self.app["build_payload"](
            "pertanyaan?", [], files if due else [],
            project_note=() if due else [f["name"] for f in files],
        )
        if due:
            chat["project_context"] = {"signature": self.app["project_signature"](files), "turn": turn}
        return payload

    def test_project_file_reaches_the_agent_at_most_twice(self):
        # Langflow stores every message with its file text and the Agent loads
        # the last 10 messages; sending files every turn put up to 6 copies
        # of the same file into one request.
        chat, history = {}, []
        for turn in range(12):
            payload = self.payload_for(chat, turn)
            window = history[-N_MESSAGES:] + [payload]
            copies = sum("### File proyek: proposal.md" in m for m in window)
            with self.subTest(turn=turn):
                self.assertGreaterEqual(copies, 1, "the file must always be visible to the Agent")
                self.assertLessEqual(copies, 2)
            history += [payload, "jawaban"]

    def test_later_turns_only_name_the_file(self):
        chat = {}
        first = self.payload_for(chat, 0)
        second = self.payload_for(chat, 1)
        self.assertIn("isi proposal", first)
        self.assertNotIn("isi proposal", second)
        self.assertIn("isinya sudah dikirim di pesan sebelumnya dalam percakapan ini): proposal.md", second)

    def test_changed_project_files_are_sent_again(self):
        chat = {}
        self.payload_for(chat, 0)
        changed = [{"name": "proposal.md", "text": "versi baru"}]
        self.assertIn("versi baru", self.payload_for(chat, 1, files=changed))

    def test_new_chat_and_no_project(self):
        due = self.app["project_context_due"]
        self.assertTrue(due(None, self.files, 0))
        self.assertFalse(due({}, [], 3))
        self.assertEqual(self.app["build_payload"]("halo", [], []), "halo")

    def test_context_budget(self):
        self.assertLessEqual(app_constant("MAX_CONTEXT_CHARS"), 80_000)
        self.assertLess(app_constant("PROJECT_CONTEXT_REFRESH_TURNS"), N_MESSAGES // 2)


if __name__ == "__main__":
    unittest.main()
