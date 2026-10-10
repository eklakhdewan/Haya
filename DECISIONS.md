# Architectural Decision Records

## ADR-001 — Managed WebRTC first

**Decision:** Use a mature WebRTC transport such as LiveKit for v1.

**Why:** The original custom Rust gateway creates unnecessary implementation risk. LiveKit already provides realtime media/data and agent infrastructure. citeturn0search5

**Revisit when:** profiling shows transport overhead is a material part of latency or custom protocol control becomes a product requirement.

## ADR-002 — Python orchestrator

**Decision:** Python for agent logic.

**Why:** strongest ecosystem for LLM, retrieval and evaluation.

## ADR-003 — Hybrid memory

**Decision:** Qdrant + Neo4j + Redis.

**Why:** vector retrieval handles semantic similarity; graph storage handles explicit relations; Redis handles ephemeral state.

## ADR-004 — External sandbox

**Decision:** E2B or equivalent microVM sandbox.

**Why:** LLM-generated code is untrusted.

## ADR-005 — Provider abstraction

**Decision:** all LLM/STT/TTS providers implement interfaces.

**Why:** providers change quickly; business logic should not.

## ADR-006 — Typed device actions

**Decision:** LLM never calls Android APIs directly.

**Why:** authorization must be deterministic and auditable.

## ADR-007 — Event-based memory

**Decision:** memory mutations create immutable audit events.

**Why:** enables correction, replay and debugging.
