# Haya — Autonomous Real-Time AI Companion

**Engineering status:** security baseline and CI improvements merged; **not production-ready**.  
**Current audit:** [Post-merge audit and remediation plan](docs/POST_MERGE_AUDIT_AND_REMEDIATION_PLAN.md)  
**Release tracker:** [v1 execution and release checklist](docs/V1_RELEASE_EXECUTION_CHECKLIST.md)

Haya (some legacy modules/docs still use the name Hina) is an agent-orchestration project intended to combine a text/voice assistant, controlled tools, user-scoped memory, isolated code execution and device-action approval.

## Current verified state

- Main branch audited at commit `a3fc5bd01bd4541cbeb07f6c58081760cc53773e` on 2026-10-11.
- [Static Analysis and Security Scanning passed](https://github.com/eklakhdewan/Haya/actions/runs/38112391755).
- [Security Regression passed](https://github.com/eklakhdewan/Haya/actions/runs/38112391747).
- PR #7 added owner-scoped memory deletion, JSON Schema tool input validation, admin checks for sensitive execution routes, request bounds and regression coverage.
- PostgreSQL-backed device-security storage and migrations are present; CI uses an ephemeral PostgreSQL service.

These checks establish the configured CI jobs passed on that commit. They do **not** establish production deployment readiness or successful validation of every external provider.

## Architecture at a glance

```text
Client / voice input
        |
        v
FastAPI orchestrator ---- JWT authentication / authorization
        |
        +---- supervisor and tool registry
        +---- user-scoped memory lifecycle
        |        +---- Qdrant adapter (available; not wired as production path yet)
        |        +---- Neo4j adapter (available; not wired as production path yet)
        +---- sandbox interface
        |        +---- E2B provider adapter (requires provider validation)
        |        +---- restricted mock interpreter (tests only)
        +---- device-action policy and confirmation
                 +---- PostgreSQL-backed security state when configured
```

The diagram describes intended components as well as current boundaries. See the audit for the difference between implemented code and production-verified integrations.

## Quick start

Use the current repository manifests and environment template. Do not use old paths from early architecture drafts without checking that they exist in the current tree.

1. Use Python 3.12 and create a virtual environment.
2. Install development dependencies:

   ```bash
   python -m pip install -r requirements-dev.txt
   ```

3. Configure a local `.env` from the current environment template if present. Set a unique random `JWT_SECRET` of at least 32 characters; never commit real secrets.
4. Start only the infrastructure required for the feature being tested. The security regression workflow documents the PostgreSQL migration/test path.
5. Run tests:

   ```bash
   pytest -q
   ```

6. Run static checks:

   ```bash
   ruff check .
   ruff format --check .
   mypy --strict orchestrator tests
   pip-audit -r requirements-dev.txt
   bandit -r orchestrator -ll
   ```

Some tests require configured local services. Passing offline/mocked tests does not count as provider-backed validation.

## Security boundaries

- All non-liveness HTTP routes require a validated bearer JWT in the current middleware.
- Sensitive tool/sandbox/coder endpoints require an admin principal.
- Memory deletion APIs include owner-scoped checks.
- The mock sandbox is not a security boundary and must remain test-only.
- Production code execution must use the isolated provider adapter and fail closed if it is unavailable.
- Real durable hybrid memory is not yet wired as the application production path; the Qdrant adapter currently uses placeholder vectors.
- Configure TLS, secrets, trusted token issuance, rate limits, observability and backup/restore before public deployment.

See [SECURITY.md](SECURITY.md), [persistent storage notes](docs/security/persistent-storage.md), and the [post-merge audit](docs/POST_MERGE_AUDIT_AND_REMEDIATION_PLAN.md).

## Documentation map

- [Start here](docs/START_HERE.md) — current setup and development sequence.
- [Post-merge audit and remediation plan](docs/POST_MERGE_AUDIT_AND_REMEDIATION_PLAN.md) — findings, evidence and priority order.
- [v1 execution and release checklist](docs/V1_RELEASE_EXECUTION_CHECKLIST.md) — source of truth for remaining work and release gates.
- [Phase 1 security report](docs/PHASE1_SECURITY_EXECUTION_REPORT.md) — security controls and evidence still required.
- [Security protocol](SECURITY.md) — threat model and operational constraints.
- [Persistent device-security storage](docs/security/persistent-storage.md) — PostgreSQL setup and boundaries.
- [Changelog](CHANGELOG.md) — notable changes.

## Definition of done

Do not call Haya production-ready until the exact release SHA passes CI and the release checklist has evidence for real provider execution, durable memory and restart recovery, route/WebSocket authorization, production identity/secrets/TLS, rate/resource limits, monitoring, backup/restore and rollback.

The current state is a stronger engineering baseline, not a production-readiness certification.
