# API Specification

## 1. API conventions

Base:
`/v1`

Headers:
```text
Authorization: Bearer <access-token>
X-Trace-Id: <uuid>
Idempotency-Key: <uuid>
```

Responses:
```json
{
  "request_id":"uuid",
  "data": {},
  "error": null
}
```

## 2. Health

`GET /v1/health`

Response:
```json
{"status":"ok","version":"0.1.0"}
```

## 3. Memory query

`POST /v1/memory/query`

Request:
```json
{
  "query":"What project am I building?",
  "top_k":5,
  "include_graph":true
}
```

Response:
```json
{
  "items":[
    {
      "memory_id":"uuid",
      "text":"...",
      "score":0.91,
      "source_turn_id":"uuid"
    }
  ]
}
```

## 4. Memory extraction

`POST /v1/memory/extract`

Request:
```json
{
  "session_id":"uuid",
  "transcript":[
    {"role":"user","content":"..."},
    {"role":"assistant","content":"..."}
  ]
}
```

## 5. Sandbox

`POST /v1/sandbox/execute`

Request:
```json
{
  "language":"python",
  "code":"print(2+2)",
  "timeout_ms":5000,
  "network":"disabled"
}
```

Response:
```json
{
  "execution_id":"uuid",
  "status":"success",
  "stdout":"4\n",
  "stderr":"",
  "exit_code":0,
  "execution_time_ms":142
}
```

## 6. Device action

`POST /v1/device/actions`

Request:
```json
{
  "device_id":"uuid",
  "intent_type":"OPEN_APP",
  "payload":{"target":"com.example.app"},
  "confirmation_token":"..."
}
```

## 7. Realtime

Use the selected realtime provider's session protocol. Do not expose an undocumented `wss://...` endpoint as a public API contract until the transport implementation is finalized.

Events:

```text
SESSION_STARTED
SPEECH_STARTED
TRANSCRIPT_PARTIAL
TRANSCRIPT_FINAL
TOOL_STARTED
TOOL_RESULT
ASSISTANT_TEXT
ASSISTANT_AUDIO
SPEECH_INTERRUPTED
SESSION_ENDED
ERROR
```

## 8. Error codes

```text
AUTH_REQUIRED
FORBIDDEN
INVALID_SCHEMA
RATE_LIMITED
PROVIDER_UNAVAILABLE
TOOL_TIMEOUT
SANDBOX_TIMEOUT
DEVICE_OFFLINE
CONFIRMATION_REQUIRED
POLICY_DENIED
MEMORY_UNAVAILABLE
INTERNAL_ERROR
```


## 9. OpenAPI implementation note

The FastAPI implementation should generate the OpenAPI document from typed request/response models. Do not manually maintain a second OpenAPI file until the endpoint surface stabilizes.
