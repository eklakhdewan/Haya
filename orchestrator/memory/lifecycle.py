"""Memory lifecycle management coordinating vector, graph, and audit reconciliation."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from orchestrator.core.models import (
    MemoryCandidate,
    MemoryOperation,
    MemoryQueryItem,
    MemoryRecord,
)
from orchestrator.memory.base import GraphStoreAdapter, VectorStoreAdapter
from orchestrator.memory.hybrid_retriever import HybridRetriever


class MemoryLifecycleManager:
    """Coordinates writes, cascading deletions, provenance, and audit logs across memory stores."""

    def __init__(
        self,
        vector_store: VectorStoreAdapter,
        graph_store: GraphStoreAdapter,
    ) -> None:
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.retriever = HybridRetriever(vector_store, graph_store)
        self._audit_log: list[dict[str, Any]] = []

    async def store_candidate(self, user_id: str, candidate: MemoryCandidate) -> MemoryRecord:
        """Persist a memory candidate into both vector and graph stores with provenance."""
        now = datetime.now(timezone.utc)
        record = MemoryRecord(
            id=str(uuid4()),
            user_id=user_id,
            kind="fact",
            subject=candidate.subject,
            predicate=candidate.predicate,
            object=candidate.object,
            confidence=candidate.confidence,
            source_turn_id=candidate.source_turn_id,
            created_at=now,
            updated_at=now,
            status="active",
        )

        natural_statement = f"User's {candidate.predicate.lower().replace('_', ' ')} is {candidate.object}"

        # 1. Write to vector store
        await self.vector_store.upsert(record, text=natural_statement)

        # 2. Write to graph store
        await self.graph_store.add_entity_relation(user_id, record)

        # 3. Log audit event
        self._audit_log.append(
            {
                "event_id": str(uuid4()),
                "event_type": "MEMORY_CREATED",
                "memory_id": record.id,
                "user_id": user_id,
                "timestamp": now.isoformat(),
                "provenance_turn_id": candidate.source_turn_id,
                "statement": natural_statement,
            }
        )

        return record

    async def query(
        self,
        user_id: str,
        query_text: str,
        top_k: int = 5,
        include_graph: bool = True,
    ) -> list[MemoryQueryItem]:
        """Perform concurrent hybrid search."""
        return await self.retriever.retrieve(
            user_id=user_id,
            query=query_text,
            top_k=top_k,
            include_graph=include_graph,
        )

    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Propagate memory deletion across vector and graph layers with audit tombstone."""
        v_deleted = await self.vector_store.delete(memory_id)
        g_deleted = await self.graph_store.delete_entity(memory_id)

        now = datetime.now(timezone.utc)
        self._audit_log.append(
            {
                "event_id": str(uuid4()),
                "event_type": "MEMORY_DELETED",
                "memory_id": memory_id,
                "user_id": user_id,
                "timestamp": now.isoformat(),
                "vector_cleared": v_deleted,
                "graph_cleared": g_deleted,
            }
        )

        return v_deleted or g_deleted

    def get_audit_trail(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return immutable audit log of memory modifications."""
        if user_id:
            return [evt for evt in self._audit_log if evt.get("user_id") == user_id]
        return list(self._audit_log)
