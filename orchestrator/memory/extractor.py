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
        """Fast offline rule-based extraction with bounded, linear string parsing."""
        candidates: list[MemoryCandidate] = []
        # Keep rule-based processing bounded even if a caller bypasses API limits.
        lower = text[:10_000].lower()
        now = datetime.now(UTC)

        def bounded_value(value: str, limit: int = 100) -> str:
            return " ".join(value[:limit].split()).strip(" .,:;")

        # Preference patterns: parse delimiters directly instead of backtracking regexes.
        prefer_at = lower.find("prefer ")
        if prefer_at >= 0:
            value_start = prefer_at + len("prefer ")
            tail = lower[value_start:]
            stop = len(tail)
            for delimiter in (" over ", " instead", ".", "\\n"):
                position = tail.find(delimiter)
                if position >= 0:
                    stop = min(stop, position)
            val = bounded_value(tail[:stop])
            if val:
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

        # Favorite patterns: "favorite <concept> is <value>".
        favorite_at = lower.find("favorite ")
        if favorite_at >= 0:
            concept_start = favorite_at + len("favorite ")
            is_at = lower.find(" is ", concept_start)
            if is_at >= 0:
                concept = bounded_value(lower[concept_start:is_at], 40)
                value_start = is_at + len(" is ")
                tail = lower[value_start:]
                stop = tail.find(".")
                if stop < 0:
                    stop = len(tail)
                val = bounded_value(tail[:stop])
                if concept and val and concept.replace("_", "").isalnum():
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

        # Project patterns: "working on <name>" or "building <name>".
        for marker in ("working on ", "building "):
            project_at = lower.find(marker)
            if project_at >= 0:
                value_start = project_at + len(marker)
                if lower[value_start:].startswith("the "):
                    value_start += len("the ")
                raw = lower[value_start:].split(maxsplit=1)[0] if lower[value_start:].split() else ""
                project = bounded_value(raw, 100).upper()
                if project and all(char.isalnum() or char in "-_" for char in project):
                    candidates.append(
                        MemoryCandidate(
                            entity_type=MemoryEntityType.PROJECT,
                            subject="User",
                            predicate="WORKS_ON",
                            object=project,
                            confidence=0.98,
                            source_turn_id=turn_id,
                            timestamp=now,
                            operation=MemoryOperation.CREATE,
                        )
                    )
                break

        # Forget patterns: "forget <target>" / "forget my <target>".
        forget_at = lower.find("forget ")
        if forget_at >= 0:
            value_start = forget_at + len("forget ")
            if lower[value_start:].startswith("my "):
                value_start += len("my ")
            tail = lower[value_start:]
            stop = tail.find(".")
            if stop < 0:
                stop = len(tail)
            target = bounded_value(tail[:stop])
            if target:
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
