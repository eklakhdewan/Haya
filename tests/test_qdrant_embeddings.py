"""Regression tests for semantic embedding behavior without external services."""

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from orchestrator.memory.qdrant_adapter import QdrantVectorAdapter


class FakeVector:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


class FakeSentenceTransformer:
    def __init__(self, model_name: str) -> None:
        assert model_name == "test-embedding-model"

    def encode(self, text: str, normalize_embeddings: bool) -> FakeVector:
        assert normalize_embeddings is True
        return FakeVector([1.0, 0.0] if "alpha" in text else [0.0, 1.0])


@pytest.mark.asyncio
async def test_qdrant_adapter_embeds_text_and_query_with_same_real_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    adapter = QdrantVectorAdapter(embedding_model="test-embedding-model")

    document_vector = await adapter._embed("alpha document")
    query_vector = await adapter._embed("beta query")

    assert document_vector == [1.0, 0.0]
    assert query_vector == [0.0, 1.0]
    assert document_vector != query_vector


@pytest.mark.asyncio
async def test_qdrant_adapter_fails_closed_when_embedding_model_cannot_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_load(model_name: str) -> Any:
        raise OSError("model unavailable")

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=fail_to_load),
    )
    adapter = QdrantVectorAdapter(embedding_model="unavailable-model")

    with pytest.raises(RuntimeError, match="embedding model could not be loaded"):
        await adapter._embed("private memory")
