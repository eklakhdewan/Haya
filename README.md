# HINA — Autonomous Real-Time AI Companion

**Version:** 1.0 engineering baseline  
**Date:** 2026-09-21  
**Status:** Build-ready specification  
**Primary goal:** a voice-first autonomous assistant with persistent hybrid memory, safe code execution, controlled device actions, and measurable real-time performance.

## 1. What Hina is

Hina is not a chat UI with a microphone attached. It is a distributed agent system:

```text
User Voice
   │
   ▼
Realtime Transport / Voice Gateway
   │
   ├── STT + turn detection
   ▼
Agent Orchestrator
   │
   ├── Router / Planner
   ├── Memory retrieval
   ├── Tool execution
   ├── Sandbox execution
   └── Device-action approval
   │
   ├──────────────► Hybrid Memory
   │                  ├── Qdrant
   │                  └── Neo4j
   │
   ├──────────────► Secure Sandbox
   │                  └── E2B
   │
   └──────────────► Android Bridge
                          │
                          ▼
                       Device
```

## 2. Engineering principle

Build in this order:

1. deterministic text agent
2. tools and permissions
3. memory
4. secure execution
5. realtime voice
6. Android bridge
7. optimization
8. production hardening

Do **not** begin by trying to make every component realtime. A large distributed system that cannot be tested deterministically is not an achievement; it is technical debt.

## 3. Definition of done

Hina v1 is complete only when:

- every external provider is behind an interface;
- all secrets are environment-managed;
- every device action passes schema + authorization checks;
- arbitrary code never runs on the host;
- memory writes are traceable to a source conversation;
- memory retrieval has an offline evaluation set;
- voice latency is measured, not guessed;
- failures degrade safely;
- CI passes formatting, type checking, unit tests and security checks;
- deployment can be reproduced from a clean machine.

## 4. Repository

See `docs/REPO_STRUCTURE.md`.

## 5. Start here

1. Read `docs/PROJECT_BRIEF.md`.
2. Read `docs/PRD.md`.
3. Read `docs/SYSTEM_ARCHITECTURE.md`.
4. Install `requirements.txt` / `pyproject.toml`.
5. Copy `.env.example` to `.env`.
6. Start local infrastructure with `docker compose -f memory_core/docker-compose.yml up -d`.
7. Run the deterministic text-agent tests before enabling external voice providers.

## 6. Important architecture correction

The original specification mixed WebRTC, raw WebSocket semantics, Rust, Python, React Native, Kotlin and Node.js without defining ownership boundaries. This rebuild makes the boundaries explicit.

For the first production path, use a managed WebRTC transport such as LiveKit or an equivalent provider rather than implementing the entire realtime media stack from scratch. LiveKit's current Agents stack already handles realtime media/data, interruptions and provider integrations. citeturn0search5turn0search13

Rust remains available for a custom low-level gateway only if measured profiling proves it is necessary.

## 7. Current model/provider baseline

Provider choice is intentionally configurable. As of September 2026, Google's Gemini API lists Gemini 3.8 Live for low-latency live voice and Gemini 3.8 Flash for agentic workloads; model IDs are explicitly versioned and production systems should avoid unstable aliases. citeturn1search0turn1search4

Deepgram Flux is a viable streaming STT option with turn detection and interruption-oriented behavior; its current guidance recommends the `/v2/listen` endpoint and 80 ms chunks. citeturn0search11

Qdrant supports dense+sparse hybrid retrieval and RRF fusion, which is the intended retrieval foundation for Hina. citeturn0search1turn0search7

Neo4j supports vector indexes alongside graph queries; current Neo4j documentation recommends the Cypher `SEARCH` syntax for vector queries on recent releases. citeturn0search12

## 8. Non-negotiable safety rule

Hina may be autonomous in planning, but **authority is bounded**. Sending a message, placing a call, changing device settings, executing code with network access, or modifying persistent memory requires an explicit policy decision and, where configured, human confirmation.
