"""Tests for MemoryExtractor, LifecycleManager, provenance, and cascading deletion."""

import asyncio
from uuid import uuid4

from orchestrator.core.models import (
    MemoryCandidate,
    MemoryEntityType,
    MemoryOperation,
)
from orchestrator.memory.extractor import MemoryExtractor
from orchestrator.memory.lifecycle import MemoryLifecycleManager
from orchestrator.memory.mock_memory import InMemoryGraphStore, InMemoryVectorStore
from orchestrator.providers.mock_llm import MockLLMProvider


def test_memory_extraction_rules() -> None:
    async def _run() -> None:
        llm = MockLLMProvider()
        extractor = MemoryExtractor(llm_provider=llm)

        transcript = [
            {"role": "user", "content": "I am working on HINA right now."},
            {"role": "assistant", "content": "That sounds like an ambitious project!"},
            {"role": "user", "content": "Please remember that my favorite language is Python."},
        ]

        candidates = await extractor.extract(transcript, turn_id="turn-extract-1")
        assert len(candidates) >= 2

        # Check project extraction
        proj = next((c for c in candidates if c.entity_type == MemoryEntityType.PROJECT), None)
        assert proj is not None
        assert proj.object == "HINA"
        assert proj.source_turn_id == "turn-extract-1"

        # Check preference extraction
        pref = next((c for c in candidates if c.entity_type == MemoryEntityType.PREFERENCE), None)
        assert pref is not None
        assert "PYTHON" in pref.object.upper()

    asyncio.run(_run())


def test_memory_lifecycle_cascading_deletion() -> None:
    async def _run() -> None:
        v_store = InMemoryVectorStore()
        g_store = InMemoryGraphStore()
        manager = MemoryLifecycleManager(vector_store=v_store, graph_store=g_store)

        user_id = "user-lifecycle-1"
        candidate = MemoryCandidate(
            entity_type=MemoryEntityType.PREFERENCE,
            subject="User",
            predicate="PREFERS",
            object="AsyncIO",
            confidence=0.97,
            source_turn_id="turn-life-1",
            operation=MemoryOperation.CREATE,
        )

        # 1. Store
        rec = await manager.store_candidate(user_id, candidate)
        assert rec.id is not None
        assert rec.status == "active"

        # 2. Query
        results = await manager.query(user_id, "AsyncIO preference")
        assert len(results) >= 1
        assert results[0].memory_id == rec.id

        # 3. Cascading Delete
        deleted = await manager.delete_memory(user_id, rec.id)
        assert deleted is True

        # 4. Verify gone from queries
        results_after = await manager.query(user_id, "AsyncIO")
        assert not any(r.memory_id == rec.id for r in results_after)

        # 5. Check audit trail has both events
        audit = manager.get_audit_trail(user_id)
        event_types = [e["event_type"] for e in audit]
        assert "MEMORY_CREATED" in event_types
        assert "MEMORY_DELETED" in event_types

    asyncio.run(_run())
