# Haya v1.0 Execution and Release Checklist

**Last reviewed:** 2026-10-10  
**Release status:** NOT RELEASE-READY  
**Current working branch:** `security/static-analysis-scanning`  
**Pull request:** [#6 — Static Analysis and Security Scanning](https://github.com/eklakhdewan/Haya/pull/6)

This is the authoritative execution tracker for the remaining v1.0 work. A checkbox may be marked complete only when evidence exists (CI URL, test report, deployment record, or recovery drill). Source changes alone do not count as proof.

## Current evidence snapshot

- PostgreSQL 16 migration and integration regression workflow passed on the PR branch: [run 38026295936](https://github.com/eklakhdewan/Haya/actions/runs/38026295936).
- Latest static-analysis run failed: [run 38026295900](https://github.com/eklakhdewan/Haya/actions/runs/38026295900).
- In that static-analysis run, secret scanning, dependency audit, and CodeQL passed; Ruff, strict mypy, and Bandit failed.
- Dependency audit passed after the requirements range changes on that run. This is evidence for the resolved declared requirements at that commit, not a guarantee about all deployed/transitive runtime environments.
- Latest mypy log showed two errors at commit `b1b3caf`: a stale `op_type` reference in `orchestrator/tools/builtin.py` and a redundant cast in `orchestrator/core/auth.py`. Follow-up commits fix those two findings; a new completed run is still required.
- Ruff reported 259 findings at `b1b3caf`; bulk formatting/lint remediation has not yet been validated.
- Bandit reported B104 for the default `0.0.0.0` bind address and B102 for `exec()` in `orchestrator/sandbox/mock_sandbox.py`. The API host default has been changed to loopback; Bandit must be rerun. The mock sandbox execution design still requires a safe resolution and tests; do not simply suppress B102.
- The CI database is ephemeral. These runs do not verify a production database, production identity issuer, real E2B execution, deployment TLS, monitoring, or backup restoration.

## Phase 0 — Local static-analysis remediation (P0)

- [ ] On the user's local machine, inspect `git status` and create a backup branch before integrating PR branch changes.
- [ ] Run `ruff check . --fix`, inspect every edit, then `ruff format .`; do not accept broad changes without review.
- [ ] Run `ruff check .` and `ruff format --check .` until both pass.
- [ ] Run `mypy --strict orchestrator tests`; fix all errors without adding blanket ignores or weakening strictness.
- [ ] Replace unsafe in-process `exec()` in the mock sandbox with a non-executing deterministic test double, or another design proven safe by tests. Do not treat restricted builtins as a security boundary.
- [ ] Confirm the API bind address is explicit for deployment; loopback is the safe local default. Set the production bind address through deployment configuration only where required.
- [ ] Run `pip-audit -r requirements-dev.txt`; inspect the dependency tree and compatibility after upgrading LangGraph and pytest.
- [ ] Run the full regression suite with PostgreSQL 16 and the complete local suite.
- [ ] Push the resulting branch and verify all CI jobs on the exact resulting SHA.
- [ ] Keep PR #6 unmerged until all required checks pass and dependency/API compatibility is verified.

## Phase 1 — Repository and architecture audit (P0)

- [ ] Inventory implemented modules, public routes, configuration, migrations, provider adapters and client integrations.
- [ ] Mark each feature as production-backed, provider-backed but unverified, mock-only, or not implemented.
- [ ] Audit route-level authentication and authorization, including admin access and user/device ownership.
- [ ] Review transactions, database constraints, migrations, retries, replay protection, confirmation expiry and revocation.
- [ ] Review logging, exception handling, PII/secret exposure, request limits and unsafe defaults.
- [ ] Record findings with severity, source path, reproducible test and disposition.

## Phase 2 — Identity and production security (P0)

- [ ] Generate a unique random `JWT_SECRET` in the deployment secret manager; never commit it or paste it into chat.
- [ ] Configure and verify a trusted production identity/token issuer; do not use the development token helper in staging/production.
- [ ] Verify issuer, audience, expiry, issued-at, subject, role and signing-key rotation.
- [ ] Configure TLS for public API, database and provider connections.
- [ ] Verify CORS, WebSocket authentication, query-token log redaction, rate limits and request-size limits.
- [ ] Test unauthenticated, ordinary-user, cross-user and admin cases against a deployed environment.
- [ ] Verify startup fails closed if persistent security storage or required secrets are missing.

## Phase 3 — Persistent state and safe actions (P0)

- [x] Add PostgreSQL-backed device, revocation, confirmation, nonce, completion and audit records.
- [x] Add Alembic migration and PostgreSQL integration coverage for restart persistence, single-use confirmation, nonce replay, concurrent intent replay and concurrent device registration.
- [x] Pass the repository's PostgreSQL CI regression suite on the recorded PR run.
- [ ] Verify clean-install migration and upgrade-from-existing-schema against a production-like database.
- [ ] Test rollback, connection loss, transaction retry, duplicate requests and race conditions beyond the existing tests.
- [ ] Specify the external side-effect idempotency/reconciliation contract. A completion row alone does not guarantee exactly-once external action execution.
- [ ] Decide and test audit retention, access control, redaction, integrity protection and backup requirements.

## Phase 4 — Real provider validation (P1)

- [ ] Run an actual E2B isolated execution using credentials supplied securely by the operator.
- [ ] Verify provider-level network isolation, timeout, CPU/memory/output bounds, cleanup and failure handling.
- [ ] Verify real LLM provider calls, timeout/retry/error behavior and quota exhaustion.
- [ ] Verify Qdrant, Neo4j and Redis against intended supported versions, including memory deletion and per-user isolation.
- [ ] Run Deepgram STT/TTS integration tests with real audio, interruption and cancellation.
- [ ] Clearly label every test as mock/offline or provider-backed; mocks do not satisfy this gate.

## Phase 5 — API, voice and device E2E (P1)

- [ ] Run authenticated and negative API tests against the deployed candidate.
- [ ] Verify WebSocket auth, reconnect, cancellation and session cleanup.
- [ ] Run the voice path end to end: audio input, STT, orchestration, response, TTS and playback.
- [ ] Verify Android/device enrollment, permissions, user confirmation, revocation and error recovery on a real supported device.
- [ ] Test provider outage, slow responses, duplicate events and interrupted actions.
- [ ] Store a reproducible acceptance report with commit SHA, environment and results.

## Phase 6 — Deployment and smoke tests (P1)

- [ ] Confirm the actual hosting provider, deployment topology, domain and rollback strategy.
- [ ] Provision production database, migrations, secret manager, TLS and provider credentials.
- [ ] Deploy the candidate and record the exact deployed commit SHA.
- [ ] Run health/readiness, auth, ordinary-user, admin-denial, WebSocket, database and provider smoke tests.
- [ ] Verify restart, scaling and configuration behavior.
- [ ] Document rollback and verify it in staging.

## Phase 7 — Monitoring and operations (P1)

- [ ] Configure structured logs, trace correlation and metrics for latency, failures, database and provider health.
- [ ] Configure alerts and prove delivery to an operator-controlled destination.
- [ ] Test alert thresholds, deduplication, recovery notifications and runbooks.
- [ ] Verify PII/secret redaction, audit access, retention and incident response.

## Phase 8 — Backup, restore and resilience (P1)

- [ ] Configure scheduled database backups and retention.
- [ ] Restore a backup into a separate test environment.
- [ ] Verify restored records, schema revision, permissions and application startup.
- [ ] Run a recovery drill and record measured RPO/RTO against explicitly chosen objectives.
- [ ] Document recovery and ensure an operator other than the original implementer can follow it.

## Phase 9 — Documentation and release hygiene (P2)

- [ ] Reconcile README, ROADMAP, SECURITY, architecture docs and this tracker with actual implementation.
- [ ] Remove stale instructions, dead links, generated artifacts and unsupported production claims.
- [ ] Document installation, configuration, migrations, deployment, rollback, provider setup and troubleshooting.
- [ ] Publish an environment-variable reference without real secret values.
- [ ] Document limitations, data handling, retention and provider dependencies.

## Phase 10 — Final audit and release decision (P0)

- [ ] Run all unit, integration, database, security and E2E suites on the exact release candidate SHA.
- [ ] Require all mandatory CI checks to pass.
- [ ] Review all dependency/security findings and document accepted risks with an owner and expiry.
- [ ] Verify production smoke tests, monitoring alert delivery and backup restoration.
- [ ] Resolve all critical/high-severity release blockers.
- [ ] Produce the final audit scoreboard with links to evidence.
- [ ] Tag `v1.0` only after all mandatory gates are satisfied.

## Operator-only prerequisites

The following cannot be truthfully completed by repository edits alone and require the operator's environment or accounts:

1. Run the local commands in Phase 0 on the actual working tree and review the diff.
2. Supply/configure production secrets and provider credentials in the relevant secret manager (never in Git or chat).
3. Provide access to the chosen staging/production infrastructure and identity issuer.
4. Execute or authorize provider-backed E2E tests, deployed smoke tests, monitoring-alert verification and a real backup restore.
5. Approve any documented residual risk and the final release go/no-go decision.

## Release rule

**Haya is not production-ready and must not be tagged v1.0 while any mandatory P0/P1 gate is unchecked.** If a gate cannot be executed because credentials, infrastructure, a device, or an operator action is unavailable, mark it BLOCKED and list the exact evidence required; never mark it complete by inference.
