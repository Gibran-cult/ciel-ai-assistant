# Ciel AI Master — Change Log

## Unreleased

### Vendor data terms reviewed
- `docs/LEGAL.md` section 3 records what each vendor's own documents say (2026-11-01) and the action left for each. The biggest finding is that Streamlit Community Cloud allows personal, non-commercial use only. DeepSeek's privacy policy uses inputs for training with an email opt-out. Exa uses query data to improve its products. Gemini's paid tier does not train. The Supabase DPA must be signed from the dashboard.
- The Privasi page now says DeepSeek and Exa may use the data they receive to train or improve their models. `terms.LEGAL_VERSION` is `2026-11-01.2`, so every account is asked to accept again once.

### Legal readiness (UU PDP, UU Perlindungan Konsumen)
- New Pengaturan > Ketentuan tab (`terms.py`, `?page=terms`): who runs Ciel, an AI accuracy notice, academic integrity, acceptable use, Ciel Pro terms, refund rules, age, service limits, changes, and Indonesian law. No standard clause that UU 8/1999 Pasal 18 forbids; `tests/test_terms.py` rejects them.
- Signed-in accounts accept the terms once per `terms.LEGAL_VERSION` on a "Sebelum mulai" screen. The acceptance is stored in the new Supabase table `consents` (`docs/chat_store.sql`). If the table cannot be read or written, the user is let in and the error is logged.
- The Privasi page names every third party that receives user data, with its country (DeepSeek, Exa, Google, Supabase, Streamlit Community Cloud, ngrok, Google Fonts, and the payment provider). It also covers cookies and keeps purchase records for 10 years for tax.
- Streamlit's built-in usage statistics are off (`.streamlit/config.toml`).
- Data saya gained "Hapus akun": it deletes server history, memory, datasets, chats, projects, and the profile, then signs out. Purchase records and consent rows are kept.
- The login page states that signing in accepts the terms and links to them. Beranda notes that Ciel is an AI and can be wrong. The landing footer links Ketentuan.
- New `docs/LEGAL.md` lists the steps code cannot do (PSE and NIB registration, vendor DPAs, secrets, tax records, refund handling, licences, lawyer review).

### Settings page with a personal profile
- New Pengaturan dialog over the app, like Settings in the Claude app: a menu on the left, the tab on the right (it scrolls on its own), closed with X, Esc, or a click outside. It opens from the ⚙ icon (no label, no box) to the right of the account name at the bottom of the sidebar. Signed-out visitors get the same icon, with the Tampilan, Paket, and Privasi tabs only. On phones the menu wraps into a row above the tab.
- Tabs: Profil, Tampilan, Data saya, Paket (the old Pricing page), and Privasi. `?page=pricing`, `?page=privacy`, and `?page=settings&tab=<tab>` open the dialog on that tab once and are then removed from the address bar, so landing links and the Midtrans return URL are unchanged. Pricing and Privacy styles now also apply inside dialogs.
- Profil: full name, the name Ciel should call you, field of study, and answer preferences (new `account_settings.py`, new Supabase table `profiles` in `docs/chat_store.sql`). The home greeting uses that name, and each normal chat message starts with a short profile block so Ciel uses it too. The tab also shows the account email, memory ID, and Pro status, and "Kosongkan profil" clears the profile.
- Data saya moved out of the account menu, unchanged, and gained "Unduh riwayat chat (JSON)".
- The light/dark toggle left the top bar. Pengaturan > Tampilan now has Gelap and Terang buttons, still saved in this browser, with dark as the default.
- The account menu now holds only the email, the plan line, and Keluar.
- The privacy page explains the profile and points to Pengaturan for data controls.

### Repeated general questions are answered from a cache
- New `answer_cache.py`: an in-memory cache (1 day, 500 questions) for the first message of a new chat when it is plain text. A hit answers instantly, costs no DeepSeek call, and uses no message quota.
- An answer is stored only after the same question is asked twice, and only if it is at least 40 characters. The key includes `FLOW_ID`.
- Only anonymous answers fill the cache, because they run without long-term memory. Logged-in users can still get cached answers, but their own answers are never stored.
- Never cached:
  - questions about the asker (`aku`, `sy`, `kita`, `namaku`);
  - memory, dataset, or earlier-conversation requests (`ingat`, `lupakan`, `dataset`, `tadi`);
  - questions about time (`hari ini`, `jam`, `tanggal`, `kapan`, `harga`, `selamat pagi`, a year).
- Punctuation inside a question is kept in the key, so `hitung 12/4` and `hitung 12*4` never share an answer.
- The message after a cached answer carries that question and answer to Langflow, so follow-ups like "jelasin lebih detail" still have context.
- Tests: new `tests/test_answer_cache.py` and `tests/test_answer_cache_app.py`, both in CI.

### Cek kutipan: the thesis title no longer counts as copying
- On the live app, a draft sentence that restated the thesis title was flagged at 44% against the source map, because the map's heading and summary repeat the same title. Five-word sequences from the topic are now left out of the comparison. A sentence copied from the map is still flagged at 100%.

### Ciel Pro: Cek kutipan & kemiripan (Riset flow v1.1.0)
- New Pro feature: **"Cek kutipan & kemiripan"** under every Riset Skripsi source map. The student pastes a draft or uploads `.docx`/`.txt`, and gets a report in the chat.
  - **Citations:** each `[n]`, "(Nama, 2024)" and "Nama dkk. (2024)" is matched with the map's Daftar Pustaka by name and year. The report lists matches, name-matched citations with the wrong year, citations not in the map, unknown numbers, and map sources never cited.
  - **Similarity:** sentences that share 40% or more of their 5-word sequences with a source's Exa excerpts or with Ciel's own summary are listed with a revision hint. Direct quotes in quotation marks are not flagged.
  - The report and the Pricing FAQ say plainly that this is not Turnitin and that Ciel does not promise to pass plagiarism or AI detectors. Ghost-writing and AI-detector evasion were declined.
- `draft_check.py`: deterministic, no model and no Langflow call, so the check costs nothing and is instant. Server-side Pro check (`pro_refusal`) and its own quota `CEK_KUTIPAN_PER_DAY` (default 20).
- The draft stays on the user message only until the check succeeds (for "Coba lagi"), so it is not saved in chat history.
- Riset Skripsi flow **v1.1.0** (`flow/riset_skripsi/v1.1.0`): Ciel Scholar Search records each result's highlights (at most 3, 1,500 characters each). Ciel Reference Builder appends the highlights of the listed sources as one `<!-- ciel-excerpts:v1 ... -->` line, and drops any such line the Agent wrote. The app removes the line and stores the excerpts with the map. Older maps are compared with the summary text only.
- Live test (2026-10-20, local test flow "Ciel Riset Skripsi (test)" on v1.1.0):
  - Topic "Pengaruh media sosial terhadap minat beli mahasiswa": 23.0 s, 17 sources, and all 17 came with excerpts (about 18 KB in total).
  - On that map, a draft sentence copied from an excerpt was flagged at 100%, and a sentence copied from Ciel's summary at 92%.
  - In the browser (local app, dark mode), checked on an older map without excerpts:
    - the third button wraps under the other two;
    - the dialog with its upload box was readable;
    - the report caught a wrong year and a citation not in the map.
- Rate limits now take one `feature` argument (`FEATURE_QUOTAS`) instead of one flag per Pro feature.
- Tests:
  - New: `tests/test_draft_check.py`, `tests/test_flow_riset_v110_contract.py`, and `tests/test_cek_kutipan_app.py` (AppTest: Pro gets a report without any Langflow call, the draft is not saved, a free account is refused, a missing map is refused, and the button is hidden without Supabase).
  - Updated: the v1.0.0 riset contract pins the two superseded components by hash, and the component tests cover highlights and the excerpts line.

### Ciel Pro: Kerangka Bab 1–3 from the source map (Ciel Penulis flow v1.0.0)
- New Pro feature: **"Susun kerangka Bab 1–3"** under every Riset Skripsi source map.
  - A dialog asks for the approach (Kuantitatif / Kualitatif / Campuran / Belum tahu) and an optional research object.
  - The result is a Bab I–III outline as **points and guiding questions, not paragraphs**: background arguments with `[n]`, a proposed problem statement, objectives, theme subsections, prior studies, the conceptual framework, hypotheses (quantitative only), and method decisions.
  - It has its own "Unduh DOCX".
  - Ciel still does not write the thesis; the Pricing FAQ says so.
- New Langflow flow `flow/penulis/v1.0.0/Ciel_Penulis.json` (`WRITER_FLOW_ID`): Chat Input → DeepSeek (thinking off, temperature 0.7, max 6,000 tokens) → Chat Output.
  - No search or tools: the source map is the only source.
  - Mode marker `[KERANGKA]`, so Review draf can use the same flow later.
- `writing.py`: the request carries the whole source map.
  - Any `[n]` not in the map's Daftar Pustaka is removed, and any reference list the model writes itself is dropped.
  - The map's Daftar Pustaka is appended, so the outline and its DOCX stand alone.
- Server-side Pro check shared with Riset Skripsi (`pro_refusal`). Own quota `KERANGKA_PER_DAY` (default 10). A missing source map is refused before any call.
- ngrok policy: `WRITER_FLOW_ID` is optional like `RESEARCH_FLOW_ID`, with the same 20-a-minute limit; empty means no change.
- Live test (2026-10-20, local Langflow):
  - IndoBERT map, quantitative: 15.7 s.
  - Stunting map, qualitative: 13.1 s. Headings followed the approach ("Subjek dan Informan", "Fokus Penelitian", "Hipotesis: Tidak dipakai").
  - Both: no `[n]` outside the map, no point over 25 words, and the author names and years in "Penelitian Terdahulu" match the reference list.
  - Through the app in the browser (TikTok map, quantitative): the button, the dialog, the outline with all 18 references, and the DOCX button all worked in dark mode.
- Tests:
  - New: `tests/test_writing.py`, `tests/test_flow_penulis_v100_contract.py`, and `tests/test_kerangka_app.py` (AppTest: Pro gets the outline from the writer flow with unknown citations removed, a free account is refused, a missing map is refused, and the button is hidden without the flow).
  - Extended: gateway policy and Pro gate tests.

### Ciel Pro in production (2026-10-19)
- **Riset Skripsi** is live on the public app.
  - The production Langflow flow is `c6ac7acc-5af8-43a9-a589-e91a27da88f8`. `RESEARCH_FLOW_ID` was added to the host `.env` and to the Streamlit Cloud secrets.
  - The ngrok policy was re-rendered: only the two run paths of that flow were added, under the 20-a-minute limit, and `tools/check_gateway.py` passed 11/11.
  - One run through the tunnel took 35 s and returned 20 sources, all within the requested range.
- **Buying Pro with Midtrans production** is live.
  - The same production server key sits in the Streamlit Cloud secrets and the `midtrans-notify` secrets (matching sha256 digests), with `MIDTRANS_PRODUCTION=true` in both. The key was set with a hidden-input command that checks it against Midtrans production first.
  - The Payment Notification URL is set in the Midtrans Production dashboard, and the function was redeployed.
  - On the web, "Perpanjang 30 hari" created a production Snap transaction (`app.midtrans.com`) and a `pending` order.
