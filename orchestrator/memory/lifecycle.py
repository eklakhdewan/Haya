"""Memory lifecycle management coordinating vector, graph, and audit reconciliation."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from orchestrator.core.models import MemoryCandidate, MemoryQueryItem, MemoryRecord
from orchestrator.memory.base import GraphStoreAdapter, VectorStoreAdapter
from orchestrator.memory.hybrid_retriever import HybridRetriever


class MemoryLifecycleManager:
    """Coordinate memory writes, owner-scoped deletion, provenance, and audit events."""

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
        """Write a candidate to both stores and compensate if the second write fails."""
        now = datetime.now(UTC)
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
        statement = f"User's {candidate.predicate.lower().replace('_', ' ')} is {candidate.object}"
        await self.vector_store.upsert(record, text=statement)
        try:
            await self.graph_store.add_entity_relation(user_id, record)
        except Exception:
            # Best-effort compensation. A production adapter should additionally
            # reconcile failed cross-store writes using a durable outbox/job.
            await self.vector_store.delete(record.id, user_id)
            raise

        self._audit_log.append(
            {
                "event_id": str(uuid4()),
                "event_type": "MEMORY_CREATED",
                "memory_id": record.id,
                "user_id": user_id,
                "timestamp": now.isoformat(),
                "provenance_turn_id": candidate.source_turn_id,
                "statement": statement,
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
        """Perform concurrent hybrid search for one authenticated user."""
        return await self.retriever.retrieve(
            user_id=user_id,
            query=query_text,
            top_k=top_k,
            include_graph=include_graph,
        )

    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Delete only the authenticated user's record and relationships."""
        vector_deleted = await self.vector_store.delete(memory_id, user_id)
        graph_deleted = await self.graph_store.delete_entity(memory_id, user_id)
        deleted = vector_deleted or graph_deleted
        if deleted:
            self._audit_log.append(
                {
                    "event_id": str(uuid4()),
                    "event_type": "MEMORY_DELETED",
                    "memory_id": memory_id,
                    "user_id": user_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "vector_cleared": vector_deleted,
                    "graph_cleared": graph_deleted,
                }
            )
        return deleted

    def get_audit_trail(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return audit events, optionally scoped to a user."""
        if user_id is not None:
            return [event for event in self._audit_log if event.get("user_id") == user_id]
        return list(self._audit_log)
