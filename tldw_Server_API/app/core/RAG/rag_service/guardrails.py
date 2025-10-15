"""
Lightweight generation guardrails for the unified RAG pipeline.

Features:
- Instruction-injection filtering: detect suspicious patterns and down-weight docs
- Numeric fidelity check: extract numbers from the answer and verify presence in sources
- Hard-citation mapping: map sentences/claims to supporting spans (doc_id, offsets)

These utilities are intentionally heuristic and dependency-light so they can
run in constrained environments and unit tests without network access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Set, Optional

try:
    # Prefer the RAG Document type for consistency
    from .types import Document
except Exception:  # pragma: no cover - fallback for tests
    from dataclasses import dataclass as _dc

    @_dc
    class Document:  # type: ignore
        id: str
        content: str
        metadata: Dict[str, Any]
        score: float = 0.0


# -------------------- Instruction-injection filtering --------------------

_INJECTION_PATTERNS = [
    r"ignore (all|previous|above) (instructions|prompts)",
    r"disregard (the|previous) (rules|instructions)",
    r"forget (the|previous) (instructions|context)",
    r"do not follow (the|any) instructions",
    r"override (system|developer) (message|prompt)",
    r"(system|developer) prompt",
    r"jailbreak|do_anything|DAN|sudo|root access",
    r"you must (comply|answer) regardless",
    r"BEGIN (PROMPT )?INJECTION|END (PROMPT )?INJECTION",
]
_INJECTION_REGEX = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def detect_injection_score(text: str) -> float:
    """Return a risk score in [0,1] based on pattern matches.

    Heuristic: score = min(1.0, matches / 3).
    """
    if not isinstance(text, str) or not text:
        return 0.0
    matches = _INJECTION_REGEX.findall(text)
    if not matches:
        return 0.0
    return min(1.0, len(matches) / 3.0)


def downweight_injection_docs(docs: List[Document], strength: float = 0.5) -> Dict[str, Any]:
    """Down-weight suspicious documents in-place and return summary stats.

    - strength in (0,1]: multiplicative factor when risk>0 (default 0.5)
    - Annotates doc.metadata['injection_risk'] and 'downweighted_due_to_injection'
    """
    affected = 0
    total = 0
    for d in docs or []:
        total += 1
        try:
            risk = detect_injection_score(getattr(d, "content", ""))
            if risk > 0:
                # annotate metadata
                md = getattr(d, "metadata", None) or {}
                md["injection_risk"] = float(risk)
                md["downweighted_due_to_injection"] = True
                d.metadata = md
                # downweight
                try:
                    s = float(getattr(d, "score", 0.0) or 0.0)
                except Exception:
                    s = 0.0
                d.score = s * max(0.05, min(1.0, float(strength)))
                affected += 1
        except Exception:
            continue
    return {"total": total, "affected": affected}


# -------------------- Numeric fidelity check --------------------

_NUMERIC_RE = re.compile(r"\b(\d{1,3}(?:[\,\._]\d{3})*|\d+)(?:\s*(%|k|m|b))?\b", re.IGNORECASE)


def _normalize_number_token(tok: str) -> str:
    t = (tok or "").strip().lower()
    if not t:
        return t
    # keep unit suffix; normalize separators
    unit = ""
    if t.endswith(("%", "k", "m", "b")):
        unit = t[-1]
        t = t[:-1]
    t = t.replace(",", "").replace("_", "").replace(".", "")
    return t + unit


def _extract_numeric_tokens(text: str) -> Set[str]:
    toks = [m.group(0) for m in _NUMERIC_RE.finditer(text or "")]
    return { _normalize_number_token(t) for t in toks if t }


@dataclass
class NumericFidelityResult:
    present: Set[str]
    missing: Set[str]
    union_source_numbers: Set[str]


def check_numeric_fidelity(answer: str, docs: List[Document]) -> NumericFidelityResult:
    """Check whether numeric tokens in the answer appear in sources.

    This is a best-effort heuristic: we consider presence if a normalized
    token (including unit suffix) appears in any source document.
    """
    answer_nums = _extract_numeric_tokens(answer or "")
    union: Set[str] = set()
    for d in docs or []:
        union |= _extract_numeric_tokens(getattr(d, "content", ""))
    present = {n for n in answer_nums if n in union}
    missing = answer_nums - present
    return NumericFidelityResult(present=present, missing=missing, union_source_numbers=union)


# -------------------- Hard citation mapping --------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.!?])\s+")


def _find_offsets(doc_text: str, target: str) -> Tuple[int, int]:
    """Best-effort offsets of target within doc_text.

    Strategy:
    1) exact match
    2) longest 64-char window inside target
    3) fallback (0, min(len(doc_text), len(target)))
    """
    full = doc_text or ""
    tgt = (target or "").strip()
    if not full or not tgt:
        return (0, 0)
    i = full.find(tgt)
    if i >= 0:
        return (i, i + len(tgt))
    if len(tgt) >= 48:
        k = min(64, len(tgt))
        mid = max(0, (len(tgt) - k) // 2)
        window = tgt[mid : mid + k]
        j = full.find(window)
        if j >= 0:
            return (j, j + len(window))
    return (0, min(len(full), len(tgt)))


def build_hard_citations(
    answer: str,
    docs: List[Document],
    claims_payload: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return a mapping suitable for response metadata under 'hard_citations'.

    If claims_payload is provided (from ClaimsEngine), use its citations (doc_id, start, end).
    Otherwise, heuristically map sentences to best matching spans by substring search.
    """
    out: Dict[str, Any] = {"sentences": [], "coverage": 0.0, "total": 0, "supported": 0}
    if not isinstance(answer, str) or not answer.strip():
        return out

    # If claims payload exists, prefer it
    if isinstance(claims_payload, list) and claims_payload:
        total = 0
        supported = 0
        for c in claims_payload:
            text = (c or {}).get("text")
            cits = (c or {}).get("citations") or []
            if isinstance(text, str) and len(text.strip()) >= 6:
                total += 1
                entry = {"text": text, "citations": []}
                for cit in cits:
                    try:
                        entry["citations"].append({
                            "doc_id": str(cit.get("doc_id")),
                            "start": int(cit.get("start", 0)),
                            "end": int(cit.get("end", 0)),
                        })
                    except Exception:
                        continue
                if entry["citations"]:
                    supported += 1
                out["sentences"].append(entry)
        out["total"] = total
        out["supported"] = supported
        out["coverage"] = (supported / total) if total else 0.0
        return out

    # Heuristic fallback: sentence split and substring match
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(answer.strip()) if s.strip()]
    total = 0
    supported = 0
    for s in sentences:
        if len(s) < 6:
            continue
        total += 1
        entry = {"text": s, "citations": []}
        # Search for best offset in top docs
        for d in (docs or [])[:10]:
            try:
                start, end = _find_offsets(getattr(d, "content", ""), s)
                if end > start:
                    entry["citations"].append({
                        "doc_id": getattr(d, "id", ""),
                        "start": int(start),
                        "end": int(end),
                    })
            except Exception:
                continue
        if entry["citations"]:
            supported += 1
        out["sentences"].append(entry)
    out["total"] = total
    out["supported"] = supported
    out["coverage"] = (supported / total) if total else 0.0
    return out

