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
Chat Input
 |
 v
Ollama Chat Component
 |
 v
Agent
 +-- DeepSeek Model
 +-- Ciel Memory Search
 +-- Ciel Memory Store
 +-- Math Tutor API Tool
 +-- Knowledge Retriever
 +-- Web Research Assistant
 |
 v
Chat Output
```

## Core Components

### Chat Input

Chat Input is the entry point for user messages.

It provides the incoming message and session-related information to the flow.

### Ollama Chat Component

The Chat Input message is processed through the Ollama chat component before reaching the main Agent.

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

Mathematical requests are delegated to the Math Tutor API Tool when specialist mathematical reasoning is required.

### Knowledge Retriever

Knowledge-related requests can be delegated through the Knowledge Retriever Run Flow component.

The nested flow is exposed as a tool available to the Agent.

### Web Research Assistant

Current or web-based research is delegated to the Web Research Assistant.

The main flow exposes a Run Flow tool for the Web Research Assistant.

The project also contains a Research Agent API Tool custom component for invoking the research flow through the Langflow API.

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

The Research Agent API Tool can also invoke a Langflow flow through the local Langflow API.

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
3. Input is processed through the Ollama chat component
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
    +-- Ciel_AI_Long-Term_Memory_Master.json
```

v1.0.0 is preserved as the production baseline.

v1.1.0 contains the long-term memory context optimization while preserving the overall orchestration architecture.

## Architecture Principles

1. Keep the Agent as the central orchestrator.
2. Delegate specialist tasks to dedicated tools or nested flows.
3. Use semantic long-term memory instead of storing every message.
4. Keep credentials outside source control.
5. Preserve versioned flow snapshots.
6. Separate production architecture changes from performance experiments.
7. Prefer verified specialist results over guessed replacements.
