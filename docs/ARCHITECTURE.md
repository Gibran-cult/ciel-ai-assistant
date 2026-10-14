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
 +-- Ciel Table Analyst   (user CSV/TSV, sent by the app via tweaks)
 +-- Math Tutor Agent     (Run Flow)
 +-- Verified Data Analyst (Run Flow, built-in sales dataset only)
 +-- Knowledge Retriever  (Run Flow)
 +-- Web Research Assistant (Run Flow)
 |
 v
Chat Output
```

## Core Components

### Chat Input

Chat Input is the entry point for user messages.

It provides the incoming message and session-related information to the flow.

### Ciel Vision Router

Text-only messages pass straight to the Agent. When a message has images, only the images go to the local vision model (`qwen2.5vl:3b`), and its reading is appended to the original message. Source: `flow/components/ciel_vision_router.py`.

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

Mathematical requests are delegated to the Math Tutor Agent flow through a native Run Flow tool (no API key in the flow).

### Verified Data Analyst

Questions about the built-in sales dataset (`200_sales_data`, 200 rows) go to the Verified Data Analyst flow, which computes verified metrics with a CSV agent. Its tool description and the routing rules limit it to that dataset.

### Ciel Table Analyst

Numbers from the user's own CSV/TSV files (attached in the chat or stored as project files) come from Ciel Table Analyst (`flow/components/ciel_table_analyst.py`). The app sends the files through tweaks; the tool computes count, sum, mean, median, min, max, unique and top values, optionally per group, without running model-written code.

### Knowledge Retriever

Knowledge-related requests can be delegated through the Knowledge Retriever Run Flow component.

The nested flow is exposed as a tool available to the Agent.

### Web Research Assistant

Current or web-based research is delegated to the Web Research Assistant.

The main flow exposes a Run Flow tool for the Web Research Assistant.

Sensitive API configuration is kept outside source control.

## Agent Routing Model

The Agent uses task-based routing.

```text
Mathematics
    -> Math Tutor

User CSV/TSV file (attached or project file)
    -> Ciel Table Analyst

Built-in sales dataset (200_sales_data)
    -> Verified Data Analyst

Knowledge Base / Internal Material
    -> Knowledge Agent

Current / Web Information
    -> Research Agent

Previous User Context
    -> Ciel Memory Search
```

Some requests may require more than one specialist.

## Research Flow

The Web Research Assistant is connected to the main Agent through the Run Flow tool mechanism.

```text
Main Agent
    |
    v
Web Research Assistant Tool
    |
    v
Nested Research Flow
    |
    v
Research Result
    |
    v
Main Agent
    |
    v
Final Response
```


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

The model is `deepseek-flash`, which runs in thinking mode. In this mode DeepSeek ignores `temperature`: at temperature 0 the same prompt gave four different answers, while an out-of-range value was rejected by DeepSeek, so the setting is sent but has no effect. Tuning temperature therefore does not change tool-routing consistency.

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

## Security Boundaries

The architecture separates:

- source code,
- flow definitions,
- runtime configuration,
- credentials,
- persistent memory.

The Agent memory policy also prohibits storing API keys, passwords, tokens, credentials, and secrets as long-term memory.

## Performance Considerations

The architecture contains nested tool execution, especially for Web Research.

Nested Run Flow execution introduces additional runtime overhead compared with direct tool execution.

Performance profiling therefore treats direct model execution, Agent execution, memory operations, direct research, and nested research execution as separate performance boundaries.

## Versioned Flow Architecture

Main flow snapshots and component sources:

```text
flow/
+-- v1.0.0/ … v1.5.1/
|   +-- Ciel_AI_Long-Term_Memory_Master.json
+-- components/
    +-- ciel_vision_router.py
    +-- ciel_memory_search.py
    +-- ciel_memory_store.py
    +-- ciel_table_analyst.py
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

## Langflow Configuration Outside the Repository

Parts of production are configured in Langflow and are not versioned here. Changes to them are recorded in `CHANGELOG.md`, backed up to `~/.ciel_ai/flow_backups/` on the Langflow host, and listed in `docs/BACKUP_AND_DISASTER_RECOVERY.md`.

- **Sub-flows:** Math Tutor Agent (Agent `n_messages` = 4), Web Research Assistant (Agent `n_messages` = 0, Exa search), Verified Data Analyst, and Knowledge Retriever (knowledge base `TITANIC_DATA_SCIENCE_SOLUTIONS`). Sub-agents get a complete question from the main Agent, so they keep little or no history; their history is scoped by session and flow.
- **API keys:** every production flow reads model and search keys from Langflow global variables (`DEEPSEEK_API_KEY`, `EXA_API_KEY`); no production flow stores a literal key.
- **Projects:** "Starter Project" holds only the five production flows. Earlier experiments and versions are in the project "Arsip" (some of them still contain literal keys).

## Public Deployment Safeguards

- One Langflow session per chat (no shared Agent history).
- Long-term memory per signed-in user; disabled for anonymous visitors.
- Hourly message limits per user plus a shared anonymous budget, checked in the app before any backend call (`RATE_LIMIT_*` settings).
- Error messages show a Request ID instead of response bodies or exception text; details go to the server log.
- The ngrok traffic policy adds Basic Auth and a per-IP rate limit on `/api/v1/run/`.

## Architecture Principles

1. Keep the Agent as the central orchestrator.
2. Delegate specialist tasks to dedicated tools or nested flows.
3. Use semantic long-term memory instead of storing every message.
4. Keep credentials outside source control.
5. Preserve versioned flow snapshots.
6. Separate production architecture changes from performance experiments.
7. Prefer verified specialist results over guessed replacements.
