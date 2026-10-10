"""Neo4j Knowledge Graph Adapter using parameterized Cypher queries."""

from typing import Any
from orchestrator.core.models import MemoryRecord
from orchestrator.memory.base import GraphStoreAdapter


class Neo4jGraphAdapter(GraphStoreAdapter):
    """Neo4j knowledge graph adapter with parameterized queries to prevent Cypher injection."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "change-me",
    ) -> None:
        self.uri = uri
        self.username = username
        self.password = password
        self._driver: Any | None = None

    def _get_driver(self) -> Any:
        if self._driver is None:
            try:
                from neo4j import AsyncGraphDatabase
                self._driver = AsyncGraphDatabase.driver(self.uri, auth=(self.username, self.password))
            except Exception as e:
                # Driver creation can fail if invalid connection
                raise ConnectionError(f"Could not initialize Neo4j driver: {e}")
        return self._driver

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def add_entity_relation(self, user_id: str, record: MemoryRecord) -> None:
        driver = self._get_driver()

        # Parameterized Cypher query
        query = """
        MERGE (u:User {id: $user_id})
        MERGE (m:Memory {id: $memory_id})
        SET m.subject = $subject,
            m.predicate = $predicate,
            m.object = $object,
            m.confidence = $confidence,
            m.source_turn_id = $source_turn_id,
            m.status = 'active'
        MERGE (u)-[:HAS_MEMORY]->(m)
        """
        params = {
            "user_id": user_id,
            "memory_id": record.id,
            "subject": record.subject,
            "predicate": record.predicate,
            "object": record.object,
            "confidence": record.confidence,
            "source_turn_id": record.source_turn_id,
        }

        # Dynamic relation based on predicate
        predicate = record.predicate.upper()
        if predicate in ["WORKS_ON", "PROJECT"]:
            query += """
            MERGE (p:Project {name: $object})
            MERGE (u)-[:WORKS_ON]->(p)
            """
        elif predicate in ["LIKES", "PREFERS"]:
            query += """
            MERGE (c:Concept {name: $object})
            MERGE (u)-[:LIKES]->(c)
            """
        elif predicate in ["KNOWS"]:
            query += """
            MERGE (pe:Person {name: $object})
            MERGE (u)-[:KNOWS]->(pe)
            """

        async with driver.session() as session:
            await session.run(query, params)

    async def search_relations(self, user_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        driver = self._get_driver()

        # Parameterized search over Memory nodes connected to User
        cypher = """
        MATCH (u:User {id: $user_id})-[:HAS_MEMORY]->(m:Memory {status: 'active'})
        WHERE m.subject CONTAINS $term OR m.object CONTAINS $term OR m.predicate CONTAINS $term
        RETURN m.id AS memory_id, m.subject AS subject, m.predicate AS predicate, m.object AS object, m.confidence AS confidence
        LIMIT $limit
        """
        results: list[dict[str, Any]] = []
        async with driver.session() as session:
            cursor = await session.run(cypher, {"user_id": user_id, "term": query, "limit": top_k})
            records = await cursor.data()
            for r in records:
                results.append(r)
        return results

    async def delete_entity(self, memory_id: str) -> bool:
        driver = self._get_driver()
        cypher = """
        MATCH (m:Memory {id: $memory_id})
        SET m.status = 'deleted'
        DETACH DELETE m
        RETURN count(m) AS deleted_count
        """
        async with driver.session() as session:
            cursor = await session.run(cypher, {"memory_id": memory_id})
            data = await cursor.single()
            if data and data["deleted_count"] > 0:
                return True
        return False