- Dark mode fix found on the web (Streamlit 1.65): typing in the Riset Skripsi topic box was invisible. Streamlit 1.65 draws the text area box on `stTextAreaRootElement`, which kept the light theme's background (`rgb(233,231,225)`) under the light dark-mode text. The input rule now covers that element as well. Checked by injecting the rule into the live page first: dark background `rgb(42,40,36)`, with readable text, caret and placeholder.
- An unopened Snap link never gets an `expire` notification. Midtrans only creates the transaction once a payment method is chosen: production had 0 transactions and an empty notification history for the test order. The row stays `pending`, so Pricing kept saying "Menunggu konfirmasi pembayaran" for up to 2 hours. `order_message` now treats a `pending` order older than the 60-minute Snap expiry as expired; paid orders are never rewritten. The Midtrans account is still in business review (registration done) as of 2026-10-19.
- Trap: a key copied from the Midtrans dashboard while it was in Sandbox mode was pasted twice as the "production" key. New accounts use the `Mid-server-` prefix in both modes, so only a Status API check tells them apart. `docs/PRO.md` now includes that check.

### Ciel Pro: buying Pro with Midtrans
- Signed-in users can buy **Pro for 30 days** (Rp79.000) from the Pricing page through Midtrans Snap: QRIS, e-wallet or virtual account. It is a one-time payment with no automatic billing, and buying again adds 30 days to what is left.
  - The Pro card appears only when `MIDTRANS_SERVER_KEY` is set. Without it, Pro stays "sedang disiapkan".
  - Guests see "Masuk untuk membeli".
- The app creates a `pro_orders` row (pending) and a Snap transaction with the server key, then shows "Bayar di Midtrans". The transaction expires after 60 minutes.
  - When the buyer comes back, the Pricing page reads that account's latest order and its Pro status from the database. It ignores the parameters Midtrans adds to the URL, including the "pricing?order_id=…" form that `current_view` now tolerates.
- New Supabase Edge Function `midtrans-notify` (`supabase/functions/`, deployed with `--no-verify-jwt`):
  1. Checks the sha512 signature.
  2. Re-reads the status from Midtrans's Status API.
  3. Settles through the SQL function `ciel_settle_order`. In one transaction it locks the order, settles it once, requires the amount to match, and adds 30 days to `pro_members`.
  - Failed and expired payments are recorded. Refunds and chargebacks are only noted, and the operator decides whether to revoke Pro.
  - Response codes make Midtrans retry only temporary failures.
- Privacy page: when payments are on, it says that Midtrans processes payments, which data goes to Midtrans (email and name for the receipt), and that Ciel never sees card, bank or e-wallet details.
- Tests:
  - `tests/test_payments.py` (in CI) covers the Snap payload and environments, order storage, the SQL contract, and Pricing/Privacy with and without payments.
  - AppTest runs cover buying (order and Snap call), a Snap failure, a paid return with a forged URL, a pending order, an old order, and payments off.
  - `node --test` on the Edge Function logic (now a CI step) covers the signature, Status API over the notification body, idempotent settling, failed and reversed payments, and retry codes.
- Sandbox test (2026-10-19) on the real Supabase project and the Midtrans sandbox, with the app running locally:
  - Order `bb949ace…` was paid by BCA virtual account through the sandbox simulator. The Edge Function answered `paid`, then `already_paid` to a repeated notification. `pro_members` got 30 days (until 18 November 2026, source `midtrans`), and Pricing showed "Pembayaran diterima. Ciel Pro aktif sampai 18 November 2026." with "Perpanjang 30 hari".
  - Four unpaid orders stayed `pending`.
  - First attempt: the function's `MIDTRANS_SERVER_KEY` secret held the literal placeholder from the setup command, so every notification was refused with 403. That is correct behaviour for a wrong signature, but it is easy to miss. `docs/PRO.md` now sets the secret from `secrets.toml` and checks it by digest.
  - Also learned: new Midtrans accounts use `Mid-server-` keys in sandbox too (no `SB-` prefix); the key line must sit above `[auth]` in `secrets.toml`; sandbox numbers are paid in the Midtrans simulator, not a real bank app.
- Riset Skripsi live through the dialog as a real Pro account (from the sandbox purchase). "Mulai riset" with "3 tahun terakhir" gave 18 sources, all 2023–2024 (one "t.t."), with every section. The chat was saved with `kind: riset_skripsi` and `min_year: 2023`.
- Dark mode fixes found in that run:
  - "Unduh DOCX" and "Unduh CSV" were light on light, because `.stDownloadButton` was not covered by the button rules.
  - Links in every answer (sources, DOI) used the light theme's navy, about 3:1 on dark paper; they now use the accent token.
  - The source map's `#` title rendered at 44 px in Streamlit's own font. Answer headings now use Fraunces for h1 (1.6rem) and Geist for h2/h3.

### Ciel Pro: Pro status and Riset Skripsi (Riset Skripsi flow v1.0.0)
- New Pro-only feature **Riset Skripsi** for thesis students. The output is a source map, not a written chapter: sources summarized per theme, research gaps, questions for the supervisor, and an APA 7 reference list. It comes from a separate Langflow flow (`RESEARCH_FLOW_ID`); the main flow is unchanged.
- Flow `flow/riset_skripsi/v1.0.0/Ciel_Riset_Skripsi.json`, cloned from the Web Research Assistant. Architecture: `docs/ARCHITECTURE.md`; first deployment: `RELEASE_CHECKLIST.md`.
  - New component **Ciel Scholar Search**: the Agent only gets Exa `search` (no `get_contents`), with 10 results per query. The year range is Exa's own `start_published_date`, set by the app per request. Each result's title, author and date are recorded.
  - New component **Ciel Reference Builder**, after Ciel Source Guard: it replaces the Agent's `[n] URL` list with an APA 7 "Daftar Pustaka" built from that recorded metadata, then renumbers. The model never writes an author or a year. Missing date: "(t.t.)"; missing author: the title goes first.
  - Agent: `max_iterations` 10, `n_messages` 0, DeepSeek with thinking off, prompt for the fixed source-map format with at most 4 searches.
- ngrok policy: `RESEARCH_FLOW_ID` (optional, a UUID) allows POST run for that flow under the same 20-a-minute per-IP limit. When it is empty the policy is exactly as before.
- Live test (2026-10-18). The snapshot was imported into local Langflow as a separate test flow, "Ciel Riset Skripsi (test)". Production and the ngrok policy are unchanged. Three real topics were sent directly to Langflow:

  | Topic (range) | Time | Entries | Outside the range | `[n]` without an entry |
  |---|---|---|---|---|
  | Literasi digital, UMKM kuliner (from 2021) | 33.2 s | 15 | 0 | 0 |
  | Stunting risk factors, rural areas (from 2023) | 30.1 s | 20 | 0 | 0 |
  | Hoax detection with IndoBERT (from 2016) | 19.9 s | 16 (one "t.t.") | 0 | 0 |

  - All three had every section and mostly journal articles (OJS journals, DOIs). Methods and sample sizes were taken from the highlights, and "not mentioned in the excerpt" was written when they were missing. Ciel Source Guard removed nothing.
  - After the first run, Ciel Reference Builder learned to split OJS page titles ("Article | Journal") so the journal name replaces the domain, and to leave DOI links without "doi.org" as a site.
  - Author names are kept as Exa gives them, without converting to "Surname, I.".
- Pro status lives in the new Supabase table `pro_members` (`docs/chat_store.sql`). The app only reads it (`ChatStore.load_pro_until`); an admin grants Pro with SQL for now, and a payment webhook will write the same table later. How to grant, extend and revoke: `docs/PRO.md`.
- The gate is on the server. Every Riset Skripsi request reads the status from the database (not the 5-minute display cache) before using any quota, so a hand-made request from a free account never reaches the research flow. If the database can't be read, the request is refused.
- Limits: Pro accounts get 150 messages an hour and 800 a day (free signed-in: 60 and 300), and Riset Skripsi has its own quota of 5 a day. All of it still counts toward the 1,500-a-day total. Settings: `RATE_LIMIT_PER_HOUR_PRO`, `RATE_LIMIT_PER_DAY_PRO`, `RISET_SKRIPSI_PER_DAY`.
- UI:
  - "Riset Skripsi" button in the sidebar. Free accounts see "· Pro", and the dialog explains the plan with a link to Pricing. Pro accounts get topic, field and year range (3/5/10 years).
  - The result has an "Unduh DOCX" button. The DOCX (`riset_export.py`, new dependency `python-docx`) uses Times New Roman 12, 1.5 spacing and hanging-indent references, and is built only when clicked.
  - Follow-up questions in that chat send the source map along as context.
  - The account menu shows the plan and when Pro ends.
  - Dialogs render outside `.stApp`, so button rules now also cover `[data-testid="stDialog"]`, with dialog colours for dark mode.
- Pricing: Pro lists Riset Skripsi and DOCX export and stays "not yet for sale" until payments exist. The headline is now "Fitur inti Ciel gratis." A new FAQ says Ciel does not write the thesis.
- Rollback: remove the `RESEARCH_FLOW_ID` secret and the feature disappears; chat is unaffected.
- Tests: new `tests/test_flow_riset_v100_contract.py` (nodes, the one chain to Chat Output, embedded code equals `flow/components/`, settings, prompt, no keys) and `tests/test_riset_components.py` (metadata record, APA entries, renumbering, dropped unknown sources, guard note kept), plus `tests/test_gateway_policy.py` cases for the optional research flow. New `tests/test_ciel_pro.py` (all in CI) covers the database read, PostgREST timestamps on Python 3.10, cache vs. server check, limits, refusal messages, retry keeping the riset inputs, follow-up context, DOCX output, and two AppTest runs. In those, a free account is refused without calling Langflow, and a Pro account reaches the research flow with `start_published_date` and a 420 s timeout.

### Faster answers, same accuracy (flow v1.12.0)
- The main Agent's DeepSeek model runs with thinking off (`model_kwargs` `extra_body.thinking.type = disabled`), like the research Agent. Analysis answers dropped from 25.1 to 15.5 s and the exact-answer checks stayed correct.
- Math questions no longer all go through the Math Tutor sub-flow. That path took 8-10 s because the nested agent wrote a full answer and the main Agent rewrote it. The main Agent now has Langflow's Calculator (`evaluate_expression`) as a tool. Prompt v14.8 makes it compute every number with the Calculator and check answer keys with it. Concept explanations, practice problems and quizzes are answered directly, and only worksheets or long multi-part problems still go to the Math Tutor. On 26 exact-answer questions: 26/26 correct, median 8.6 → 6.3 s, max 28.9 → 12.8 s.
- Prompt v14.8 also lists health, nutrition, medicine and safety, and law, official rules, scholarships, prices and official figures as research topics. With thinking off, v14.7 answered a paracetamol dose without a search; v14.8 routed 11/11 must-search and must-not-search questions correctly. Every other v14.7 line is unchanged apart from the old math routing and two lines that now name the Calculator.
- Both Run Flow nodes (Math Tutor, Knowledge Retriever) have `cache_flow` on, so the sub-flow graph is built once (keyed by flow ID). An edit to those sub-flows may only take effect after Langflow restarts.
- Outside the repository the Math Tutor sub-flow runs with thinking off and without the date tool: 26/26 correct, and its slowest answer dropped from 28.9 to 13.6 s.
- Production (2026-10-18):
  - Backups: `~/.ciel_ai/flow_backups/math_tutor_before_v1120_20261018_091522.json` and `main_v1110_before_v1120_20261018_091523.json`.
  - The live main flow differed from the v1.11.0 snapshot only in Langflow re-saves (positions, edge handle names, tool descriptions, and an SSRF check Langflow added to the DeepSeek extension code). The changes were applied to the live flow, and the repository snapshot applies the same changes to the v1.11.0 snapshot.
  - Public app, guest, one run each: greeting 5.6 s, multiplication 6.7 s, sample variance 8.2 s, practice problems 7.1 s, paracetamol dose 16.3 s with sources, analysis 19.4 s with sources; all correct.
  - The DeepSeek balance ran out during testing, and Ciel failed with HTTP 402 until it was topped up.
