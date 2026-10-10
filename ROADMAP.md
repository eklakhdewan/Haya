# Implementation Plan — 16 Weeks

## Phase 0 — Foundation (Week 1)

Deliver:
- repository
- Python environment
- CI
- configuration system
- logging/tracing
- typed domain models
- test harness

Exit gate:
- clean install from README
- CI green

## Phase 1 — Deterministic Agent Core (Weeks 2–3)

Build:
- state model
- Supervisor
- provider adapter
- tool registry
- calculator/web/time tools
- policy engine
- structured outputs

Exit gate:
- 50 golden routing tests
- no direct provider calls from business logic

## Phase 2 — Secure Execution (Week 4)

Build:
- sandbox adapter
- timeout
- network policy
- execution result schema
- repair loop

Exit gate:
- 100 execution tests
- zero host execution

## Phase 3 — Memory (Weeks 5–7)

Build:
- Qdrant
- Neo4j
- Redis
- memory extraction
- provenance
- hybrid retrieval
- graph traversal
- deletion/correction

Qdrant's hybrid query API supports dense+sparse retrieval and RRF; use it rather than manually adding incomparable dense and lexical scores. citeturn0search7turn0search14

Exit gate:
- golden memory dataset
- precision@5 >= 0.90

## Phase 4 — Realtime Voice (Weeks 8–10)

Start with managed WebRTC transport.

Build:
- session authentication
- streaming STT
- streaming LLM
- streaming TTS
- interruption
- trace correlation

Deepgram Flux currently exposes turn-oriented streaming behavior and interruption-oriented features. citeturn0search11

Exit gate:
- benchmarked p95 response-start target

## Phase 5 — Android Bridge (Weeks 11–12)

Build:
- device enrollment
- authenticated channel
- intent schema
- permission manager
- confirmation UI
- action audit

Exit gate:
- all high-risk negative tests pass

## Phase 6 — Dashboard (Week 13)

Build:
- live session
- traces
- memory graph
- action audit
- sandbox console

## Phase 7 — Hardening (Weeks 14–15)

- load tests
- security tests
- dependency pinning
- secret management
- backup/restore
- failure drills

## Phase 8 — Release (Week 16)

- staging
- production configuration
- runbooks
- demo script
- architecture diagram
- benchmark report

## Acquisition order

Acquire/enable infrastructure only when its phase begins:

1. GitHub + CI
2. LLM API
3. Qdrant + Neo4j local Docker
4. sandbox account
5. realtime transport
6. STT/TTS
7. Android test device
8. production cloud
9. monitoring

Do not buy everything on day one.
