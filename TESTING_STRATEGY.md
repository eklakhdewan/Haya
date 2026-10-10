# Testing Strategy

## 1. Test pyramid

### Unit
Fast, deterministic:
- router
- policies
- schemas
- memory extraction normalization
- retrieval fusion
- tool adapters
- state transitions

### Integration
Real local dependencies:
- Qdrant
- Neo4j
- Redis
- API service
- sandbox mock

### End-to-end
Controlled staging:
- voice session
- memory
- tool
- sandbox
- Android action

### Load
- concurrent sessions
- memory query load
- sandbox requests
- device bridge connections

## 2. Minimum test gates

```text
ruff check .
ruff format --check .
mypy --strict .
pytest -q
```

Rust:
```text
cargo fmt --check
cargo clippy -- -D warnings
cargo test
```

## 3. Critical security tests

1. prompt asks for `rm -rf /`
2. tool output contains malicious instructions
3. memory contains a fake system instruction
4. device action requests an unallowlisted package
5. SMS target is changed after approval
6. expired device token is replayed
7. sandbox attempts network access
8. sandbox attempts secret access

## 4. Voice tests

Measure:
- end-of-turn detection
- partial transcript latency
- LLM first token
- TTS first audio
- interruption time
- total perceived latency

## 5. Golden datasets

Maintain:
- `tests/golden/router.jsonl`
- `tests/golden/memory.jsonl`
- `tests/golden/tools.jsonl`
- `tests/golden/device_actions.jsonl`

Every regression becomes a permanent test case.

## 6. Load target

Initial staging target:
- 100 concurrent realtime sessions
- 1,000 memory queries/min
- 20 concurrent sandbox jobs

These are test targets, not claims of production capacity.
