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
 +-- Math Tutor Agent     (Run Flow)
 +-- Verified Data Analyst (Run Flow)
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

Dataset / Metrics
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

Flow snapshots are versioned under:

```text
flow/
+-- v1.0.0/
|   +-- Ciel_AI_Long-Term_Memory_Master.json
|
+-- v1.1.0/
+-- v1.2.0/
+-- v1.3.0/
|   +-- Ciel_AI_Long-Term_Memory_Master.json
+-- components/
    +-- ciel_vision_router.py
    +-- ciel_memory_search.py
    +-- ciel_memory_store.py
```

v1.0.0 is preserved as the production baseline.

v1.1.0 contains the long-term memory context optimization while preserving the overall orchestration architecture.

v1.2.0 replaces the always-on vision preprocessor with Ciel Vision Router and runs Math Tutor as a native Run Flow tool.

v1.4.1 renames the memory components' owner input from `user_id` to `memory_owner`. Langflow's `Component` already has a read-only `user_id` (the Langflow account that owns the flow), which shadowed the input in v1.3.0/v1.4.0, so every visitor was stored under that account. Component inputs must not reuse Langflow's own attribute names.

v1.4.0 changes only the Agent system prompt: two persona modes (warm default, "Great Sage" analysis mode), anti-fabrication rules, and study-companion behavior.

v1.3.0 scopes long-term memory to the signed-in user and removes the unconnected Research Agent API Tool node. Custom component sources live in `flow/components/`, and contract tests check that the flow JSON embeds the same code.

## Public Deployment Safeguards

- One Langflow session per chat (no shared Agent history).
- Long-term memory per signed-in user; disabled for anonymous visitors.
- Hourly message limits per user plus a shared anonymous budget, checked in the app before any backend call (`RATE_LIMIT_*` settings).

## Architecture Principles

1. Keep the Agent as the central orchestrator.
2. Delegate specialist tasks to dedicated tools or nested flows.
3. Use semantic long-term memory instead of storing every message.
4. Keep credentials outside source control.
5. Preserve versioned flow snapshots.
6. Separate production architecture changes from performance experiments.
7. Prefer verified specialist results over guessed replacements.
