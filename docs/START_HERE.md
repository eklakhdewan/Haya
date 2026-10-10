# Start Here — Hina Build Order

## Day 1

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env
docker compose -f memory_core/docker-compose.yml up -d
pytest -q
```

## First milestone

Do not add voice yet.

Build a text endpoint that can:

```text
input
→ router
→ memory retrieval
→ tool decision
→ response
→ audit event
```

## Second milestone

Add sandbox.

## Third milestone

Add persistent memory.

## Fourth milestone

Add realtime voice.

## Fifth milestone

Add Android.

This order minimizes debugging ambiguity.
