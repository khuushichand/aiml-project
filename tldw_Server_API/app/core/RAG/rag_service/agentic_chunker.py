"""
Agentic chunking orchestrator for query-time, LLM-guided evidence assembly.

Design goals:
- Perform coarse retrieval to get top-K candidate documents/sections.
- Use lightweight, deterministic heuristics to assemble a query-specific
  synthetic context ("ephemeral chunk") with provenance spans.
- Avoid introducing latency or external dependencies by default; upstream
  callers can pass generation knobs to produce an answer from the assembled
  chunk using existing generation utilities.

This module deliberately ships a conservative baseline that is test-friendly:
- It does not call external LLMs to plan tool use (that can be added later).
- It extracts spans by keyword proximity and returns a compact synthetic chunk
  with simple provenance metadata. This keeps behavior deterministic in CI.

Integration entrypoint: `agentic_rag_pipeline(...)` which mirrors a subset of
`unified_rag_pipeline` parameters and returns a `UnifiedSearchResult`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import re
import time
import hashlib

from loguru import logger

from .types import Document, DataSource
from .unified_pipeline import UnifiedSearchResult
from .database_retrievers import MultiDatabaseRetriever, RetrievalConfig


@dataclass
class AgenticConfig:
    """Configuration for agentic chunking.

    The defaults aim to be conservative and CI-friendly. Callers can tune
    budgets without changing global behavior.
    """

    top_k_docs: int = 3
    window_chars: int = 1200
    max_tokens_read: int = 6000
    max_tool_calls: int = 8
    extractive_only: bool = True
    quote_spans: bool = True
    # Tool loop (ReAct-like)
    enable_tools: bool = False
    use_llm_planner: bool = False
    time_budget_sec: Optional[float] = None
    # Caching
    cache_ttl_sec: int = 600
    debug_trace: bool = False


# Simple in-process ephemeral cache
_EPHEMERAL_CACHE: Dict[str, Dict[str, Any]] = {}


def _now() -> float:
    return time.time()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    entry = _EPHEMERAL_CACHE.get(key)
    if not entry:
        return None
    if entry.get("expires_at", 0) < _now():
        try:
            _EPHEMERAL_CACHE.pop(key, None)
        except Exception:
            pass
        return None
    return entry.get("value")


def _cache_set(key: str, value: Dict[str, Any], ttl: int) -> None:
    try:
        _EPHEMERAL_CACHE[key] = {"value": value, "expires_at": _now() + max(1, int(ttl))}
    except Exception:
        pass


def _token_estimate(text: str) -> int:
    # Roughly 4 chars/token heuristic; safe for budgets
    return max(1, int(len(text) / 4))


def _keyword_terms(query: str) -> List[str]:
    """Extract lightweight keyword set from query (alphanum >= 3 chars)."""
    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9_-]{3,}", query or "")]
    # Deduplicate while preserving order
    seen = set()
    out: List[str] = []
    for t in terms:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out[:12]


def _find_spans(text: str, terms: List[str], max_spans: int = 6, window: int = 300) -> List[Tuple[int, int]]:
    """Find up to `max_spans` promising spans around keyword hits.

    This is a deterministic, cheap heuristic: locate case-insensitive matches
    of any query term, then expand a window around the match. Merge small
    overlaps to keep the chunk compact.
    """
    if not text:
        return []
    lowered = text.lower()
    hits: List[Tuple[int, int]] = []
    for term in terms:
        start = 0
        while True:
            idx = lowered.find(term, start)
            if idx == -1:
                break
            left = max(0, idx - window)
            right = min(len(text), idx + len(term) + window)
            hits.append((left, right))
            start = idx + len(term)
            if len(hits) >= max_spans * 3:  # cap raw hits before merging
                break
        if len(hits) >= max_spans * 3:
            break

    if not hits:
        # fallback: take beginning of the doc
        return [(0, min(len(text), window * 2))]

    # Merge overlapping/adjacent ranges
    hits.sort(key=lambda x: x[0])
    merged: List[Tuple[int, int]] = []
    for s, e in hits:
        if not merged or s > merged[-1][1] + 20:
            merged.append((s, e))
        else:
            prev_s, prev_e = merged[-1]
            merged[-1] = (prev_s, max(prev_e, e))

    # Keep top spans (by length proxy) up to max_spans
    merged.sort(key=lambda x: (x[1] - x[0]), reverse=True)
    return sorted(merged[:max_spans], key=lambda x: x[0])


def _assemble_ephemeral_chunk(
    docs: List[Document],
    query: str,
    cfg: AgenticConfig,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Build a synthetic chunk and provenance from top documents.

    Returns:
        (chunk_text, provenance) where provenance is list of dicts with
        doc_id, title, start, end, snippet.
    """
    terms = _keyword_terms(query)
    remaining_tokens = int(cfg.max_tokens_read)
    parts: List[str] = []
    provenance: List[Dict[str, Any]] = []

    for d in docs[: max(1, cfg.top_k_docs)]:
        if remaining_tokens <= 0:
            break
        text = d.content or ""
        spans = _find_spans(text, terms, max_spans=4, window=int(cfg.window_chars / 4))
        for (s, e) in spans:
            snippet = text[s:e]
            toks = _token_estimate(snippet)
            if toks > remaining_tokens:
                # Trim to budget (approximate by chars)
                allowed_chars = max(50, remaining_tokens * 4)
                snippet = snippet[:allowed_chars]
                toks = _token_estimate(snippet)
            if toks <= 0:
                continue
            # Add simple guard for extractive-only: we only quote snippets
            parts.append(snippet.strip())
            provenance.append({
                "document_id": d.id,
                "title": (d.metadata or {}).get("title"),
                "start": int(s),
                "end": int(s + len(snippet)),
                "snippet_preview": snippet[:120]
            })
            remaining_tokens -= toks
            if remaining_tokens <= 0:
                break

    # Minimal glue with delimiters
    glue = "\n\n---\n\n"
    chunk_text = glue.join(parts) if parts else (docs[0].content[: cfg.window_chars] if docs else "")
    return chunk_text, provenance


