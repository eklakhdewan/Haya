"""Service-backed integration tests for durable Qdrant and Neo4j adapters."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from orchestrator.core.models import MemoryRecord
from orchestrator.memory.neo4j_adapter import Neo4jGraphAdapter
from orchestrator.memory.qdrant_adapter import QdrantVectorAdapter


@pytest.mark.asyncio
async def test_qdrant_adapter_persists_and_enforces_owner_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.getenv("QDRANT_URL")
    if not url:
        pytest.skip("QDRANT_URL is not configured; service-backed test only.")
    collection = f"haya_test_{uuid4().hex}"
    adapter = QdrantVectorAdapter(
        url=url,
        api_key=os.getenv("QDRANT_API_KEY", ""),
        collection_name=collection,
        embedding_model="test-embedding-model",
    )

    async def embed(text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    monkeypatch.setattr(adapter, "_embed", embed)
    record = MemoryRecord(
        id=str(uuid4()),
        user_id="qdrant-owner",
        subject="User",
        predicate="WORKS_ON",
        object="Project Phoenix",
        confidence=0.9,
        source_turn_id="integration-turn",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    try:
        await adapter.initialize()
        await adapter.upsert(record, "User works on Project Phoenix")
        owner_results = await adapter.search("qdrant-owner", "Project Phoenix")
        other_results = await adapter.search("other-user", "Project Phoenix")
        assert any(item.memory_id == record.id for item in owner_results)
        assert not other_results
        assert await adapter.delete(record.id, "other-user") is False
        assert await adapter.delete(record.id, "qdrant-owner") is True
        assert not any(
            item.memory_id == record.id
            for item in await adapter.search("qdrant-owner", "Project Phoenix")
        )
    finally:
        client = adapter._get_client()
        await client.delete_collection(collection_name=collection)
        await adapter.close()


@pytest.mark.asyncio
async def test_neo4j_adapter_persists_and_enforces_owner_scope() -> None:
    uri = os.getenv("NEO4J_URI")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not password:
        pytest.skip("NEO4J_URI/NEO4J_PASSWORD not configured; service-backed test only.")
    adapter = Neo4jGraphAdapter(
        uri=uri,
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=password,
    )
    record = MemoryRecord(
        id=str(uuid4()),
        user_id="neo4j-owner",
        subject="User",
        predicate="WORKS_ON",
        object=f"Project-{uuid4().hex}",
        confidence=0.9,
        source_turn_id="integration-turn",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    try:
        await adapter.initialize()
        await adapter.add_entity_relation(record.user_id, record)
        assert await adapter.search_relations(record.user_id, record.object)
        assert not await adapter.search_relations("other-user", record.object)
        assert await adapter.delete_entity(record.id, "other-user") is False
        assert await adapter.delete_entity(record.id, record.user_id) is True
        assert not await adapter.search_relations(record.user_id, record.object)
    finally:
        await adapter.close()