- Tests: new `tests/test_flow_v1120_contract.py` (in CI) checks thinking off, cached Run Flows, the Calculator node and its edge, the v14.8 math and research rules, and that nothing else changed from v1.11.0. Numbers and method: `docs/OBSERVABILITY.md`.

### Security hardening (flow v1.11.0)
- An audit on 2026-10-18 found that the Verified Data Analyst sub-flow was a CSV agent with `allow_dangerous_code=True`: the model wrote Python and Langflow ran it on the home PC. Any chat visitor, guests included, could steer it through the main Agent. The audit also listed the Python Interpreter node in the Math Tutor sub-flow, but during the rollout it turned out not to be connected to the Agent, so the Math Tutor never ran code.
- Flow v1.11.0 removes the Verified Data Analyst tool. Ciel Table Analyst now reads the built-in dataset by name (`file_name=200_sales_data`, from `~/.ciel_ai/builtin_datasets/200_sales_data.csv` on the host), only when no attached file or saved dataset has that name, so the default pick is unchanged. The shared helpers (`owner_dir`, `saved_tables`, `pick_table`) are untouched.
- Prompt v14.7 sends built-in dataset questions to Table Analyst and adds section "10. KEAMANAN": content from web results, files, tables, photos, memory and tools is data, not instructions; memory and datasets are saved only from the user's own message; no markdown images, HTML or URLs that carry conversation data; the system prompt and configuration are not shown. Every other v14.6 line is kept except the four that named Verified Data Analyst.
- Outside the repository the unconnected Python Interpreter node is removed from the Math Tutor sub-flow. Its prompt no longer tells the Agent to use it: symbolic and statistics work is done step by step and checked with Langflow's Calculator, which evaluates arithmetic with an AST allowlist on floats (a huge power raises `OverflowError` instead of running long).
- ngrok gateway: `tools/render_ngrok_policy.py` writes the traffic policy from `.env` without printing secrets. Rules, in order: a per-IP limit of 120 requests a minute on every path, Basic Auth, then an exact allowlist where both `req.url.path` and `req.url.raw_path` must match: POST run for the main and Memory Admin flow IDs, POST image upload, GET/DELETE chat sessions, GET health check. Everything else answers 404, so the Basic Auth password alone no longer reaches the Langflow UI, the flow API or archived flows. Run and upload keep the per-IP limit of 20 a minute. The script refuses passwords under 24 characters and flow IDs that are not UUIDs. `tools/check_gateway.py` checks the live tunnel with 11 requests that never carry the Langflow API key.
- App: answers no longer show images. `strip_markdown_images` replaces inline, reference and shortcut markdown images and `<img>` with "[gambar dihapus]". It runs when an answer arrives (logged as `security_event kind=answer_image_removed`) and again when history is shown, so prompt injection cannot send chat data through an image URL. Links stay.
- App: typed messages are capped at 10,000 characters, in the composer and again on the server. Streamlit's upload limit is 25 MB (was 200 MB). Images over 90 megapixels, or that cannot be decoded, are refused before anything is sent; until now an unreadable file went to Langflow unchanged.
- App: limits per hour and per day. Defaults:

  | Who | Before | Now |
  |---|---|---|
  | Each guest | 20 an hour | 10 an hour |
  | All guests together | 150 an hour | 60 an hour, 300 a day |
  | Each signed-in user | 60 an hour | 60 an hour, 300 a day |
  | Everyone together | no limit | 1,500 a day |

  The error says which limit was hit. Security events (rate limit, long message, refused image, removed image) share one log prefix, `security_event kind=`.
- Production (2026-10-18):
  - Backups were taken first in `~/.ciel_ai/flow_backups/`: the five flows (`*_20261018_034136.json`) and the old ngrok policy (`ngrok-ciel-policy_before_allowlist_20261018_034635.yml`).
  - The built-in CSV was copied to `~/.ciel_ai/builtin_datasets/200_sales_data.csv` (Sales_Amount total 1,065,600.71).
  - The Math Tutor's orphan node was removed; the limit question still gives 6, step by step.
  - The main flow was patched in place (same FLOW_ID). Only the Verified Data Analyst node and edge, the Table Analyst node and the Agent prompt changed, because the live flow differed slightly from the v1.10.2 snapshot elsewhere.
  - Checks through 127.0.0.1: the built-in total came from `analyze_table` in 5.4 s; chat took 4.0 s; a file with a hidden instruction to add an image URL and save a memory was summarized, the instruction was reported and ignored, and no tool ran.
  - `MEMORY_ADMIN_FLOW_ID` was added to the host's `.env`, and the policy was rendered and ngrok restarted (about 1 minute offline). `tools/check_gateway.py`: 11/11 PASS.
  - Through the tunnel: a per-category mean on the built-in dataset matched an independent calculation (6.9 s), and an image upload answered 201. Ciel checked chat and "Data saya" in the browser.
  - Verified Data Analyst and the Arsip flows "Data Analysis Assistant" and "Verified Data Analyst (Backup)" were deleted from Langflow. No flow in Langflow contains a CSV agent or a Python REPL any more.
  - The Basic Auth password (24 characters) has not been rotated yet; see `SECURITY.md`.
- CI: `actions/checkout` and `actions/setup-python` are pinned to commit SHAs (v7.0.1, v7.0.0) without persisted credentials, `pip-audit -r requirements.txt` runs on every build (no known vulnerabilities on 2026-10-18), and Dependabot proposes weekly updates for pip and GitHub Actions.
- New `SECURITY.md`: how to report a vulnerability, the controls per threat, an incident runbook (taking Ciel offline, rotating each secret, where the logs are) and the owner checklist (2FA, provider spending caps, host and router settings).
- Tests: new `tests/test_flow_v1110_contract.py` (in CI) checks that no component runs model-written code, that only the Agent prompt and Table Analyst change from v1.10.2 besides the removed tool, the embedded code, the built-in routing, the security section, and the built-in dataset's behaviour (guests, case and extension, attached files win, never without its name). `tests/test_flow_v170_contract.py` treats v1.7.0's Table Analyst as historical (unchanged through v1.10.2). New `tests/test_gateway_policy.py` and `tests/test_app_security.py` (in CI). `tests/test_rate_limit.py` covers daily windows and the messages, and `tests/test_vision_images.py` covers refused images.

### Navbar buttons in the style of the claude.ai app
- The theme toggle and Masuk are now quiet ghost buttons: no border, 8px corners, and no underline. Masuk sits on a soft grey background (`--c-raised`) with bolder text and darkens on hover and on the login page (new `--c-raised-strong`, with a dark-mode value).
- Masuk text stays well above AA in both themes (12.6–13.9:1). Checked on Streamlit 1.65 in light and dark mode, including a real pointer hover; `tests/test_theme.py` covers the new navbar rules.
- "Harga" is now "Pricing", and it and Privasi only show after sign-in, as the first rows of the account menu: left-aligned, with an icon, and the grey background on the current page (new `page_nav_buttons` helper, `.st-key-accountnav` rules). Before sign-in the top bar shows only the theme toggle and Masuk. The `?page=pricing` and `?page=privacy` links still open for everyone, so the privacy policy stays public.
- The account menu moved from the top bar to the bottom of the sidebar, as in the claude.ai app. The account button (icon, name, chevron) stays in view while the history scrolls and sits at the bottom when the sidebar is short. Its menu opens upwards with the email, Pricing, Privasi, the memory note, "Data saya", and Keluar as a menu row under a line. The email is plain HTML, so markdown does not turn it into a blue mailto link.
- Checked on Streamlit 1.65 with 3 and 40 chats in both themes (menu text 7.6–16.6:1). `tests/test_login.py` covers where the buttons are before and after sign-in, and `tests/test_theme.py` covers the sticky account button.

### Fastest Gemini model first (flow v1.10.2)
- Image questions in production still took 30-32 s. The image itself took 9.9-21.7 s to read, while the Agent took about 8 s. Timing both models on 8 new photos showed `gemini-3.5-flash-lite` reading every one in 1.3-2.7 s. `gemini-3.1-flash-lite` took up to 10 s when it answered and timed out at 20 s three times, and every timeout delayed the answer by 20 s before the backup ran.
- Ciel Vision Router now reads with `gemini-3.5-flash-lite` first, uses `gemini-3.1-flash-lite` as the backup, and limits each model to 8 s (`api_timeout`). The cost per photo stays about the same.
- Through ngrok on a test copy, four new phone photos took 7.6-13.8 s per question, with the image read in 1.9-3.7 s. All answers were correct, and the local model was not used.
- Production was patched in place after a backup (`main_v1.10.1_before_v1.10.2_20261017_211114.json`). Two photo questions through ngrok took 11.6 s (image read in 2.7 s) and 25.0 s (image read in 15.4 s, likely one 8 s timeout before the backup answered). Both answers were correct, so Gemini's response time can still vary.
- New `tests/test_flow_v1102_contract.py` (in CI). `tests/test_flow_v1101_contract.py` treats v1.10.1's router as historical.

### Backup Gemini model for image reading (flow v1.10.1)
- Right after flow v1.10.0 went live, `gemini-3.1-flash-lite` answered HTTP 503 for a while. The router fell back to the local model, which took 136.5 s to read one photo (153.6 s for the whole question) and filled the PC's memory. A probe showed `gemini-3.5-flash-lite` still answering at the same time.
- Ciel Vision Router now tries `api_fallback_model` (`gemini-3.5-flash-lite`) when the main model fails, and only then the local model. The status lists each model's error. The same model in both fields is tried once.
- Production was patched in place after a backup (`main_v1.10.0_before_v1.10.1_20261017_205804.json`). Image questions through ngrok then took 31.2 and 33.1 s, with the image read in 10.0 and 21.8 s and no local fallback.
- Tests: `tests/test_vision_router.py` covers the backup model and the single try. New `tests/test_flow_v1101_contract.py` (in CI) checks that only the router changes and that the embedded code matches the repository. `tests/test_flow_v1100_contract.py` treats v1.10.0's router as historical.

### Faster and working image questions (flow v1.10.0)
- Photos from a phone camera (about 3024x4032) were never read: the local vision model needed 4,283 tokens for them, more than its 4,096-token context, so the Agent only got "Gambar tidak dapat dibaca". The app now shrinks every photo to 1024 px on the longest side, turns it upright from its EXIF orientation, and puts transparent images on white before uploading (`fit_for_vision`). Small upright images are sent unchanged; the 5 MB limit is unchanged.
- Reading a new 1024 px photo with the local model took 66-68 s on the laptop CPU (prompt processing about 22 tokens/s). Ciel Vision Router now reads images with the Gemini API (`gemini-3.1-flash-lite`, paid tier, key in the Langflow global variable `GEMINI_API_KEY`) in 2.8-9.7 s, and falls back to the local model when the key is empty, the API fails or it takes more than 20 s. The API key never appears in the router's status or answer.
- Privacy page (updated 18 Oktober 2026): photos are shrunk and read by a third-party AI model on a paid plan that does not use the data for training, possibly outside Indonesia, with the local model as fallback. Following the page's own rule, the production flow switches only after this page is live.
- Tests (in CI): `tests/test_vision_images.py` (shrinking, EXIF rotation, transparency, unreadable files, size limit), `tests/test_vision_router.py` (API reading, fallback on HTTP errors and timeouts, no key, data URL parsing), `tests/test_flow_v1100_contract.py` (only the router changes from v1.9.0, embedded code, key from the global variable, local settings kept). `tests/test_flow_v120_contract.py` now treats v1.2.0's router as historical (unchanged through v1.9.0).

