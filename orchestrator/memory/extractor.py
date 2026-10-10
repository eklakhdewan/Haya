"""Memory Candidate Extractor implementing the Memory Agent contract."""

import re
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from orchestrator.core.models import (
    MemoryCandidate,
    MemoryEntityType,
    MemoryOperation,
)
from orchestrator.providers.base import LLMMessage, LLMProvider

MEMORY_EXTRACT_SYSTEM_PROMPT = """You are the Memory Agent for HINA.
Your job is to extract durable user facts and relationship candidates from conversation turns.

Valid Entity Types:
- Person
- Preference
- Project
- Event
- Organization
- Skill
- Relationship

Valid Operations:
- CREATE: New durable fact discovered
- UPDATE: Modifying an existing fact
- DELETE: User explicitly asking to forget or remove a fact
- IGNORE: Ephemeral small-talk or temporary context

Every candidate must include:
- entity_type
- subject (e.g. "User", "Alice")
- predicate (e.g. "WORKS_ON", "PREFERS", "KNOWS", "LIVES_IN")
- object (e.g. "HINA", "Python", "Bob", "San Francisco")
- confidence (0.0 to 1.0)
- operation (CREATE, UPDATE, DELETE, IGNORE)
"""


class ExtractedCandidatesList(BaseModel):
    candidates: list[MemoryCandidate] = Field(default_factory=list)


class MemoryExtractor:
    """Extracts typed memory candidates from conversation turns."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    def _rule_based_extract(self, text: str, turn_id: str) -> list[MemoryCandidate]:
        """Fast offline rule-based extraction for deterministic test environments."""
        candidates: list[MemoryCandidate] = []
        lower = text.lower()
        now = datetime.now(UTC)

        # Preference patterns
        pref_match = re.search(r"prefer\s+([a-zA-Z0-9\s]+?)(?:\s+over|\s+instead|\.|$)", lower)
        if pref_match:
            val = pref_match.group(1).strip()
            candidates.append(
                MemoryCandidate(
                    entity_type=MemoryEntityType.PREFERENCE,
                    subject="User",
                    predicate="PREFERS",
                    object=val,
                    confidence=0.95,
                    source_turn_id=turn_id,
                    timestamp=now,
                    operation=MemoryOperation.CREATE,
                )
            )

        # Favorite patterns
        fav_match = re.search(r"favorite\s+(\w+)\s+is\s+([a-zA-Z0-9\s]+?)(?:\.|$)", lower)
        if fav_match:
            concept = fav_match.group(1).strip()
            val = fav_match.group(2).strip()
            candidates.append(
                MemoryCandidate(
                    entity_type=MemoryEntityType.PREFERENCE,
                    subject="User",
                    predicate=f"FAVORITE_{concept.upper()}",
                    object=val,
                    confidence=0.96,
                    source_turn_id=turn_id,
                    timestamp=now,
                    operation=MemoryOperation.CREATE,
                )
            )

        # Project patterns
        proj_match = re.search(r"(?:working on|building)\s+(?:the\s+)?([a-zA-Z0-9\-_]+)", lower)
        if proj_match:
            proj = proj_match.group(1).strip().upper()
            candidates.append(
                MemoryCandidate(
                    entity_type=MemoryEntityType.PROJECT,
                    subject="User",
                    predicate="WORKS_ON",
                    object=proj,
                    confidence=0.98,
                    source_turn_id=turn_id,
                    timestamp=now,
                    operation=MemoryOperation.CREATE,
                )
            )

        # Forget patterns
        forget_match = re.search(r"forget\s+(?:my\s+)?([a-zA-Z0-9\s]+?)(?:\.|$)", lower)
        if forget_match:
            target = forget_match.group(1).strip()
            candidates.append(
                MemoryCandidate(
                    entity_type=MemoryEntityType.PREFERENCE,
                    subject="User",
                    predicate="FORGET",
                    object=target,
                    confidence=0.99,
                    source_turn_id=turn_id,
                    timestamp=now,
                    operation=MemoryOperation.DELETE,
                )
            )

        return candidates

    async def extract(
        self,
        transcript: list[dict[str, str]],
        turn_id: str | None = None,
    ) -> list[MemoryCandidate]:
        current_turn_id = turn_id or str(uuid4())
        user_texts = [turn["content"] for turn in transcript if turn.get("role") == "user"]
        combined_text = "\n".join(user_texts)

        # 1. Try rule-based first for fast matching
        candidates = self._rule_based_extract(combined_text, current_turn_id)
        if candidates:
            return candidates

        # 2. Query LLM provider with structured schema
        messages = [
            LLMMessage(role="user", content=f"Transcript turns:\n{combined_text}"),
        ]

        try:
            res = await self.llm_provider.generate_structured(
                messages=messages,
                response_schema=ExtractedCandidatesList,
                system_prompt=MEMORY_EXTRACT_SYSTEM_PROMPT,
                temperature=0.0,
            )
            # Ensure turn_id is attached to every candidate
            for c in res.candidates:
                c.source_turn_id = current_turn_id
            return res.candidates
        except Exception:
            # Fallback to empty candidate list if model structured parsing fails
            return []
