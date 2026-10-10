# Security and Privacy Protocol

## 1. Security model

Assume:
- prompts can be malicious;
- tool outputs can be malicious;
- retrieved memory can be poisoned;
- LLM output is untrusted;
- devices can be compromised;
- external providers can fail.

## 2. Threat matrix

| Threat | Control |
|---|---|
| Prompt injection | tool isolation + policy engine |
| Tool poisoning | schema validation + output sanitization |
| Sandbox escape | external microVM sandbox |
| Secret leakage | secret manager + redaction |
| Device abuse | allowlist + RBAC + confirmation |
| Memory poisoning | provenance + confidence + user correction |
| Replay | nonce + timestamp + idempotency |
| Stolen device token | rotation + revocation |
| SSRF | egress allowlist |
| Excessive tool loops | max iterations |
| Data leakage | minimum-data principle |

## 3. Sandbox rules

- no host filesystem
- no host process access
- no ambient cloud credentials
- network disabled by default
- dependency installation restricted
- execution timeout
- memory/CPU quota
- output cap
- ephemeral filesystem

## 4. Device rules

Default:
- OPEN_APP: low risk
- SYSTEM_SETTING: medium/high risk
- SEND_SMS: high risk
- MAKE_CALL: high risk

High-risk actions require explicit user approval unless the user has configured an explicit trusted policy.

## 5. Authentication and authorization

All HTTP routes require a signed JWT bearer token except `GET /v1/health`. The realtime WebSocket requires a token in the Authorization header or a short-lived `access_token` query parameter (use TLS; query tokens can appear in proxy logs).

Required JWT claims:
- `sub`: authenticated user ID (non-empty string)
- `iss`: `hina-orchestrator` by default
- `aud`: `hina-api` by default
- `iat` and `exp`: issued-at and expiry timestamps

Tokens are verified with HS256 and `JWT_SECRET`. Generate a unique random secret of at least 32 characters; do not use the `.env.example` placeholder. The API intentionally does not expose a public token-minting endpoint: production tokens must come from a trusted identity component. For local development only, set `ENVIRONMENT=development` and use `python scripts/issue_dev_token.py --subject local-user --role user`; the helper refuses to run in staging or production. Admin-only access to the dashboard and trace endpoints requires the signed `role=admin` claim.

Memory namespaces are derived from the authenticated `sub`; caller-supplied user IDs cannot select another user's namespace. Device registration and revocation enforce device ownership. High-risk action approvals are short-lived, one-time, and bound to the exact intent payload, device, and user. Replaying or modifying an approved intent is denied.

Never put provider API keys in:
- Android app bundle
- frontend JavaScript
- Git
- logs
- prompts

## 6. PII

Minimize PII sent to external providers. Redact where appropriate.

Do not claim that redaction makes privacy absolute. It is a risk reduction layer.

## 7. Memory deletion

Deletion must propagate to:
1. canonical memory record
2. Qdrant point
3. Neo4j nodes/edges
4. caches
5. derived indexes where applicable

Keep only an audit tombstone if required by the chosen privacy policy.

## 8. Security gates before release

- dependency audit
- secret scan
- SAST
- container scan
- auth tests
- authorization tests
- sandbox escape tests
- prompt injection tests
- device action abuse tests


## 9. Phase 1 implementation notes

- The in-process mock sandbox is test-only. Non-test environments use the E2B adapter and fail closed when `E2B_API_KEY` or the provider dependency is missing.
- Network-enabled sandbox execution is denied until provider-level egress isolation is implemented and tested.
- The AST checker is defense-in-depth, not a security boundary; isolation must be provided by the external sandbox.
- Device ownership/revocation, pending approvals, used nonces, completed intent IDs, and action audit events can be persisted in PostgreSQL when `DATABASE_URL` is configured. Production startup fails closed if the database or migrated security schema is unavailable. The in-memory manager remains the development/test fallback when no database URL is configured. PostgreSQL-backed guarantees must be demonstrated by the CI integration suite; durable audit rows are not tamper-evident, and completion records do not guarantee exactly-once external side effects.
- Run `pytest` and the dedicated security tests before merging. Then perform provider-backed E2B tests and production configuration checks in the target environment.
