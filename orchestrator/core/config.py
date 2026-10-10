"""Configuration management for Hina using Pydantic Settings."""

from enum import Enum
import os
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # LLM Provider
    google_api_key: str = Field(default="", description="Google Gemini API key")
    llm_model: str = Field(default="gemini-3.8-flash", description="Default LLM model identifier")

    # Voice / STT / TTS
    deepgram_api_key: str = Field(default="", description="Deepgram API key")
    deepgram_stt_model: str = Field(default="flux-general-en", description="Deepgram streaming STT model")
    tts_provider: str = Field(default="deepgram", description="Streaming TTS provider")

    # Memory Infrastructure
    # Persistent Security Storage
    database_url: str = Field(
        default="",
        description="PostgreSQL connection URL for persistent security state",
        repr=False,
    )
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant endpoint")
    qdrant_api_key: str = Field(default="", description="Qdrant API key if secured")
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI")
    neo4j_username: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(default="change-me", description="Neo4j password")
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")

    # Code Execution Sandbox
    e2b_api_key: str = Field(default="", description="E2B API key for microVM sandboxes")
    sandbox_network: Literal["enabled", "disabled"] = "disabled"
    sandbox_timeout_ms: int = 5000
    sandbox_max_repairs: int = 2

    # Security & Tokens
    jwt_secret: str = Field(default_factory=lambda: os.getenv("JWT_SECRET", ""), min_length=32, description="JWT HS256 signing secret; set JWT_SECRET to a unique random value")
    jwt_issuer: str = "hina-orchestrator"
    jwt_audience: str = "hina-api"
    device_token_ttl_seconds: int = 300
    action_confirmation_ttl_seconds: int = 120

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        if self.jwt_secret in {"replace-with-a-long-random-secret", "insecure-dev-secret-replace-in-production"}:
            raise ValueError("Replace the JWT_SECRET placeholder with a unique random secret.")
        if self.environment == Environment.PRODUCTION and self.neo4j_password == "change-me":
            raise ValueError("Production requires a non-default NEO4J_PASSWORD.")
        if self.environment == Environment.PRODUCTION:
            if not self.database_url.strip():
                raise ValueError(
                    "Production requires DATABASE_URL for persistent security storage."
                )
            if not self.database_url.startswith(
                ("postgresql://", "postgresql+asyncpg://", "postgres://")
            ):
                raise ValueError(
                    "DATABASE_URL must use a PostgreSQL connection URL."
                )

        return self

    # Observability
    otel_service_name: str = "hina-orchestrator"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"


# Cached settings instance factory
_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Retrieve or create application settings."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
