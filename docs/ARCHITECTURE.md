# Ciel AI Master - Architecture

## Overview

Ciel AI Master is a Langflow-based AI assistant centered on a primary Agent that receives user messages, selects the appropriate tool or specialist, and returns a final response.

The main flow is named:

Ciel AI Long-Term Memory Master

The flow is built and tested with Langflow 1.12.4.

## High-Level Architecture

```text
User
 |
 v
Streamlit app (app.py)
 |   session_id = <user>-<chat id>, tweaks: memory_owner, images
 v
Chat Input
 |
 v
Ciel Vision Router
 |
 v
Agent
 +-- DeepSeek Model
 +-- Ciel Memory Search   (filtered by owner)
 +-- Ciel Memory Store    (tagged with owner)
 +-- Ciel Table Analyst   (user CSV/TSV via tweaks, and the built-in sales dataset)
 +-- Ciel ML Analyst      (models on the same user CSV/TSV)
 +-- Ciel Dataset Store   (personal datasets of signed-in users)
 +-- Calculator           (evaluate_expression, since v1.12.0)
 +-- Math Tutor Agent     (Run Flow, cached)
 +-- Knowledge Retriever  (Run Flow, cached)
 +-- Ciel Exa Search      (web search; records every URL Exa returns)
 |
 v
Ciel Source Guard        (drops sources no search returned)
 |
 v
Chat Output
```

## Core Components

### Chat Input

Chat Input is the entry point for user messages.

It provides the incoming message and session-related information to the flow.

### Ciel Vision Router

Text-only messages pass straight to the Agent. When a message has images, only the images go to a vision model, and its reading is appended to the original message. Source: `flow/components/ciel_vision_router.py`.

Since v1.10.0 the router reads images with the Gemini API (`gemini-3.1-flash-lite`, key from the Langflow global variable `GEMINI_API_KEY`, paid tier so the images are not used for training) tries a backup Gemini model (`gemini-3.5-flash-lite`, since v1.10.1) when the main one fails, and falls back to the local model (`qwen2.5vl:3b` on Ollama) when the key is empty or both API models fail or take longer than `api_timeout` (20 s each). The HTTP call runs in a thread so it does not block Langflow's event loop. The app shrinks every photo to 1024 px on the longest side and turns it upright (EXIF) before uploading (`fit_for_vision` in `app.py`).

### Sessions

The app sends one Langflow `session_id` per chat (`<user key>-<chat id>`). The Agent's chat history (`n_messages`) therefore only contains messages from the same chat of the same user, and "New chat" starts with an empty context.

### Agent

The Agent is the central orchestration component.

Responsibilities include:

- interpreting the user request,
- deciding which specialist or tool should be used,
- using long-term memory when required,
- combining specialist results,
- following routing and response rules,
- returning the final response.

The Agent receives a language model through its model input and exposes tools for memory and specialist workflows.

## Long-Term Memory

Ciel AI Master has two dedicated long-term memory tools:

```text
Agent
 |
 +-- Ciel Memory Search
 |
 +-- Ciel Memory Store
          |
          v
     Ollama Embedding
          |
          v
       Chroma DB
```

### Ciel Memory Search

Memory search performs semantic retrieval.

Processing flow:

```text
Search Query
    |
    v
Ollama Embedding
    |
    v
Vector Search in Chroma
    |
    v
Top K Relevant Memories
    |
    v
Agent
```

The configured default is:

Top K = 5

The local Chroma database is stored under:

~/.ciel_ai/long_term_memory

### Memory Ownership (v1.4.1)

Both memory components have a `memory_owner` input that is not a tool argument: the app sets it through `tweaks`, so the Agent cannot read or write another user's memories.

- Signed-in user (Google login via `st.login`): `memory_owner` is a hash of the account.
- Anonymous visitor: `memory_owner` is empty and both tools refuse to store or search.

Store writes the owner into each memory's `user_id` metadata field; Search filters with `where={"user_id": ...}`. Memories saved by older flows have no owner until `tools/migrate_memory_owner.py` assigns them.

### Ciel Memory Store

Memory storage follows this pipeline:

```text
Memory Text
    |
    v
Ollama Embedding
    |
    v
Vector + Metadata
    |
    v
Chroma Database
```

The Agent is instructed to store only information with long-term value.

