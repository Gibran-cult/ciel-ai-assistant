import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "flow" / "components"
GUARD_SOURCE = (COMPONENTS / "ciel_source_guard.py").read_text(encoding="utf-8")
SEARCH_SOURCE = (COMPONENTS / "ciel_exa_search.py").read_text(encoding="utf-8")


def install_stubs():
    """Langflow, LangChain and Exa are not installed in CI; stub what the components import."""

    class Component:
        def __init__(self, **inputs):
            self.__dict__.update(inputs)
            self.ctx = {}

    class Message:
        def __init__(self, text=""):
            self.text = text

    class StructuredTool:
        def __init__(self, func, name, description, args_schema):
            self.func, self.name, self.description, self.args_schema = func, name, description, args_schema

        @classmethod
        def from_function(cls, func, name, description, args_schema):
            return cls(func, name, description, args_schema)

    class ExaSearchToolkit(Component):
        def build_toolkit(self):
            return [StructuredTool(self.fake_search, "search", "Search the web.", "SearchArgs")]

    def spec(*args, **kwargs):
        return kwargs

    modules = {name: types.ModuleType(name) for name in (
        "langflow", "langflow.custom", "langflow.field_typing", "langflow.io", "langflow.schema", "langflow.schema.message",
        "langchain_core", "langchain_core.tools",
        "lfx_exa", "lfx_exa.components", "lfx_exa.components.exa", "lfx_exa.components.exa.exa_search",
    )}
    modules["langflow.custom"].Component = Component
    modules["langflow.field_typing"].Tool = object
    modules["langflow.io"].MessageInput = spec
    modules["langflow.io"].Output = spec
    modules["langflow.schema.message"].Message = Message
    modules["langchain_core.tools"].StructuredTool = StructuredTool
    modules["lfx_exa.components.exa.exa_search"].ExaSearchToolkit = ExaSearchToolkit

    added = [name for name in modules if name not in sys.modules]
    for name in added:
        sys.modules[name] = modules[name]

    def uninstall():
        for name in added:
            sys.modules.pop(name, None)

    return uninstall


def load(source, name):
    namespace = {}
    exec(compile(source, name, "exec"), namespace)
    return namespace


class FakeResult:
    def __init__(self, url):
        self.url = url


class FakeResponse:
    def __init__(self, *urls):
        self.results = [FakeResult(url) for url in urls]


# Shape of real notes from the live test on 2026-10-17 (one search returned the
# first three URLs; [4] and [5] were cited from memory).
LIVE_NOTES = """Temuan:
- Performa AI di benchmark baru naik tajam; SWE-bench melonjak dalam setahun [2].
- Model kecil makin mampu: Phi-3-mini menyamai ambang yang dulu butuh model besar [1].
- Menurut Stanford AI Index 2025, skor MMMU, GPQA, dan SWE-bench naik 18,8, 48,9, dan 67,3 poin [4][5].
- Reasoning runtuh pada masalah baru yang menuntut penalaran mendalam [3][5].

Konflik atau ketidakpastian: [1] dan [5] menekankan lonjakan benchmark, sementara [3] menunjukkan batasnya.

Sumber:
[1] DeepLearning.AI — The Batch Issue 333 — https://www.deeplearning.ai/the-batch/issue-333 — 2025
[2] IEEE Spectrum — The State of AI 2025 — https://spectrum.ieee.org/ai-2025 — 2025
[3] Ars Technica — From prophet to product — https://arstechnica.com/ai/2025/12/from-prophet-to-product-how-ai-came-back-down-to-earth-in-2025/ — Desember 2025
[4] Stanford HAI — The 2025 AI Index Report — https://hai.stanford.edu/ai-index/2025-ai-index-report — tidak tersedia
[5] Stanford HAI — Research and Development — https://hai.stanford.edu/ai-index/2025-ai-index-report/research-and-development — tidak tersedia"""

LIVE_RETRIEVED = [
    "https://www.deeplearning.ai/the-batch/issue-333",
    "https://spectrum.ieee.org/ai-2025",
    "https://arstechnica.com/ai/2025/12/from-prophet-to-product-how-ai-came-back-down-to-earth-in-2025/",
]


class SourceGuardTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        uninstall = install_stubs()
        try:
            cls.guard = load(GUARD_SOURCE, "ciel_source_guard")
        finally:
            uninstall()
        cls.filter = staticmethod(cls.guard["filter_sources"])

    def test_live_notes_lose_memory_sources_and_their_findings(self):
        checked, removed = self.filter(LIVE_NOTES, LIVE_RETRIEVED)
        self.assertEqual(removed, 2)
        self.assertNotIn("hai.stanford.edu", checked)
        self.assertNotIn("Stanford AI Index 2025", checked)
        self.assertNotIn("[4]", checked)
        self.assertNotIn("[5]", checked)
        self.assertIn("- Reasoning runtuh pada masalah baru yang menuntut penalaran mendalam [3].", checked)
        self.assertIn("Konflik atau ketidakpastian: [1] dan menekankan", checked)
        for url in LIVE_RETRIEVED:
            self.assertIn(url, checked)
        self.assertTrue(checked.endswith("(2 sumber dihapus karena tidak ada di hasil pencarian Exa.)"))

    def test_notes_with_only_retrieved_sources_are_unchanged(self):
        notes = LIVE_NOTES.split("[4] Stanford")[0].rstrip()
        notes = notes.replace(" [4][5]", " [2]").replace("[3][5]", "[3]").replace("dan [5]", "dan [2]")
        self.assertEqual(self.filter(notes, LIVE_RETRIEVED), (notes, 0))

    def test_text_without_sources_section_passes_through(self):
        text = "Aku tidak menemukan sumber yang relevan untuk pertanyaan ini."
        self.assertEqual(self.filter(text, []), (text, 0))

    def test_no_search_results_remove_every_source(self):
        checked, removed = self.filter(LIVE_NOTES, [])
        self.assertEqual(removed, 5)
        self.assertNotIn("https://", checked)
        self.assertIn("Sumber:", checked)

    def test_url_variants_still_match(self):
        notes = (
            "Temuan:\n- Fakta A [1].\n- Fakta B [2].\n- Fakta C [3].\n\n**Sumber:**\n"
            "[1] Wiki — [Overfitting](https://en.wikipedia.org/wiki/Overfitting_(machine_learning)) — 2024\n"
            "- [2] Kompas — http://kompas.com/berita/123/ — 2026\n"
            "[3] Contoh — https://www.example.org/a#bagian — 2026"
        )
        retrieved = [
            "https://en.wikipedia.org/wiki/Overfitting_(machine_learning)",
            "https://www.kompas.com/berita/123",
            "https://example.org/a",
        ]
        self.assertEqual(self.filter(notes, retrieved), (notes, 0))

    def test_entry_without_url_is_removed(self):
        notes = "Temuan:\n- Fakta A [1].\n- Fakta B [2].\n\nSumber:\n[1] A — https://a.example/x — 2026\n[2] Buku B — tanpa tautan"
        checked, removed = self.filter(notes, ["https://a.example/x"])
        self.assertEqual(removed, 1)
        self.assertNotIn("Fakta B", checked)
        self.assertNotIn("Buku B", checked)

    def test_finding_after_the_source_list_is_checked_too(self):
        # Live test: the Agent wrote a finding below "Sumber:" citing a source from memory.
        notes = (
            "Temuan:\n- Fakta asli [1].\n\nSumber:\n[1] A — https://a.example/x — 2026\n"
            "[9] Contoh Palsu — https://contoh-palsu.example/laporan — 2026\n\n- Temuan uji dari laporan palsu [9]."
        )
        checked, removed = self.filter(notes, ["https://a.example/x"])
        self.assertEqual(removed, 1)
        self.assertNotIn("contoh-palsu", checked)
        self.assertNotIn("Temuan uji", checked)
        self.assertIn("[1] A — https://a.example/x — 2026", checked)

    def test_marker_lists_keep_remaining_numbers(self):
        notes = "Temuan:\n- Fakta [1, 2].\n\nSumber:\n[1] A — https://a.example/x\n[2] B — https://b.example/y"
        checked, removed = self.filter(notes, ["https://a.example/x"])
        self.assertEqual(removed, 1)
        self.assertIn("- Fakta [1].", checked)

    def test_component_reads_urls_from_the_graph_context(self):
        uninstall = install_stubs()
        try:
            namespace = load(GUARD_SOURCE, "ciel_source_guard")
            Message = sys.modules["langflow.schema.message"].Message
            guard = namespace["CielSourceGuard"](notes=Message(LIVE_NOTES))
            guard.ctx[namespace["RETRIEVED_URLS_KEY"]] = LIVE_RETRIEVED
            result = guard.check()
        finally:
            uninstall()
        self.assertNotIn("hai.stanford.edu", result.text)
        self.assertEqual(guard.status, "3 URL dari Exa, 2 sumber dihapus.")


class ExaSearchRecordTest(unittest.TestCase):

    def test_search_records_returned_urls_and_returns_the_response(self):
        uninstall = install_stubs()
        try:
            namespace = load(SEARCH_SOURCE, "ciel_exa_search")
            response = FakeResponse("https://a.example/x", "https://b.example/y")
            component = namespace["CielExaSearch"](fake_search=lambda query: response)
            [search] = component.build_toolkit()
            self.assertIs(search.func(query="berita terbaru"), response)
            search.func(query="kueri kedua")
        finally:
            uninstall()
        self.assertEqual((search.name, search.description, search.args_schema), ("search", "Search the web.", "SearchArgs"))
        self.assertEqual(component.ctx[namespace["RETRIEVED_URLS_KEY"]], ["https://a.example/x", "https://b.example/y"] * 2)

    def test_both_components_share_one_context_key(self):
        uninstall = install_stubs()
        try:
            guard_key = load(GUARD_SOURCE, "ciel_source_guard")["RETRIEVED_URLS_KEY"]
            search_key = load(SEARCH_SOURCE, "ciel_exa_search")["RETRIEVED_URLS_KEY"]
        finally:
            uninstall()
        self.assertEqual(guard_key, search_key)


if __name__ == "__main__":
    unittest.main()