class AgenticToolbox:
    """Deterministic tool primitives used by the tool loop.

    These avoid external dependencies and work over the provided Document objects.
    """

    def __init__(self, docs: List[Document]):
        self.docs = docs

    def search_within(self, doc: Document, query: str, max_hits: int = 8, window: int = 300) -> List[Tuple[int, int]]:
        terms = _keyword_terms(query)
        return _find_spans(doc.content or "", terms, max_spans=max_hits, window=window)

    def open_section(self, doc: Document, heading: str) -> Optional[Tuple[int, int]]:
        """Find a section by heuristic heading match; returns [start,end) char range."""
        text = doc.content or ""
        if not text:
            return None
        # Split by lines and detect simple headings (#, ##, numbered)
        lines = text.splitlines()
        offsets = []
        pos = 0
        for ln in lines:
            offsets.append(pos)
            pos += len(ln) + 1
        candidates = []
        for i, ln in enumerate(lines):
            if re.match(r"^\s*(#+|\d+[\)\.]\s+)\s+", ln) or len(ln) < 80:
                if heading.lower() in ln.lower():
                    candidates.append(i)
        if not candidates:
            return None
        idx = candidates[0]
        start = offsets[idx]
        # End at next heading or end of text
        j = idx + 1
        while j < len(lines):
            if re.match(r"^\s*(#+|\d+[\)\.]\s+)\s+", lines[j]):
                break
            j += 1
        end = len(text) if j >= len(lines) else offsets[j]
        return (start, end)

    def expand_window(self, doc: Document, start: int, end: int, delta: int = 200) -> Tuple[int, int]:
        text = doc.content or ""
        left = max(0, start - delta)
        right = min(len(text), end + delta)
        return (left, right)

    def quote_spans(self, doc: Document, spans: List[Tuple[int, int]]) -> List[str]:
        text = doc.content or ""
        return [text[s:e] for s, e in spans]