### Research by the main Agent (flow v1.9.0)
- Ciel's own browser test after PR #33 still took 31.8-40.5 s on the Langflow side. Research answers were written twice: the Web Research Assistant's Agent planned, searched and wrote notes, then the main Agent rewrote them, which cost about 8-14 s per research question. The first memory call after 5 idle minutes reloaded the embedding model (14 s), and analysis ran 3 search rounds inside the sub-flow.
- The main Agent now searches itself with Ciel Exa Search (5 results, highlights capped at 1,500 characters, key from the global variable), and Ciel Source Guard sits between the Agent and Chat Output. The Web Research Assistant tool is removed from the main flow; the sub-flow stays in Langflow as the rollback path and runs the same guard code.
- Prompt v14.6 rewrites "D. RESEARCH": fast research is one round with 2 queries at once, analysis at most 3 rounds, no `get_contents`, sources and URLs only from that run's search, numbered [n] and listed under "Sumber:". Mode Analisis now ends with "Sumber:" after the Batasan line when it searched (in production v1.8.0 only 3 of 6 analysis answers listed sources, because the format said to end right after Batasan). Every other v14.5 line is kept.
- Ciel Source Guard for the main flow: answers from runs without a search pass through unchanged, source lines without a URL (files, the Knowledge Base) are kept, and only the final answer's text block is kept. Langflow 1.12 derives `Message.text` from the text blocks and its setter joins them into one; Chat Output assigns it, so on the first test the app showed a tool round's text and the answer one after the other. The new test reproduces that behaviour and fails with the earlier guard code.
- Memory search and store send `keep_alive: "1h"` to Ollama, so the embedding model stays loaded for an hour after use (a warm call takes 0.04 s, a cold one took 5-14 s). `tests/test_flow_v141_contract.py` now treats v1.4.1's memory code as a historical snapshot (the current source minus the `keep_alive` line).
- Measured through ngrok with the same questions as before: chat 4.0-6.3 s, tutor 5.5-10.9 s, fast research 8.5-13.8 s, analysis 16.0 s (v1.8.0 with the source guard: up to 7.5, 40, 40.4 and 60.2 s). Every research answer listed sources that Exa returned in the same run. Response quality on a test copy: 9/9. Chat history across turns still works.
- Production was patched in place (same FLOW_ID). Backups: `main_v1.8.0_before_v1.9.0_20261017_192734.json` and `subflow_web_research_before_v1.9.0_guard_20261017_192734.json` in `~/.ciel_ai/flow_backups/`.
- New `tests/test_flow_v190_contract.py` (in CI): only the expected parts change from v1.8.0, the search tool and guard are wired, embedded code matches `flow/components/`, Exa settings and key, `keep_alive`, the research rules, and every other v14.5 line kept in order.

### Faster answers (flow v1.8.0 and Langflow host settings)
- Testers found Ciel too slow. Production traces (108 runs, 13-17 Oct) had a median of 29.9 s and a P90 of 127 s, with no answer under 10 s. Span timings showed the DeepSeek call for a simple chat took about 4 s, while the request spent 11-17 s before the Agent started.
- Cause 1: Langflow 1.12 logs each component's build result one after another after every graph layer (`_execute_tasks` in `lfx/graph/graph/base.py`), at 1-3.6 s per component. The Langflow Desktop `.env` now has `LANGFLOW_VERTEX_BUILDS_STORAGE_ENABLED=false`; those rows only feed the editor's build view. Messages and transactions are still stored.
- Cause 2: the Langflow SQLite database had grown to 3.2 GB, about 3 GB of it old tracing spans (tracing is now off). The `span` and `trace` rows were deleted and the database compacted to 232 MB. Row counts of flows, messages, variables, API keys, users, folders, transactions and files were identical before and after, and `quick_check` passed. A backup is in `~/.ciel_ai/langflow_db_backups/20261017_081932`.
- Cause 3: web research took 100-160 s. The Research Agent ran 7-9 search rounds on up to 37k characters per search, wrote a ~20k-character report, and the main Agent rewrote it. Now:
  - The main Agent (prompt v14.5) marks each research question `[RISET CEPAT]`, or `[RISET DALAM]` only in Mode Analisis, calls the Research Agent once, and keeps research answers in Mode Santai short. Every v14.4 line is kept.
  - The Web Research Assistant sub-flow (now versioned as `flow/subflows/Web_Research_Assistant.json`) does one search round with at most 2 queries in fast mode and at most 3 rounds in deep mode, never calls `get_contents`, asks for the date in the same round as the search, and returns notes (at most 5 or 10 findings, 4 or 6 sources). The anti-ngarang rules stay. Agent `max_iterations` 15 to 6; Exa highlights capped at 1,500 characters per result (0 meant unlimited).
- Follow-up on the same day: the research sub-flow's DeepSeek model runs with thinking off (`model_kwargs = {"extra_body": {"thinking": {"type": "disabled"}}}`, as in DeepSeek's thinking-mode docs; the main Agent keeps thinking on). Measured on 9 direct runs per setting: median 12.5 to 10.7 s, max 16.7 to 11.5 s, notes of the same shape. The experiment also showed that with 3 Exa results and one search the notes sometimes cited sources that were not in the recorded search output. The prompt now requires 2 different queries in fast mode and says every source and URL must come from that run's search results; Exa is back to 5 results (highlights stay capped at 1,500 characters). 2 of 9 runs still cited URLs that no recorded search had returned. A later probe found Langflow recorded every search, so these were sources from memory. Details in `docs/OBSERVABILITY.md`.
- Ciel Source Guard (in production since 2026-10-17): new `flow/components/ciel_exa_search.py` records every URL Exa returns in the graph context, and `flow/components/ciel_source_guard.py` removes "Sumber:" entries whose URL Exa did not return, their `[n]` markers, and findings that cited only them, then says how many it removed. Notes without a "Sumber:" section pass through unchanged. Langflow finds a component class by its written bases, so `CielExaSearch` lists `Component` next to `ExaSearchToolkit`; `build_toolkit` is annotated `-> Tool` so the output is a tool. Tested on a copy of the sub-flow: 9 normal runs removed nothing; a fake source added on purpose was removed together with its finding, including a finding written below the source list. In production the official Exa node is replaced by Ciel Exa Search with the same settings (key from the global variable), and the guard sits between the Agent and Chat Output. Backup: `subflow_web_research_before_source_guard_20261017_095839.json`. End to end through ngrok after the install: fast research 9.8-40.4 s, analysis 60.2 s, all with sources. The guard takes under 0.1 s; the variation comes from the main Agent's DeepSeek calls. `tests/test_flow_v180_contract.py` checks the wiring and that the embedded code matches the repository files. `tests/test_source_guard.py` (in CI) covers real-shaped notes, URL variants (Markdown links, parentheses, www, trailing slash), entries without a URL, marker lists, the shared context key and the recording wrapper. Backup: `subflow_web_research_before_thinking_off_*`.
- Production was patched in place (same FLOW_ID and sub-flow id). Backups of the previous versions are in `~/.ciel_ai/flow_backups/` (`main_v1.7.0_before_v1.8.0_*`, `subflow_web_research_before_fast_*`).
- Measured through ngrok with the same questions before and after:

  | Type | Before | After |
  |---|---|---|
  | Chat | 21.7 s median | 5.3 s |
  | Tutor | 18.8 s | 6.9 s |
  | Fast research | up to 147 s | about 22 s median, 37 s max |
  | Analysis with deep research | 157 s | 45 s |

  Research answers still end with real sources. `docs/OBSERVABILITY.md` has the table and how to find where a slow request spends its time.
- During testing the PC ran out of memory (about 160 MB available, committed memory near its limit). Langflow, Ollama and ngrok all timed out until unused apps were closed. Documented in `docs/OBSERVABILITY.md`.
- Quality collector (`tests/results/quality_latest.json`, labeled v1.8.0): response quality 8/9, median 6.4 s, P95 18.7 s (was 14.6 s and 16.7 s). The failed case, research_machine_learning_01, answered on topic with sources but without the keyword; three reruns passed. knowledge_overfitting_01 now accepts "training", "data latihan" or "pelatihan" (an earlier run failed on "data latihan").
- New `tests/test_flow_v180_contract.py` (in CI): only the prompt changes from v1.7.0, every v1.7.0 line stays in order, both research modes are routed, and the sub-flow keeps its limits, source rule, thinking-off setting, anti-ngarang rules and global-variable keys.

### Send button clear of Streamlit Cloud's badges on phones
- On Android the send button sat under Streamlit Community Cloud's bottom-right badges (Streamlit logo and creator avatar). Cloud runs the app in an iframe and draws those badges in the page around it, so app CSS can't move or hide them.
- `UI_JS` marks `<html data-ciel-hosted>` when the app runs inside an iframe; on screens up to 960px wide (where the composer reaches that corner) the composer is lifted by 3.5rem and the end of the chat gets matching room. Run locally, nothing changes; on wide screens the composer is centred and never reaches the badges, so it isn't lifted.
- Checked on Streamlit 1.65: at 375px inside an iframe the send button ends 69px above the bottom edge (it used to sit inside the badge area); opened directly or at 1280px inside an iframe, the composer is unchanged. `tests/test_theme.py` covers the flag and the rule.

### Disabled buttons stay readable on hover
- In the account menu, "Hapus semua memoriku", "Hapus semua datasetku" and "Hapus riwayat chat-ku di server" (disabled until their checkbox is ticked) lost their label when the pointer was on them in dark mode: the hover background met Streamlit's light-theme disabled text (`rgba(28, 27, 25, 0.4)` on `#2a2824`). Without hover they looked exactly like enabled buttons.
- Disabled buttons now have their own rule (after the primary-button rules): transparent background, thin border, `--c-faint` text and icon, `not-allowed` cursor, and no change on hover. Checked with a real pointer hover on Streamlit 1.65: 5.7:1 in dark mode and 5.5:1 in light mode, and visibly muted next to enabled buttons. `tests/test_theme.py` covers the rule and its order.

