# Start Here — Haya Development Guide

**Current status:** engineering baseline; not production-ready.  
**First read:** [Post-merge audit and remediation plan](POST_MERGE_AUDIT_AND_REMEDIATION_PLAN.md).  
**Track remaining work:** [v1 release checklist](V1_RELEASE_EXECUTION_CHECKLIST.md).

## 1. Prerequisites

- Python 3.12
- Git
- Access to install the project's Python dependencies
- Optional service credentials only for provider-backed testing; never commit credentials

Check the repository's current manifests and environment template before following setup commands. Older architecture drafts may mention paths or services that no longer exist.

## 2. Set up a local environment

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Linux/macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Configure environment variables using the current template if available. Use a unique random `JWT_SECRET` of at least 32 characters. Do not use a placeholder in a deployed environment and do not commit secrets.

PostgreSQL-backed security integration tests use a database configured by the environment; the CI workflow shows the expected test database setup and runs Alembic before pytest.

## 3. Run checks

```bash
python -m compileall -q orchestrator tests
ruff check .
ruff format --check .
mypy --strict orchestrator tests
pytest -q
pip-audit -r requirements-dev.txt
bandit -r orchestrator -ll
```

Some tests require services or provider credentials. Label test results as offline/mock or provider-backed; one must not be used as evidence for the other.

## 4. Development sequence

1. **Sandbox safety:** ensure mock execution is test-only and production fails closed.
2. **Durable memory:** real embeddings and Qdrant/Neo4j lifecycle, ownership, persistence and recovery tests.
3. **Authorization:** route and WebSocket matrix for anonymous, regular-user, cross-user and admin requests.
4. **Durability:** persistent memory audit and cross-store reconciliation.
5. **Abuse controls:** rate limits, concurrency limits, request/output bounds and provider budgets.
6. **Staging validation:** real providers, TLS/secrets, monitoring, backup/restore and rollback.
7. **Release review:** update the checklist with exact SHA and evidence.

Do not start by expanding voice/device scope while these P0 safety and persistence gates remain open.

## 5. Security boundaries

- The mock sandbox is a deterministic test adapter, not a security boundary.
- Production code execution must use a real isolated provider and fail closed if unavailable.
- The Qdrant adapter's constant vector is a placeholder and must not be presented as semantic search.
- In-memory stores and in-memory audit records are not durable across restarts.
- CI passing on an ephemeral service does not certify production deployment.

## 6. Documentation map

- [README](../README.md)
- [Post-merge audit and remediation plan](POST_MERGE_AUDIT_AND_REMEDIATION_PLAN.md)
- [v1 release checklist](V1_RELEASE_EXECUTION_CHECKLIST.md)
- [Phase 1 security execution report](PHASE1_SECURITY_EXECUTION_REPORT.md)
- [Security protocol](../SECURITY.md)
- [Persistent security storage notes](security/persistent-storage.md)