async def _tool_loop(docs: List[Document], query: str, cfg: AgenticConfig) -> Tuple[str, List[Dict[str, Any]]]:
    """Simple bounded tool loop. If cfg.use_llm_planner is True, we try a light
    planning prompt; otherwise use a deterministic heuristic policy. Network
    failures automatically fall back to heuristics.
    """
    tb = AgenticToolbox(docs)
    remaining_tokens = int(cfg.max_tokens_read)
    max_steps = max(1, int(cfg.max_tool_calls))
    deadline = (_now() + cfg.time_budget_sec) if cfg.time_budget_sec else None

    assembled: List[Tuple[Document, int, int]] = []
    steps = 0

    def time_left() -> bool:
        return (deadline is None) or (_now() < deadline)

    # Optional: LLM planning for headings/keywords (best-effort)
    planned_headings: List[str] = []
    planned_terms: List[str] = []
    if cfg.use_llm_planner:
        try:
            from .generation import AnswerGenerator
            planner = AnswerGenerator(model=None)
            prompt = (
                "You are planning a bounded read to answer a query from long documents. "
                "Suggest up to 5 short headings to jump to and up to 8 keywords to search for. "
                "Respond as JSON with keys 'headings' and 'keywords'.\n\n"
                f"Query: {query}"
            )
            gen = await planner.generate(query=query, context="", prompt_template="default", max_tokens=200)
            # Handle sync result returned by adapter
            if isinstance(gen, dict):
                text = gen.get("answer", "")
            else:
                text = str(gen)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                import json as _json
                obj = _json.loads(m.group(0))
                if isinstance(obj.get("headings"), list):
                    planned_headings = [str(x)[:80] for x in obj["headings"]][:5]
                if isinstance(obj.get("keywords"), list):
                    planned_terms = [str(x)[:40] for x in obj["keywords"]][:8]
        except Exception:
            planned_headings = []
            planned_terms = []

    # Heuristic policy: scan top docs, pick best spans by search_within, expand a bit
    for d in docs[: max(1, cfg.top_k_docs)]:
        if steps >= max_steps or not time_left():
            break
        # Use planned terms if available
        local_query = " ".join([query] + planned_terms) if planned_terms else query
        hits = tb.search_within(d, local_query, max_hits=4, window=int(cfg.window_chars / 4))
        # Try planned headings as targeted opens
        if not hits and planned_headings:
            for h in planned_headings[:3]:
                sec = tb.open_section(d, h)
                if sec:
                    hits = [sec]
                    break
        for (s, e) in hits:
            if steps >= max_steps or not time_left():
                break
            s2, e2 = tb.expand_window(d, s, e, delta=100)
            assembled.append((d, s2, e2))
            steps += 1
            # Budget check (coarse): each assembled span approximates to tokens
            remaining_tokens -= _token_estimate((d.content or "")[s2:e2])
            if remaining_tokens <= 0:
                break

    # Fallback if nothing assembled
    if not assembled and docs:
        d0 = docs[0]
        assembled = [(d0, 0, min(len(d0.content or ''), cfg.window_chars))]

    # Compose chunk and provenance
    parts: List[str] = []
    provenance: List[Dict[str, Any]] = []
    for d, s, e in assembled:
        snippet = (d.content or "")[s:e]
        parts.append(snippet.strip())
        provenance.append({
            "document_id": d.id,
            "title": (d.metadata or {}).get("title"),
            "start": int(s),
            "end": int(e),
            "snippet_preview": snippet[:120]
        })

    glue = "\n\n---\n\n"
    return glue.join(parts), provenance


