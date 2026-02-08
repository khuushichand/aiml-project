"""
Follow-up Suggestions Generator.

After generating a RAG response, automatically produce follow-up questions
the user might want to ask next. Inspired by Perplexica's suggestion agent.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional

from loguru import logger


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SUGGESTION_SYSTEM_PROMPT = """\
You are a follow-up question generator. Given a user's original query and \
the assistant's response, generate follow-up questions the user might \
naturally want to ask next.

Rules:
- Generate exactly {num_suggestions} suggestions
- Keep each suggestion short (under 15 words)
- Make suggestions diverse: cover different angles, aspects, or follow-ups
- Suggestions should be self-contained questions (not references like "tell me more")
- Focus on genuinely useful next steps, not trivial rephrasing
- Output valid JSON: a JSON array of strings, nothing else

Example output:
["What are the main advantages of X?", "How does X compare to Y?", "What are common pitfalls when using X?"]"""

_SUGGESTION_USER_PROMPT = """\
Original query: {query}

Response summary:
{response_summary}

{history_context}
Generate {num_suggestions} follow-up question suggestions as a JSON array:"""


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------

_GENERIC_TEMPLATES = [
    "Can you explain {topic} in more detail?",
    "What are the alternatives to {topic}?",
    "What are the pros and cons of {topic}?",
    "How does {topic} compare to other approaches?",
    "What are real-world examples of {topic}?",
    "What are common mistakes when working with {topic}?",
    "What are the latest developments in {topic}?",
    "How do I get started with {topic}?",
]


def _extract_topic(query: str) -> str:
    """Extract a rough topic phrase from the query for heuristic fallbacks."""
    # Remove question-word phrases like "what is", "how does", "can you tell me about"
    cleaned = re.sub(
        r"^(what|how|why|when|where|who|which|can|could|should|does|do)"
        r"(\s+(is|are|was|were|does|do|did|can|could|would|should|you|me|we|about|the))* *",
        "",
        query.lower().strip().rstrip("?"),
        flags=re.IGNORECASE,
    )
    # Take first meaningful chunk (up to 6 words)
    words = cleaned.split()
    return " ".join(words[:6]) if words else query


def _heuristic_suggestions(query: str, num: int = 5) -> list[str]:
    """Generate generic follow-up suggestions without an LLM."""
    topic = _extract_topic(query)
    suggestions = []
    for template in _GENERIC_TEMPLATES[:num]:
        suggestions.append(template.format(topic=topic))
    return suggestions


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

async def generate_suggestions(
    query: str,
    response_text: str,
    chat_history: list[dict[str, str]] | None = None,
    llm_provider: str = "openai",
    llm_model: str | None = None,
    num_suggestions: int = 5,
) -> list[str]:
    """Generate follow-up question suggestions based on query and response.

    Args:
        query: The user's original query.
        response_text: The generated response text.
        chat_history: Optional conversation history for context.
        llm_provider: LLM provider for generation.
        llm_model: Optional model override.
        num_suggestions: Number of suggestions to generate (default 5).

    Returns:
        List of follow-up question strings. Falls back to heuristic
        suggestions if the LLM call fails.
    """
    # Build response summary (truncate if very long)
    response_summary = response_text[:1500] if len(response_text) > 1500 else response_text

    # Build history context
    history_context = ""
    if chat_history:
        recent = chat_history[-4:]  # Last 2 exchanges
        history_lines = []
        for msg in recent:
            role = msg.get("role", "user")
            content = str(msg.get("content", ""))[:200]
            history_lines.append(f"{role}: {content}")
        history_context = "Recent conversation:\n" + "\n".join(history_lines) + "\n"

    system_prompt = _SUGGESTION_SYSTEM_PROMPT.format(num_suggestions=num_suggestions)
    user_prompt = _SUGGESTION_USER_PROMPT.format(
        query=query,
        response_summary=response_summary,
        history_context=history_context,
        num_suggestions=num_suggestions,
    )

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        provider = (llm_provider or "openai").strip().lower()
        model = (llm_model or "").strip() or None

        call_kwargs: dict[str, Any] = {
            "api_provider": provider,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 300,
            "stream": False,
        }
        if model:
            call_kwargs["model"] = model

        raw_response = await asyncio.wait_for(
            perform_chat_api_call_async(**call_kwargs),
            timeout=15.0,
        )

        # Extract text from response
        response_content = ""
        if isinstance(raw_response, str):
            response_content = raw_response
        elif isinstance(raw_response, dict):
            choices = raw_response.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                response_content = msg.get("content", "")
            if not response_content:
                response_content = raw_response.get("content", "") or raw_response.get("text", "")
        elif hasattr(raw_response, "content"):
            response_content = str(raw_response.content)
        else:
            response_content = str(raw_response)

        # Parse JSON array from response
        suggestions = _parse_suggestions(response_content, num_suggestions)
        if suggestions:
            return suggestions[:num_suggestions]

    except Exception as exc:
        logger.debug(f"Suggestion generation LLM call failed: {exc!r}")

    # Fallback to heuristic suggestions
    return _heuristic_suggestions(query, num_suggestions)


def _parse_suggestions(text: str, expected: int) -> list[str]:
    """Parse a JSON array of suggestion strings from LLM output."""
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(s).strip() for s in parsed if isinstance(s, str) and s.strip()]
    except json.JSONDecodeError:
        pass

    # Try finding a JSON array in the text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return [str(s).strip() for s in parsed if isinstance(s, str) and s.strip()]
        except json.JSONDecodeError:
            pass

    # Try line-by-line extraction (numbered list)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    suggestions = []
    for line in lines:
        # Remove numbering like "1. " or "- "
        cleaned = re.sub(r"^(\d+[\.\)]\s*|-\s*|\*\s*)", "", line).strip()
        cleaned = cleaned.strip('"\'')
        if cleaned and "?" in cleaned:
            suggestions.append(cleaned)
    if suggestions:
        return suggestions[:expected]

    return []
