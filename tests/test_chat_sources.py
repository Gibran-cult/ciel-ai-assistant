import unittest

from chat_sources import AnswerGroup, Source, answer_sources, guesses, reference_sources, split_sources, summarize


# One-line "Sumber:" blocks exactly as the live app wrote them on 2026-10-20
# (spec appendix A).
VASWANI_SUMBER = (
    "Sumber: [1] arXiv — Attention Is All You Need (Vaswani dkk., 2017) — https://arxiv.org/abs/1706.03762 — 12 Juni 2017 "
    "[2] arXiv HTML v3 — Attention Is All You Need (teks lengkap) — https://arxiv.org/html/1706.03762v3 "
    "[3] arXiv HTML v4 — Attention Is All You Need (bagian 3.2, 3.5, Table 3) — https://arxiv.org/html/1706.03762v4 "
    "[4] NeurIPS Proceedings — Attention is All you Need — "
    "https://proceedings.neurips.cc/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html"
)
KOTO_SUMBER = (
    "Sumber: [1] ACL Anthology — IndoLEM and IndoBERT: A Benchmark Dataset and Pre-trained Language Model for Indonesian NLP — "
    "https://aclanthology.org/2020.coling-main.66/ "
    "[2] arXiv — [2011.00677] IndoLEM and IndoBERT — https://arxiv.org/abs/2011.00677 — 2 November 2020 "
    "[3] ACL Anthology (PDF) — IndoLEM and IndoBERT — https://aclanthology.org/2020.coling-main.66.pdf "
    "[4] DOI — IndoLEM and IndoBERT — https://doi.org/10.18653/v1/2020.coling-main.66 — 2020"
)
FAKE_JOURNAL_REFUSAL = (
    "Aku nggak bisa meringkas jurnal itu, karena sejauh pencarianku, jurnal tersebut tidak ada.\n\n"
    "Mau aku lanjut cari penelitian asli yang paling dekat dengan topik ini?"
)
# Riset Skripsi answer tail, in the shape ciel_reference_builder.py writes.
RISET_TEXT = """# Peta sumber: Literasi digital UMKM

Ringkasan dua kalimat [1][2].

## Daftar Pustaka

[1] Sari, D. (2023). *Literasi Digital dan Kinerja UMKM*. jurnal.ugm.ac.id. https://jurnal.ugm.ac.id/jbs/article/view/123

[2] *SME Digitalisation Report*. (2022). oecd.org. https://www.oecd.org/digital/sme-report

[3] Putra, A. (t.t.). *Adopsi e-commerce UMKM*. repository.ui.ac.id. https://repository.ui.ac.id/x

Daftar pustaka disusun otomatis dari data sumber hasil pencarian. Periksa nama penulis, tahun, dan judul di sumber aslinya sebelum mengutip.

(1 sumber dihapus karena tidak ada di hasil pencarian.)"""
KERANGKA_TEXT = """# Kerangka Bab 1–3

## BAB I PENDAHULUAN
- Literasi digital naikkan kinerja [1]

## Daftar Pustaka (dari peta sumber)

[1] Sari, D. (2023). *Literasi Digital*. Jurnal X. https://example.org/a

[2] Putra, A. (2024). *Adopsi E-commerce*. Jurnal Y. https://example.org/b
"""


