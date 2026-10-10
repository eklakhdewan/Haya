# Technology Stack — Approved Baseline

## 1. Runtime

| Layer | Baseline | Reason |
|---|---|---|
| Orchestrator | Python 3.12 | AI ecosystem + typing |
| Realtime | LiveKit initially | Mature WebRTC/agent transport |
| Custom low-level gateway | Rust, optional | Only if profiling justifies it |
| Dashboard | Next.js + TypeScript | mature admin/debugging UI |
| Android | Kotlin | native OS permissions and intents |
| Containers | Docker Compose | reproducible local stack |

## 2. AI

### Primary LLM
Use a provider adapter. Default candidate: Gemini 3.8 Flash for low-latency agent work; current Google documentation describes it as designed for long-horizon software engineering, autonomous agents and enterprise workflows. citeturn1search0

### Voice
Two supported strategies:

**A. Managed realtime model path**
- Gemini 3.8 Live or equivalent.

**B. Composable pipeline**
- Deepgram Flux STT
- selected LLM
- Deepgram Flux TTS / Cartesia / equivalent

Deepgram currently documents Flux STT as a low-latency voice-agent model and recommends `/v2/listen`; Flux TTS is also designed as an interruptible streaming voice-agent API. citeturn0search11turn0search19

Do not hard-code a provider into business logic.

## 3. Memory

- Qdrant: hybrid dense+sparse retrieval.
- Neo4j: relationships and graph reasoning.
- Redis: ephemeral session state and queues.

Qdrant's Query API supports multi-stage hybrid queries and RRF. citeturn0search7
Neo4j supports vector indexes plus graph/full-text retrieval. citeturn0search12

## 4. Sandbox

- E2B or an equivalent isolated microVM sandbox.
- No host execution fallback.
- Python first.

## 5. Observability

- OpenTelemetry SDKs
- Prometheus metrics
- Grafana dashboards
- Jaeger/Tempo-compatible traces

OpenTelemetry currently provides stable Python traces/metrics APIs and Rust instrumentation support. citeturn0search0turn0search3

## 6. Selection rule

"Best" means best for the measured Hina workload, not the most famous vendor.

Benchmark:
- p50/p95 latency
- transcription quality
- tool-call correctness
- cost/turn
- failure rate
- availability
- privacy/compliance
- SDK quality
- migration effort

Keep at least one fallback provider for critical paths.
