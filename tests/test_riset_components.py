"""Ciel Scholar Search and Ciel Reference Builder (flow Ciel Riset Skripsi)."""

import types
import unittest

from tests.test_source_guard import GUARD_SOURCE, COMPONENTS, install_stubs, load

SCHOLAR_SOURCE = (COMPONENTS / "ciel_scholar_search.py").read_text(encoding="utf-8")
BUILDER_SOURCE = (COMPONENTS / "ciel_reference_builder.py").read_text(encoding="utf-8")


def load_component(source, name):
    uninstall = install_stubs()
    try:
        return load(source, name)
    finally:
        uninstall()


class Result:
    def __init__(self, url, title="", author=None, published_date=None):
        self.url, self.title, self.author, self.published_date = url, title, author, published_date


class Response:
    def __init__(self, *results):
        self.results = list(results)


SOURCES = [
    {"url": "https://jurnal.ugm.ac.id/jbs/article/view/123", "title": "Literasi Digital dan Kinerja UMKM",
     "author": "Sari, D.", "published_date": "2023-04-01T00:00:00.000Z"},
    {"url": "https://www.oecd.org/digital/sme-report", "title": "SME Digitalisation Report",
     "author": "", "published_date": "2022-11-10"},
    {"url": "https://repository.ui.ac.id/skripsi/456", "title": "Adopsi *e-commerce* UMKM",
     "author": "Putra, A.", "published_date": ""},
]

NOTES = """# Peta Sumber: Literasi digital UMKM

Ringkasan literatur [1][3].

## Tema: Adopsi teknologi
- Literasi digital menaikkan omzet, survei 200 UMKM [1].
- Hambatan biaya dan pelatihan [4].
- Dukungan kebijakan [2, 4].

## Celah riset
- Belum ada studi di kota kecil [3].

Sumber:
[1] https://jurnal.ugm.ac.id/jbs/article/view/123
[2] https://oecd.org/digital/sme-report/
[3] https://repository.ui.ac.id/skripsi/456
[4] https://contoh.example/dari-ingatan

(1 sumber dihapus karena tidak ada di hasil pencarian.)"""


class ScholarSearchTest(unittest.TestCase):

    def test_only_search_is_exposed_and_metadata_is_recorded(self):
        namespace = load_component(SCHOLAR_SOURCE, "ciel_scholar_search")
        response = Response(
            Result("https://a.example/x", " Judul A ", "Ani", "2024-01-02"),
            Result("https://b.example/y"),
            Result(None, "tanpa url"),
        )
        component = namespace["CielScholarSearch"](fake_search=lambda query: response)
        [search] = component.build_toolkit()

        self.assertIs(search.func(query="literasi digital umkm jurnal"), response)
        self.assertEqual(search.name, "search")
        self.assertEqual(component.ctx[namespace["RETRIEVED_URLS_KEY"]], ["https://a.example/x", "https://b.example/y"])
        self.assertEqual(component.ctx[namespace["RETRIEVED_SOURCES_KEY"]], [
            {"url": "https://a.example/x", "title": "Judul A", "author": "Ani", "published_date": "2024-01-02"},
            {"url": "https://b.example/y", "title": "", "author": "", "published_date": ""},
        ])

    def test_keys_match_the_guard_and_the_builder(self):
        scholar = load_component(SCHOLAR_SOURCE, "ciel_scholar_search")
        self.assertEqual(scholar["RETRIEVED_URLS_KEY"], load_component(GUARD_SOURCE, "ciel_source_guard")["RETRIEVED_URLS_KEY"])
        self.assertEqual(scholar["RETRIEVED_SOURCES_KEY"], load_component(BUILDER_SOURCE, "ciel_reference_builder")["RETRIEVED_SOURCES_KEY"])


class ReferenceBuilderTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.builder = load_component(BUILDER_SOURCE, "ciel_reference_builder")
        cls.build = staticmethod(cls.builder["build_references"])

    def test_apa_entries_come_from_metadata_only(self):
        text, count = self.build(NOTES, SOURCES)
        self.assertEqual(count, 3)
        self.assertIn(
            "[1] Sari, D. (2023). *Literasi Digital dan Kinerja UMKM*. jurnal.ugm.ac.id. "
            "https://jurnal.ugm.ac.id/jbs/article/view/123",
            text,
        )
        # No author: the title goes first. URL kept exactly as Exa returned it.
        self.assertIn("[2] *SME Digitalisation Report*. (2022). oecd.org. https://www.oecd.org/digital/sme-report", text)
        # No date: (t.t.); Markdown in the title is removed.
        self.assertIn("[3] Putra, A. (t.t.). *Adopsi e-commerce UMKM*. repository.ui.ac.id.", text)
        self.assertNotIn("\nSumber:\n", text)
        self.assertIn("## Daftar Pustaka\n\n[1] ", text)
        self.assertIn(self.builder["REFERENCES_NOTE"], text)
        # The guard's note stays, after the list.
        self.assertTrue(text.rstrip().endswith("(1 sumber dihapus karena tidak ada di hasil pencarian.)"))

    def test_ojs_titles_name_the_journal_and_doi_links_stand_alone(self):
        # Shapes from the live run on 2026-10-18.
        entry = self.builder["apa_entry"]
        ojs = {"url": "https://journals.stie-yai.ac.id/index.php/JUMPA/article/view/690",
               "title": "Mendorong Kinerja UMKM Kuliner | Jurnal Manajemen dan Perbankan (JUMPA)",
               "author": "Febrianawati, Nindy Puspitasari", "published_date": "2024-02-01T00:00:00.000Z"}
        self.assertEqual(
            entry(2, ojs),
            "[2] Febrianawati, Nindy Puspitasari. (2024). *Mendorong Kinerja UMKM Kuliner*. "
            "Jurnal Manajemen dan Perbankan (JUMPA). https://journals.stie-yai.ac.id/index.php/JUMPA/article/view/690",
        )
        doi = {"url": "https://doi.org/10.52155/ijpsat.v38.2.5291", "title": "The Effect Of Digital Literacy",
               "author": "Nurlina Nurlina", "published_date": "2023-05-01"}
        self.assertEqual(
            entry(1, doi),
            "[1] Nurlina Nurlina. (2023). *The Effect Of Digital Literacy*. https://doi.org/10.52155/ijpsat.v38.2.5291",
        )

    def test_unknown_sources_are_dropped_and_markers_follow(self):
        text, _ = self.build(NOTES, SOURCES)
        self.assertNotIn("contoh.example", text)
        self.assertNotIn("[4]", text)
        self.assertIn("- Hambatan biaya dan pelatihan.", text)
        self.assertIn("- Dukungan kebijakan [2].", text)
        self.assertIn("Ringkasan literatur [1][3].", text)

    def test_numbers_are_compacted_after_removed_entries(self):
        notes = "Temuan [2] dan [3].\n\nSumber:\n[1] https://hilang.example/a\n[2] https://a.example/x\n[3] https://b.example/y"
        sources = [{"url": "https://a.example/x", "title": "A", "author": "Ani", "published_date": "2021"},
                   {"url": "https://b.example/y", "title": "B", "author": "Budi", "published_date": "2020-05-01"}]
        text, count = self.build(notes, sources)
        self.assertEqual(count, 2)
        self.assertTrue(text.startswith("Temuan [1] dan [2]."))
        self.assertIn("[1] Ani. (2021). *A*. a.example. https://a.example/x", text)
        self.assertIn("[2] Budi. (2020). *B*. b.example. https://b.example/y", text)

    def test_answer_without_a_source_list_is_unchanged(self):
        self.assertEqual(self.build("Pencarian gagal, coba lagi.", SOURCES), ("Pencarian gagal, coba lagi.", 0))

    def test_no_searched_sources_leaves_an_honest_empty_list(self):
        text, count = self.build("Temuan [1].\n\nSumber:\n[1] https://a.example/x", [])
        self.assertEqual(count, 0)
        self.assertIn("Tidak ada sumber hasil pencarian yang bisa dicantumkan.", text)
        self.assertIn("Temuan.", text)

    def test_component_edits_text_blocks_in_place(self):
        uninstall = install_stubs()
        try:
            namespace = load(BUILDER_SOURCE, "ciel_reference_builder")
            message = namespace["Message"]()
            block = types.SimpleNamespace(type="text", text=NOTES)
            message.content_blocks = [types.SimpleNamespace(type="tool_use"), block]
            component = namespace["CielReferenceBuilder"](notes=message)
            component.ctx[namespace["RETRIEVED_SOURCES_KEY"]] = SOURCES
            result = component.build()
        finally:
            uninstall()
        self.assertIs(result, message)
        self.assertEqual(len(message.content_blocks), 2)
        self.assertIn("## Daftar Pustaka", block.text)
        self.assertIn("3 entri", component.status)


if __name__ == "__main__":
    unittest.main()
