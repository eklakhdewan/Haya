"""Unit tests for Vector and Graph store adapters."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from orchestrator.core.models import MemoryRecord
from orchestrator.memory.mock_memory import InMemoryGraphStore, InMemoryVectorStore


def test_in_memory_vector_store() -> None:
    async def _run() -> None:
        v_store = InMemoryVectorStore()
        now = datetime.now(UTC)
        user_id = "test-user-v"

        rec1 = MemoryRecord(
            id=str(uuid4()),
            user_id=user_id,
            subject="User",
            predicate="PREFERS",
            object="Python",
            confidence=0.95,
            source_turn_id="turn-1",
            created_at=now,
            updated_at=now,
        )
        rec2 = MemoryRecord(
            id=str(uuid4()),
            user_id=user_id,
            subject="User",
            predicate="WORKS_ON",
            object="HINA",
            confidence=0.98,
            source_turn_id="turn-2",
            created_at=now,
            updated_at=now,
        )

        await v_store.upsert(rec1, "User prefers Python for development")
        await v_store.upsert(rec2, "User is actively developing project HINA")

        # Search Python
        results = await v_store.search(user_id, "Python development", top_k=5)
        assert len(results) >= 1
        assert results[0].memory_id == rec1.id
        assert results[0].score > 0.5

        # Search HINA
        results_hina = await v_store.search(user_id, "HINA project", top_k=5)
        assert len(results_hina) >= 1
        assert results_hina[0].memory_id == rec2.id

        # Cross-user deletion must not disclose or mutate another user's record.
        assert await v_store.delete(rec1.id, "attacker-user") is False
        assert any(
            item.memory_id == rec1.id for item in await v_store.search(user_id, "Python", top_k=5)
        )

        # Delete as the owner.
        del_res = await v_store.delete(rec1.id, user_id)
        assert del_res is True

        # Searching again should not return deleted memory
        results_after = await v_store.search(user_id, "Python", top_k=5)
        assert not any(r.memory_id == rec1.id for r in results_after)

    asyncio.run(_run())


def test_in_memory_graph_store() -> None:
    async def _run() -> None:
        g_store = InMemoryGraphStore()
        now = datetime.now(UTC)
        user_id = "test-user-g"

        rec = MemoryRecord(
            id=str(uuid4()),
            user_id=user_id,
            subject="User",
            predicate="WORKS_ON",
            object="HINA_COMPANION",
            confidence=0.99,
            source_turn_id="turn-g1",
            created_at=now,
            updated_at=now,
        )

        await g_store.add_entity_relation(user_id, rec)

        # Search relation
        rels = await g_store.search_relations(user_id, "HINA_COMPANION", top_k=5)
        assert len(rels) == 1
        assert rels[0]["predicate"] == "WORKS_ON"
        assert rels[0]["object"] == "HINA_COMPANION"

        # Cross-user deletion must not remove another user's graph relation.
        assert await g_store.delete_entity(rec.id, "attacker-user") is False
        assert len(await g_store.search_relations(user_id, "HINA_COMPANION", top_k=5)) == 1

        # Delete relation as the owner.
        deleted = await g_store.delete_entity(rec.id, user_id)
        assert deleted is True

        rels_after = await g_store.search_relations(user_id, "HINA_COMPANION", top_k=5)
        assert len(rels_after) == 0

    asyncio.run(_run())