### Dark mode inside popovers
- In dark mode the account menu showed "Data saya", "Tampilkan memoriku", "Tampilkan datasetku" and "Keluar" as light boxes with light text (contrast about 1.1:1), and "Proyek baru" had a light text box with light text. Popover content renders outside `.stApp`, and the button and expander rules were scoped to `.stApp`; on Streamlit 1.65 the text input box is also drawn on a new element (`stTextInputRootElement`).
- Button, primary-button and expander rules now cover `:is(.stApp, [data-testid="stPopoverBody"])` (same specificity as before), the text input rule includes `stTextInputRootElement`, and success/error/warning messages use `--c-ok`/`--c-err`/`--c-warn` (they were 3.2-3.4:1 in dark mode).
- The project file uploader (sidebar, shown once a project exists) had a light "Upload" button, an invisible "200MB per file • TXT, ..." hint (1.06:1) and an invisible "?" help icon. The button, the hint and the help icon (`stTooltipIcon`, which needed a more specific selector than Streamlit's own) now use the tokens.
- The account menu needs a signed-in user, so it was checked on a scratch page with the app's own CSS and the same widgets, on Streamlit 1.54 and 1.65: every text in both popovers reaches 4.5:1 in both themes. A contrast scan of chat, pricing, privacy and sign-in on 1.65 found nothing below 4.5:1 in either theme. `tests/test_theme.py` covers the popover scope, the input element and the message colours.

### PDF attachments
- PDFs can be attached in chat and added to projects. The backend only takes text, so `read_text_file` extracts the text with `pypdf` (new dependency, `pypdf>=6` in `requirements.txt` and CI) and then treats it like any text file: same per-file character limit, truncation flag and prompt section.
- Extraction stops once the text passes `MAX_FILE_CHARS` or after `MAX_PDF_PAGES` (100) pages, so a large upload doesn't keep the server busy. No OCR: a PDF without extractable text (e.g. a scan) is refused with a hint to send it as a photo; password-protected and damaged PDFs are refused with a short message (damaged ones are logged).
- Pricing lists "Lampiran foto, PDF, dan file teks"; README describes the behaviour.
- Checked in the browser: a generated two-page PDF attached in the chat composer was accepted, and the prompt the app sent (184 characters in the server log) matched exactly what `build_payload` produces with both pages' text. New `tests/test_pdf_attachments.py` (in CI): text extraction, character and page limits, scanned, damaged and password-protected PDFs, text files unchanged, and pdf allowed in chat and projects.

### Dark mode and a shorter upload hint
- Dark mode with the same roles on dark paper (`DARK_TOKENS`: background `#161513`, text `#eceae4`, accent `#9db3e8`, gold `#e9d06a`). It follows the device setting; a moon/sun button in the top bar overrides it, and the choice is kept in the browser (`localStorage`, page still works when storage is blocked). The choice lives on `<html data-ciel-theme>`, which React never touches. Every text pair passes WCAG AA in both themes.
- Streamlit's own widgets take colours from the light theme in `config.toml`, so their surfaces now point at the tokens (captions, popovers and their inputs, tooltips, chat message text and avatars, expanders, inline code, the "+" upload button, sidebar and heading icons). Light mode is unchanged. A scan of every visible element on chat, pricing, privacy, sign-in, the popover, the tooltip and an error card found no light leftovers in dark mode and none in light mode.
- The "+" button's tooltip listed every accepted extension ("Upload or drag and drop files (TXT, MD, MARKDOWN, ...)"); it now says "Lampirkan file atau foto", also used as the button's accessible name. Streamlit has no option for this text, so `UI_JS` replaces it when the tooltip appears.
- The toggle icon is drawn in CSS because `st.html` strips inline SVG. The hidden script container is renamed `pagejs`.
- The sidebar's « collapse button stayed black in dark mode: Streamlit colours its icon itself, and the button only appears while the sidebar is hovered, so the first scan missed it. Its icon and hover now use the tokens; a rescan with every hover-only element forced visible found nothing else.
- New `tests/test_theme.py` (in CI): every light colour token has a dark value, both themes pass AA, dark tokens follow the device and the toggle, the toggle and storage contract, and the upload hint.

### Personal datasets that grow over time (flow v1.7.0)
- Ciel can now learn from a user's own data over time, without keeping any model. Signed-in users ask Ciel to save a CSV/TSV ("simpan file ini ke datasetku") or to log rows from the chat ("catat: hari ini belajar 3 jam, nilai kuis 80"). The new tool Ciel Dataset Store (`manage_dataset`) grows one dataset per topic, and Table Analyst and ML Analyst read it by name, so statistics and models always use the whole history.
- Storage: `~/.ciel_ai/user_datasets/<owner>/<name>.csv` on the Langflow host. The owner comes from the app (same hash as long-term memory), never from the Agent. Anonymous visitors store nothing, and names cannot leave the owner's folder. Limits: 5 datasets, 10.000 rows and 1 MB each.
- Safety: Ciel saves only on an explicit request. Columns must match to append, the same file is not saved twice, and numbers are rewritten in the dataset's own format. The Agent cannot delete. "Data saya" now lists, downloads and deletes datasets through new Memory Admin actions.
- Privacy page (updated 16 Oktober 2026): describes personal datasets and the right to view, download and delete them, only when login is configured.
- Prompt v14.4 keeps every v14.3 line. Langflow ignores tweaks for fields a flow does not have (checked in `lfx/processing/process.py`), so the new app also works with the v1.6.0 flow.
- Tests (in CI): `tests/test_flow_v170_contract.py` and `tests/test_personal_datasets.py` cover the store, analysts on saved data, isolation between accounts, admin actions, app tweaks and the privacy text. The v1.5.0 and v1.6.0 snapshot tests became historical, as v1.3.0's did in v1.4.1.
- Live test (2026-10-16) through ngrok on a separate "(test)" flow with a fake test account; production untouched, test flows and test data deleted afterwards.
  - Day 1: a 30-row study log saved as dataset `belajar`, and a row typed in the chat appended with the right column names.
  - Later sessions without a file: the average came from all 31 rows; "apa yang paling memengaruhi nilai kuisku?" trained on the saved dataset (R² 0,94, study hours first).
  - Guards: a question about an attached file saved nothing; an anonymous save was refused; "hapus dataset belajarku" was sent to Data saya.
  - Admin actions on a temporary copy of the admin flow: list, download and delete work, another account's dataset is `not_found`, and the memory list still works.
- Fixed after the live run (prompt): the Agent listed datasets even when the user named one, and twice said a message "terkirim dua kali". The second came from Langflow showing the current message again in the chat history; it was stored once. Retest: named datasets go straight to the tool, and two rows logged in a row got no duplicate remark.
- Google login: `[auth]` and `MEMORY_ADMIN_FLOW_ID` were added to the deployed app's secrets on 2026-10-16, and sign-in works. The Google OAuth app was then published (Branding completed, status "In production"), so any Google account can sign in.
- Production (2026-10-16, after #23 was merged with CI green): the main flow was patched in place to v1.7.0 (same FLOW_ID), and the "Ciel Memory Admin" flow to the version with dataset actions (same ID). Before patching, both were checked against their previous repo versions (same nodes, values and edges), so no production-only change was overwritten. Backups: `~/.ciel_ai/flow_backups/prod_v1.6.0_before_v1.7.0_20261016_033534.json` and `admin_before_datasets_20261016_033534.json`. After the patch: 14 nodes including `CielDatasetStore-d4tA5`, prompt v14.4; the admin node has the `dataset_name` input.
- Verified through ngrok against production with a fake test account: a 30-row file saved as dataset `belajar`; "apa yang paling memengaruhi nilai kuisku?" trained on the saved dataset (study hours first, R² 0,94); an anonymous visitor's file question was answered without saving anything; the admin flow listed, exported and deleted the dataset, and the memory list still worked. The test data was deleted afterwards.
- Checked by the owner in a browser with a real signed-in account: the dataset part of "Data saya" works and looks right.

### Machine learning on the user's own files (flow v1.6.0)
- New tool Ciel ML Analyst (`flow/components/ciel_ml_analyst.py`, tool `train_model`) on the same CSV/TSV files the app already sends to Ciel Table Analyst. `task=predict` trains a linear regression (numeric target) or logistic regression (category target) and reports the strongest factors in the column's own units; `predict_for` predicts a new row. `task=cluster` groups similar rows with k-means, choosing the number of groups by silhouette unless the user gives it.
- Anti-fabrication for models: quality is measured with 5-fold cross-validation and compared with a simple baseline (mean or most common class). Weak models, near-perfect results (possible target leakage), small files, truncated or sampled files are flagged under "Catatan untuk jawaban", together with "hubungan statistik, bukan sebab-akibat".
- numpy only, fixed seed, no new dependency on the Langflow host (scikit-learn is not installed there). Row numbers and ID-like columns are skipped automatically.
- Prompt v14.3: routes prediction and grouping questions on user files to the tool, forbids derived target columns as features, requires the model quality in the answer, and lets the study-companion mode explain ML with the user's own data. Every v14.2 line is kept.
- App: sends the same encoded tables to `ML_ANALYST_ID` (default `CielMLAnalyst-m7Lq2`). Langflow ignores tweaks for node IDs that are not in the flow, so the new app also works with the v1.5.1 flow.
- Tests (in CI): `tests/test_flow_v160_contract.py` (node wiring, embedded code and hash, only the ML node, its edge and the prompt change from v1.5.1, prompt lines) and `tests/test_ml_analyst.py` (recovers known effects from synthetic data, beats the baseline, flags weak and leaky models, cluster recovery, determinism, input errors, Langflow string processing, file-reading helpers identical to Table Analyst). The helper check caught a lost non-breaking space in the first copy of `clean()`.
- Live test (2026-10-15) on a separate flow "Ciel AI Long-Term Memory Master v1.6.0 (test)" through ngrok, production flow untouched, with the app's payload (20-row preview + base64 tweaks): important factors, new-row prediction ("belajar 6 jam, kehadiran 90"), pass/fail classification, customer segments and a plain average per city. Each went to the right tool (the average stayed with analyze_table); the Agent left out the derived `lulus`/`nilai` columns by itself; the three planted customer segments were found (silhouette 0,70); tool numbers matched a local run exactly. 18–32 s per answer.
- Fixed after the live run: the Agent re-ranked factors by their "setiap +1" effects (hours against percentage points) and put a weaker factor first. Regression effects now also give the change for +1 standard deviation, and the tool says the order is already comparable and must be kept. Retest: correct order, standard-deviation figures quoted.
- Production (2026-10-16, after #21 was merged with CI green): the production flow was patched in place to v1.6.0, keeping the same FLOW_ID. Before patching, the production flow was checked against `flow/v1.6.0`'s base `flow/v1.5.1`: same nodes, values and edges, so no production-only change was overwritten. Backup: `~/.ciel_ai/flow_backups/prod_v1.5.1_before_v1.6.0_20261015_214444.json`. After the patch: 13 nodes including `CielMLAnalyst-m7Lq2`, prompt v14.3.
- Verified through ngrok against production: important factors (kept the tool's order, quoted the standard-deviation figures, left out `lulus`), customer segments (3 segments, silhouette 0,70), a plain average per city (still `analyze_table`), and a question without a file (answered without tools). 19–35 s per answer. The "(test)" flow was deleted afterwards.
- Not yet checked: a CSV upload through the deployed Streamlit app.

### Cleaner chat composer
- Focusing the message box drew a second, square box around the text inside the rounded composer: the app-wide `:focus-visible` outline also applied to the composer's textarea. The textarea's outline is now off; the composer's own border, which turns ink navy on focus, stays the single focus indicator. Checked in the browser.

### Running 24/7
- Problem: Ciel stopped answering when nobody was watching. Streamlit Community Cloud sleeps the app after 12 hours without visitors, and on the host only Ollama started by itself; Langflow Desktop and the ngrok tunnel were started by hand and stayed down after a crash or reboot.
- `.github/workflows/keep-awake.yml` + `tools/wake_streamlit.py`: every 4 hours a headless browser opens the app, presses the wake button if the app sleeps, and waits for the app to render (also inside Cloud's iframe). Needs the repository variable `STREAMLIT_APP_URL`; skips without it. A failed run emails the owner. Page load only: no ngrok requests or model tokens.
- `tools/ciel_watchdog.ps1`: checks Ollama, Langflow (`/health_check`) and the ngrok tunnel (agent API on 4040) and starts what is down, in that order. Desktop gets a 10-minute boot window, counted from when its processes started, before it is restarted. A stale ngrok agent is stopped first, since it holds the static domain. The tunnel only starts with the traffic policy file, and the script checks once that the public URL answers 401 without credentials, stopping the tunnel otherwise. Healthy runs send nothing through the tunnel, so the watchdog does not use ngrok's monthly request quota. `-Install` registers the Task Scheduler task "Ciel backend watchdog" (at logon + every 5 minutes, hidden with `conhost --headless`).
- `tests/test_keep_alive.py` (in CI): the wake script imports without Playwright and finds the app in any frame; the schedule stays well inside 12 hours; the URL comes from a variable via `env`; the watchdog never starts a tunnel without the policy and contains no tunnel URL or credentials.
- Checked: watchdog dry runs on the host (healthy in 1 s, wrong tunnel and missing policy detected, headless launch writes the log); wake script against the local app (awake, exit 0), a simulated sleeping page that loads the app in an iframe after the button (woken, exit 0) and an error page (exit 1).
- After deploying: the keep-awake workflow passed against the deployed app ("awake", 51 s). The first restart test failed: the running ngrok had been started from an administrator PowerShell window, so the task, which has no admin rights, could not stop it, and would have started a second agent that cannot bind the same static domain. The watchdog now logs that the agent cannot be stopped and starts nothing. With ngrok started by the task: from nothing in 13 s, after killing the agent in 11 s, Basic Auth active (401 without credentials, `/health_check` ok with them), and the next healthy run logs nothing.
- Langflow restart test, first try: after Desktop was closed, the watchdog reopened it but gave up after its 4-minute window; Desktop took about 5 minutes (2 min 40 s before it even launched the backend), and the next run would have killed it mid-boot. Also found: Desktop does not respawn a backend that died, so its window stays open with nothing behind it. The boot window is now 10 minutes counted from when Desktop's processes were created (so a later run does not restart a booting Desktop), and a Desktop open for 5 minutes without any backend process is restarted right away. Retest: Desktop closed, healthy again in 137 s; backend killed with Desktop left open, restarted at 312 s and healthy in 130 s; afterwards `/health_check` through the tunnel with credentials returned ok.

### Privacy page reviewed against UU 27/2022 (PDP)
- Review found the page silent on processing outside Indonesia and on children, the two high-priority gaps for a public study companion. Article references were checked against the law's text; this is a product checklist, not legal advice.
- Added: who runs Ciel (new `OPERATOR_NAME` config) and where to send requests (`CONTACT_URL`) (Pasal 5); purpose and basis (consent, withdrawable) (Pasal 20-21); third-party AI model and web search providers whose servers can be outside Indonesia, without brand names (Pasal 56); the full list of data-subject rights and that requests are recorded and answered (Pasal 6-14); users under 18 use Ciel with a parent or guardian's permission (Pasal 25); written notice within 3x24 hours if a data protection failure affects them (Pasal 46); changes announced on the page before they apply, with a "Terakhir diperbarui" date (Pasal 21 ayat 2).
- Before going public: set `OPERATOR_NAME` and `CONTACT_URL` in the deployment secrets, and have a procedure for the 3x24-hour breach notice the page now promises.
- `tests/test_privacy.py`: the page covers every checklist item, discloses third parties without brand names, and the app passes the operator name.

### Hide-on-scroll navbar works on Streamlit Cloud
- Problem: on the deployed app the top bar never slid away when scrolling down. The script bound its scroll listener to `section.stMain` once; when that element is replaced after the script ran (the Cloud app shell can remount it), the listener stays on the detached element. Reproduced locally by swapping the element: the bar stayed visible. Not a version issue: Streamlit 1.65 (what Cloud installs) has the same DOM and worked locally.
- The listener now sits on `document` in the capture phase and uses whichever element scrolls (ignoring the sidebar); the run-once guard moved to `window`. A container seen for the first time counts from the top, so the first scroll after load is not dropped (found while testing with a real mouse wheel).
- Checked on Streamlit 1.54 and 1.65: normal scrolling, after the scroll container is replaced, inside an iframe (as on Cloud), sidebar scrolling ignored, and real mouse-wheel scrolling. Not yet checked on the deployed app itself.

### Warm, minimal redesign and a sign-in page
- Anti "AI slop" pass after a design review (structure and copy, not colors):
  - Fonts: headings and labels inside markdown (plan names, prices, FAQ questions, sidebar labels) rendered in Streamlit's Source Sans instead of Geist, because only `p`/`li` were overridden; the markdown container now sets Geist. Weight 560 (not loaded) became 600. Pills and labels no longer use the monospace face; it stays for code, file names and sizes.
  - One tagline instead of three: the top bar and sidebar show only the wordmark. The home hero says "Kalau sumbernya tidak ada, Ciel bilang tidak tahu." and, instead of a four-item feature list, shows a sample analysis-mode answer in the flow's real format ("Analisis dimulai.", Kesimpulan, Dasar with [Terverifikasi]/[Dugaan] labels, Tingkat keyakinan, Batasan), marked as illustrative data. Starter prompts lost their arrow glyphs.
  - Pricing: no monthly/yearly toggle and no disabled "Segera hadir" buttons for plans that can't be bought. Gratis is the one plan card; Pro and Tim are listed under "Sedang disiapkan" with "Rencana Rp…/bulan". `plan_price`/`YEARLY_MONTHS_CHARGED` removed, `planned_price` added.
  - Sign-in page shows only working controls: no disabled email/password form (a note says it is coming), no Google button unless `[auth]` is configured, and "Lanjut tanpa masuk" becomes the primary action when it is the only one.
  - Privacy page, "Apa yang terjadi saat kamu mengirim pesan": dropped "(Langflow yang berjalan di komputer pengelola)" and the sentence naming DeepSeek and Exa as third-party processors, at the owner's request. The page now says messages go to Ciel's server and that photos and memory embeddings are processed on Ciel's own server.
  - Indonesian labels in the sidebar and error card ("Chat baru", "Proyek", "Riwayat", "Semua chat", "Hapus chat", "Coba lagi", "Detail teknis", badge "Gagal").
  - Errors: messages no longer start with an emoji and no longer tell public users to check ngrok or Langflow Desktop. What users read is a plain sentence with advice; HTTP status, Request ID and cause sit under "Detail teknis". A `CielError` (str subclass) now marks a failure instead of the leading emoji (`ERROR_MARKERS` removed).
  - Tests: every `ask_langflow`/`upload_images` failure is a `CielError` whose title and advice are ASCII and free of backend names; normal text starting with an emoji is not an error; pricing has a single button and no billing toggle; the sign-in page has no inputs or disabled buttons.
- New light palette "Kertas & Tinta": neutral paper canvas (`#f3f2ee`), off-white cards (`#fcfbf9`), warm ink-black text (`#1c1b19`) and warm greys, so the ink-navy accent (`#203a72`) is the only cool colour on screen and marks actions, the current page and verified claims; highlighter gold (`#f4dc6e`) marks guesses. It replaced a first pass ("Gading & Navy Tinta") whose cool navy-tinted greys clashed with its yellowish ivory canvas and made the accent blend into body text. The `--c-*` tokens in `CIEL_CSS` and `.streamlit/config.toml` match, so pricing, privacy and sign-in follow automatically. Fraunces (serif) for the wordmark and page titles; softer radii and light shadows on cards, the user bubble and the composer. Every text pair passes WCAG AA (body 15.4:1, faintest text 5.1:1, success/error 5.7–5.8:1), input borders 3.7:1.
- New sign-in page at `?page=login` (`login.py`), opened from "Masuk" in the sidebar (shown whenever the user is not signed in; it replaces the sidebar's direct "Masuk dengan Google" button). "Masuk dengan Google" calls the existing `st.login` and is disabled with an explanation when `[auth]` is not configured. Email and password sign-in is UI only: fields and button are disabled and marked "Segera hadir", since there is no account backend. Notes under the form follow the configured rate limits and login state; "Lanjut tanpa masuk" returns to chat, which still works without signing in.
- Navigation moved to the top bar: "Harga", "Privasi" (text links, the current page underlined) and "Masuk" (outline button) sit right of the wordmark in one flex row that stays on one line on phones, where the sidebar is collapsed. Signed in, "Masuk" becomes an account menu with the long-term memory status and ID, "Data saya" (moved unchanged) and "Keluar". The sidebar now holds only New chat, Projects, History and Clear chat; the "About long-term memory" text moved into the sign-in page notes. The main area's top padding clears Streamlit's header toolbar so it no longer covers the nav. The top bar is sticky (on Streamlit's layout wrapper, under a now-solid header), so the nav stays reachable on long pages, on desktop and phone. While scrolling it follows the page pixel for pixel (scrolling down pushes it up behind the header, scrolling up pulls it back); when scrolling stops it glides fully in or out by the last direction, so a small scroll up always brings it back. It always shows at the top and when the nav has keyboard focus. Nav links get an underline that grows from the centre on hover; the current page keeps an accent underline. This runs as a small script through `st.html(..., unsafe_allow_javascript=True)` (`NAV_SCROLL_JS`); the state lives on `<body>` so reruns don't reset it. `streamlit[auth]>=1.54`, the version this was tested on. Privacy page and README point to the account menu instead of the sidebar.
- `tests/test_login.py` (in CI): notes follow the configuration and never promise email sign-in, the page renders without the composer, every sign-in control is disabled without `[auth]`, and "Lanjut tanpa masuk" returns to chat; the nav is in the top bar and not the sidebar, "Masuk" opens the sign-in page, and a signed-in user (mocked `st.user` with `[auth]`) gets the account menu with memory status, "Data saya" and "Keluar". Checked in the browser at desktop and 375px (chat, pricing, privacy, sign-in); the signed-in menu was not checked with a real Google account.

### Privacy page, "Data saya" and chat retention
- Problem: users were not told what Ciel stores or sends to third parties, could not see or delete their long-term memories ("Memory belum dapat dilihat atau dihapus dari aplikasi"), and Langflow kept every message of every session indefinitely.
- New "Privasi" page (`privacy.py`, sidebar): what happens to a message (DeepSeek, Exa, local models), what is stored and for how long, how to control it, and what not to send. The content follows the configuration: retention days, whether login/memory is active, whether data controls are available, and `CONTACT_URL`.
- New "Data saya" panel for signed-in users: list memories, delete one, delete all (with a confirmation checkbox), and delete their own chat history on the Langflow server (with a confirmation checkbox). Chat history is deleted by Langflow session and only for sessions starting with the user's own key.
- Memory actions go to a separate flow with the new Ciel Memory Admin component (`flow/components/ciel_memory_admin.py`), set up with `MEMORY_ADMIN_FLOW_ID`. It is not an Agent tool, takes the owner only from the app's tweak, and only touches that owner's memories. Without `MEMORY_ADMIN_FLOW_ID` the panel says data controls are not active and the privacy page does not promise them.
- The admin flow is in `flow/memory_admin/Ciel_Memory_Admin.json` (Ciel Memory Admin -> Chat Output with "store messages" off). Created in Langflow as a new flow next to production. Live check through ngrok with throwaway owners: anonymous and unknown actions refused; list shows only the owner's memories; another owner's ID returns `not_found`; delete one and delete all remove only the owner's memories (collection size unchanged afterwards); the flow stores no messages; deleting chat history removed the user's two test sessions and kept another user's session.
- Retention: `tools/prune_chat_history.py` deletes Langflow messages older than `CHAT_RETENTION_DAYS` (default 30), with `--dry-run`; meant to run daily on the Langflow host (Task Scheduler example in README). Long-term memory is not affected.
- `tests/test_privacy.py` (in CI): the admin component against a real Chroma database (owner isolation for list, delete and delete all; anonymous and unknown actions refused; no reserved input names), the app's admin request and session filtering/batching, the privacy page content and rendering, and the retention script's timestamp parsing, paging, deletion and dry run.

### Pricing page matches what the app offers
- Problem: the pricing page sold Pro (Rp79.000/month) for long-term memory, photo attachments and projects, which every visitor already gets for free, and the free plan listed less than the app provides. Plans are not enforced and there is no payment system.
- The free plan now lists everything available (research with sources, math, CSV/TSV analysis, photos and text files, projects, session history), plus long-term memory "perlu login" when Google login is configured and the hourly message limits. Limits and login state come from `app.py` (`RATE_LIMIT_*`, `[auth]`), so the page follows the configuration.
- Pro and Tim are shown as plans: tag "Segera hadir", prices labeled "Rencana", buttons always disabled (also when `CONTACT_URL` is set). Pro no longer claims features the free plan has; it plans higher message limits. `CONTACT_URL` now adds a "Hubungi kami" link for people interested in paid plans.
- Header and FAQ describe the current state: Ciel is free with hourly limits; paid plans are not open; memory needs login (or is not active when login is not configured); why limits exist.
- `tests/test_pricing.py` checks that unavailable plans claim no free feature, only available plans are highlighted, paid buttons stay disabled with a contact URL, and the free plan and FAQ follow the limits and login state passed by the app. Checked in the browser.

## v1.5.2 — 2026-10-14

App hardening, tests, documentation and Langflow operations. The main flow is unchanged since v1.5.1 (`flow/v1.5.1`).

### Langflow configuration changes (made in Langflow; sub-flows are not in this repo)
- Sub-agent history: Agent `n_messages` in the Web Research Assistant sub-flow 100 -> 0, in Math Tutor Agent 100 -> 4. The main Agent already sends sub-agents a complete question. Measured in one chat, the research sub-agent loaded 9,663 and 22,750 characters of unused history on the 2nd and 3rd research question, and 0 after the change; answers kept their sources and a math follow-up was still answered correctly. The production flow's default session had accumulated ~490k characters of research history, which every live test run loaded.
- API keys: the literal DeepSeek `api_key` in the production sub-flows Verified Data Analyst (2 nodes) and Math Tutor Agent (1 node) now points at the global variable `DEEPSEEK_API_KEY`, the one the main flow and Web Research already use. No production flow stores a literal key anymore. Verified through ngrok.
- Old flows: the 22 flows not used by production (experiments, earlier versions, backups, test flows) moved to a new Langflow project "Arsip"; nothing was deleted. "Starter Project" holds only the 5 production flows. Archived flows still contain one DeepSeek key copied into 10 flows and one Google key; clean them before exporting or sharing an archived flow.
- Langflow API keys: deleted the 5 never-used "MCP Project Starter Project - langflow" keys; only the app's key remains. The key exposed in the public v1.0.0/v1.1.0 snapshots was already rejected (HTTP 403). No local MCP client referenced Langflow.
- DeepSeek temperature: not changed. `deepseek-flash` ignores it: at temperature 0 four runs gave four different answers, while an out-of-range value was rejected by DeepSeek itself, so the value is sent. This matches DeepSeek's documentation (temperature has no effect in thinking mode).
- Every in-place change has a backup in `~/.ciel_ai/flow_backups/` on the Langflow host.

### Documentation and release tags
- README, RELEASE_CHECKLIST, docs/OBSERVABILITY, docs/BACKUP_AND_DISASTER_RECOVERY, docs/ARCHITECTURE and docs/PRODUCTION_READINESS_REVIEW describe the current state instead of v1.1.0. BACKUP_AND_DISASTER_RECOVERY now covers the parts that are not in Git: sub-flows, Langflow global variables, the ngrok traffic policy, and the Chroma memory database.
- Release tags v1.2.0 to v1.5.2 point at the commits listed in RELEASE_CHECKLIST.md.

### Remove unused code
- Removed `check_backend_health` from `app.py` (117 lines). It was left behind when the backend status panel was removed and was never called. The `/health_check` endpoint itself is unchanged and is still used by `tests/test_ciel_master.py` and the recovery checks in `docs/`.
- `tests/test_app_hygiene.py` (in CI) fails when a top-level function or constant in `app.py` is never referenced; run against the previous `main` it flags exactly `check_backend_health`.
- Checked that `app.py` still renders with Streamlit's `AppTest` (no exceptions; chat input, sidebar and starter prompts present).

### Error messages no longer show internal details to users
- Three error paths showed raw technical text to public users: an unknown Langflow response shape printed the whole response JSON (flow structure, tool content), and other request errors and image-upload errors printed the raw exception, which can contain the ngrok host and URL.
- Users now get a short explanation and a Request ID (shown under "Technical details" in the existing error card). The response JSON (first 500 characters) and the exception type and text go to the server log under the same Request ID. The title lines are unchanged, so the error card and Retry work as before.
- Checked in the browser against a mock Langflow that returned an unexpected shape with a marker string: the card showed the explanation and Request ID, the marker was not on the page, and the server log had it under that Request ID.
- `tests/test_resilience.py`: unknown response shape, `InvalidURL` / `TooManyRedirects` / `ChunkedEncodingError` on requests, and upload errors must not show the host or raw JSON, must show a Request ID, and must log the detail.

### Quality run with isolated sessions, and two test fixes
- First full collector run with the session-isolated scripts (production flow v1.5.1 with the sub-agent `n_messages` change, through local Langflow): first request 50.6 -> 16.8 s, median 18.9 -> 15.5 s, P95 43.1 -> 29.8 s compared with the previous v1.5.0 run that used the shared default session. Response quality 8/9; the collector named the failing case for the first time: `research_machine_learning_01`, "Tidak menemukan: 'machine'". Two reruns of that question answered about machine learning with dates and sources and contained the term. `tests/results/quality_latest.json` holds this run, labeled v1.5.1.
- `research_machine_learning_01` now accepts "machine" or "pembelajaran mesin" (`expected_any`): an Indonesian answer may use the Indonesian term. A test checks that an unrelated answer still fails.
- Failed cases keep the answer: `test_response_quality.py` prints a 1,200-character preview for failed cases (160 for passed ones), and `collect_quality.py` stores it as `failed_cases[].answer_preview` and prints its start. The failing answer of the run above was not recorded because this did not exist yet.
- Live run with these fixes (same setup): response quality 9/9, automated checks 5/5, status healthy, memory recall K=5 100%; first request 17.4 s, median 14.6 s, P95 16.7 s. `tests/results/quality_latest.json` holds this run.

### Live test scripts: one session per request, app tweaks, user-visible answer
- Problem: `tests/test_response_quality.py`, `tests/test_performance_snapshot.py` and `tests/test_ciel_master.py` sent no `session_id`, so every live test used the production flow's default Langflow session. Its research sub-agent history had grown to ~490k characters (until the sub-agent's `n_messages` was lowered on 2026-10-14), test cases influenced each other, and a 9/9 suite flaked to 8/9. The scripts also judged `data.text`, which in Langflow 1.12 joins every Agent round, so duplicated text was evaluated instead of the answer users see.
- New `tests/live_session.py`, used by all three scripts: a fresh `session_id` per request (`livetest-<label>-<id>`), the tweaks the app sends for an anonymous visitor (memory off, no tables), and `answer_from()`, which runs `app.final_answer_text` loaded from `app.py`, so tests and app share one implementation.
- `tests/collect_quality.py` records failing response-quality cases with their reasons (`response_quality.failed_cases`) and prints them, so a degraded run says which case failed.
- `tests/test_live_scripts.py` (offline, in CI) checks that every run payload in the live scripts has `session_id` and `tweaks`, that none reads `["data"]["text"]` directly, that two cases get two sessions and the vision case keeps its image tweak, and the failed-case parser.

## v1.5.1 — 2026-10-14

### Project files are no longer resent with every message
- Problem: project file text (up to 150k characters) was added to every message in a project chat. Langflow stores each message with that text and the Agent loads the last 10 messages, so from the 3rd turn the same file reached the model several times in one request (up to 6 copies).
- The app now sends project file text only for a new chat, when the project files change (`project_signature`), or every `PROJECT_CONTEXT_REFRESH_TURNS = 4` turns, before the last copy leaves the Agent's 10-message window. Other turns name the files ("isinya sudah dikirim di pesan sebelumnya") so the Agent uses the copy in its history. The record is kept per chat and updated only after a successful answer.
- Budgets: `MAX_CONTEXT_CHARS` 150,000 -> 80,000 and `MAX_FILE_CHARS` 60,000 -> 40,000 per text file, so the at most two copies in a request stay modest. CSV/TSV files are unaffected (preview in the prompt, full file to Ciel Table Analyst).
- Simulation with the app's own functions (60k-character project file, 10 turns, 1.5k-character answers): peak context per request 368k -> 88k characters, total over 10 turns 2.76M -> 0.62M (-78%), copies of the file per request at most 2 instead of 6. `tests/test_project_context.py` keeps that bound over 12 turns and checks that the file is always visible to the Agent.
- Live on the test flow: after sending a proposal once, turns 2-4 sent about 200 characters instead of 1,400, and the Agent answered three detail questions from it correctly (supervisor, a budget line, risk and harvest week).

### Fix: duplicated answers and English-format numbers (flow v1.5.1)
- **Duplicated or glued answers.** In Langflow 1.12.4 `Message.text` (and `data.text`) joins every text block of every Agent round: text written before a tool call, an answer the model wrote twice, and internal narration. Users saw answers twice ("…23,685 … 23,69.Rata-rata Quantity_Sold…"), text glued without a space ("…filenya ya.Ini hasilnya"), and on research questions the agent's narration ("Saya akan mencari… Pertama, mari cek tanggal…"). `ask_langflow` now returns the last text block the model wrote (`final_answer_text`), skipping Langflow's own "Output" blocks, and falls back to `data.text` when there are no content blocks.
  - Checked on real responses (greeting, math, research, CSV): the new answer is always the end of the old text, so nothing from the final answer is lost. Research 7,600 -> 2,186 chars with the "Sumber:" list intact; math 1,296 -> 519 (the sub-agent's full explanation no longer repeats the final one).
  - `tests/assets/langflow_agent_message.json` is a trimmed real Langflow message used by `tests/test_resilience.py`.
- **Number format.** Verified Data Analyst and other tools write English-format numbers ("23.685" = 23,685), which read as thousands in Indonesian. Prompt v14.2 (flow `v1.5.1`, prompt-only change) tells the Agent to write Indonesian format (1.065.600,71; 23,685), convert tool output, not mix formats, and not add a currency the data does not state (it had written "Rp 1.065.600,71" for the unit-less Sales_Amount). Live on the test flow: 4/4 answers in Indonesian format, 3/3 without an invented currency.

## v1.5.0 — 2026-10-14

### Numbers from the user's own CSV/TSV files (flow v1.5.0)
- Problem: Verified Data Analyst always reads the built-in `200_sales_data` file, and the routing sent every "dataset / CSV" question to it. A question about a user's own CSV could be answered with numbers from the sample dataset, labeled as verified.
- New component **Ciel Table Analyst** (`flow/components/ciel_table_analyst.py`, tool `analyze_table`): describe, count, sum, mean, median, min, max, unique, top values, optionally per group, computed directly from the file without running model-written code. Number format is decided per column ("1.250.000" and "1.234,5" vs "1,234.5"), using Rupiah values or a ";" delimiter as hints for ambiguous values, and the result states how the column was read. Truncated files carry a warning.
- The app keeps attached CSV/TSV files (and project CSV/TSV files) per chat, so follow-up questions work without re-uploading, and sends them through tweaks as base64. Plain JSON did not survive: Langflow runs str inputs through `unescape_string`, which turns every backslash-n into a newline; the tool always answered "no file" in the first live test.
- The prompt now gets only a 20-row preview of each table instead of up to 60k characters, which also cuts tokens.
- Prompt v14.1 routes by data source: user files to Ciel Table Analyst, the built-in sales dataset to Verified Data Analyst, never mixed. Verified Data Analyst's tool description says the same.
- Tests: `tests/test_flow_v150_contract.py` covers the flow contract, the app wiring, number-format detection, the base64 path through a copy of Langflow's `unescape_string`, and the tool's answers on Indonesian-format data. The component was also run with Langflow's real `Component` class.
- Live check on a separate v1.5.0 test flow (production untouched): "total omzet per cabang" on a ";"-separated Rupiah CSV gave Medan 5.205.250 and Makassar 4.130.500, the follow-up "rata-rata unitnya" gave 41,2, both exact; "total Sales_Amount pada dataset" without a file still went to Verified Data Analyst (1.065.600,71).
- Quality run: response quality 8/9 in the collector run, then 9/9 in two reruns of `tests/test_response_quality.py` (26/27 overall). The collector does not record which case failed; the live test scripts send no `session_id`, so all cases share one Langflow session, which is the likely source of the flake. Median latency 18.9 s (v1.4.0: 16.2 s), P95 43.1 s (20.9 s), first request 50.6 s on a freshly imported flow.

## v1.4.1 — 2026-10-14

### Fix: per-user memory isolation did not work (flow v1.4.1)
- Found in production after switching to v1.4.0: an anonymous visitor's "ingat namaku ..." was stored, and another session could read it.
- Root cause: the memory components' owner input was named `user_id`, but Langflow's `Component` already has a read-only `user_id` (the Langflow account that owns the flow). `self.user_id` returned that account id instead of the app's tweak, so every visitor shared one owner. The offline test missed it because its Langflow stub had no such attribute.
- The input is now `memory_owner` (components, flow snapshot `flow/v1.4.1`, and the app's tweaks). Chroma metadata still uses the `user_id` key, so `tools/migrate_memory_owner.py` is unchanged.
- `tests/test_flow_v141_contract.py`: the Langflow stub now keeps a read-only `user_id`, a regression test shows the v1.4.0 code storing under the Langflow account, and a check rejects component inputs that reuse Langflow attribute names. The behavior tests moved here from `tests/test_flow_v130_contract.py`, which now only checks the historical snapshot.
- Production flow updated in place to v1.4.1 (same `FLOW_ID`; backups in `~/.ciel_ai/flow_backups/`). Verified on the production flow: anonymous store and search are refused with the memory count unchanged; a test owner without memories gets "belum ada memory".
- Deploy this app version with the v1.4.1 flow. With v1.4.1 and an older app (which sends `user_id`), memory is off for everyone; nothing leaks.

## v1.4.0 — 2026-10-14

### Ciel identity: anti-fabrication research + study companion (flow v1.4.0)
- New flow snapshot `flow/v1.4.0`: identical to v1.3.0 except the Agent system prompt (v14.0, 8.7k -> 13.4k chars; DeepSeek caches the unchanged prefix).
- **Two persona modes.** Default is warm and casual ("aku"/"kamu"). When the user explicitly asks for analysis ("analisis", "bedah", "kaji", ...), Ciel switches to a terse "Great Sage" style that opens with "Analisis dimulai." and answers as Kesimpulan / Dasar (each point labeled [Terverifikasi] or [Dugaan]) / Tingkat keyakinan / Batasan.
- **Anti-ngarang rules** for every mode: never invent titles, authors, DOIs, URLs or quotes; research answers end with a "Sumber:" list of sources the tools actually returned; non-trivial numbers go through Math Tutor or Verified Data Analyst; no fabricated bibliographies for theses (point to Google Scholar, Garuda, SINTA instead).
- **Study companion:** step-by-step explanations with a short comprehension check or practice offer; practice questions are given without answers first; learning topics and recurring mistakes may be stored in (per-user) long-term memory.
- App copy (tagline, empty state, capabilities, starter prompts, working indicator) now presents this identity, including an example "Analisis: ..." prompt.
- `tests/test_flow_v140_contract.py` checks that only the system prompt changed and that the earlier rules are kept.
- Live validation (2026-10-14, v1.4.0 imported as a separate test flow in local Langflow 1.12.4, production flow untouched, requests sent to `127.0.0.1:7860` instead of through ngrok):
  - `tests/collect_quality.py`: 5/5 automated checks, response quality 9/9, memory recall K=5 100%. Median latency 36.2 s -> 16.2 s, P95 51.1 s -> 20.9 s versus the v1.1.0 baseline. Most of the gain likely comes from v1.2.0 no longer sending every message through the vision model; the baseline may also have gone through ngrok, so the numbers are not a strict A/B.
  - Style check: "halo" -> casual mode; "analisis kelebihan RAG" -> Great Sage structure with every point labeled [Dugaan] because no sources were fetched; "ajari aku turunan" -> step-by-step explanation ending with a comprehension question.
  - The first analysis answer had 9 points and a casual closing offer, so the prompt now limits Dasar to 5 points and ends at Batasan. Re-run: 5 points, 52 s -> 37 s.

## v1.3.0 — 2026-10-14

### Public-ready isolation and cost control (flow v1.3.0)
- **Conversation isolation.** `ask_langflow` now sends a `session_id` (`<user>-<chat id>`). Before, every request used Langflow's default session, so the Agent's last 10 messages (`n_messages`) were shared by all visitors and "New chat" did not reset the Agent's context. Each chat now has its own history, which also keeps prompts shorter.
- **Per-user long-term memory.** New flow snapshot `flow/v1.3.0`: Ciel Memory Search/Store (sources in `flow/components/ciel_memory_search.py` and `ciel_memory_store.py`) take a `user_id` input that the app sets through `tweaks`. It is not a tool argument, so the Agent cannot choose it. Store tags each memory with `user_id`; Search filters on it and skips the embedding call when the user has no memories. Empty `user_id` (anonymous visitor) disables memory: nothing is stored or read.
- **Optional Google login** (`st.login`, configured by an `[auth]` block in secrets). Signed-in users get memory keyed by a hash of their account; without `[auth]` the app runs anonymously with memory off. `requirements.txt` now needs `streamlit[auth]>=1.45`.
- **Rate limit** before any backend call: `RATE_LIMIT_PER_HOUR` (anonymous, default 20), `RATE_LIMIT_PER_HOUR_LOGIN` (default 60), and a shared `RATE_LIMIT_ANON_TOTAL_PER_HOUR` (default 150) so reloading the page does not reset the anonymous budget. Over the limit, the existing error card is shown.
- **Lower Streamlit memory use.** After a successful answer, attached photos in chat history are replaced by ~360 px JPEG thumbnails and the file-context payload is dropped. Originals are kept only while Retry may need them.
- Memory Store no longer returns the memory ID, total count, or DB path to the Agent. Removed the unconnected `Research Agent API Tool` node.
- `tools/migrate_memory_owner.py` assigns memories saved by older flows to one account (`--dry-run` first).
- New offline tests: `tests/test_flow_v130_contract.py` (contract plus a real Chroma isolation test with Langflow stubbed) and `tests/test_rate_limit.py`; `tests/test_resilience.py` checks `session_id`/`tweaks` in the payload. CI runs them.
- Upgrade: import `flow/v1.3.0` into Langflow, update `FLOW_ID` if the import created a new flow, then deploy the app. The app's tweaks need the v1.3.0 memory components; with an older flow, memory stays shared.
- Not changed: DeepSeek temperature (still 1). Lowering it for more consistent tool routing should be decided with `tests/collect_quality.py` against the live backend.

## v1.2.0 — 2026-10-14

### Pricing page
- Added a pricing page (`?page=pricing`, sidebar item "Harga & paket") with Gratis, Pro, and Tim plans, a monthly/yearly toggle (yearly = 10 months), and an FAQ.
- Plan data, Rupiah formatting, and rendering live in `pricing.py`; `app.py` only adds routing and the sidebar item.
- New optional config `CONTACT_URL` (https:// or mailto:). Paid plan buttons link there; without it they render as disabled "Segera hadir". There is no payment integration or plan enforcement yet.
- Added `tests/test_pricing.py` (formatting, yearly math, URL allow-list, render) to the offline CI suite; CI now installs `streamlit`.

### Fix: image messages failing with "Backend mengalami internal error"
- Root cause: the Ollama vision preprocessor (`qwen2.5vl:3b`, 4096-token context) sat between Chat Input and Agent and received the full message, including project-file context. Messages over ~4096 tokens failed with HTTP 500 (`request (5203 tokens) exceeds the available context size`). The Agent also only ever saw the vision model's output, never the original question or file context.
- Replaced it with `Ciel Vision Router` (`flow/components/ciel_vision_router.py`): text-only messages pass straight to the Agent without calling the vision model; with images, the vision model gets only the images plus a short instruction, and its reading is appended to the original message. If the vision model fails, the Agent still answers and says the image could not be read.
- Measured locally: image + 20k-char project context 500 -> 200 (39 s); image only ~90 s -> 28 s; text only unchanged.
- New flow snapshot `flow/v1.2.0` (hardcoded API key in the Math Tutor API Tool code redacted) with an offline contract test.
- `ask_langflow` now logs the Langflow error body (first 500 chars) on HTTP errors so failures can be diagnosed from server logs. The user-facing message is unchanged.

### Security: remove hardcoded Langflow API key from the Math Tutor tool
- The "Math Tutor API Tool" custom component called this same Langflow over HTTP with an API key written in its code; that key is in the public `flow/v1.0.0` and `flow/v1.1.0` snapshots. It is replaced by a native Run Flow tool (`Math-Tutor-Agent_tool`) that runs the Math Tutor Agent flow in-process, so no key is needed. Verified: derivative question routed to Math Tutor and answered correctly.
- `ask_langflow` request timeout raised from 120 s to 240 s: image messages that call several tools took up to ~107 s locally, too close to the old limit once ngrok latency is added.

### UI
- Polished the Streamlit workspace UI: dark theme with teal accent, responsive layout, empty state, working indicator, error card with technical details and retry, informative long-term memory panel.
- Sidebar now has New chat, chat History, and Projects; Connection, Configuration, and backend status panels were removed.
- Added Add files: text files can be attached in the composer or stored as project files, and are inserted into the prompt as context. `ask_langflow` is unchanged.
- Chat history and projects live in the browser session only (not persisted).
- Added photo attachments (png, jpg, jpeg, bmp): images are uploaded to Langflow (`/api/v1/files/upload/{flow_id}`) and passed to the Chat Input component through `tweaks`. `ask_langflow` only gained an optional `tweaks` argument.
- New optional config `CHAT_INPUT_ID` (default `ChatInput-X8W7I`, the Chat Input ID in the v1.1.0 flow).
- Visual refresh: flat neutral ink palette without glow, 6-12 px radii, Geist font (loaded from Google Fonts, falls back to system fonts), plain-text hero and spec-style capability list, caret working indicator, letter avatars. WCAG AA contrast checked for text and form-control borders.
- Added `.streamlit/config.toml` theme; `requirements.txt` now requires `streamlit>=1.43` (container keys, button icons, chat input file attachments).
- No changes to `ask_langflow`, `check_backend_health`, flow, memory, or tests.

### CI / Automation
- Added GitHub Actions CI workflow.
- Added automated flow JSON validation.
- Added automated offline test execution.
- Added CI dependency installation for `requests` and `chromadb`.
- Scoped CI to deterministic offline tests that do not require production credentials.

## v1.1.0 — Memory Context Optimization

### Changes
- Optimized Ciel Memory Search output for lower agent context usage.
- Kept Memory Search Top K at 5.
- Removed query, distance, and metadata from the agent-facing memory output.
- Preserved retrieved memory contents and ranking order.

### Validation
- Memory contract tests: 6/6 PASS.
- Full local unittest discovery: 16/16 PASS.
- Multi-query recall benchmark: 100% recall at Top K = 5.
- Context reduction: approximately 60.7% at Top K = 5.
- No changes were made to the v1.0.0 baseline snapshot.

## v1.0.0 — Production Baseline

### Flow Snapshot
- Baseline snapshot stored at:
  `flow/v1.0.0/Ciel_AI_Long-Term_Memory_Master.json`
- Snapshot is tracked in the current main repository history.
- No production-flow changes were introduced by the versioning step.

### Git History Note
- Tag `v1.0.0` is preserved as the production baseline.
- The current flow snapshots are maintained in the current main repository lineage.
- Previous repository history is intentionally preserved rather than force-merged.
