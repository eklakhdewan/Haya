# Product Requirements Document — Hina

## 1. Product objective

Build a production-oriented autonomous voice agent with bounded authority and persistent, inspectable memory.

## 2. User stories

| ID | User story | Acceptance criterion |
|---|---|---|
| US-01 | I speak to Hina naturally | Streaming audio is accepted and transcribed |
| US-02 | I interrupt Hina | Current TTS playback stops without waiting for completion |
| US-03 | Hina remembers a fact | Fact is retrievable in a later session with provenance |
| US-04 | Hina handles a relation | Graph relationship can be queried |
| US-05 | Hina runs code | Code executes only inside approved sandbox |
| US-06 | Hina uses tools | Tool calls are schema validated and traced |
| US-07 | Hina controls Android | Only allowlisted intents can execute |
| US-08 | I can inspect Hina | Dashboard exposes transcript, actions, memory and traces |
| US-09 | Hina fails safely | Provider/network/tool failure produces bounded fallback |
| US-10 | I can revoke access | Device/tool permissions can be disabled centrally |

## 3. Functional requirements

### Voice
- FR-V01: support streaming bidirectional audio.
- FR-V02: support turn detection.
- FR-V03: support barge-in.
- FR-V04: stream partial transcripts.
- FR-V05: stream partial TTS output.
- FR-V06: correlate every turn with a trace ID.

### Agent
- FR-A01: classify intent.
- FR-A02: select tools.
- FR-A03: maintain execution state.
- FR-A04: enforce maximum tool iterations.
- FR-A05: support retries with exponential backoff.
- FR-A06: support human approval gates.
- FR-A07: produce structured action records.

### Memory
- FR-M01: store episodic conversation records.
- FR-M02: extract durable facts.
- FR-M03: store entity relationships.
- FR-M04: attach provenance to every durable memory.
- FR-M05: support semantic + lexical retrieval.
- FR-M06: support graph traversal.
- FR-M07: support memory correction/deletion.
- FR-M08: prevent unverified model output from silently becoming authoritative memory.

### Sandbox
- FR-S01: execute Python initially.
- FR-S02: isolate execution from the host.
- FR-S03: enforce timeout.
- FR-S04: cap output size.
- FR-S05: restrict network by policy.
- FR-S06: return stdout/stderr/exit status.
- FR-S07: allow at most N repair attempts.
- FR-S08: log execution metadata without storing secrets.

### Android
- FR-D01: authenticate device.
- FR-D02: validate intent JSON.
- FR-D03: check user policy.
- FR-D04: execute only supported actions.
- FR-D05: return success/failure and OS error.
- FR-D06: support revocation.
- FR-D07: require confirmation for risky actions.

## 4. Non-functional requirements

| Area | Requirement |
|---|---|
| Voice | p95 first response audio target <500 ms after end-of-turn for the optimized path |
| Reliability | graceful degradation for each external dependency |
| Security | zero arbitrary host-code execution |
| Observability | every turn has distributed trace context |
| Privacy | secrets and sensitive payloads minimized/redacted |
| Portability | provider interfaces allow replacement |
| Testability | deterministic offline mode exists |
| Availability | target 99.9% for production core after hardening |

**Important:** 500 ms is a target, not a guarantee. Measure each stage separately. A provider cannot be forced to meet a latency budget that the network and model do not support.

## 5. Priority

P0 = must ship  
P1 = important  
P2 = later

P0: text agent, tools, memory, sandbox, auth, observability, tests  
P1: realtime voice, Android bridge, dashboard  
P2: proactive behavior, multimodal vision, iOS
