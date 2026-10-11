# Haya v1.0 Execution and Release Checklist

**Last reviewed:** 2026-10-11  
**Release status:** NOT RELEASE-READY  
**Latest audited main SHA:** `a3fc5bd01bd4541cbeb07f6c58081760cc53773e`  
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

- [ ] Enforce mock sandbox selection as test-only; fail startup or reject requests if a non-test environment selects it.
- [ ] Test missing E2B credentials, missing SDK, provider outage, timeout, cancellation and malformed provider results.
- [ ] Prove that no production failure path falls back to in-process/mock execution.
- [ ] Run a provider-backed isolated execution test and verify network egress remains disabled at the provider boundary.
- [ ] Verify execution timeout, output limits, cleanup and resource bounds.

### P0.2 Durable hybrid memory

- [ ] Add a real embedding interface/provider; remove constant placeholder vectors from production paths.
- [ ] Wire Qdrant and Neo4j adapters into application startup/shutdown using validated configuration.
- [ ] Verify collection/index setup, credentials, connection health and failure behavior.
- [ ] Test persistence across API restarts and worker processes.
- [ ] Test cross-user query and delete isolation against real adapters.
- [ ] Test adapter failure, partial write, retry and reconciliation behavior.
- [ ] Fail closed or explicitly disable the durable-memory feature if production configuration is incomplete.

### P0.3 Authentication and authorization

- [ ] Inventory every HTTP route and WebSocket path; record required role and ownership policy.
- [ ] Test unauthenticated, regular-user, cross-user and admin access for all sensitive routes.
- [ ] Verify JWT issuer, audience, expiry, issued-at, subject and role handling.
- [ ] Verify trusted production token issuance and signing-secret rotation.
- [ ] Verify WebSocket authentication, reconnect and query-token log redaction if query tokens are supported.
- [ ] Verify TLS, CORS and deployment proxy settings.
- [ ] Verify production startup fails closed when required secrets or persistent security storage are missing.

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
