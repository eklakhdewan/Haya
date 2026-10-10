from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.core.config import Settings

VALID_JWT_SECRET = "test-only-random-secret-not-for-production"
VALID_NEO4J_PASSWORD = "test-only-neo4j-password"


def make_settings(**overrides: Any) -> Settings:
    values = {
        "environment": "development",
        "jwt_secret": VALID_JWT_SECRET,
        "neo4j_password": VALID_NEO4J_PASSWORD,
        "database_url": "",
    }
    values.update(overrides)
    return Settings.model_validate(values)


@pytest.mark.parametrize(
    "jwt_secret",
    [
        "",
        " " * 32,
        "replace-with-a-long-random-secret",
        "insecure-dev-secret-replace-in-production",
        "short-secret",
    ],
)
def test_rejects_missing_weak_or_placeholder_jwt_secret(jwt_secret: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(jwt_secret=jwt_secret)


def test_production_rejects_empty_neo4j_password() -> None:
    with pytest.raises(ValidationError, match="NEO4J_PASSWORD"):
        make_settings(
            environment="production",
            neo4j_password="",
            database_url="postgresql+asyncpg://user:pass@localhost:5432/haya",
        )


def test_development_allows_missing_database_url() -> None:
    settings = make_settings()
    assert settings.database_url == ""


@pytest.mark.parametrize(
    "database_url",
    ["", "   ", "mysql://user:pass@localhost/db", "sqlite:///local.db"],
)
def test_production_rejects_missing_or_non_postgres_database_url(database_url: str) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        make_settings(
            environment="production",
            database_url=database_url,
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:pass@localhost:5432/haya",
        "postgresql+asyncpg://user:pass@localhost:5432/haya",
        "postgres://user:pass@localhost:5432/haya",
    ],
)
def test_production_accepts_postgres_url_scheme(database_url: str) -> None:
    settings = make_settings(
        environment="production",
        database_url=database_url,
    )
    assert settings.database_url == database_url


def test_production_rejects_default_neo4j_password() -> None:
    with pytest.raises(ValidationError, match="NEO4J_PASSWORD"):
        make_settings(
            environment="production",
            neo4j_password="change-me",
            database_url="postgresql+asyncpg://user:pass@localhost:5432/haya",
        )
