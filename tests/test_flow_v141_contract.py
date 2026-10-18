import ast
import copy
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FLOW_V140 = ROOT / "flow" / "v1.4.0" / "Ciel_AI_Long-Term_Memory_Master.json"
FLOW_V141 = ROOT / "flow" / "v1.4.1" / "Ciel_AI_Long-Term_Memory_Master.json"
COMPONENTS = ROOT / "flow" / "components"

MEMORY_SEARCH_ID = "CielMemorySearch-BC6pl"
MEMORY_STORE_ID = "CielMemoryStore-uBmzx"
SOURCES = {
    MEMORY_SEARCH_ID: "ciel_memory_search.py",
    MEMORY_STORE_ID: "ciel_memory_store.py",
}

# Attributes that Langflow's Component already defines. An input with one of
# these names is shadowed: `self.<name>` returns Langflow's value, not the
# input. v1.3.0/v1.4.0 named the memory owner input `user_id` and every
# visitor was stored under the Langflow account id.
RESERVED_COMPONENT_ATTRIBUTES = {
    "user_id", "flow_id", "flow_name", "graph", "status", "name",
    "display_name", "description", "icon", "code", "inputs", "outputs",
    "cache", "vertex", "log", "tools_metadata",
}

LANGFLOW_ACCOUNT_ID = "05461fb3-0000-0000-0000-langflowuser"


def normalize(text):
    # Bandingkan tanpa beda CRLF/LF (checkout Windows vs JSON flow).
    return text.replace("\r\n", "\n").strip()


def input_names(source):
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "").endswith("Input"):
            for kw in node.keywords:
                if kw.arg == "name":
                    names.append(kw.value.value)
    return names


