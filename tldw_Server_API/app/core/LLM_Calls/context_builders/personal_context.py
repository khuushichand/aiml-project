"""
Personal context builder (Stage 1 scaffold)

Given a chat input, returns a compact user profile summary and top-k memories.

NOTE: This module is currently dead code - it is NOT wired into any chat endpoint.
The actual chat pipeline does not yet inject personalization context.

TODO(Stage-2): Wire into chat endpoint after memory taxonomy is implemented.
    The chat context builder should inject a brief profile summary (<300 chars)
    and selected memories (<3-5) into the system prompt. Integration point is
    the chat completion handler in the LLM_Calls module.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PersonalContext:
    profile_summary: str
    memories: list[str]


def build_personal_context(user_id: str, query_text: str, top_k: int = 3) -> PersonalContext | None:
    """Scaffold builder that returns a static summary with no real retrieval.

    TODO(Stage-2): Replace with actual DB lookups:
        1. Load user profile from PersonalizationDB
        2. Retrieve top-k relevant memories via semantic search
        3. Format into compact context string
    """
    if not user_id:
        return None
    summary = "User has enabled personalization."
    mems: list[str] = []
    return PersonalContext(profile_summary=summary, memories=mems)
