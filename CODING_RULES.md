# Coding Rules

## Python

- Python 3.12.
- `ruff` for lint/format.
- `mypy --strict`.
- Pydantic for external/agent schemas.
- async I/O for provider/network operations.
- no hidden global state.
- dependency injection for providers.
- no raw `dict` for core domain state when a typed model is practical.
- exceptions must be meaningful and mapped at API boundaries.

## Rust

If/when the custom gateway is introduced:
- `cargo fmt`
- `cargo clippy -- -D warnings`
- Tokio for async
- `thiserror` for typed library errors
- `anyhow` at application boundaries
- no `unwrap()` / `expect()` in production paths

## API

- version endpoints.
- validate input.
- idempotency for mutating requests.
- never log authorization headers.
- use UTC timestamps.

## Git

Conventional Commits:

```text
feat(memory): add hybrid retrieval
fix(device): reject expired action token
test(agent): add routing regression
docs(api): document sandbox endpoint
```

Use short-lived branches and squash merge.

## Agent code

- prompts are versioned files.
- schemas are code-reviewed.
- tool descriptions are treated as security-sensitive.
- max iterations are explicit.
- every action has an audit event.
