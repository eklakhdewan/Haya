"""Google Gemini Provider Adapter for HINA."""

import os
from typing import Any, TypeVar
from pydantic import BaseModel

from orchestrator.core.errors import ProviderUnavailableError
from orchestrator.providers.base import LLMMessage, LLMProvider

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class GeminiProvider(LLMProvider):
    """Google Gemini adapter supporting Gemini 3.8 Flash."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-3.8-flash") -> None:
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self.model = model
        self._client = None

        if not self.api_key:
            # We don't raise immediately on init so mock workflows can load without error,
            # but API calls will raise ProviderUnavailableError if called without a key.
            pass

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise ProviderUnavailableError(
                    "GOOGLE_API_KEY is not configured. Set GOOGLE_API_KEY in .env or switch to MockLLMProvider."
                )
            try:
                from google import genai  # type: ignore[import-not-found]
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise ProviderUnavailableError(
                    "google-genai SDK is not installed. Install via pip install google-genai."
                )
        return self._client

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        client = self._get_client()
        # Call Gemini SDK
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"temperature": temperature, "system_instruction": system_prompt} if system_prompt else {"temperature": temperature},
        )
        return response.text or ""

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        response_schema: type[SchemaT],
        system_prompt: str | None = None,
        temperature: float = 0.1,
    ) -> SchemaT:
        client = self._get_client()
        prompt_text = "\n".join([f"{m.role}: {m.content}" for m in messages])

        response = client.models.generate_content(
            model=self.model,
            contents=prompt_text,
            config={
                "response_mime_type": "application/json",
                "response_schema": response_schema,
                "temperature": temperature,
                "system_instruction": system_prompt,
            },
        )
        if response.text:
            return response_schema.model_validate_json(response.text)
        raise ProviderUnavailableError("Gemini returned empty response for structured request")