Secrets and credentials are not intended to be stored in long-term memory.

## Specialist Tool Architecture

### Math Tutor

Since v1.12.0 the main Agent does calculations itself with Langflow's Calculator (`evaluate_expression`): arithmetic, percentages, interest, statistics from numbers in the message, and the numbers in limits, derivatives, integrals and equations. Prompt v14.8 requires every computed number in an answer to come from the Calculator. Concept explanations, practice problems and quizzes are written by the main Agent, which checks each answer key with the Calculator. The Calculator evaluates an AST allowlist (`+ - * / **`, numbers as floats, no names or calls), so a huge power raises `OverflowError` instead of running long; it has no unary minus (`-3` must be written `0-3`).

Worksheets with many problems, or long multi-part problems, still go to the Math Tutor Agent flow through a native Run Flow tool (no API key in the flow). The Math Tutor works step by step with its own Calculator; since v1.11.0 it has no Python Interpreter, and since v1.12.0 its DeepSeek model runs with thinking off and without the date tool (changed outside the repository). Before v1.12.0 every math question went through the Math Tutor: the nested agent wrote a full answer that the main Agent then rewrote, which added about 3-4 s.

### Built-in sales dataset

Questions about the built-in sales dataset (`200_sales_data`, 200 rows) go to Ciel Table Analyst with `file_name=200_sales_data` (since v1.11.0). The component reads `~/.ciel_ai/builtin_datasets/200_sales_data.csv` on the Langflow host, only when the dataset is named and no attached file or saved dataset has that name, so the default pick (the only attached file or saved dataset) is unchanged. Until v1.10.2 these questions went to the Verified Data Analyst sub-flow, a CSV agent with `allow_dangerous_code=True` that ran model-written Python on the host.

### Ciel Table Analyst

Numbers from the user's own CSV/TSV files (attached in the chat or stored as project files) come from Ciel Table Analyst (`flow/components/ciel_table_analyst.py`). The app sends the files through tweaks; the tool computes count, sum, mean, median, min, max, unique and top values, optionally per group, without running model-written code.

### Ciel ML Analyst

Machine learning on the same files comes from Ciel ML Analyst (`flow/components/ciel_ml_analyst.py`, tool `train_model`), which receives the same base64 tables from the app. It uses numpy only (already a Langflow dependency, so nothing extra is installed on the host) and a fixed seed, so the same file always gives the same result.

- `task=predict` with a `target`: a numeric target with at least 11 distinct values is a ridge linear regression; anything else is a multinomial logistic regression (at most 20 classes). Effects are reported in the column's own units ("setiap +1") or as a category versus the most common one.
- `task=cluster`: k-means (k-means++, 4 starts); k is chosen from 2 to 6 by silhouette unless the user gives it. Category columns are scaled so two different categories are one standard deviation apart; standardizing them made rare categories their own cluster.
- Quality comes from 5-fold cross-validation (stratified for classes): every row is predicted by a model that did not see it, and medians, categories and scaling are refit inside each fold. Results are compared with guessing the mean or the most common class; a model that does not beat it is called weak, and R² above 0,99 or 100% accuracy triggers a target-leakage warning.
- Row numbers, constant columns and ID-like text columns are skipped. Files above 10.000 rows are sampled; the worst case measured (10.000 rows, 9 columns) took about 5 s.
- `predict_for` (`kolom=nilai; ...`) predicts a new row; missing columns use the median or the most common category, and the result says so.

The file-reading helpers are copied from Ciel Table Analyst, because Langflow components cannot import each other; `tests/test_ml_analyst.py` fails if the copies drift.

### Personal datasets

Signed-in users can keep data that grows over time, such as a study log. Ciel Dataset Store (`flow/components/ciel_dataset_store.py`, tool `manage_dataset`) stores each dataset as `~/.ciel_ai/user_datasets/<owner>/<name>.csv` on the Langflow host. The owner is the app's hash of the account (the same `memory_owner` as long-term memory), sent through tweaks; an empty or malformed owner stores nothing, and names are reduced to `[a-z0-9_-]`, so neither can point outside the owner's folder.

