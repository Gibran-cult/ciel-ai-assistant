import hashlib
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "flow" / "v1.3.0" / "Ciel_AI_Long-Term_Memory_Master.json"
COMPONENTS = ROOT / "flow" / "components"

CHAT_INPUT_ID = "ChatInput-X8W7I"
MEMORY_SEARCH_ID = "CielMemorySearch-BC6pl"
MEMORY_STORE_ID = "CielMemoryStore-uBmzx"


def normalize(text):
    # Bandingkan tanpa beda CRLF/LF (checkout Windows vs JSON flow).
    return text.replace("\r\n", "\n").strip()


class FlowV130ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_PATH.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.nodes = {node["id"]: node for node in cls.flow["data"]["nodes"]}
        cls.edges = cls.flow["data"]["edges"]

    def template(self, node_id):
        return self.nodes[node_id]["data"]["node"]["template"]

    def test_ids_used_by_app_are_stable(self):
        # app.py mengirim tweaks ke ID ini (CHAT_INPUT_ID, MEMORY_*_ID).
        for node_id in (CHAT_INPUT_ID, MEMORY_SEARCH_ID, MEMORY_STORE_ID):
            self.assertIn(node_id, self.nodes)

    def test_memory_tools_still_feed_agent(self):
        tool_sources = {
            e["source"]
            for e in self.edges
            if e["target"].startswith("Agent-")
            and e["data"]["targetHandle"].get("fieldName") == "tools"
        }
        self.assertIn(MEMORY_SEARCH_ID, tool_sources)
        self.assertIn(MEMORY_STORE_ID, tool_sources)

    def test_memory_code_matches_repository_source(self):
        for node_id, filename in (
            (MEMORY_SEARCH_ID, "ciel_memory_search.py"),
            (MEMORY_STORE_ID, "ciel_memory_store.py"),
        ):
            with self.subTest(node=node_id):
                self.assertEqual(
                    normalize(self.template(node_id)["code"]["value"]),
                    normalize((COMPONENTS / filename).read_text(encoding="utf-8")),
                )

    def test_user_id_is_not_controlled_by_the_agent(self):
        for node_id in (MEMORY_SEARCH_ID, MEMORY_STORE_ID):
            with self.subTest(node=node_id):
                field = self.template(node_id)["user_id"]
                self.assertFalse(field["tool_mode"])
                self.assertEqual(field["value"], "")
                self.assertIn("user_id", self.nodes[node_id]["data"]["node"]["field_order"])
                tool_args = self.template(node_id)["tools_metadata"]["value"][0]["args"]
                self.assertNotIn("user_id", tool_args)

    def test_store_output_does_not_leak_internals(self):
        code = self.template(MEMORY_STORE_ID)["code"]["value"]
        self.assertNotIn("Database:", code)
        self.assertNotIn("Total memory", code)

    def test_orphan_research_api_tool_is_gone(self):
        self.assertNotIn("CustomComponent-2R2c7", self.nodes)
        self.assertFalse(any("127.0.0.1:7860" in json.dumps(n) for n in self.nodes.values()))

    def test_edges_only_reference_existing_nodes(self):
        for edge in self.edges:
            self.assertIn(edge["source"], self.nodes)
            self.assertIn(edge["target"], self.nodes)

    def test_snapshot_contains_no_hardcoded_api_keys(self):
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{16,}", self.raw))


# ------------------------------------------------------------
# Behaviour: run the memory components against a real Chroma DB
# in a temp dir, with Langflow stubbed and a fake embedding model.
# ------------------------------------------------------------

def install_langflow_stub():
    class Component:
        pass

    class Message:
        def __init__(self, text=""):
            self.text = text

    def spec(*args, **kwargs):
        return kwargs

    modules = {
        "langflow": types.ModuleType("langflow"),
        "langflow.custom": types.ModuleType("langflow.custom"),
        "langflow.io": types.ModuleType("langflow.io"),
        "langflow.schema": types.ModuleType("langflow.schema"),
    }
    modules["langflow.custom"].Component = Component
    modules["langflow.io"].MessageTextInput = spec
    modules["langflow.io"].IntInput = spec
    modules["langflow.io"].Output = spec
    modules["langflow.schema"].Message = Message

    # Only add/remove these keys: patch.dict(sys.modules) would also drop
    # chromadb's native module on exit, which cannot be imported twice.
    added = [name for name in modules if name not in sys.modules]
    for name in added:
        sys.modules[name] = modules[name]

    def uninstall():
        for name in added:
            sys.modules.pop(name, None)

    return uninstall


class FakeEmbeddingResponse:
    status_code = 200
    text = ""

    def __init__(self, text):
        digest = hashlib.sha256(text.encode()).digest()
        self.vector = [b / 255 for b in digest[:16]]

    def json(self):
        return {"embeddings": [self.vector]}


def fake_embed(url, json, timeout):
    return FakeEmbeddingResponse(json["input"])


def load_component(filename, class_name):
    namespace = {}
    exec(compile((COMPONENTS / filename).read_text(encoding="utf-8"), filename, "exec"), namespace)
    return namespace[class_name]


@unittest.skipUnless(__import__("importlib").util.find_spec("chromadb"), "chromadb not installed")
class MemoryIsolationTest(unittest.TestCase):

    def setUp(self):
        self.uninstall_stub = install_langflow_stub()
        self.home = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.home_patch = patch.object(Path, "home", return_value=Path(self.home.name))
        self.home_patch.start()
        self.embed_patch = patch("requests.post", side_effect=fake_embed)
        self.embed = self.embed_patch.start()

        self.Search = load_component("ciel_memory_search.py", "CielMemorySearch")
        self.Store = load_component("ciel_memory_store.py", "CielMemoryStore")

    def tearDown(self):
        self.embed_patch.stop()
        self.home_patch.stop()
        self.uninstall_stub()
        from chromadb.api.client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
        self.home.cleanup()

    def store(self, user_id, text):
        component = self.Store()
        component.memory_text = text
        component.user_id = user_id
        return component.save_memory().text

    def search(self, user_id, query="siapa namaku?"):
        component = self.Search()
        component.search_query = query
        component.top_k = 5
        component.user_id = user_id
        return component.search_memory()

    def test_users_only_see_their_own_memories(self):
        self.assertEqual(self.store("aaaa1111aaaa1111", "Nama pengguna adalah Andi."), "Memory berhasil disimpan.")
        self.store("bbbb2222bbbb2222", "Nama pengguna adalah Budi.")

        result_a = self.search("aaaa1111aaaa1111")
        result_b = self.search("bbbb2222bbbb2222")

        self.assertIn("Andi", result_a)
        self.assertNotIn("Budi", result_a)
        self.assertIn("Budi", result_b)
        self.assertNotIn("Andi", result_b)

    def test_user_without_memories_skips_embedding(self):
        self.store("aaaa1111aaaa1111", "Nama pengguna adalah Andi.")
        self.embed.reset_mock()

        result = self.search("cccc3333cccc3333")

        self.assertIn("Belum ada memory", result)
        self.assertNotIn("Andi", result)
        self.embed.assert_not_called()

    def test_anonymous_users_cannot_store_or_search(self):
        self.store("aaaa1111aaaa1111", "Nama pengguna adalah Andi.")
        self.embed.reset_mock()

        self.assertIn("TIDAK disimpan", self.store("", "Nama saya Rahasia."))
        result = self.search("")

        self.assertIn("hanya tersedia untuk pengguna yang login", result)
        self.assertNotIn("Andi", result)
        self.embed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
