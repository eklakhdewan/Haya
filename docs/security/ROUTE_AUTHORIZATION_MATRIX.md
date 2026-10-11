# HTTP and WebSocket Authorization Matrix

This matrix describes the current route policy implemented in `orchestrator/main.py`. It is a source-level contract; deployed proxy/TLS behavior must still be checked in staging.

| Route | Authentication | Role / ownership rule | Regression coverage |
|---|---|---|---|
| `GET /v1/health` | Anonymous | Liveness only; do not expose provider or secret details | `tests/test_auth_boundaries.py` |
| `OPTIONS /*` | Middleware bypass | CORS preflight only; CORS policy must be configured by deployment | Verify deployed CORS allow-list |
| `GET /`, `GET /dashboard` | Bearer JWT | Admin only | `tests/test_auth_boundaries.py` |
| `GET /v1/traces`, `GET /v1/traces/{trace_id}` | Bearer JWT | Admin only | `tests/test_auth_boundaries.py` |
| `GET /v1/tools` | Bearer JWT | Any authenticated principal; exposes tool names/schemas only | Existing API tests |
| `POST /v1/tools/execute` | Bearer JWT | Admin only | Existing authorization coverage; extend when tools change |
| `POST /v1/sandbox/execute` | Bearer JWT | Admin only; code and output are bounded | `tests/test_sandbox_api.py`, `tests/test_sandbox_provider_failures.py` |
| `POST /v1/coder/task` | Bearer JWT | Admin only; task payload is bounded | `tests/test_sandbox_api.py` |
| `POST /v1/supervisor/route` | Bearer JWT | Body `user_id` must equal token subject | `tests/test_auth_boundaries.py` |
| `POST /v1/memory/query`, `POST /v1/memory/extract`, `POST /v1/memory/store` | Bearer JWT | Authenticated user owns created/query context; never trust a caller-supplied owner ID | Existing `tests/test_memory_api.py`; cross-user store/query tests remain part of full suite |
| `DELETE /v1/memory/{memory_id}` | Bearer JWT | Owner derived from token subject; adapters enforce owner-scoped deletion | Existing memory store and API tests |
| `POST /v1/device/register`, `/v1/device/revoke`, `/v1/device/actions`, `/v1/device/confirm`, `GET /v1/device/audit` | Bearer JWT | Owner derived from token subject; device manager enforces ownership and confirmation policy | Persistent-device and security regression tests |
| `/v1/realtime/ws` | Bearer JWT in Authorization header; legacy query token is also accepted | Optional `user_id` must match token subject; session must belong to the authenticated user | `tests/test_auth_boundaries.py` |

## Token contract

The API validates HS256 signature, issuer, audience, expiry, issued-at time, and non-empty bounded subject. Tokens are expected to be issued by a trusted identity component; the public API does not issue user tokens. Production must use a unique managed signing secret and have a rotation procedure.

## Deployment verification still required

- Verify TLS termination and trusted proxy behavior.
- Configure a strict CORS allow-list; `OPTIONS` bypass is not an authorization grant.
- Remove query-string WebSocket token support once clients use Authorization headers, or prove access tokens are redacted from proxy, access, tracing, and error logs.
- Run this matrix against a staging deployment and record exact release SHA plus test output.
