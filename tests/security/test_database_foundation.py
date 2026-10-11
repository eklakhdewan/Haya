import asyncio
from types import SimpleNamespace

import pytest

import orchestrator.core.database as database
from orchestrator.core.config import Environment
from orchestrator.devices.persistence_models import SecurityBase


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "postgresql://user:password@localhost:5432/hina",
            "postgresql+asyncpg://user:password@localhost:5432/hina",
        ),
        (
            "postgres://user:password@localhost:5432/hina",
            "postgresql+asyncpg://user:password@localhost:5432/hina",
        ),
        (
            "postgresql+asyncpg://user:password@localhost:5432/hina",
            "postgresql+asyncpg://user:password@localhost:5432/hina",
        ),
    ],
)
def test_normalize_async_database_url(source: str, expected: str) -> None:
    assert database.normalize_async_database_url(source) == expected


@pytest.mark.parametrize("url", ["", "sqlite:///local.db", "mysql://localhost/hina"])
def test_normalize_async_database_url_rejects_unsupported_scheme(url: str) -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        database.normalize_async_database_url(url)


def test_database_runtime_is_optional_outside_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(environment=Environment.DEVELOPMENT, database_url=""),
    )
    assert database.create_database_runtime() is None


def test_database_runtime_fails_closed_in_production_without_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(environment=Environment.PRODUCTION, database_url=""),
    )
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        database.create_database_runtime()


def test_database_runtime_creates_async_engine_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(
            environment=Environment.DEVELOPMENT,
            database_url="postgresql://user:password@localhost:5432/hina",
        ),
    )
    runtime = database.create_database_runtime()
    assert runtime is not None
    assert runtime.engine.url.drivername == "postgresql+asyncpg"
    asyncio.run(runtime.dispose())


def test_security_metadata_contains_expected_tables() -> None:
    assert set(SecurityBase.metadata.tables) == {
        "security_devices",
        "security_pending_confirmations",
        "security_used_nonces",
        "security_completed_intents",
        "security_action_audit",
    }
    assert SecurityBase.metadata.tables["security_used_nonces"].primary_key.columns.keys() == [
        "nonce"
    ]
    assert SecurityBase.metadata.tables[
        "security_completed_intents"
    ].primary_key.columns.keys() == ["intent_id"]
