# Repository Structure

```text
hina/
├── .github/
│   └── workflows/
├── config/
│   ├── schemas/
│   └── policies/
├── docs/
├── gateway/
│   └── src/                         # optional custom Rust gateway
├── orchestrator/
│   ├── agents/
│   ├── core/
│   ├── providers/
│   ├── policies/
│   ├── tools/
│   ├── memory/
│   └── main.py
├── memory_core/
│   ├── docker-compose.yml
│   └── migrations/
├── mobile_client/
│   └── android/
├── tests/
│   ├── golden/
│   ├── integration/
│   ├── security/
│   └── load/
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── README.md
```

## Boundary rule

Business logic belongs in `orchestrator/`.

Provider-specific code belongs in `orchestrator/providers/`.

Security decisions belong in `orchestrator/policies/`.

Persistent storage access belongs in `orchestrator/memory/`.

UI must not contain authorization logic.
