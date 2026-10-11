"""Qdrant vector store with real sentence-transformer embeddings."""

import asyncio
from typing import Any

from orchestrator.core.models import MemoryQueryItem, MemoryRecord
from orchestrator.memory.base import VectorStoreAdapter


class QdrantVectorAdapter(VectorStoreAdapter):
    """Persistent Qdrant adapter; refuses placeholder or zero-vector retrieval."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str = "",
        collection_name: str = "hina_memories",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        self._client: Any | None = None
        self._model: Any | None = None
        self._initialized = False
        self._embedding_lock = asyncio.Lock()

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from qdrant_client import AsyncQdrantClient

                self._client = AsyncQdrantClient(url=self.url, api_key=self.api_key or None)
            except Exception as exc:
                raise ConnectionError("Failed to initialize Qdrant client.") from exc
        return self._client

    async def _embed(self, text: str) -> list[float]:
        """Create a normalized semantic embedding; never substitute a placeholder vector."""
        async with self._embedding_lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer

                    self._model = await asyncio.to_thread(
                        SentenceTransformer, self.embedding_model_name
                    )
                except Exception as exc:
                    raise RuntimeError(
                        "Semantic memory is unavailable: embedding model could not be loaded."
                    ) from exc
            model = self._model
        if model is None:
            raise RuntimeError("Semantic memory is unavailable: embedding model is not loaded.")
        vector = await asyncio.to_thread(model.encode, text, normalize_embeddings=True)
        values = vector.tolist()
        if not isinstance(values, list) or not values or not all(
            isinstance(value, (int, float)) for value in values
        ):
            raise RuntimeError("Embedding provider returned an invalid vector.")
        return [float(value) for value in values]

    async def initialize(self) -> None:
        """Verify Qdrant and create the collection using the configured model dimensions."""
        if self._initialized:
            return
        client = self._get_client()
        from qdrant_client.models import Distance, VectorParams

        vector = await self._embed("Haya memory collection dimension probe")
        exists = await client.collection_exists(collection_name=self.collection_name)
        if not exists:
            await client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=len(vector), distance=Distance.COSINE),
            )
        else:
            details = await client.get_collection(collection_name=self.collection_name)
            config = details.config.params.vectors
            if isinstance(config, dict):
                vector_config = config.get("")
                if vector_config is None or vector_config.size != len(vector):
                    raise RuntimeError(
                        "Qdrant collection vector dimensions do not match the embedding model."
                    )
            elif getattr(config, "size", None) != len(vector):
                raise RuntimeError(
                    "Qdrant collection vector dimensions do not match the embedding model."
                )
        await client.get_collections()
        self._initialized = True

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
        self._initialized = False

    async def upsert(self, record: MemoryRecord, text: str) -> None:
        await self.initialize()
        client = self._get_client()
        from qdrant_client.models import PointStruct

        vector = await self._embed(text)
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
            wait=True,
        )

    async def search(self, user_id: str, query: str, top_k: int = 5) -> list[MemoryQueryItem]:
        await self.initialize()
        client = self._get_client()
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_vector = await self._embed(query)
        user_filter = Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        )
        search_result = await client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=user_filter,
            limit=top_k,
            with_payload=True,
        )
        items: list[MemoryQueryItem] = []
        for hit in search_result.points:
            payload = hit.payload or {}
            items.append(
                MemoryQueryItem(
                    memory_id=str(payload.get("memory_id", hit.id)),
                    text=str(payload.get("text", "")),
                    score=float(hit.score or 0.0),
                    source_turn_id=str(payload.get("source_turn_id", "")),
                )
            )
        return items

    async def delete(self, memory_id: str, user_id: str) -> bool:
        await self.initialize()
        client = self._get_client()
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        owned_point = await client.retrieve(
            collection_name=self.collection_name,
            ids=[memory_id],
            with_payload=["user_id", "memory_id"],
            with_vectors=False,
        )
        if not owned_point or (owned_point[0].payload or {}).get("user_id") != user_id:
            return False
        res = await client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="memory_id", match=MatchValue(value=memory_id)),
                ]
            ),
            wait=True,
        )
        return getattr(res, "status", "") == "completed"
