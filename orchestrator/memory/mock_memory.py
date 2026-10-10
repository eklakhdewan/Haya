"""Deterministic in-memory vector and knowledge graph stores for testing."""

import re
from typing import Any
from orchestrator.core.models import MemoryQueryItem, MemoryRecord
from orchestrator.memory.base import GraphStoreAdapter, VectorStoreAdapter


class InMemoryVectorStore(VectorStoreAdapter):
    """In-memory vector store using lexical token-matching and semantic similarity simulation."""

    def __init__(self) -> None:
        # memory_id -> (MemoryRecord, text, set_of_tokens)
        self._records: dict[str, tuple[MemoryRecord, str, set[str]]] = {}

    def _tokenize(self, text: str) -> set[str]:
        return set(re.findall(r"\w+", text.lower()))

    async def upsert(self, record: MemoryRecord, text: str) -> None:
        tokens = self._tokenize(text)
        self._records[record.id] = (record, text, tokens)

    async def search(self, user_id: str, query: str, top_k: int = 5) -> list[MemoryQueryItem]:
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        scored_items: list[tuple[float, MemoryRecord, str]] = []
        for mem_id, (rec, text, tokens) in self._records.items():
            if rec.user_id != user_id or rec.status != "active":
                continue

            # Jaccard + token overlap scoring
            intersection = len(q_tokens.intersection(tokens))
            union = len(q_tokens.union(tokens))
            jaccard = intersection / union if union > 0 else 0.0

            # Boost if any query token is directly in text
            if intersection > 0:
                score = round(min(1.0, 0.5 + (jaccard * 0.5) * rec.confidence), 3)
                scored_items.append((score, rec, text))

        scored_items.sort(key=lambda x: x[0], reverse=True)

        return [
            MemoryQueryItem(
                memory_id=rec.id,
                text=text,
                score=score,
                source_turn_id=rec.source_turn_id,
            )
            for score, rec, text in scored_items[:top_k]
        ]

    async def delete(self, memory_id: str) -> bool:
        if memory_id in self._records:
            rec, text, tokens = self._records[memory_id]
            # Soft delete / tombstone
            rec.status = "deleted"
            del self._records[memory_id]
            return True
        return False


class InMemoryGraphStore(GraphStoreAdapter):
    """In-memory knowledge graph store modeling typed relations and traversals."""

    def __init__(self) -> None:
        # user_id -> list of relations: {"memory_id": ..., "subject": ..., "predicate": ..., "object": ..., "type": ...}
        self._relations: list[dict[str, Any]] = []

    async def add_entity_relation(self, user_id: str, record: MemoryRecord) -> None:
        rel = {
            "memory_id": record.id,
            "user_id": user_id,
            "subject": record.subject,
            "predicate": record.predicate,
            "object": record.object,
            "confidence": record.confidence,
        }
        self._relations.append(rel)

    async def search_relations(self, user_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        q_lower = query.lower()
        results: list[dict[str, Any]] = []

        for rel in self._relations:
            if rel["user_id"] != user_id:
                continue

            # If query mentions subject or object
            if rel["subject"].lower() in q_lower or rel["object"].lower() in q_lower:
                results.append(rel)
            elif any(w in rel["object"].lower() for w in q_lower.split()):
                results.append(rel)

        return results[:top_k]

    async def delete_entity(self, memory_id: str) -> bool:
        initial_len = len(self._relations)
        self._relations = [r for r in self._relations if r["memory_id"] != memory_id]
        return len(self._relations) < initial_len
