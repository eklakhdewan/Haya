"""Concurrent Hybrid Retriever executing Vector and Knowledge Graph queries with strict deadlines."""

import asyncio
from typing import Any
from uuid import uuid4

from orchestrator.core.models import MemoryQueryItem
from orchestrator.memory.base import GraphStoreAdapter, VectorStoreAdapter


class HybridRetriever:
    """Executes parallel vector and graph queries and fuses ranking via Reciprocal Rank Fusion (RRF)."""

    def __init__(
        self,
        vector_store: VectorStoreAdapter,
        graph_store: GraphStoreAdapter,
        timeout_seconds: float = 0.1,  # 100ms deadline from SYSTEM_ARCHITECTURE.md
    ) -> None:
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.timeout_seconds = timeout_seconds

    async def retrieve(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        include_graph: bool = True,
    ) -> list[MemoryQueryItem]:
        # 1. Prepare async tasks for parallel execution
        vector_coro = self.vector_store.search(user_id, query, top_k=top_k * 2)

        if include_graph:
            graph_coro = self.graph_store.search_relations(user_id, query, top_k=top_k * 2)
            results = await asyncio.gather(
                asyncio.wait_for(vector_coro, timeout=self.timeout_seconds),
                asyncio.wait_for(graph_coro, timeout=self.timeout_seconds),
                return_exceptions=True,
            )
            vector_res, graph_res = results[0], results[1]
        else:
            try:
                vector_res = await asyncio.wait_for(vector_coro, timeout=self.timeout_seconds)
            except Exception as e:
                vector_res = e
            graph_res = []

        vector_items: list[MemoryQueryItem] = []
        if isinstance(vector_res, list):
            vector_items = vector_res

        graph_items: list[dict[str, Any]] = []
        if isinstance(graph_res, list):
            graph_items = graph_res

        # 2. Reciprocal Rank Fusion (RRF) with constant k=60
        # RRF_score(d) = 1 / (60 + rank)
        rrf_scores: dict[str, float] = {}
        item_map: dict[str, MemoryQueryItem] = {}

        # Rank vector items
        for rank, item in enumerate(vector_items, start=1):
            rrf_scores[item.memory_id] = rrf_scores.get(item.memory_id, 0.0) + (1.0 / (60 + rank))
            item_map[item.memory_id] = item

        # Rank graph items
        for rank, g_item in enumerate(graph_items, start=1):
            mem_id = str(g_item.get("memory_id", str(uuid4())))
            rrf_scores[mem_id] = rrf_scores.get(mem_id, 0.0) + (1.0 / (60 + rank))

            if mem_id not in item_map:
                statement = f"{g_item.get('subject')} {g_item.get('predicate')} {g_item.get('object')}"
                item_map[mem_id] = MemoryQueryItem(
                    memory_id=mem_id,
                    text=statement,
                    score=float(g_item.get("confidence", 0.9)),
                    source_turn_id="graph-retrieval",
                )

        # 3. Sort by combined RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda mid: rrf_scores[mid], reverse=True)

        final_items: list[MemoryQueryItem] = []
        for mid in sorted_ids[:top_k]:
            item = item_map[mid]
            # Normalize RRF score representation for presentation
            item.score = round(rrf_scores[mid], 4)
            final_items.append(item)

        return final_items