async def agentic_rag_pipeline(
    *,
    query: str,
    # data sources
    sources: Optional[List[str]] = None,
    media_db: Any = None,
    chacha_db: Any = None,
    media_db_path: Optional[str] = None,
    notes_db_path: Optional[str] = None,
    character_db_path: Optional[str] = None,
    # retrieval config
    search_mode: str = "hybrid",
    fts_level: str = "media",
    hybrid_alpha: float = 0.7,
    top_k: int = 10,
    min_score: float = 0.0,
    index_namespace: Optional[str] = None,
    # agentic config
    agentic: Optional[AgenticConfig] = None,
    # generation config passthrough
    enable_generation: bool = True,
    generation_model: Optional[str] = None,
    generation_prompt: Optional[str] = None,
    max_generation_tokens: int = 500,
    # misc
    enable_citations: bool = False,
    include_chunk_citations: bool = True,
    debug_mode: bool = False,
) -> UnifiedSearchResult:
    """Agentic RAG: coarse retrieve, assemble ephemeral chunk, optional answer.

    This function is intentionally lightweight and safe to call in tests.
    """
    t0 = time.time()
    cfg = agentic or AgenticConfig()

    # 1) Build retriever
    db_paths: Dict[str, str] = {}
    if media_db_path:
        db_paths["media_db"] = media_db_path
    if notes_db_path:
        db_paths["notes_db"] = notes_db_path
    if character_db_path:
        db_paths["character_cards_db"] = character_db_path

    retriever = MultiDatabaseRetriever(
        db_paths,
        user_id="rag_agentic",
        media_db=media_db,
        chacha_db=chacha_db,
    )

    # 2) Coarse retrieval (prefer media-level)
    config = RetrievalConfig(
        max_results=max(1, int(top_k or 10)),
        min_score=float(min_score or 0.0),
        use_fts=(search_mode in ("fts", "hybrid")),
        use_vector=(search_mode in ("vector", "hybrid")),
        include_metadata=True,
        fts_level=(fts_level or "media"),
    )

    # Map source strings to DataSource for retriever
    src_map = {
        "media_db": DataSource.MEDIA_DB,
        "notes": DataSource.NOTES,
        "characters": DataSource.CHARACTER_CARDS,
        "chats": DataSource.CHARACTER_CARDS,
    }
    wanted_sources = [src_map.get(s, DataSource.MEDIA_DB) for s in (sources or ["media_db"]) ]

    try:
        docs = await retriever.retrieve(query=query, sources=wanted_sources, config=config, index_namespace=index_namespace)
    except Exception as e:
        logger.warning(f"Agentic coarse retrieval failed: {e}")
        docs = []

    # 3) Cache key
    def _hashable_doc(d: Document) -> str:
        md = d.metadata or {}
        created = str(md.get("created_at") or md.get("ingestion_date") or "")
        length = str(len(d.content or ""))
        return f"{d.id}|{created}|{length}"

    key_raw = "|".join([query.strip().lower()] + sorted(_hashable_doc(d) for d in docs[: cfg.top_k_docs]))
    cache_key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
    cached = _cache_get(cache_key)
    if cached:
        chunk_text = cached.get("chunk_text", "")
        prov = cached.get("provenance", [])
        cached_hit = True
    else:
        cached_hit = False
        # 4) Assemble ephemeral chunk (either tools or heuristics)
        if cfg.enable_tools:
            chunk_text, prov = await _tool_loop(docs, query, cfg)
        else:
            chunk_text, prov = _assemble_ephemeral_chunk(docs, query, cfg)
        _cache_set(cache_key, {"chunk_text": chunk_text, "provenance": prov}, cfg.cache_ttl_sec)

    # Represent the ephemeral chunk as a Document so the existing
    # generation and response formatting utilities can handle it.
    synthetic = Document(
        id=f"agentic:{hash((query, len(chunk_text))) & 0xFFFFFFFF:x}",
        content=chunk_text,
        metadata={
            "title": "Agentic Ephemeral Chunk",
            "source": "agentic",
            "provenance": prov,
            "strategy": "agentic",
        },
        score=1.0,
        source=DataSource.MEDIA_DB,
    )

    result = UnifiedSearchResult(
        documents=[synthetic],
        query=query,
        expanded_queries=[],
        metadata={
            "strategy": "agentic",
            "coarse_docs": [
                {
                    "id": d.id,
                    "title": (d.metadata or {}).get("title"),
                    "score": float(getattr(d, "score", 0.0) or 0.0),
                }
                for d in docs[: cfg.top_k_docs]
            ],
            "provenance": prov,
        },
        timings={},
        citations=[],
        cache_hit=bool(cached_hit),
        errors=[],
        security_report=None,
        total_time=0.0,
    )

    # 4) Optional generation grounded in the synthetic chunk
    if enable_generation:
        try:
            from .generation import AnswerGenerator
            gen = AnswerGenerator(model=generation_model)
            ctx = chunk_text
            gen_out = await gen.generate(
                query=query,
                context=ctx,
                prompt_template=generation_prompt or "default",
                max_tokens=max_generation_tokens,
            )
            ans = gen_out["answer"] if isinstance(gen_out, dict) else str(gen_out)
            result.generated_answer = ans
        except Exception as e:
            logger.warning(f"Agentic generation failed: {e}")
            result.errors.append(str(e))

    # Timings
    result.total_time = time.time() - t0
    result.timings["total"] = result.total_time
    result.timings["agentic_chunking"] = result.total_time
    if debug_mode or cfg.debug_trace:
        logger.info(
            f"Agentic RAG built synthetic chunk of {len(chunk_text)} chars from {len(docs)} docs in {result.total_time:.3f}s"
        )

    return result
