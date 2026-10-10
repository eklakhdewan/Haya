# Evaluation and Benchmark Plan

## 1. Core principle

Do not report a target as a result. Record measured p50/p95/p99 values with workload and environment.

## 2. Latency budget

| Stage | Target |
|---|---:|
| turn detection | <150 ms |
| STT finalization | <150 ms |
| memory retrieval | <100 ms parallel |
| LLM first token | <250 ms |
| TTS first audio | <150 ms |
| perceived response start | <500 ms target |

These budgets overlap; they must not simply be added together.

## 3. Memory evaluation

Metrics:
- Recall@k
- Precision@k
- MRR
- nDCG
- answer faithfulness
- provenance correctness
- stale-memory rate

Test categories:
1. exact fact
2. paraphrase
3. multi-hop relation
4. contradictory fact
5. stale fact
6. irrelevant distractors

## 4. Agent evaluation

Measure:
- correct route
- tool selection accuracy
- tool argument validity
- task completion
- unnecessary tool calls
- loop count
- refusal correctness

## 5. Sandbox evaluation

100+ tasks:
- arithmetic
- Python debugging
- data transformation
- dependency usage
- intentional failures

Metrics:
- success rate
- repair success
- mean execution time
- timeout rate

## 6. Device evaluation

Test every intent with:
- valid payload
- invalid payload
- missing permission
- revoked device
- replayed token
- confirmation denied
- offline device

## 7. Acceptance thresholds

Initial release gate:

```text
Unit/integration tests: 100% pass
Critical security tests: 100% pass
Memory precision@5: >= 0.90
Tool argument validity: >= 0.98
Sandbox escape tests: 0 successful escapes
High-risk unauthorized actions: 0
Voice perceived response target: <500 ms p95 on benchmark environment
```

Thresholds may be tightened after baseline measurement.
