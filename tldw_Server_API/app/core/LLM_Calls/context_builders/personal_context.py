"""
Personal context builder (scaffold)

Given a chat input, returns a compact user profile summary and top-k memories.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PersonalContext:
    profile_summary: str
    memories: List[str]


def build_personal_context(user_id: str, query_text: str, top_k: int = 3) -> Optional[PersonalContext]:
    """Scaffold builder that returns a static summary with no real retrieval."""
    if not user_id:
        return None
    summary = "User has enabled personalization."
    mems = []
    return PersonalContext(profile_summary=summary, memories=mems)