class SplitSourcesTest(unittest.TestCase):

    def test_one_line_sumber_block_from_the_live_app(self):
        body, sources, leftover = split_sources("Ringkasan.\n\n" + VASWANI_SUMBER)
        self.assertEqual(body.rstrip(), "Ringkasan.")
        self.assertEqual([s.number for s in sources], [1, 2, 3, 4])
        self.assertEqual(sources[0].url, "https://arxiv.org/abs/1706.03762")
        self.assertEqual(sources[0].domain, "arxiv.org")
        self.assertEqual(sources[0].title, "Attention Is All You Need (Vaswani dkk., 2017)")
        self.assertEqual(sources[3].domain, "proceedings.neurips.cc")
        self.assertEqual(leftover, "")

    def test_titles_that_contain_brackets_survive(self):
        _, sources, _ = split_sources("Jawaban.\n\n" + KOTO_SUMBER)
        self.assertEqual(len(sources), 4)
        self.assertEqual(sources[1].title, "[2011.00677] IndoLEM and IndoBERT")
        self.assertEqual(sources[3].url, "https://doi.org/10.18653/v1/2020.coling-main.66")

    def test_one_entry_per_line_and_hyphen_separator(self):
        body, sources, _ = split_sources("Isi.\n\nSumber:\n[1] Nama - Judul satu - https://x.org/a\n[2] Lain — Judul dua — https://www.y.org/b.")
        self.assertEqual(body.rstrip(), "Isi.")
        self.assertEqual([(s.title, s.domain, s.url) for s in sources],
                         [("Judul satu", "x.org", "https://x.org/a"), ("Judul dua", "y.org", "https://www.y.org/b")])

    def test_answer_without_sources_is_untouched(self):
        self.assertEqual(split_sources(FAKE_JOURNAL_REFUSAL), (FAKE_JOURNAL_REFUSAL, [], ""))

    def test_urlless_entries_and_guard_note_stay_as_leftover(self):
        text = ("Isi.\n\nSumber:\n[1] Web — Judul — https://x.org/a\n[2] File lampiran — catatan.pdf\n\n"
                "(1 sumber dihapus karena tidak ada di hasil pencarian.)")
        _, sources, leftover = split_sources(text)
        self.assertEqual([s.number for s in sources], [1])
        self.assertIn("[2] File lampiran — catatan.pdf", leftover)
        self.assertIn("(1 sumber dihapus karena tidak ada di hasil pencarian.)", leftover)

    def test_rejects_non_http_urls_and_keeps_text(self):
        _, sources, leftover = split_sources("x\n\nSumber: [1] Evil — <script>a</script> — javascript:alert(1)")
        self.assertEqual(sources, [])
        self.assertIn("<script>a</script>", leftover)  # escaping is the renderer's job


class SplitSourcesKeepsContentTest(unittest.TestCase):
    # Final review: text after the source block (the source guard notes the
    # model sometimes writes findings there) and prose before the first [n]
    # must never vanish from the display.

    def test_paragraph_after_the_block_is_kept(self):
        text = ("Ringkasan.\n\nSumber: [1] arXiv — A — https://arxiv.org/abs/1 — 12 Juni 2017 [2] X — Y — https://x.org/a"
                "\n\nMau aku lanjut cari penelitian lain?")
        _, sources, leftover = split_sources(text)
        self.assertEqual([s.url for s in sources], ["https://arxiv.org/abs/1", "https://x.org/a"])
        self.assertIn("Mau aku lanjut cari penelitian lain?", leftover)

    def test_prose_line_after_entries_is_kept(self):
        _, sources, leftover = split_sources("Isi.\n\nSumber: [1] A — B — https://a.org\nSeperti dijelaskan di [1] tadi, lanjut.")
        self.assertEqual(len(sources), 1)
        self.assertIn("Seperti dijelaskan di [1] tadi, lanjut.", leftover)

    def test_prose_before_the_first_marker_is_kept(self):
        _, sources, leftover = split_sources("Isi.\n\nSumber: dari hasil pencarian. [1] A — B — https://a.org")
        self.assertEqual(len(sources), 1)
        self.assertIn("dari hasil pencarian.", leftover)

    def test_malformed_url_never_raises(self):
        text = "Isi.\n\nSumber: [1] A — B — https://[link tidak tersedia] [2] C — D — https://ok.org/x"
        _, sources, _ = split_sources(text)
        self.assertEqual([s.url for s in sources], ["https://ok.org/x"])
        summarize([{"role": "assistant", "content": text},
                   {"role": "assistant", "content": "## Daftar Pustaka\n\n[1] A. (2020). *B*. https://[x]"}])


