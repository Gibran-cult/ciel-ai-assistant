"""Cache jawaban di app.py: kapan dipakai, kapan diisi, dan konteks pesan lanjutan."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from answer_cache import cacheable_question, question_key  # noqa: E402
from tests.test_ciel_pro import SOURCE, load_app  # noqa: E402

NAMES = {"answer_cache_key", "cached_turn_context"}
PLAIN = {"text": "Apa itu AI?", "payload": "Apa itu AI?", "images": []}

# Jalur kirim pesan: blok top-level `if pending_request:` di akhir app.py.
SEND_PATH = SOURCE[SOURCE.rindex("\nif pending_request:"):]


def load(chat_tables=lambda chat: {}):
    return load_app(NAMES, chat_tables=chat_tables, question_key=question_key, cacheable_question=cacheable_question)


class AnswerCacheKeyTest(unittest.TestCase):

    def setUp(self):
        self.app = load()

    def test_first_plain_message_gets_a_key(self):
        chat = {"messages": [{"role": "user", "content": "Apa itu AI?"}]}
        self.assertEqual(self.app["answer_cache_key"](chat, PLAIN), question_key("apa itu ai"))

    def test_ineligible_requests_get_no_key(self):
        one = {"messages": [{"role": "user", "content": "x"}]}
        three = {"messages": [{"role": "user"}, {"role": "assistant"}, {"role": "user"}]}
        for chat, pending in (
            (three, PLAIN),
            (one, {**PLAIN, "payload": "Gunakan isi file berikut...\n### Pertanyaan\nApa itu AI?"}),
            (one, {**PLAIN, "images": [{"name": "a.png"}]}),
            (one, {**PLAIN, "riset": {"topic": "x"}}),
            (one, {**PLAIN, "kerangka": {"topic": "x"}}),
            (one, {**PLAIN, "cek": {"topic": "x"}}),
            (one, {**PLAIN, "text": "siapa namaku", "payload": "siapa namaku"}),
            (one, {**PLAIN, "text": "aku siapa", "payload": "aku siapa"}),
        ):
            self.assertIsNone(self.app["answer_cache_key"](chat, pending), pending)

    def test_chat_with_tables_gets_no_key(self):
        app = load(chat_tables=lambda chat: {"data.csv": "..."})
        chat = {"messages": [{"role": "user", "content": "Apa itu AI?"}]}
        self.assertIsNone(app["answer_cache_key"](chat, PLAIN))


class CachedTurnContextTest(unittest.TestCase):

    def setUp(self):
        self.context = load()["cached_turn_context"]

    def test_follow_up_after_cached_reply_carries_previous_turn(self):
        chat = {"messages": [
            {"role": "user", "content": "Apa itu AI?"},
            {"role": "assistant", "content": "AI adalah ...", "cached": True},
            {"role": "user", "content": "jelasin lebih detail"},
        ]}
        context = self.context(chat)
        self.assertIn("Pengguna: Apa itu AI?", context)
        self.assertIn("Ciel: AI adalah ...", context)
        self.assertTrue(context.endswith("### Pesan baru\n"))

    def test_no_context_once_langflow_has_seen_the_chat(self):
        q = {"role": "user", "content": "Apa itu AI?"}
        hit = {"role": "assistant", "content": "AI adalah ...", "cached": True}
        fresh = {"role": "assistant", "content": "Lebih detail ..."}
        error = {"role": "assistant", "content": "Gagal", "error": True}
        new = {"role": "user", "content": "lagi"}
        self.assertEqual(self.context({"messages": [q, hit, q, fresh, new]}), "")
        self.assertEqual(self.context({"messages": [q, fresh, new]}), "")
        self.assertEqual(self.context({"messages": [new]}), "")
        # Balasan error tidak dihitung: konteks cache masih perlu dikirim.
        self.assertIn("Ciel: AI adalah ...", self.context({"messages": [q, hit, q, error, new]}))


class SendPathTest(unittest.TestCase):

    def test_cache_is_checked_before_the_rate_limit(self):
        self.assertIn("cache_key = answer_cache_key(chat, pending_request)", SEND_PATH)
        self.assertLess(SEND_PATH.index("answer_cache().get(cache_key)"), SEND_PATH.index("check_rate_limit("))

    def test_only_fresh_anonymous_successes_are_stored(self):
        self.assertIn("if cache_key and not cached and not failed and not memory_owner_id():", SEND_PATH)
        self.assertEqual(SEND_PATH.count("answer_cache().put("), 1)

    def test_main_flow_calls_carry_the_cached_turn(self):
        self.assertEqual(SEND_PATH.count('cached_turn_context(chat) + pending_request["payload"]'), 2)
        self.assertNotIn('ask_langflow(\n                pending_request["payload"]', SEND_PATH)
        self.assertNotIn('ask_langflow(\n                    pending_request["payload"]', SEND_PATH)

    def test_cached_reply_is_marked(self):
        self.assertIn('reply["cached"] = True', SEND_PATH)


if __name__ == "__main__":
    unittest.main()
