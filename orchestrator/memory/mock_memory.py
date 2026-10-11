"""Deterministic in-memory vector and knowledge graph stores for testing."""

import re
from typing import Any

from orchestrator.core.models import MemoryQueryItem, MemoryRecord
from orchestrator.memory.base import GraphStoreAdapter, VectorStoreAdapter


class InMemoryVectorStore(VectorStoreAdapter):
    """In-memory lexical store for tests; not a production vector database."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[MemoryRecord, str, set[str]]] = {}

    def _tokenize(self, text: str) -> set[str]:
        return set(re.findall(r"\w+", text.lower()))

    async def upsert(self, record: MemoryRecord, text: str) -> None:
        self._records[record.id] = (record, text, self._tokenize(text))

    async def search(self, user_id: str, query: str, top_k: int = 5) -> list[MemoryQueryItem]:
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []
        scored: list[tuple[float, MemoryRecord, str]] = []
        for record, text, tokens in self._records.values():
            if record.user_id != user_id or record.status != "active":
                continue
            intersection = len(q_tokens.intersection(tokens))
            if intersection:
                union = len(q_tokens.union(tokens))
                jaccard = intersection / union if union else 0.0
                score = round(min(1.0, 0.5 + jaccard * 0.5 * record.confidence), 3)
                scored.append((score, record, text))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            MemoryQueryItem(
                memory_id=record.id,
                text=text,
                score=score,
                source_turn_id=record.source_turn_id,
            )
            for score, record, text in scored[:top_k]
        ]

    async def delete(self, memory_id: str, user_id: str) -> bool:
        """Delete only when the stored record belongs to the caller."""
        entry = self._records.get(memory_id)
        if entry is None:
            return False
        record, _, _ = entry
        if record.user_id != user_id:
            return False
        record.status = "deleted"
        del self._records[memory_id]
        return True


class InMemoryGraphStore(GraphStoreAdapter):
    """In-memory graph store for tests; not a production graph database."""

    def __init__(self) -> None:
        self._relations: list[dict[str, Any]] = []

    async def add_entity_relation(self, user_id: str, record: MemoryRecord) -> None:
        self._relations.append(
            {
                "memory_id": record.id,
                "user_id": user_id,
                "subject": record.subject,
                "predicate": record.predicate,
                "object": record.object,
                "confidence": record.confidence,
            }
        )

    async def search_relations(
        self, user_id: str, query: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        q_lower = query.lower()
        results = []
        for relation in self._relations:
            if relation["user_id"] != user_id:
                continue
            if (
                relation["subject"].lower() in q_lower
                or relation["object"].lower() in q_lower
                or any(word in relation["object"].lower() for word in q_lower.split())
            ):
                results.append(relation)
        return results[:top_k]

    async def delete_entity(self, memory_id: str, user_id: str) -> bool:
        """Delete only relationships owned by the caller."""
        owned = [
            relation
            for relation in self._relations
            if relation["memory_id"] == memory_id and relation["user_id"] == user_id
        ]
        if not owned:
            return False
        self._relations = [
            relation
            for relation in self._relations
            if not (relation["memory_id"] == memory_id and relation["user_id"] == user_id)
        ]
        return True