class SourceCleanupTest(unittest.TestCase):

    def test_sources_are_deduplicated_within_an_answer(self):
        _, sources, _ = split_sources("Isi.\n\nSumber: [1] A — B — https://x.org/a [2] C — D — https://x.org/a [3] E — F — https://y.org/b")
        self.assertEqual([(s.number, s.url) for s in sources], [(1, "https://x.org/a"), (3, "https://y.org/b")])

    def test_url_trimming_matches_the_source_guard(self):
        def url(entry):
            return split_sources(f"Isi.\n\nSumber: [1] Nama — Judul — {entry}")[1][0].url
        self.assertEqual(url("**https://x.org/a**"), "https://x.org/a")
        self.assertEqual(url("https://x.org/a_"), "https://x.org/a")
        self.assertEqual(url("https://en.wikipedia.org/wiki/Gaya_(fisika)"), "https://en.wikipedia.org/wiki/Gaya_(fisika)")
        self.assertEqual(url("(lihat https://x.org/a)."), "https://x.org/a")

    def test_titles_collapse_whitespace(self):
        _, sources, _ = split_sources("Isi.\n\nSumber: [1] Nama — Judul   yang\tpanjang — https://x.org/a")
        self.assertEqual(sources[0].title, "Judul yang panjang")


class ReferenceSourcesTest(unittest.TestCase):

    def test_daftar_pustaka_entries_from_riset_and_kerangka(self):
        riset = reference_sources(RISET_TEXT)
        self.assertEqual([s.url for s in riset][0], "https://jurnal.ugm.ac.id/jbs/article/view/123")
        self.assertEqual(riset[0].title, "Literasi Digital dan Kinerja UMKM")
        self.assertEqual(riset[1].domain, "oecd.org")
        self.assertEqual(len(riset), 3)
        self.assertEqual(len(reference_sources(KERANGKA_TEXT)), 2)

    def test_answer_sources_prefers_sumber_then_daftar_pustaka(self):
        self.assertEqual(len(answer_sources("a\n\n" + VASWANI_SUMBER)), 4)
        self.assertEqual(len(answer_sources(RISET_TEXT)), 3)
        self.assertEqual(answer_sources(FAKE_JOURNAL_REFUSAL), [])


class GuessesTest(unittest.TestCase):

    def test_guesses_strip_the_label(self):
        self.assertEqual(
            guesses("1. Nilai terendah di geometri. [Dugaan]\n2. Rata-rata 78. [Terverifikasi]"),
            ["Nilai terendah di geometri."],
        )

    def test_long_guesses_are_cut_at_a_word(self):
        (item,) = guesses("- " + "kata " * 60 + "[Dugaan]")
        self.assertLessEqual(len(item), 141)
        self.assertTrue(item.endswith("…"))


class SummarizeTest(unittest.TestCase):

    def messages(self):
        return [
            {"role": "user", "content": "Ringkas paper Vaswani"},
            {"role": "assistant", "content": "Ringkasan.\n\n" + VASWANI_SUMBER},
            {"role": "user", "content": "Gagal"},
            {"role": "assistant", "content": "Error", "error": True},
            {"role": "user", "content": "Paper Koto relevan?"},
            {"role": "assistant", "content": "Relevan.\n\n" + KOTO_SUMBER + "\n1. Data SmSA. [Dugaan]"},
        ]

    def test_summary_groups_newest_first_and_counts_unique_urls(self):
        summary = summarize(self.messages())
        self.assertEqual([g.question for g in summary.groups], ["Paper Koto relevan?", "Ringkas paper Vaswani"])
        self.assertIsInstance(summary.groups[0], AnswerGroup)
        self.assertEqual(summary.unique_count, 8)
        self.assertEqual(summary.map_entries, 0)

    def test_summary_skips_error_messages_and_counts_the_last_map(self):
        messages = self.messages() + [
            {"role": "user", "content": "Riset Skripsi: UMKM"},
            {"role": "assistant", "content": RISET_TEXT, "kind": "riset_skripsi"},
        ]
        summary = summarize(messages)
        self.assertEqual(len(summary.groups), 3)
        self.assertEqual(summary.map_entries, 3)
        self.assertEqual(summary.guesses, [])  # the [Dugaan] line sits after the Sumber block

    def test_guesses_come_from_answer_bodies(self):
        summary = summarize([{"role": "user", "content": "q"},
                             {"role": "assistant", "content": "1. Geometri lemah. [Dugaan]\n2. Rata 78. [Terverifikasi]"}])
        self.assertEqual(summary.guesses, ["Geometri lemah."])
        self.assertEqual(summary.groups, [])

    def test_source_is_a_value_object(self):
        self.assertEqual(Source(1, "T", "x.org", "https://x.org"), Source(1, "T", "x.org", "https://x.org"))


if __name__ == "__main__":
    unittest.main()
