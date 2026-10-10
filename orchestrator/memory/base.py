"""Abstract base interfaces for Vector and Knowledge Graph memory stores."""

from abc import ABC, abstractmethod
from typing import Any
from orchestrator.core.models import MemoryQueryItem, MemoryRecord


class VectorStoreAdapter(ABC):
    """Abstract interface for dense/sparse vector retrieval."""

    @abstractmethod
    async def upsert(self, record: MemoryRecord, text: str) -> None:
        """Upsert memory embedding and metadata."""
        ...

    @abstractmethod
    async def search(self, user_id: str, query: str, top_k: int = 5) -> list[MemoryQueryItem]:
        """Perform semantic hybrid similarity search."""
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete vector record by memory ID."""
        ...


class GraphStoreAdapter(ABC):
    """Abstract interface for entity-relationship knowledge graph."""

    @abstractmethod
    async def add_entity_relation(self, user_id: str, record: MemoryRecord) -> None:
        """Add nodes and typed edge relation into the knowledge graph."""
        ...

    @abstractmethod
    async def search_relations(self, user_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Traverse connected entities matching user query."""
        ...

    @abstractmethod
    async def delete_entity(self, memory_id: str) -> bool:
        """Delete memory node and associated relationships."""
        ...
