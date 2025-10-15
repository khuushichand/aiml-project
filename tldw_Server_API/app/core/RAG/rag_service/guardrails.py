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
from html.parser import HTMLParser

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

_NUMERIC_RE = re.compile(
    r"\b(\d{1,3}(?:[\,\._]\d{3})*|\d+(?:\.\d+)?)(?:\s*(%|k|m|b))?(?=[^0-9A-Za-z]|$)",
    re.IGNORECASE,
)

# Word multipliers (normalize to k/m/b suffix)
_WORD_MULTIPLIERS = {
    "thousand": "k",
    "thousands": "k",
    "million": "m",
    "millions": "m",
    "billion": "b",
    "billions": "b",
    "percent": "%",
    "percentage": "%",
}

# Currency symbols to strip for normalization
_CURRENCY_PREFIX = set("$€£¥₩₹")


def _normalize_number_token(tok: str) -> str:
    t = (tok or "").strip().lower()
    if not t:
        return t
    # keep unit suffix; normalize separators
    unit = ""
    if t.endswith(("%", "k", "m", "b")):
        unit = t[-1]
        t = t[:-1]
    # Strip leading currency symbols
    while t and t[0] in _CURRENCY_PREFIX:
        t = t[1:]
    t = t.replace(",", "").replace("_", "")
    # do not drop dot here; keep for expansions
    return t + unit


def _extract_numeric_tokens(text: str) -> Set[str]:
    """Extract normalized numeric tokens with basic unit/word handling.

    - Captures digits with optional decimal and suffix (%/k/m/b)
    - Maps word multipliers (million/billion/thousand/percent)
    - Strips currency symbols
    """
    s = text or ""
    toks = [m.group(0) for m in _NUMERIC_RE.finditer(s)]
    # Handle simple word multipliers like "3 million" or "5 percent"
    try:
        word_pairs = re.findall(r"(\d+(?:\.\d+)?)\s+(million|millions|billion|billions|thousand|thousands|percent|percentage)\b", s, re.IGNORECASE)
        for num, word in word_pairs:
            unit = _WORD_MULTIPLIERS.get(word.lower(), "")
            toks.append(f"{num}{unit}")
    except Exception:
        pass
    base: Set[str] = set()
    expanded: Set[str] = set()
    for raw in toks:
        nrm = _normalize_number_token(raw)
        if not nrm:
            continue
        # Drop spurious single-digit tokens without suffix
        if re.fullmatch(r"\d", nrm):
            continue
        base.add(nrm)
        # Add canonical numeric form (strip separators and dot) for matching
        try:
            canon = nrm
            unit = canon[-1] if canon and canon[-1] in {"k", "m", "b", "%"} else ""
            if not unit:  # only for plain numbers
                core = canon.replace(",", "").replace("_", "").replace(".", "")
                if core and core.isdigit():
                    expanded.add(core)
        except Exception:
            pass
        # Add expansion for k/m/b to canonical integer string for matching against raw numbers
        try:
            unit = nrm[-1] if nrm and nrm[-1] in {"k", "m", "b", "%"} else ""
            val_str = nrm[:-1] if unit else nrm
            val_str = val_str.replace(",", "").replace("_", "")
            # Keep decimal for multiplication
            if unit in {"k", "m", "b"}:
                factor = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[unit]
                try:
                    num = float(val_str)
                    canonical = str(int(round(num * factor)))
                    expanded.add(canonical)
                except Exception:
                    pass
        except Exception:
            pass
    return base | expanded


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
    # A token is considered present if itself or its expanded numeric alias exists in sources
    def _exp_single(n: str) -> Set[str]:
        n = (n or "").strip()
        out: Set[str] = {n}
        try:
            unit = n[-1] if n and n[-1].lower() in {"k", "m", "b", "%"} else ""
            if unit in {"k", "m", "b"}:
                core = n[:-1]
                core = core.replace(",", "").replace("_", "")
                num = float(core)
                factor = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[unit]
                out.add(str(int(round(num * factor))))
        except Exception:
            pass
        return out
    present = set()
    for n in answer_nums:
        if n in union:
            present.add(n)
            continue
        aliases = _exp_single(n)
        if aliases & union:
            present.add(n)
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


# -------------------- Quote-level citations --------------------

_QUOTE_RE = re.compile(r"\"([^\"]{4,})\"|'([^']{4,})'")


def _verify_offsets(doc_text: str, start: int, end: int, target: str) -> bool:
    try:
        segment = (doc_text or "")[max(0, start):max(0, end)]
        # Relax whitespace for verification
        def _norm(x: str) -> str:
            return re.sub(r"\s+", " ", (x or "").strip())
        return _norm(segment) in {_norm(target), _norm(target[: len(segment)])}
    except Exception:
        return False


