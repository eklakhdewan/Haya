# Project Brief — Hina

## 1. Executive definition

Hina is a voice-first autonomous AI companion that can:

- understand realtime speech;
- maintain persistent user memory;
- reason over previous facts and relationships;
- use external tools;
- execute generated code in an isolated environment;
- request controlled actions on an Android device;
- explain what it did and why;
- expose traces and memory through a developer dashboard.

## 2. Problem

Conventional assistants have three engineering limitations:

### Latency
Request/response architectures often feel discontinuous for spoken interaction.

### Amnesia
Conversation history alone is not a durable knowledge model. Hina needs explicit memory with provenance and controlled updates.

### Limited agency
A useful assistant must interact with tools and devices, but unrestricted autonomy is unsafe.

## 3. Solution

Hina combines:

- realtime media transport;
- streaming STT and TTS;
- a stateful agent graph;
- hybrid vector + graph memory;
- isolated code execution;
- policy-controlled device actions;
- observability and evaluation.

## 4. Target user

Primary: a technically sophisticated individual using Hina as a personal engineering and productivity assistant.

Secondary: engineering demonstrator / portfolio system proving competence in:

- AI agents;
- retrieval;
- distributed systems;
- realtime systems;
- security;
- MLOps/observability.

## 5. Product boundaries

### v1
- Android only
- cloud LLM APIs
- Python orchestrator
- hybrid memory
- safe code sandbox
- selected tools
- web dashboard
- authenticated device bridge

### Not v1
- iOS
- unrestricted root/device control
- autonomous financial transactions
- autonomous account deletion
- unrestricted shell on host
- unsupervised high-impact communication
- training a foundation model

## 6. Success definition

Hina is successful when it demonstrates measurable improvement over a stateless baseline in:

1. task completion;
2. memory retrieval precision;
3. response latency;
4. safe action execution;
5. recovery from tool/code failures.
