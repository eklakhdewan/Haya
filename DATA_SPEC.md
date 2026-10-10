# Data Specification

## 1. IDs

All persistent entities use UUIDv4 or UUIDv7.

Required fields:
- id
- created_at
- updated_at
- user_id
- source
- trace_id

## 2. Memory record

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "kind": "fact",
  "subject": "string",
  "predicate": "string",
  "object": "string",
  "confidence": 0.96,
  "source_turn_id": "uuid",
  "created_at": "2026-09-21T00:00:00Z",
  "updated_at": "2026-09-21T00:00:00Z",
  "status": "active"
}
```

## 3. Graph model

```text
(:User)-[:HAS_MEMORY]->(:Memory)
(:User)-[:KNOWS]->(:Person)
(:User)-[:WORKS_ON]->(:Project)
(:User)-[:LIKES]->(:Concept)
(:Project)-[:USES]->(:Technology)
(:Event)-[:INVOLVES]->(:Person)
```

Do not store arbitrary LLM-generated Cypher directly. Generate typed graph operations and compile them into parameterized Cypher.

## 4. Vector payload

```json
{
  "memory_id": "uuid",
  "user_id": "uuid",
  "kind": "fact",
  "source_turn_id": "uuid",
  "text": "The user prefers Python for prototyping.",
  "confidence": 0.94,
  "created_at": "timestamp"
}
```

## 5. Mobile intent

See `config/schemas/mobile_intent.schema.json`.

## 6. Action audit

```json
{
  "action_id": "uuid",
  "user_id": "uuid",
  "device_id": "uuid",
  "intent_type": "SEND_SMS",
  "risk": "high",
  "confirmation": "approved",
  "requested_at": "timestamp",
  "executed_at": "timestamp",
  "result": "success"
}
```

## 7. Audio

- Opus preferred for transport.
- 16 kHz is a practical STT input target.
- Do not force 20 ms chunks across every provider; provider-specific streaming requirements win. Deepgram Flux currently recommends 80 ms chunks for its v2 streaming path. citeturn0search11