def build_quote_citations(answer: str, docs: List[Document]) -> Dict[str, Any]:
    """Extract quoted spans from answer and map to source offsets.

    Returns a structure with entries: {text, citations:[{doc_id,start,end,verified}]} and coverage ratio.
    """
    out: Dict[str, Any] = {"quotes": [], "total": 0, "supported": 0, "coverage": 0.0}
    if not isinstance(answer, str) or not answer.strip():
        return out
    matches = _QUOTE_RE.findall(answer)
    quotes: List[str] = []
    for a, b in matches:
        q = a or b
        if q and len(q.strip()) >= 4:
            quotes.append(q.strip())
    out["total"] = len(quotes)
    supported = 0
    for q in quotes:
        entry = {"text": q, "citations": []}
        for d in (docs or [])[:10]:
            try:
                start, end = _find_offsets(getattr(d, "content", ""), q)
                verified = _verify_offsets(getattr(d, "content", ""), start, end, q)
                if end > start:
                    entry["citations"].append({
                        "doc_id": getattr(d, "id", ""),
                        "start": int(start),
                        "end": int(end),
                        "verified": bool(verified),
                    })
            except Exception:
                continue
        if entry["citations"]:
            supported += 1
        out["quotes"].append(entry)
    out["supported"] = supported
    out["coverage"] = (supported / out["total"]) if out["total"] else 0.0
    return out


# -------------------- Content policy filters (PII/PHI) --------------------

_PII_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",               # SSN-like
    r"\b\d{16}\b",                          # 16-digit (credit card-ish)
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",  # email
    r"\b\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}\b",  # phone
]
_PHI_PATTERNS = [
    r"\b(diagnos(e|is|ed)|prescription|medical record|patient|hipaa)\b",
]
_PII_RE = re.compile("|".join(_PII_PATTERNS), re.IGNORECASE)
_PHI_RE = re.compile("|".join(_PHI_PATTERNS), re.IGNORECASE)


def detect_pii_phi(text: str) -> Dict[str, int]:
    if not isinstance(text, str) or not text:
        return {"pii": 0, "phi": 0}
    pii = len(_PII_RE.findall(text))
    phi = len(_PHI_RE.findall(text))
    return {"pii": int(pii), "phi": int(phi)}


def apply_content_policy(
    docs: List[Document],
    policy_types: List[str],
    mode: str = "redact",
) -> Dict[str, int]:
    """Apply a lightweight content policy to documents.

    - policy_types: subset of ["pii", "phi"]
    - mode: "redact" (replace matches), "drop" (remove doc), "annotate" (metadata only)
    """
    allowed = {t.strip().lower() for t in (policy_types or [])}
    redact_token = "[REDACTED]"
    dropped = 0
    affected = 0
    kept: List[Document] = []
    for d in (docs or []):
        txt = getattr(d, "content", "") or ""
        flags = detect_pii_phi(txt)
        triggered = (flags["pii"] > 0 and "pii" in allowed) or (flags["phi"] > 0 and "phi" in allowed)
        if not triggered:
            kept.append(d)
            continue
        affected += 1
        md = getattr(d, "metadata", None) or {}
        md["policy_flags"] = flags
        d.metadata = md
        if mode == "drop":
            dropped += 1
            continue
        if mode == "redact":
            # Redact PII/PHI hits
            t = txt
            if "pii" in allowed:
                t = _PII_RE.sub(redact_token, t)
            if "phi" in allowed:
                t = _PHI_RE.sub(redact_token, t)
            d.content = t
        # annotate mode leaves content unchanged
        kept.append(d)

    docs[:] = kept
    return {"affected": affected, "dropped": dropped}


# -------------------- HTML sanitizer (allow-list) --------------------

class _AllowlistHTMLStripper(HTMLParser):
    def __init__(self, allowed_tags: Set[str], allowed_attrs: Set[str]):
        super().__init__()
        self.allowed_tags = allowed_tags
        self.allowed_attrs = allowed_attrs
        self.output: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.allowed_tags:
            safe_attrs = " ".join(
                f"{k}='{v}'" for k, v in attrs if k in self.allowed_attrs
            )
            if safe_attrs:
                self.output.append(f"<{tag} {safe_attrs}>")
            else:
                self.output.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in self.allowed_tags:
            self.output.append(f"</{tag}>")

    def handle_data(self, data):
        self.output.append(data)

    def get_data(self) -> str:
        return "".join(self.output)


def sanitize_html_allowlist(text: str, allowed_tags: Optional[List[str]] = None, allowed_attrs: Optional[List[str]] = None) -> str:
    if not isinstance(text, str) or not text:
        return text or ""
    tags = set((allowed_tags or ["p", "b", "i", "strong", "em", "code", "pre", "ul", "ol", "li", "br"]))
    attrs = set((allowed_attrs or ["href", "title"]))
    stripper = _AllowlistHTMLStripper(tags, attrs)
    try:
        stripper.feed(text)
        return stripper.get_data()
    except Exception:
        # On parser failure, return plain text fallback
        return re.sub(r"<[^>]+>", "", text)


# -------------------- OCR confidence gating --------------------

def gate_docs_by_ocr_confidence(docs: List[Document], threshold: float = 0.0) -> int:
    """Drop documents whose metadata.ocr_confidence falls below threshold.

    Returns number of dropped docs.
    """
    kept: List[Document] = []
    dropped = 0
    for d in (docs or []):
        md = getattr(d, "metadata", None) or {}
        conf = None
        try:
            conf = float(md.get("ocr_confidence") or md.get("ocr", {}).get("confidence"))
        except Exception:
            conf = None
        if conf is not None and conf < float(threshold):
            dropped += 1
            continue
        kept.append(d)
    docs[:] = kept
    return dropped
