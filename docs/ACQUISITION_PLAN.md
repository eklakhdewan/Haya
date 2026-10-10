# Hina Acquisition Plan — Build vs Buy

## Principle

Acquire infrastructure only when the current phase needs it. Prefer managed components for hard realtime/security primitives and keep application logic portable.

| Capability | v1 choice | Acquire? | Fallback |
|---|---|---:|---|
| LLM | Gemini 3.8 Flash | Yes/API | second LLM adapter |
| Realtime transport | LiveKit or equivalent | Yes | custom WebRTC later |
| STT | Deepgram Flux | Yes/API | Gemini Transcribe |
| TTS | Deepgram Flux TTS / Cartesia | Yes/API | Gemini TTS |
| Vector | Qdrant | No, local first | managed Qdrant |
| Graph | Neo4j | No, local first | managed Neo4j |
| Cache | Redis | No, local first | managed Redis |
| Sandbox | E2B | Yes/API | another microVM provider |
| Android test | physical Android device | Recommended | emulator |
| Observability | OpenTelemetry + local collector | No | managed backend |

## Selection process

For every paid provider, run a 50–100 request benchmark before committing.

Record:
- p50/p95 latency
- error rate
- quality score
- cost
- rate limits
- regional availability
- data retention
- support
- SDK quality

Current official documentation supports Gemini 3.8 Live/Flash as current options for realtime and agentic workloads, Deepgram Flux for low-latency streaming STT, Qdrant for hybrid retrieval, Neo4j for graph/vector retrieval, and LiveKit for realtime agent infrastructure. citeturn1search0turn0search11turn0search7turn0search12turn0search5

## Spending rule

Do not purchase enterprise plans during prototyping.

Start with:
- free/local tiers
- pay-as-you-go APIs
- local databases
- one Android device
- one staging environment

Upgrade only when a measured bottleneck or quota requires it.
