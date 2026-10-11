# Haya v1.0 Execution and Release Checklist

**Last reviewed:** 2026-10-11  
**Release status:** NOT RELEASE-READY  
**Latest audited main SHA:** `93730b2c5f327c96d63d25fd20f9025b11feb600`  
**Latest audit:** [Post-merge audit and remediation plan](POST_MERGE_AUDIT_AND_REMEDIATION_PLAN.md)

This is the source of truth for remaining v1 work. Mark an item complete only when evidence exists (CI run, test report, provider validation, deployment record or recovery drill). Source changes alone are not evidence of operational readiness.

## Current evidence

- [Static Analysis and Security Scanning passed on audited main SHA](https://github.com/eklakhdewan/Haya/actions/runs/38112391755).
- [Security Regression passed on audited main SHA](https://github.com/eklakhdewan/Haya/actions/runs/38112391747).
- Static workflow includes Ruff lint/format, strict mypy, pip-audit, Bandit, Gitleaks and CodeQL.
- Security regression workflow runs compilation, Alembic migration checks and pytest with an ephemeral PostgreSQL 16 service.
- These CI runs do not validate a deployed identity issuer, production TLS/secrets, real E2B isolation, real Qdrant/Neo4j memory, monitoring or backup restoration.

## P0 — required before production

### P0.1 Sandbox safety

- [x] Enforce mock sandbox selection as test-only; reject mock in development/staging/production.
- [x] Test missing E2B credentials, missing SDK, provider outage, timeout and malformed provider results.
- [x] Test that missing credentials/provider errors do not fall back to local/mock execution.
- [ ] Run a provider-backed isolated execution test and verify network egress remains disabled at the provider boundary.
- [x] Enforce timeout policy and bound returned stdout/stderr.
- [ ] Verify provider-side cleanup and resource bounds in a controlled environment.

### P0.2 Durable hybrid memory

- [x] Add real sentence-transformer embeddings for both document writes and query vectors; remove constant placeholder vectors.
- [x] Wire Qdrant and Neo4j adapters into staging/production startup and shutdown.
- [x] Add Qdrant collection dimension validation and Neo4j connectivity/constraint initialization.
- [ ] Confirm service-backed Qdrant/Neo4j integration tests pass on this PR SHA.
- [ ] Test persistence across API restarts and worker processes.
- [ ] Test cross-user query and delete isolation against real adapters (service-backed tests added; CI evidence pending).
- [ ] Test adapter failure, partial write, retry and reconciliation behavior.
- [x] Fail startup when staging/production provider credentials or required memory configuration is incomplete.

### P0.3 Authentication and authorization

- [x] Inventory HTTP routes and WebSocket path with role/ownership policy in [route authorization matrix](security/ROUTE_AUTHORIZATION_MATRIX.md).
- [ ] Complete positive/negative tests for every sensitive route across anonymous, regular-user, cross-user and admin cases (representative regression tests added; full matrix evidence pending).
- [x] Add JWT regression tests for issuer, audience, expiry, issued-at, subject and role-gated admin access.
- [ ] Verify trusted production token issuance and signing-secret rotation.
- [ ] Verify WebSocket reconnect behavior and query-token log redaction while legacy query-token support remains enabled.
- [ ] Verify TLS, CORS and deployment proxy settings in staging.
- [ ] Verify production startup fails closed when required secrets, providers or persistent security storage are missing (configuration/startup guards added; deployment evidence pending).

### P0.4 Persistence and migration readiness

- [x] PostgreSQL-backed device/security state and Alembic migrations exist.
- [x] PostgreSQL integration regression workflow passed on the audited main SHA.
- [ ] Test clean installation and upgrade from a representative previous schema.
- [ ] Test connection loss, transaction rollback, concurrent requests and recovery in a staging-like environment.
- [ ] Define external side-effect idempotency and reconciliation; database completion rows alone do not guarantee exactly-once external actions.

## P1 — required before a public/production release

### P1.1 Memory audit and reconciliation

- [ ] Replace in-memory memory audit events with durable, access-controlled storage.
- [ ] Add outbox/reconciliation for failed cross-store writes and failed compensating deletes.
- [ ] Define audit retention, redaction, access, integrity and backup policies.
- [ ] Test retry idempotency and restart recovery.

### P1.2 Rate and resource controls

- [ ] Define per-user/IP rate limits for HTTP and WebSocket operations.
- [ ] Add concurrency limits for LLM, memory and sandbox operations.
- [ ] Bound provider timeouts, retries, output size and cost-sensitive requests.
- [ ] Test repeated requests, oversized payloads, connection floods and quota exhaustion.

### P1.3 Provider and end-to-end validation

- [ ] Verify real LLM provider timeout, retry, authentication, quota and outage behavior.
- [ ] Verify real Qdrant/Neo4j/Redis connections against supported versions.
- [ ] Verify Deepgram STT/TTS with real audio, interruption and cancellation if enabled for release.
- [ ] Run end-to-end authenticated API and WebSocket tests against a staging deployment.
- [ ] Test Android/device enrollment, approval, revocation and recovery on a supported device if device integration is in release scope.

### P1.4 Operations and recovery

- [ ] Configure production secret manager and TLS for API and data services.
- [ ] Add health/readiness checks, structured logs, metrics, alerting and trace redaction.
- [ ] Perform database backup and restore drill.
- [ ] Document rollback and incident response.
- [ ] Verify deployment from a clean environment using pinned/reproducible dependencies.

## P2 — maintainability and product quality

- [ ] Resolve remaining Haya/Hina naming inconsistency intentionally, preserving public API compatibility.
- [ ] Remove stale documentation paths and verify all documented commands from a clean checkout.
- [ ] Add feature-by-feature status labels: implemented, mock-only, provider-backed/unverified, not implemented.
- [ ] Add memory retrieval quality evaluation and a repeatable labeled benchmark.
- [ ] Define measurable voice latency and reliability targets before optimizing.
- [ ] Review dependency pinning/update policy and add container/image scanning if containers are part of deployment.

## Release gate

Do not release until all P0 items have evidence and the release owner accepts the remaining P1 operational risks. A green CI result is necessary but not sufficient.

Before tagging a release, attach:
1. exact release SHA and green workflow links;
2. provider-backed sandbox and memory test evidence;
3. authorization test matrix;
4. staging smoke-test report;
5. backup/restore and rollback evidence;
6. updated audit with no unresolved release-blocking P0 findings.
