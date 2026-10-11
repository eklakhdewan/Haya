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
        "e2b_api_key": "test-e2b-key",
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


@pytest.mark.parametrize("environment", ["development", "staging", "production"])
def test_mock_sandbox_provider_is_rejected_outside_testing(environment: str) -> None:
    with pytest.raises(ValidationError, match="SANDBOX_PROVIDER=mock"):
        make_settings(environment=environment, sandbox_provider="mock")



def test_staging_rejects_missing_e2b_credentials() -> None:
    with pytest.raises(ValidationError, match="E2B_API_KEY"):
        make_settings(
            environment="staging",
            database_url="postgresql+asyncpg://user:pass@localhost:5432/haya",
            e2b_api_key="",
        )

def test_mock_sandbox_provider_is_allowed_only_for_testing() -> None:
    settings = make_settings(environment="testing", sandbox_provider="mock")
    assert settings.sandbox_provider == "mock"


@pytest.mark.parametrize("environment", ["development", "staging", "production", "testing"])
def test_e2b_is_default_sandbox_provider(environment: str) -> None:
    overrides: dict[str, Any] = {
        "environment": environment,
        "e2b_api_key": "test-e2b-key",
    }
    if environment in {"staging", "production"}:
        overrides["database_url"] = "postgresql+asyncpg://user:pass@localhost:5432/haya"
    settings = make_settings(**overrides)
    assert settings.sandbox_provider == "e2b"
