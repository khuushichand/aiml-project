"""
hyde.py - HYDE/doc2query helper utilities

Provides a minimal question generator and normalization/hash helpers for
Option A HYDE integration (generated inside the embedding worker).

Generation is best-effort and returns an empty list on failure or when
provider/model are not configured. The embedding worker should treat HYDE
as optional and never block baseline embeddings.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import List, Optional

from loguru import logger

try:
    # LLM analyze entrypoint used elsewhere in the project
    from tldw_Server_API.app.core.Evaluations.rag_evaluator import analyze as llm_analyze  # type: ignore
except Exception:  # pragma: no cover - optional import for environments without full deps
    llm_analyze = None  # type: ignore


_DEFAULT_PROMPT = (
    "Generate {n} concise, user-style questions that a researcher might ask "
    "and that can be answered by the following text. Avoid duplicates. "
    "Keep each question 6-20 words."
)


def normalize_question(text: str) -> str:
    """Normalize question text for hashing/dedup.

    Steps: NFC normalize, lowercase, collapse whitespace, strip trailing
    punctuation/closers like .,;:!? ) ] ' " and dashes.
    """
    try:
        if not isinstance(text, str):
            text = str(text or "")
        s = unicodedata.normalize("NFC", text).strip().lower()
        # Collapse whitespace
        s = re.sub(r"\s+", " ", s)
        # Strip trailing punctuation and closers (em/en dashes via \u2013/\u2014)
        s = re.sub(r"""[\s\-\u2013\u2014]*[.;:!?\)\]\}"']*$""", "", s)
        return s
    except Exception:
        return (text or "").strip().lower()


def question_hash(text: str) -> str:
    """Return SHA256 hex digest of normalized question text."""
    norm = normalize_question(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _build_prompt(n: int, language: Optional[str]) -> str:
    base = _DEFAULT_PROMPT.format(n=max(1, int(n)))
    if language and language not in ("auto", ""):
        return base + f" Generate the questions in {language}."
    return base


def _split_lines(output: str) -> List[str]:
    # Split into non-empty lines; strip bullets/numbers
    lines: List[str] = []
    for raw in (output or "").splitlines():
        t = raw.strip()
        if not t:
            continue
        t = re.sub(r"^[\-\*\u2022\d\.\)\s]+", "", t)
        if t:
            lines.append(t)
    return lines


def _dedupe_and_trim(items: List[str], n: int) -> List[str]:
    seen = set()
    out: List[str] = []
    for q in items:
        norm = normalize_question(q)
        if not norm:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        out.append(q.strip())
        if len(out) >= n:
            break
    return out


def generate_questions(
    text: str,
    n: int,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 96,
    language: Optional[str] = None,
    prompt_version: Optional[int] = None,
) -> List[str]:
    """Generate up to N HYDE questions for a chunk of text.

    Returns empty list on any error or when provider/model are not set.
    """
    try:
        if not provider or not model:
            return []
        if llm_analyze is None:
            return []
        prompt = _build_prompt(n, language)
        # system_message can be light; keep instructions in custom prompt
        system_message = "You create short, useful research questions."
        out = llm_analyze(
            provider,
            input_data=text,
            custom_prompt_arg=prompt,
            api_key=None,
            system_message=system_message,
            temp=temperature,
            streaming=False,
            recursive_summarization=False,
            chunked_summarization=False,
            chunk_options=None,
            model_override=model,
        )
        if not isinstance(out, str):
            try:
                out = str(out or "")
            except Exception:
                return []
        lines = _split_lines(out)
        # Heuristic length bounds: 6-20 words, <= 160 chars (allow headroom)
        bounded = [
            q for q in lines
            if 3 <= len(q.strip().split()) <= 24 and len(q.strip()) <= 160
        ]
        return _dedupe_and_trim(bounded or lines, n)
    except Exception as e:
        logger.debug(f"HYDE generate_questions failed (provider={provider}, model={model}): {e}")
        return []
