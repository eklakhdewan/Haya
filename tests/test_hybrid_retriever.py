"""Tests for concurrent HybridRetriever and Reciprocal Rank Fusion (RRF)."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from orchestrator.core.models import MemoryRecord
from orchestrator.memory.hybrid_retriever import HybridRetriever
from orchestrator.memory.mock_memory import InMemoryGraphStore, InMemoryVectorStore


def test_hybrid_retrieval_and_rrf_fusion() -> None:
    async def _run() -> None:
        v_store = InMemoryVectorStore()
        g_store = InMemoryGraphStore()
        retriever = HybridRetriever(vector_store=v_store, graph_store=g_store)

        user_id = "user-hybrid-1"
        now = datetime.now(timezone.utc)
        mem_id = str(uuid4())

        record = MemoryRecord(
            id=mem_id,
            user_id=user_id,
            subject="User",
            predicate="PREFERS",
            object="Dark Theme",
            confidence=0.98,
            source_turn_id="turn-theme",
            created_at=now,
            updated_at=now,
        )

        # Present in both vector and graph
        await v_store.upsert(record, "User prefers dark theme for all editor interfaces")
        await g_store.add_entity_relation(user_id, record)

        items = await retriever.retrieve(
            user_id=user_id,
            query="dark theme preference",
            top_k=5,
            include_graph=True,
        )

        assert len(items) >= 1
        top_item = items[0]
        assert top_item.memory_id == mem_id
        # Because it appears in BOTH vector and graph, its RRF score is higher: (1/61) + (1/61) ~ 0.0328
        assert top_item.score > 0.03

    asyncio.run(_run())