- `save_file` saves an attached CSV/TSV as a new dataset or appends it (columns must match; a file whose rows equal the dataset's last rows is not saved twice). `add_rows` appends rows typed in the chat as `kolom=nilai; ...`. Numbers in a new file or row are rewritten in the dataset's own number format, so a column never mixes `3.5` and `3,5`. `list` and `show` read. There is no delete action: deleting is only possible under "Data saya".
- Limits: 5 datasets per account, 10.000 rows and 1 MB per dataset; truncated files are refused.
- Table Analyst and ML Analyst also get the owner and read saved datasets by name (`pick_table`): an attached file wins over a dataset with the same name, and without a name the only attached file, or else the only dataset, is used.
- Ciel Memory Admin gained `list_datasets`, `export_dataset`, `delete_dataset` and `delete_all_datasets` (input `dataset_name`) for the "Data saya" panel, where users list, download and delete their datasets.

`owner_dir` and `saved_tables` are identical in all four components, and `pick_table` in both analysts; `tests/test_personal_datasets.py` checks this.

### Knowledge Retriever

Knowledge-related requests can be delegated through the Knowledge Retriever Run Flow component.

The nested flow is exposed as a tool available to the Agent.

### Web Research (v1.9.0)

The main Agent searches the web itself with Ciel Exa Search. Until v1.8.0 it delegated research to the Web Research Assistant sub-flow, which is still in Langflow (with its own guard) as the rollback path but is no longer connected.

Sensitive API configuration is kept outside source control.

## Agent Routing Model

The Agent uses task-based routing.

```text
Mathematics
    -> Math Tutor

User CSV/TSV file (attached or project file)
    -> Ciel Table Analyst

Prediction, important factors or grouping on a user CSV/TSV file
    -> Ciel ML Analyst

Save or add data to a personal dataset (signed-in users)
    -> Ciel Dataset Store

Built-in sales dataset (200_sales_data)
    -> Ciel Table Analyst (file_name=200_sales_data)

Knowledge Base / Internal Material
    -> Knowledge Agent

Current / Web Information
    -> search (Ciel Exa Search)

Previous User Context
    -> Ciel Memory Search
```

Some requests may require more than one specialist.

## Research Flow

Since v1.9.0 research is direct: the main Agent calls Exa, writes the answer with numbered sources, and the guard checks the sources before Chat Output.

```text
Main Agent
    |
    v
search (Ciel Exa Search, 2 queries at once)
    |
    v
Main Agent writes the answer + "Sumber:"
    |
    v
Ciel Source Guard
    |
    v
Final Response
```

Until v1.8.0 the main Agent called the Web Research Assistant sub-flow, whose own Agent searched and wrote notes that the main Agent then rewrote. Writing every research answer twice, plus the sub-agent's planning step and building the sub-flow, cost about 8-14 s per research question.

### Research Rules (v1.9.0, prompt v14.6)

- Mode Santai (fast research): one round, 2 different queries at once, then the answer.
- Mode Analisis (deep research): at most 3 rounds of at most 2 queries; the answer still ends with "Sumber:" after the Batasan line (before v14.6 the analysis format said to end right after Batasan, and only 3 of 6 production analysis answers listed sources).
- No `get_contents`; the date is asked for in the same round as the search; sources and URLs only from that run's search results, numbered as [1], [2] and listed under "Sumber:".
- Ciel Exa Search returns 5 results per query with at most 1,500 highlight characters each and records every URL Exa returns in the graph context. Ciel Source Guard removes source lines whose URLs no search returned, their markers and the findings that cited only them, and says how many it removed. Runs without a search pass through unchanged, and so do source lines without a URL (a file, the Knowledge Base). The guard keeps only the final answer's text block: Langflow 1.12's Chat Output assigns `Message.text`, which joins every text block, and the app would otherwise show earlier rounds too.

### Research Modes in the Web Research Assistant (v1.8.0, rollback path)

The main Agent starts every question for the Research Agent with a mode marker:

- `[RISET CEPAT]` (default, Mode Santai): one search round with 2 different Exa queries at once, then notes with at most 5 findings and 4 sources.
- `[RISET DALAM]` (only in Mode Analisis / Great Sage): at most 3 search rounds, then notes with at most 10 findings and 6 sources.

The Research Agent never calls `get_contents`, has `max_iterations` 6, and Exa returns 5 results with at most 1,500 highlight characters each. Every source and URL in the notes must come from a search result in the same run; the agent may not add sources from memory. Ciel Exa Search (`flow/components/ciel_exa_search.py`) replaces the official Exa node and records every URL Exa returns in the graph context. Ciel Source Guard (`flow/components/ciel_source_guard.py`), between the Agent and Chat Output, removes sources whose URL Exa did not return, along with their markers and findings, and says how many it removed. Its DeepSeek model runs with thinking off (`model_kwargs = {"extra_body": {"thinking": {"type": "disabled"}}}`); the main Agent keeps thinking on. It hands back notes (findings + sources), not an essay; the main Agent writes the answer and its "Sumber:" section. The sub-flow snapshot is `flow/subflows/Web_Research_Assistant.json`.

### Riset Skripsi (Ciel Pro, `flow/riset_skripsi/v1.0.0`)

A separate flow, not a tool of the main Agent: the app calls it directly (`RESEARCH_FLOW_ID`) only for Pro accounts (`docs/PRO.md`). It was cloned from the Web Research Assistant.

```
Chat Input -> Agent (DeepSeek, thinking off) -> Ciel Source Guard -> Ciel Reference Builder -> Chat Output
                 ^ tool: Ciel Scholar Search
```

- **Ciel Scholar Search** (`flow/components/ciel_scholar_search.py`):
  - Takes the Exa toolkit's inputs and gives the Agent only `search`; `get_contents` is left out.
  - Returns 10 results with at most 1,000 highlight characters each.
  - The app sets `start_published_date` per request (tweak, e.g. `2021-01-01` for "5 tahun terakhir"), and Exa applies it.
  - Besides the URL list for the guard, it records each result's title, author and published date in the graph context.
- **Agent:** `max_iterations` 10, `n_messages` 0, date tool on, no calculator.
  - The prompt asks for a fixed source map (`# Peta Sumber`, `## Tema: …` with `[n]` markers, `## Celah riset`, `## Pertanyaan untuk dosen pembimbing`).
  - It also asks for at most 4 searches, and ends with a "Sumber:" list of `[n] URL` lines only.
  - The model never writes authors, years or a reference list.
- **Ciel Source Guard:** the same component as the main flow; it drops source lines whose URL no search returned.
- **Ciel Reference Builder** (`flow/components/ciel_reference_builder.py`):
  - Replaces the "Sumber:" list with `## Daftar Pustaka` in APA 7 style: `[n] Penulis. (Tahun). *Judul*. domain. URL`.
  - Everything in an entry comes from the recorded Exa metadata. With no author, the title goes first. With no date, it writes "(t.t.)".
  - Entries without metadata are dropped, numbers are compacted to 1..n, and the `[n]` markers in the text follow.
  - A note asks the student to check names and years in the original source.

Since v1.1.0, Ciel Scholar Search also records each result's Exa highlights, and Ciel Reference Builder ends the answer with one line `<!-- ciel-excerpts:v1 BASE64 -->` holding the highlights of the listed sources (`[{n, highlights}]`). The app removes that line (`draft_check.split_excerpts`) and stores the excerpts on the source map message for Cek kutipan & kemiripan.

The app shows the result as one chat message with an "Unduh DOCX" button (`riset_export.py`). Follow-up questions in that chat go to the main flow with the source map as context. Time is bounded by the app's 420 s timeout for this flow.


### Kerangka Bab 1–3 (Ciel Pro, `flow/penulis/v1.0.0`)

A second Pro flow, **Ciel Penulis**, called directly by the app (`WRITER_FLOW_ID`) from the "Susun kerangka Bab 1–3" button under a source map:

```
Chat Input -> DeepSeek (system prompt, no tools) -> Chat Output
```

- The app (`writing.py`) sends `[KERANGKA]`, the topic, the approach, an optional object, and the whole source map, including its Daftar Pustaka.
- The prompt asks for Bab I–III as points (25 words at most) and guiding questions, never ready-to-copy paragraphs. It may cite only `[n]` from the map, with no new sources, and may copy author names and years only from the map's list.
- After the reply, `writing.finish_kerangka` drops any `[n]` the map doesn't have and any reference list the model wrote, then appends the map's Daftar Pustaka.
- No web search runs, so a run takes about 15 s. The same flow is meant to take further modes (Review draf) later.


### Cek kutipan & kemiripan (Ciel Pro, `draft_check.py`)

A third button under a source map. The student pastes a draft or uploads a `.docx`/`.txt` file. There is no Langflow call and no model: the check runs in the app and is deterministic.

- **Citations.** Every `[n]`, "(Nama, 2024)" and "Nama dkk. (2024)" is matched against the map's Daftar Pustaka by author name tokens (accents and case ignored) and year. Results are "cocok", "nama cocok, tahun beda", "tidak ada di peta sumber", or "nomor tidak ada". Map sources never cited are listed too. The draft's own reference list is ignored.
- **Similarity.** Each sentence of 10 words or more is compared, as 5-word shingles, with each source's stored Exa excerpts and with the map's own summary text. A sentence is flagged at 40% shared shingles. Citations are left out of the comparison, and sentences that are mostly in quotation marks count as direct quotes.
- The report says what it compared against, and that it is not Turnitin: only the map's sources are checked, and translations are not detected.
- The draft is kept on the user message only until the check succeeds (for "Coba lagi"), so it is not stored in chat history. Maps made before Riset flow v1.1.0 have no excerpts and are compared with the summary text only.


## Model Architecture

The main Agent receives a DeepSeek language model through its model connection.

```text
DeepSeek Model
      |
      v
    Agent
      |
      +-- Memory Tools
      +-- Specialist Tools
      +-- Research Tools
```

The model acts as the reasoning engine while the Agent remains responsible for orchestration and tool usage.

The model is `deepseek-flash`. Since v1.12.0 the main Agent runs it with thinking off (`model_kwargs = {"extra_body": {"thinking": {"type": "disabled"}}}`), like the research Agent and the Math Tutor. Thinking made analysis answers take about 25 s, and turning it off kept all 26 exact-answer checks correct. In thinking mode DeepSeek ignores `temperature` (at temperature 0 the same prompt gave four different answers); with thinking off the flow's temperature of 1 applies, which is DeepSeek's default.

Without thinking, tool routing depends more on the prompt's wording. In tests on 2026-10-18, small unrelated edits to the prompt made "Makanan penurun kolestrol" go unsearched in 3-4 of 4 runs, and v14.7 answered a paracetamol dose without a search. Prompt v14.8 therefore names health, nutrition, medicine and safety, and law, official rules, scholarships, prices and official figures as research topics. Check research routing with a must-search / must-not-search set after every prompt change.

## Request Lifecycle

```text
1. User sends a message
        |
        v
2. Chat Input receives the message
        |
        v
3. Ciel Vision Router reads attached images, if any
        |
        v
4. Agent receives the request
        |
        v
5. Agent determines the task type
        |
        +-- Memory
        +-- Mathematics
        +-- Data
        +-- Knowledge
        +-- Research
        |
        v
6. Appropriate tool is executed
        |
        v
7. Specialist result returns to Agent
        |
        v
8. Agent combines relevant information
        |
        v
9. Chat Output returns the final response
```

### Answer cache (`answer_cache.py`)

Before step 1 reaches Langflow, the app checks an in-memory cache for repeated general questions:

- **Who fills it:** only anonymous visitors, whose requests run without long-term memory, so the answer holds nothing personal. Logged-in answers are never stored. An answer is stored only when the same question comes in a second time, and only if it is at least 40 characters (shorter replies are usually apologies or failed tools).
- **Who reads it:** everyone, but only for the first message of a new chat that is plain text: no images, attached or project files, tables, or Pro features. These are never cached:
  - questions about the asker (`aku`, `sy`, `kita`, `namaku`);
  - memory, dataset, or earlier-conversation requests (`ingat`, `lupakan`, `dataset`, `tadi`);
  - questions about time (`hari ini`, `jam`, `tanggal`, `kapan`, `harga`, greetings like `selamat pagi`, a year).
- **Matching:** exact match after lowercasing, collapsing spaces, and dropping `?!.,` at the ends. Punctuation inside the question stays, so `12/4` and `12*4` never share an answer. The key includes `FLOW_ID`, so a new flow does not reuse the old flow's answers.
- **Lifetime:** 1 day, at most 500 questions, oldest dropped first. The cache lives in the Streamlit process, so a reboot empties it.
- A cache hit uses no message quota and is marked `cached` on the reply. Langflow never saw that turn, so the next message in that chat carries the question and answer in its payload once.
- Logs record only the first 8 characters of the key hash, never the question.

## Security Boundaries

The architecture separates:

- source code,
- flow definitions,
- runtime configuration,
- credentials,
- persistent memory.

The Agent memory policy also prohibits storing API keys, passwords, tokens, credentials, and secrets as long-term memory.

## Performance Considerations

The architecture contains nested tool execution (Math Tutor, Knowledge Retriever). Research has been direct since v1.9.0.

Nested Run Flow execution introduces additional runtime overhead compared with direct tool execution: each nested Agent adds its own model calls. Since v1.12.0 both Run Flow nodes have `cache_flow` on, so the sub-flow graph is built once and kept in Langflow's shared component cache, keyed by flow ID (`run_flow:<user>:<flow_id>`). An edit to the Math Tutor or Knowledge Retriever may only take effect after Langflow restarts.

Performance profiling therefore treats direct model execution, Agent execution, memory operations, direct research, and nested research execution as separate performance boundaries.

## Versioned Flow Architecture

Main flow snapshots and component sources:

```text
flow/
+-- v1.0.0/ … v1.7.0/
|   +-- Ciel_AI_Long-Term_Memory_Master.json
+-- components/
    +-- ciel_vision_router.py
    +-- ciel_memory_search.py
    +-- ciel_memory_store.py
    +-- ciel_table_analyst.py
    +-- ciel_ml_analyst.py
    +-- ciel_dataset_store.py
```

Contract tests check that each snapshot embeds the same component code as `flow/components/`.

- **v1.0.0:** production baseline.
- **v1.1.0:** long-term memory context optimization.
- **v1.2.0:** Ciel Vision Router replaces the always-on vision preprocessor; Math Tutor runs as a native Run Flow tool.
- **v1.3.0:** long-term memory scoped to the signed-in user; the unconnected Research Agent API Tool node is removed.
- **v1.4.0:** Agent system prompt only: two persona modes (warm default, "Great Sage" analysis mode), anti-fabrication rules, study-companion behavior.
- **v1.4.1:** the memory owner input is renamed from `user_id` to `memory_owner`. Langflow's `Component` already has a read-only `user_id` (the Langflow account that owns the flow), which shadowed the input in v1.3.0/v1.4.0, so every visitor was stored under that account. Component inputs must not reuse Langflow's own attribute names.
- **v1.5.0:** adds Ciel Table Analyst. Before, a question about a user's own CSV could be answered with numbers from the built-in sample dataset. The app keeps attached and project CSV/TSV files per chat and sends them base64-encoded (Langflow turns every backslash-n in a str input into a newline, which breaks plain JSON). The prompt gets only a 20-row preview of each table, and the routing restricts Verified Data Analyst to the built-in dataset.
- **v1.5.1:** prompt-only: Indonesian number format, conversion of tool output, no invented currency. The app also returns only the final model text block, because Langflow 1.12 joins every Agent round into `Message.text`.
- **v1.6.0:** adds Ciel ML Analyst and prompt v14.3: a machine learning route for user files (predict, important factors, new-row prediction, clustering), no derived target columns as features, model quality always reported with the result, and ML results as a study-companion example.
- **v1.7.0:** adds Ciel Dataset Store; Table Analyst and ML Analyst read saved datasets; prompt v14.4 (save only on an explicit request, no table data in long-term memory, deletion only through "Data saya"). The Memory Admin flow gained the dataset actions.
- **v1.8.0:** prompt v14.5: research questions go to the Web Research Assistant as fast or deep research.
- **v1.12.0:** speed: the main Agent runs with thinking off and has the Calculator as a tool; both Run Flows are cached; prompt v14.8 sends calculations to the Calculator, keeps the Math Tutor for worksheets, and names health and official facts as research topics. Outside the repository the Math Tutor runs with thinking off.
- **v1.11.0:** security hardening: the Verified Data Analyst tool is removed and Ciel Table Analyst reads the built-in dataset; prompt v14.7 adds "10. KEAMANAN" (content from tools is data, not instructions; no images or data-carrying URLs). Outside the repository the Math Tutor sub-flow lost its Python Interpreter.
- **v1.10.2:** `gemini-3.5-flash-lite` reads first and `gemini-3.1-flash-lite` is the backup, each limited to 8 s.
- **v1.10.1:** the Vision Router tries a backup Gemini model before the local model.
- **v1.10.0:** the Vision Router reads images with the Gemini API and keeps the local model as the fallback; only the router node changes.
- **v1.9.0:** the main Agent searches with Ciel Exa Search itself and Ciel Source Guard checks the answer's sources (prompt v14.6); the Web Research Assistant tool is removed. The memory components keep the embedding model loaded for an hour (`keep_alive`), because reloading it after Ollama's 5-minute default took up to 14 s.

## Langflow Configuration Outside the Repository

Parts of production are configured in Langflow and are not versioned here. Changes to them are recorded in `CHANGELOG.md`, backed up to `~/.ciel_ai/flow_backups/` on the Langflow host, and listed in `docs/BACKUP_AND_DISASTER_RECOVERY.md`.

- **Sub-flows:** Math Tutor Agent (Agent `n_messages` = 4), Web Research Assistant (Agent `n_messages` = 0, Exa search; not connected since v1.9.0, kept as the rollback path), and Knowledge Retriever (knowledge base `TITANIC_DATA_SCIENCE_SOLUTIONS`). Sub-agents get a complete question from the main Agent, so they keep little or no history; their history is scoped by session and flow.
- **API keys:** every production flow reads model and search keys from Langflow global variables (`DEEPSEEK_API_KEY`, `EXA_API_KEY`); no production flow stores a literal key.
- **Projects:** "Starter Project" holds only the five production flows. Earlier experiments and versions are in the project "Arsip" (some of them still contain literal keys).

## Privacy and Data Controls

```text
"Data saya" panel (signed-in only)
 |
 +-- memories      -> POST /api/v1/run/<MEMORY_ADMIN_FLOW_ID>
 |                    tweaks: memory_owner, memory_action (list | delete | delete_all), memory_id
 |                    Ciel Memory Admin -> Chat Output (message not stored)
 |
 +-- chat history  -> GET  /api/v1/monitor/messages/sessions
                      DELETE /api/v1/monitor/messages/sessions  (only "<user key>-..." sessions)
```

- **Ciel Memory Admin** (`flow/components/ciel_memory_admin.py`) runs in its own small flow, not in the main flow, so it is never an Agent tool: the model cannot list or delete memories. Like the memory tools, the owner comes only from the app's tweak, and every action is limited to memories whose `user_id` metadata equals that owner; deleting another owner's ID returns `not_found`. Anonymous calls are refused.
- **Chat history** is stored by Langflow per session. Signed-in users' sessions start with their user key (`<user key>-<chat id>`), so the app deletes exactly those. Anonymous sessions use a random per-browser key that cannot be tied to a person; they are removed by retention.
- **Retention:** `tools/prune_chat_history.py`, scheduled on the Langflow host, deletes messages older than `CHAT_RETENTION_DAYS` (default 30) across all flows of the account, including sub-flows. The privacy page (`privacy.py`) shows the same number.

## Public Deployment Safeguards

- One Langflow session per chat (no shared Agent history).
- Long-term memory per signed-in user; disabled for anonymous visitors.
- Hourly and daily message limits per user, a shared hourly and daily budget for anonymous visitors, and a daily total for everyone, checked in the app before any backend call (`RATE_LIMIT_*` settings). Typed messages are capped at 10,000 characters (checked on the server too), uploads at 25 MB, and images at 90 megapixels before they are decoded.
- Error messages show a Request ID instead of response bodies or exception text; details go to the server log.
- The ngrok traffic policy (generated by `tools/render_ngrok_policy.py`) applies a per-IP rate limit, Basic Auth, and an exact allowlist of the paths and flow IDs the app uses; everything else answers 404.
- No component runs model-written code (since v1.11.0), and prompt v14.7 treats web, file, photo and memory content as data. The app removes markdown images from answers, so prompt injection cannot send chat data through an image URL.
- See `SECURITY.md` for the full list, the incident runbook and the owner checklist.
- A privacy page, self-service deletion of memories and server chat history for signed-in users, and a retention period for server-side messages (see Privacy and Data Controls).

## Architecture Principles

1. Keep the Agent as the central orchestrator.
2. Delegate specialist tasks to dedicated tools or nested flows.
3. Use semantic long-term memory instead of storing every message.
4. Keep credentials outside source control.
5. Preserve versioned flow snapshots.
6. Separate production architecture changes from performance experiments.
7. Prefer verified specialist results over guessed replacements.
