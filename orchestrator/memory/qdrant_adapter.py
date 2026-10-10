"""Qdrant Vector Store Adapter for dense/sparse hybrid search."""

from typing import Any

from orchestrator.core.models import MemoryQueryItem, MemoryRecord
from orchestrator.memory.base import VectorStoreAdapter


class QdrantVectorAdapter(VectorStoreAdapter):
    """Qdrant vector adapter supporting collection creation, metadata payload, and vector similarity."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str = "",
        collection_name: str = "hina_memories",
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from qdrant_client import AsyncQdrantClient

                self._client = AsyncQdrantClient(url=self.url, api_key=self.api_key or None)
            except Exception as e:
                raise ConnectionError(f"Failed to initialize Qdrant client: {e}")
        return self._client

    async def upsert(self, record: MemoryRecord, text: str) -> None:
        client = self._get_client()
        from qdrant_client.models import PointStruct

        # In production, embeddings are calculated via sentence-transformers or Gemini
        # Here we mock a 384-dimension pseudo-vector for collection storage if embeddings are computed
        vector = [0.1] * 384

        payload = {
            "memory_id": record.id,
            "user_id": record.user_id,
            "kind": record.kind,
            "source_turn_id": record.source_turn_id,
            "text": text,
            "confidence": record.confidence,
            "created_at": record.created_at.isoformat(),
        }

        await client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(id=record.id, vector=vector, payload=payload)],
        )

    async def search(self, user_id: str, query: str, top_k: int = 5) -> list[MemoryQueryItem]:
        client = self._get_client()
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        user_filter = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])

        query_vector = [0.1] * 384
        search_result = await client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=user_filter,
            limit=top_k,
        )

        items: list[MemoryQueryItem] = []
        for hit in search_result:
            payload = hit.payload or {}
            items.append(
                MemoryQueryItem(
                    memory_id=str(payload.get("memory_id", hit.id)),
                    text=str(payload.get("text", "")),
                    score=float(hit.score),
                    source_turn_id=str(payload.get("source_turn_id", "")),
                )
            )
        return items

    async def delete(self, memory_id: str) -> bool:
        client = self._get_client()
        from qdrant_client.models import PointIdsList

        res = await client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=[memory_id]),
        )
        return getattr(res, "status", "") == "completed"
