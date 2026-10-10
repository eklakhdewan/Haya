# Persistent Device Security Storage

HINA can use PostgreSQL to persist device ownership, revocation state, approval challenges, nonce usage, completed intent IDs, and action audit events across process restarts and workers.

## Configuration

Set `DATABASE_URL` in the runtime environment. Use a PostgreSQL URL, for example:

```text
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<database>
```

The standard `postgresql://` scheme is also accepted and normalized to SQLAlchemy's `asyncpg` driver. Never commit real credentials.

In development and tests, leaving `DATABASE_URL` empty preserves the in-memory device manager. In production, `DATABASE_URL` is required and the application fails startup if the database is unavailable or the security schema has not been migrated.

## Apply migrations

Install project dependencies, configure `DATABASE_URL`, and run this command against the target database before starting the API:

```bash
alembic upgrade head
```

To inspect the current revision:

```bash
alembic current
```

The application intentionally does not create or alter production tables automatically at startup. Schema changes must be reviewed and applied through Alembic migrations.

## Security properties and boundaries

- Approval tokens are stored only as SHA-256 digests.
- Database primary-key constraints make nonce reuse and duplicate completed-intent IDs conflict across workers.
- Approval confirmation and execution state changes use transactions and row locks.
- Device revocation and deletion of pending approvals happen in the same transaction.
- Audit records are durable, but this schema does not make them tamper-evident; restrict database permissions and configure backups/retention separately.
- Persistent state prevents duplicate authorization/completion records. It does not guarantee exactly-once delivery to an external device or provider. External side effects need their own idempotency contract.
- Nonce records are retained durably. Define and test a retention policy before adding automated cleanup; deleting nonce records too early can weaken replay protection.

## Verification status

Unit tests cover URL normalization, production fail-closed configuration, and metadata constraints. A live PostgreSQL instance is required to verify migrations, locking behavior, and concurrent requests. Do not describe those integration properties as verified until PostgreSQL-backed tests have passed.