class FlowV141ContractTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = FLOW_V141.read_text(encoding="utf-8")
        cls.flow = json.loads(cls.raw)
        cls.base = json.loads(FLOW_V140.read_text(encoding="utf-8"))
        cls.nodes = {node["id"]: node for node in cls.flow["data"]["nodes"]}

    def template(self, node_id):
        return self.nodes[node_id]["data"]["node"]["template"]

    def test_memory_code_matches_repository_source(self):
        # Snapshot historis: sejak v1.9.0 permintaan embedding memakai
        # keep_alive 1 jam; kode terkini dicek di tests/test_flow_v190_contract.py.
        def without_keep_alive(source):
            lines = source.splitlines()
            keep_alive = next(i for i, line in enumerate(lines) if '"keep_alive": "1h",' in line)
            return "\n".join(lines[:keep_alive - 2] + lines[keep_alive + 1:])

        for node_id, filename in SOURCES.items():
            with self.subTest(node=node_id):
                self.assertEqual(
                    normalize(self.template(node_id)["code"]["value"]),
                    normalize(without_keep_alive((COMPONENTS / filename).read_text(encoding="utf-8"))),
                )

    def test_inputs_do_not_shadow_langflow_attributes(self):
        for filename in SOURCES.values():
            with self.subTest(component=filename):
                names = input_names((COMPONENTS / filename).read_text(encoding="utf-8"))
                self.assertIn("memory_owner", names)
                self.assertFalse(RESERVED_COMPONENT_ATTRIBUTES & set(names))

    def test_memory_owner_is_set_by_app_not_agent(self):
        for node_id in SOURCES:
            with self.subTest(node=node_id):
                template = self.template(node_id)
                self.assertNotIn("user_id", template)
                field = template["memory_owner"]
                self.assertFalse(field["tool_mode"])
                self.assertEqual(field["value"], "")
                self.assertEqual(field["name"], "memory_owner")
                field_order = self.nodes[node_id]["data"]["node"]["field_order"]
                self.assertIn("memory_owner", field_order)
                self.assertNotIn("user_id", field_order)
                self.assertNotIn("memory_owner", template["tools_metadata"]["value"][0]["args"])

    def test_only_memory_components_change_from_v140(self):
        def strip(flow):
            flow = copy.deepcopy(flow)
            flow["data"]["nodes"] = [n for n in flow["data"]["nodes"] if n["id"] not in SOURCES]
            return flow

        self.assertEqual(strip(self.flow), strip(self.base))

    def test_app_sends_memory_owner_tweak(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('MEMORY_SEARCH_ID: {"memory_owner": owner}', app)
        self.assertIn('MEMORY_STORE_ID: {"memory_owner": owner}', app)


# ------------------------------------------------------------
# Behaviour: run the memory components against a real Chroma DB
# in a temp dir, with a Langflow stub that keeps Langflow's
# read-only Component.user_id, and a fake embedding model.
# ------------------------------------------------------------

def install_langflow_stub():
    class Component:
        # Langflow sets input values as attributes; its own properties
        # (such as user_id) take precedence over inputs with the same name.
        def __init__(self, **inputs):
            self._attributes = dict(inputs)

        def __getattr__(self, name):
            attributes = self.__dict__.get("_attributes", {})
            if name in attributes:
                return attributes[name]
            raise AttributeError(name)

        @property
        def user_id(self):
            return LANGFLOW_ACCOUNT_ID

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


def compile_class(source, class_name):
    namespace = {}
    exec(compile(source, class_name, "exec"), namespace)
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

        self.Search = compile_class((COMPONENTS / "ciel_memory_search.py").read_text(encoding="utf-8"), "CielMemorySearch")
        self.Store = compile_class((COMPONENTS / "ciel_memory_store.py").read_text(encoding="utf-8"), "CielMemoryStore")

    def tearDown(self):
        self.embed_patch.stop()
        self.home_patch.stop()
        self.uninstall_stub()
        from chromadb.api.client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
        self.home.cleanup()

    def store(self, owner, text):
        return self.Store(memory_text=text, memory_owner=owner).save_memory().text

    def search(self, owner, query="siapa namaku?"):
        return self.Search(search_query=query, top_k=5, memory_owner=owner).search_memory()

    def stored_owners(self):
        import chromadb
        collection = chromadb.PersistentClient(
            path=str(Path(self.home.name) / ".ciel_ai" / "long_term_memory")
        ).get_collection("ciel_long_term_memory")
        return [m.get("user_id") for m in collection.get(include=["metadatas"])["metadatas"]]

    def test_users_only_see_their_own_memories(self):
        self.assertEqual(self.store("aaaa1111aaaa1111", "Nama pengguna adalah Andi."), "Memory berhasil disimpan.")
        self.store("bbbb2222bbbb2222", "Nama pengguna adalah Budi.")

        result_a = self.search("aaaa1111aaaa1111")
        result_b = self.search("bbbb2222bbbb2222")

        self.assertIn("Andi", result_a)
        self.assertNotIn("Budi", result_a)
        self.assertIn("Budi", result_b)
        self.assertNotIn("Andi", result_b)
        self.assertEqual(sorted(self.stored_owners()), ["aaaa1111aaaa1111", "bbbb2222bbbb2222"])

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
        self.assertNotIn(LANGFLOW_ACCOUNT_ID, self.stored_owners())

    def test_v140_code_was_shadowed_by_langflow_user_id(self):
        # Regression proof: with Langflow's Component.user_id, the v1.4.0 Store
        # ignored the anonymous owner and saved under the Langflow account.
        flow = json.loads(FLOW_V140.read_text(encoding="utf-8"))
        code = next(n for n in flow["data"]["nodes"] if n["id"] == MEMORY_STORE_ID)["data"]["node"]["template"]["code"]["value"]
        OldStore = compile_class(code, "CielMemoryStore")

        OldStore(memory_text="Nama saya Anonim.", user_id="").save_memory()

        self.assertEqual(self.stored_owners(), [LANGFLOW_ACCOUNT_ID])


if __name__ == "__main__":
    unittest.main()
