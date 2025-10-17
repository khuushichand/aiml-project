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
from .advanced_cache import AGENTIC_CACHE
from .agentic_tools import make_default_registry
from .unified_pipeline import UnifiedSearchResult
from .database_retrievers import MultiDatabaseRetriever, RetrievalConfig

# Expose AnswerGenerator at module level for tests/patching parity with unified pipeline
try:
    from .generation import AnswerGenerator  # type: ignore
except Exception:
    AnswerGenerator = None  # type: ignore


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
    # Query decomposition
    enable_query_decomposition: bool = False
    subgoal_max: int = 3
    # Intra-doc semantic search
    enable_semantic_within: bool = True
    semantic_dim: int = 2048
    # Structural anchors
    enable_section_index: bool = True
    prefer_structural_anchors: bool = True
    # Table/figure support
    enable_table_support: bool = True
    table_trigger_keywords: Tuple[str, ...] = ("table", "figure", "tabular", "dataset")
    table_min_bar_count: int = 3  # '|' count heuristic
    # VLM late chunking (agentic path)
    agentic_enable_vlm_late_chunking: bool = False
    agentic_vlm_backend: Optional[str] = None
    agentic_vlm_detect_tables_only: bool = True
    agentic_vlm_max_pages: Optional[int] = None
    agentic_vlm_late_chunk_top_k_docs: int = 2
    # Provider embeddings for intra-doc vectors
    agentic_use_provider_embeddings_within: bool = False
    agentic_provider_embedding_model_id: Optional[str] = None
    # Adaptive budgets & stopping criteria
    adaptive_budgets: bool = True
    coverage_target: float = 0.8
    min_corroborating_docs: int = 2
    max_redundancy: float = 0.9
    # Metrics control
    enable_metrics: bool = True


# Simple in-process caches (namespaced via adapter)
_INTRA_DOC_VEC_CACHE: Dict[str, Any] = {}
# Back-compat ephemeral cache dict used by older tests
_EPHEMERAL_CACHE: Dict[str, Any] = {}

# Lazy DB handle for structure index lookups
_STRUCT_DB: Any = None

def _get_media_db_for_structure() -> Any:
    """Return a MediaDatabase instance bound to the configured content backend.

    Uses a singleton to avoid repeated initialization. Returns None on failure.
    """
    global _STRUCT_DB
    if _STRUCT_DB is not None:
        return _STRUCT_DB
    try:
        from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase as _MDB
        from tldw_Server_API.app.core.DB_Management.content_backend import get_content_backend as _get_cb
        from tldw_Server_API.app.core.config import load_comprehensive_config as _load_cfg
        cfg = _load_cfg()
        backend = _get_cb(cfg) if cfg else None
        if backend is None:
            return None
        # Use in-memory path; backend drives the actual connection
        _STRUCT_DB = _MDB(db_path=":memory:", client_id="agentic_toolbox", backend=backend)
        return _STRUCT_DB
    except Exception:
        return None


def _now() -> float:
    return time.time()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    v = AGENTIC_CACHE.get("ephemeral_chunk", key)
    if isinstance(v, dict):
        return v
    # Fallback to legacy dict
    v2 = _EPHEMERAL_CACHE.get(key)
    return v2 if isinstance(v2, dict) else None


def _cache_set(key: str, value: Dict[str, Any], ttl: int) -> None:
    AGENTIC_CACHE.set("ephemeral_chunk", key, value, ttl)
    # Mirror into legacy dict for test visibility
    _EPHEMERAL_CACHE[key] = value


def invalidate_intra_doc_vectors(media_id: str) -> int:
    """Invalidate cached intra-doc paragraph vectors for a given media/document id.

    Returns the number of entries removed.
    """
    if not media_id:
        return 0
    to_delete = [k for k in list(_INTRA_DOC_VEC_CACHE.keys()) if str(k).startswith(f"{media_id}|")]
    removed = 0
    for k in to_delete:
        try:
            _INTRA_DOC_VEC_CACHE.pop(k, None)
            removed += 1
        except Exception:
            pass
    return removed


def clear_agentic_caches() -> None:
    """Clear ephemeral chunk cache and intra-doc vector cache."""
    try:
        AGENTIC_CACHE.invalidate_prefix("ephemeral_chunk", "")
    except Exception:
        pass
    try:
        _INTRA_DOC_VEC_CACHE.clear()
    except Exception:
        pass
    try:
        _EPHEMERAL_CACHE.clear()
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


def _split_headings_and_paragraphs(text: str) -> Tuple[List[Tuple[str, int, int]], List[Tuple[int, int]]]:
    """Return (sections, paragraphs).

    sections: list of (heading_text, start_offset, end_offset)
    paragraphs: list of (start_offset, end_offset)
    """
    if not text:
        return [], []
    # Identify headings (markdown '#' or underlined or short uppercase lines)
    lines = text.splitlines()
    offsets: List[int] = []
    pos = 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln) + 1
    section_indices: List[int] = []
    section_titles: List[str] = []
    for i, ln in enumerate(lines):
        if re.match(r"^\s*#{1,6}\s+", ln):
            section_indices.append(i)
            section_titles.append(re.sub(r"^\s*#+\s+", "", ln).strip())
        elif i + 1 < len(lines) and (set(lines[i + 1].strip()) <= set("=-") and len(lines[i + 1].strip()) >= min(3, len(ln))):
            # underlined heading style
            section_indices.append(i)
            section_titles.append(ln.strip())
        elif len(ln) <= 80 and len(ln) >= 3 and ln.strip().isupper():
            section_indices.append(i)
            section_titles.append(ln.strip())

    sections: List[Tuple[str, int, int]] = []
    for idx, title in zip(section_indices, section_titles):
        start = offsets[idx]
        # next section or end
        j = None
        for nxt in section_indices:
            if nxt > idx:
                j = nxt
                break
        end = len(text) if j is None else offsets[j]
        sections.append((title, start, end))

    # Paragraph detection: split on blank lines or long gaps
    paragraphs: List[Tuple[int, int]] = []
    start = 0
    for m in re.finditer(r"\n\s*\n", text):
        end = m.start()
        if end > start:
            paragraphs.append((start, end))
        start = m.end()
    if start < len(text):
        paragraphs.append((start, len(text)))
    return sections, paragraphs


def _hash_embed(text: str, dim: int = 2048) -> 'np.ndarray':
    import numpy as _np
    v = _np.zeros(dim, dtype=_np.float32)
    if not text:
        return v
    for tok in re.findall(r"[A-Za-z0-9_-]{2,}", text.lower()):
        h = int(hashlib.md5(tok.encode('utf-8')).hexdigest(), 16)
        idx = h % dim
        v[idx] += 1.0
    # L2 normalize
    n = _np.linalg.norm(v)
    if n > 0:
        v /= n
    return v


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
            if cfg.enable_metrics:
                try:
                    from tldw_Server_API.app.core.Metrics.metrics_manager import observe_histogram, increment_counter
                    observe_histogram("agentic_span_length_chars", float(len(snippet)), labels={"phase": "assemble"})
                    increment_counter("span_bytes_read_total", float(len(snippet.encode('utf-8'))), labels={"tool": "heuristic"})
                except Exception:
                    pass
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

    def __init__(self, docs: List[Document], cfg: AgenticConfig):
        self.docs = docs
        self.cfg = cfg
        self._sections: Dict[str, List[Tuple[str, int, int]]] = {}
        self._paragraphs: Dict[str, List[Tuple[int, int]]] = {}
        self._para_vecs: Dict[str, List[Any]] = {}
        if cfg.enable_section_index or cfg.enable_semantic_within:
            self._build_indexes()

    def _build_indexes(self) -> None:
        try:
            import numpy as _np  # noqa: F401
        except Exception:
            pass
        for d in self.docs:
            text = d.content or ""
            sections, paragraphs = _split_headings_and_paragraphs(text)
            self._sections[d.id] = sections
            self._paragraphs[d.id] = paragraphs
            if self.cfg.enable_semantic_within:
                # Try provider embeddings first if enabled; cache per doc-version
                if self.cfg.agentic_use_provider_embeddings_within:
                    try:
                        key = f"{d.id}|{len(text)}|{hash(text)}|{self.cfg.agentic_provider_embedding_model_id or ''}|prov"
                        cached = _INTRA_DOC_VEC_CACHE.get(key)
                        if cached is not None:
                            self._para_vecs[d.id] = cached
                            if self.cfg.enable_metrics:
                                try:
                                    from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                                    increment_counter("agentic_cache_hits_total", 1, labels={"cache_type": "intra_doc"})
                                except Exception:
                                    pass
                        else:
                            from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import create_embeddings_batch
                            from tldw_Server_API.app.core.config import load_comprehensive_config
                            app_cfg = load_comprehensive_config() or {}
                            embedding_settings = app_cfg.get("EMBEDDING_CONFIG", {})
                            app_config = {"embedding_config": embedding_settings}
                            texts = [text[s:e] for (s, e) in paragraphs]
                            vecs_list = create_embeddings_batch(texts, app_config, self.cfg.agentic_provider_embedding_model_id)
                            import numpy as _np
                            vecs_np = [_np.array(v, dtype=_np.float32) for v in vecs_list]
                            for i, v in enumerate(vecs_np):
                                n = float((v ** 2).sum()) ** 0.5
                                if n > 0:
                                    vecs_np[i] = v / n
                            self._para_vecs[d.id] = vecs_np
                            _INTRA_DOC_VEC_CACHE[key] = vecs_np
                            continue
                    except Exception:
                        # Fallback to hashed embeddings
                        pass
                vecs = []
                for (s, e) in paragraphs:
                    vecs.append(_hash_embed(text[s:e], self.cfg.semantic_dim))
                self._para_vecs[d.id] = vecs

    def search_within(self, doc: Document, query: str, max_hits: int = 8, window: int = 300) -> List[Tuple[int, int]]:
        if self.cfg.enable_semantic_within and doc.id in self._para_vecs:
            try:
                import numpy as _np
                qv = _hash_embed(query, self.cfg.semantic_dim)
                vecs = self._para_vecs.get(doc.id) or []
                if not vecs:
                    return []
                sims = [float(_np.dot(qv, v)) for v in vecs]
                # pick top indices
                idxs = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:max_hits]
                paras = self._paragraphs.get(doc.id) or []
                return [paras[i] for i in idxs]
            except Exception:
                pass
        # Fallback keyword window search
        terms = _keyword_terms(query)
        return _find_spans(doc.content or "", terms, max_spans=max_hits, window=window)

    def open_section(self, doc: Document, heading: str) -> Optional[Tuple[int, int]]:
        """Find a section by heuristic heading match; returns [start,end) char range."""
        # Prefer DB-backed structure index when available
        try:
            from tldw_Server_API.app.core.config import rag_enable_structure_index
            _enable_si = rag_enable_structure_index()
        except Exception:
            _enable_si = True
        if _enable_si:
            try:
                mid_raw = (doc.metadata or {}).get('media_id') if isinstance(doc.metadata, dict) else None
                if mid_raw is not None:
                    db = _get_media_db_for_structure()
                    if db is not None:
                        res = db.lookup_section_by_heading(int(str(mid_raw)), heading)
                        if isinstance(res, tuple):
                            return (int(res[0]), int(res[1]))
            except Exception:
                pass
        if self.cfg.enable_section_index and doc.id in self._sections:
            secs = self._sections.get(doc.id) or []
            for title, s, e in secs:
                if heading.lower() in (title or "").lower():
                    return (s, e)
        # fallback heuristic if no index
        text = doc.content or ""
        if not text:
            return None
        lines = text.splitlines()
        offsets = []
        pos = 0
        for ln in lines:
            offsets.append(pos)
            pos += len(ln) + 1
        for i, ln in enumerate(lines):
            if re.match(r"^\s*(#+|\d+[\)\.]\s+)\s+", ln) and heading.lower() in ln.lower():
                start = offsets[i]
                # end at next heading
                j = i + 1
                while j < len(lines) and not re.match(r"^\s*(#+|\d+[\)\.]\s+)\s+", lines[j]):
                    j += 1
                end = len(text) if j >= len(lines) else offsets[j]
                return (start, end)
        return None

    def expand_window(self, doc: Document, start: int, end: int, delta: int = 200) -> Tuple[int, int]:
        text = doc.content or ""
        left = max(0, start - delta)
        right = min(len(text), end + delta)
        return (left, right)

    def quote_spans(self, doc: Document, spans: List[Tuple[int, int]]) -> List[str]:
        text = doc.content or ""
        return [text[s:e] for s, e in spans]

    def section_title_for(self, doc: Document, start: int) -> Optional[str]:
        secs = self._sections.get(doc.id) or []
        for title, s, e in secs:
            if s <= start < e:
                return title
        return None

    def looks_table(self, text: str) -> bool:
        if not text:
            return False
        bars = text.count('|')
        tabs = text.count('\t')
        nums = len(re.findall(r"\d", text))
        return bars >= self.cfg.table_min_bar_count or tabs >= 2 or (nums >= 10 and ('|' in text or '\t' in text))


def _decompose_query(query: str, cfg: AgenticConfig) -> List[str]:
    # Heuristic split on ' and ', ' then ', ',', and question separators
    q = (query or '').strip()
    if not q:
        return []
    parts = re.split(r"\b(?:and then|then|and|,|;|\?)\b", q, flags=re.IGNORECASE)
    sub = [p.strip() for p in parts if p and len(p.strip()) >= 3]
    if cfg.subgoal_max and len(sub) > cfg.subgoal_max:
        sub = sub[: cfg.subgoal_max]
    # Fall back to single if no clear split
    return sub or [q]


async def _tool_loop(docs: List[Document], query: str, cfg: AgenticConfig) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Simple bounded tool loop. If cfg.use_llm_planner is True, we try a light
    planning prompt; otherwise use a deterministic heuristic policy. Network
    failures automatically fall back to heuristics.
    """
    tb = AgenticToolbox(docs, cfg)
    registry = make_default_registry(tb)
    remaining_tokens = int(cfg.max_tokens_read)
    max_steps = max(1, int(cfg.max_tool_calls))
    deadline = (_now() + cfg.time_budget_sec) if cfg.time_budget_sec else None

    assembled: List[Tuple[Document, int, int]] = []
    steps = 0
    tool_trace: List[Dict[str, Any]] = []

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

    # Query decomposition (multi-hop support)
    subgoals = _decompose_query(query, cfg) if cfg.enable_query_decomposition else [query]

    # Helper to compute coverage/corroboration + redundancy
    def _compute_progress_metrics() -> Dict[str, Any]:
        try:
            terms = _keyword_terms(query)
            assembled_text = "\n".join([(d.content or "")[s:e] for d, s, e in assembled])
            term_hits = 0
            for t in terms:
                if t.lower() in (assembled_text or "").lower():
                    term_hits += 1
            coverage = (term_hits / max(1, len(terms)))
            uniq_docs = len({getattr(d, 'id', '') for d, _, _ in assembled})
            raw = 0
            merged = 0
            per_doc: Dict[str, List[Tuple[int, int]]] = {}
            for d, s, e in assembled:
                per_doc.setdefault(getattr(d, 'id', ''), []).append((int(s), int(e)))
            for _doc_id, ranges in per_doc.items():
                ranges = sorted(ranges, key=lambda x: x[0])
                raw += sum(e - s for s, e in ranges)
                merged_ranges: List[Tuple[int, int]] = []
                for s, e in ranges:
                    if not merged_ranges or s > merged_ranges[-1][1]:
                        merged_ranges.append((s, e))
                    else:
                        ps, pe = merged_ranges[-1]
                        merged_ranges[-1] = (ps, max(pe, e))
                merged += sum(e - s for s, e in merged_ranges)
            redundancy = 1.0 - (merged / max(1, raw))
            return {"coverage": coverage, "unique_docs": uniq_docs, "redundancy": redundancy}
        except Exception:
            return {"coverage": 0.0, "unique_docs": 0, "redundancy": 0.0}

    # Heuristic policy per subgoal: scan top docs, pick best spans by semantic/keyword hits, consider headings
    for goal in subgoals:
        for d in docs[: max(1, cfg.top_k_docs)]:
            if steps >= max_steps or not time_left():
                break
            # Use planned terms if available
            local_query = " ".join([goal] + planned_terms) if planned_terms else goal

            # Table-aware routing: if goal mentions table-like concepts, prefer table-like paragraphs
            _t0 = time.time()
            search = registry.get("search_within")
            hits = search(d, local_query, max_hits=4, window=int(cfg.window_chars / 4)) if search else tb.search_within(d, local_query, max_hits=4, window=int(cfg.window_chars / 4))
            _t1 = time.time()
            if cfg.enable_metrics:
                try:
                    from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter, observe_histogram
                    increment_counter("agentic_tool_calls_total", 1, labels={"tool": "search_within"})
                    observe_histogram("agentic_tool_duration_seconds", (_t1 - _t0), labels={"tool": "search_within"})
                except Exception:
                    pass
            if cfg.enable_table_support and any(kw in local_query.lower() for kw in cfg.table_trigger_keywords):
                # Reorder to prefer table-like spans
                hits = sorted(hits, key=lambda rng: int(not tb.looks_table((d.content or "")[rng[0]:rng[1]])))

            # Try planned headings if no hits
            if not hits and planned_headings:
                for h in planned_headings[:3]:
                    _s0 = time.time()
                    open_sec = registry.get("open_section")
                    sec = open_sec(d, h) if open_sec else tb.open_section(d, h)
                    _s1 = time.time()
                    if cfg.enable_metrics:
                        try:
                            from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter, observe_histogram
                            increment_counter("agentic_tool_calls_total", 1, labels={"tool": "open_section"})
                            observe_histogram("agentic_tool_duration_seconds", (_s1 - _s0), labels={"tool": "open_section"})
                        except Exception:
                            pass
                    if sec:
                        hits = [sec]
                        break
            for (s, e) in hits:
                if steps >= max_steps or not time_left():
                    break
                _e0 = time.time()
                expand = registry.get("expand_window")
                s2, e2 = (expand(d, s, e, delta=100) if expand else tb.expand_window(d, s, e, delta=100))
                _e1 = time.time()
                if cfg.enable_metrics:
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter, observe_histogram
                        increment_counter("agentic_tool_calls_total", 1, labels={"tool": "expand_window"})
                        observe_histogram("agentic_tool_duration_seconds", (_e1 - _e0), labels={"tool": "expand_window"})
                    except Exception:
                        pass
                assembled.append((d, s2, e2))
                steps += 1
                snippet = (d.content or "")[s2:e2]
                remaining_tokens -= _token_estimate(snippet)
                if cfg.enable_metrics:
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import observe_histogram, increment_counter
                        observe_histogram("agentic_span_length_chars", float(len(snippet)), labels={"phase": "tool"})
                        increment_counter("span_bytes_read_total", float(len(snippet.encode('utf-8'))), labels={"tool": "expand_window"})
                    except Exception:
                        pass
                if cfg.debug_trace:
                    tool_trace.append({
                        "tool": "expand_window",
                        "doc_id": getattr(d, 'id', ''),
                        "start": int(s2),
                        "end": int(e2),
                        "duration_ms": int((_e1 - _e0) * 1000.0),
                        "bytes": int(len(snippet.encode('utf-8'))),
                        "reason": "around-hit",
                    })
                if remaining_tokens <= 0:
                    break

                # Adaptive stop if coverage + corroboration achieved
                if cfg.adaptive_budgets:
                    prog = _compute_progress_metrics()
                    if (prog.get("coverage", 0.0) >= float(cfg.coverage_target or 1.0)) and (prog.get("unique_docs", 0) >= int(cfg.min_corroborating_docs or 1)):
                        steps = max_steps
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
            "section_title": tb.section_title_for(d, s),
            "snippet_preview": snippet[:120]
        })

    glue = "\n\n---\n\n"
    return glue.join(parts), provenance, tool_trace


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
    explain_only: bool = False,
    # verification/guardrails (optional)
    require_hard_citations: bool = False,
    enable_numeric_fidelity: bool = False,
    numeric_fidelity_behavior: str = "continue",  # continue|ask|decline|retry
    enable_claims: bool = False,
    claim_verifier: str = "hybrid",
    claims_top_k: int = 5,
    claims_conf_threshold: float = 0.7,
    claims_max: int = 25,
    nli_model: Optional[str] = None,
    claims_concurrency: int = 8,
    # NLI/low-confidence gate
    adaptive_unsupported_threshold: float = 0.15,
    low_confidence_behavior: str = "continue",
) -> UnifiedSearchResult:
    """Agentic RAG: coarse retrieve, assemble ephemeral chunk, optional answer.

    This function is intentionally lightweight and safe to call in tests.
    """
    t0 = time.time()
    cfg = agentic or AgenticConfig()

    # Config-driven default: require_hard_citations toggle
    try:
        from tldw_Server_API.app.core.config import rag_require_hard_citations as _rag_req_hc
        if not bool(require_hard_citations) and bool(_rag_req_hc(default=False)):
            require_hard_citations = True  # type: ignore[assignment]
    except Exception:
        pass

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

    # Optional: VLM late chunking to add table/figure hints for PDFs
    if cfg.agentic_enable_vlm_late_chunking and docs:
        try:
            try:
                from tldw_Server_API.app.core.Ingestion_Media_Processing.VLM.registry import get_backend as _get_vlm_backend
            except Exception:
                _get_vlm_backend = lambda name=None: None  # type: ignore
            backend = _get_vlm_backend(cfg.agentic_vlm_backend if cfg.agentic_vlm_backend not in (None, "auto") else None)
            if backend is not None:
                # Select top-k docs with local PDF path
                sel = []
                for d in docs:
                    md = d.metadata or {}
                    url = md.get("url") or md.get("pdf_path") or md.get("file_path")
                    if not url:
                        continue
                    try:
                        from pathlib import Path
                        p = Path(str(url))
                        if p.exists() and p.suffix.lower() == ".pdf":
                            sel.append((d, str(p)))
                    except Exception:
                        continue
                sel = sel[: max(1, int(cfg.agentic_vlm_late_chunk_top_k_docs or 1))]
                added: List[Document] = []
                for (doc0, pdf_path) in sel:
                    detections = []
                    # Prefer doc-level processing
                    if hasattr(backend, "process_pdf"):
                        res = backend.process_pdf(pdf_path, max_pages=cfg.agentic_vlm_max_pages)
                        by_page = []
                        if isinstance(getattr(res, "extra", None), dict):
                            by_page = res.extra.get("by_page") or []
                        for entry in by_page:
                            page_no = entry.get("page")
                            for d in (entry.get("detections") or []):
                                label = str(d.get("label"))
                                if cfg.agentic_vlm_detect_tables_only and label.lower() != "table":
                                    continue
                                detections.append({
                                    "label": label,
                                    "score": float(d.get("score", 0.0)),
                                    "bbox": d.get("bbox") or [0.0, 0.0, 0.0, 0.0],
                                    "page": page_no,
                                })
                    else:
                        # Per-page fallback via pymupdf
                        try:
                            import pymupdf
                            with pymupdf.open(pdf_path) as _doc:
                                total = len(_doc)
                                maxp = min(cfg.agentic_vlm_max_pages or total, total)
                                for i, page in enumerate(_doc, start=1):
                                    if i > maxp:
                                        break
                                    pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), alpha=False)
                                    img_bytes = pix.tobytes("png")
                                    res = backend.process_image(img_bytes, context={"page": i, "pdf_path": pdf_path})
                                    for det in (getattr(res, "detections", []) or []):
                                        label = str(getattr(det, "label", ""))
                                        if cfg.agentic_vlm_detect_tables_only and label.lower() != "table":
                                            continue
                                        detections.append({
                                            "label": label,
                                            "score": float(getattr(det, "score", 0.0)),
                                            "bbox": list(getattr(det, "bbox", [0.0, 0.0, 0.0, 0.0])),
                                            "page": i,
                                        })
                        except Exception:
                            pass
                    for idx, dct in enumerate(detections[:100]):
                        label = dct.get("label", "vlm")
                        score = dct.get("score", 0.0)
                        bbox = dct.get("bbox")
                        page_no = dct.get("page")
                        chunk_text = f"Detected {label} ({score:.2f}) on page {page_no} at {bbox}"
                        added.append(
                            Document(
                                id=f"vlm:{doc0.id}:{idx}",
                                content=chunk_text,
                                source=doc0.source,
                                metadata={
                                    **(doc0.metadata or {}),
                                    "chunk_type": ("table" if str(label).lower() == "table" else "vlm"),
                                    "page": page_no,
                                    "bbox": bbox,
                                    "derived_from": doc0.id,
                                },
                                score=float(getattr(doc0, "score", 0.0)),
                            )
                        )
                if added:
                    docs.extend(added)
        except Exception as e:
            logger.debug(f"Agentic VLM late chunking skipped: {e}")

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
        if cfg.enable_metrics:
            try:
                from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                increment_counter("agentic_cache_hits_total", 1, labels={"cache_type": "ephemeral"})
            except Exception:
                pass
    else:
        cached_hit = False
        # 4) Assemble ephemeral chunk (either tools or heuristics)
        tool_trace: List[Dict[str, Any]] = []
        if cfg.enable_tools:
            chunk_text, prov, tool_trace = await _tool_loop(docs, query, cfg)
        else:
            chunk_text, prov = _assemble_ephemeral_chunk(docs, query, cfg)
            tool_trace = []
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

    # Attach lightweight coverage/precision metrics
    try:
        terms = _keyword_terms(query)
        term_hits = sum(1 for t in terms if t in (chunk_text or "").lower())
        coverage = (term_hits / max(1, len(terms)))
        uniq_docs = len({str(p.get("document_id")) for p in (prov or []) if isinstance(p, dict)})
        per_doc: Dict[str, List[Tuple[int, int]]] = {}
        for p in (prov or []):
            try:
                per_doc.setdefault(str(p.get("document_id")), []).append((int(p.get("start", 0)), int(p.get("end", 0))))
            except Exception:
                continue
        raw = 0
        merged = 0
        for _doc_id, ranges in per_doc.items():
            ranges = sorted(ranges, key=lambda x: x[0])
            raw += sum(e - s for s, e in ranges)
            merged_ranges: List[Tuple[int, int]] = []
            for s, e in ranges:
                if not merged_ranges or s > merged_ranges[-1][1]:
                    merged_ranges.append((s, e))
                else:
                    ps, pe = merged_ranges[-1]
                    merged_ranges[-1] = (ps, max(pe, e))
            merged += sum(e - s for s, e in merged_ranges)
        redundancy = 1.0 - (merged / max(1, raw))
        result.metadata.setdefault("agentic_metrics", {})
        result.metadata["agentic_metrics"].update({
            "term_coverage": float(coverage),
            "unique_docs": int(uniq_docs),
            "redundancy": float(redundancy),
        })
    except Exception:
        pass

    # Explain-only dry run: return plan/provenance without answer or chunk body
    if explain_only and not enable_generation:
        try:
            # Remove documents to avoid heavy payloads; keep provenance and metrics
            result.documents = []
            result.metadata.setdefault("explain", {})
            # Include a minimal plan derived from tool trace and coverage
            result.metadata["explain"].update({
                "provenance": prov,
            })
        except Exception:
            pass
        # Timings and return
        result.total_time = time.time() - t0
        result.timings["total"] = result.total_time
        result.timings["agentic_chunking"] = result.total_time
        return result

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

    # Guardrails and verification: hard citations + numeric fidelity + optional claims/NLI
    if result.generated_answer:
        claims_payload = None
        # Optional claims verification (NLI/LLM) constrained to assembled spans
        if enable_claims:
            try:
                import tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib as sgl  # type: ignore
                from .claims import ClaimsEngine
                def _analyze(api_name: str, input_data: Any, custom_prompt_arg: Optional[str] = None,
                             api_key: Optional[str] = None, system_message: Optional[str] = None,
                             temp: Optional[float] = None, **kwargs):
                    return sgl.analyze(api_name, input_data, custom_prompt_arg, api_key, system_message, temp, **kwargs)
                engine = ClaimsEngine(_analyze)
                async def _retrieve_for_claim(_c_text: str, top_k: int = 3):
                    return [synthetic]
                claims_run = await engine.run(
                    answer=result.generated_answer,
                    query=query,
                    documents=[synthetic],
                    claim_extractor="auto",
                    claim_verifier=claim_verifier,
                    claims_top_k=claims_top_k,
                    claims_conf_threshold=claims_conf_threshold,
                    claims_max=claims_max,
                    retrieve_fn=_retrieve_for_claim,
                    nli_model=nli_model,
                    claims_concurrency=claims_concurrency,
                )
                claims_payload = claims_run.get("claims")
                result.metadata["claims"] = claims_payload
                result.metadata["factuality"] = claims_run.get("summary")
            except Exception as _e:
                logger.debug(f"Agentic claims verification skipped: {_e}")

        # Hard citations using assembled spans
        try:
            from .guardrails import build_hard_citations
            hc = build_hard_citations(result.generated_answer, [synthetic], claims_payload=claims_payload)
            if isinstance(hc, dict):
                result.metadata["hard_citations"] = hc
                cov = float(hc.get("coverage") or 0.0)
                if require_hard_citations and cov < 1.0:
                    result.metadata.setdefault("generation_gate", {})
                    result.metadata["generation_gate"].update({
                        "reason": "missing_hard_citations",
                        "coverage": cov,
                        "at": time.time(),
                    })
                    # Abstain if strict
                    result.generated_answer = "Insufficient evidence: missing citations for some statements."
        except Exception as _ec:
            result.errors.append(f"Hard citations failed: {str(_ec)}")

    # Numeric fidelity check and optional mitigation
        try:
            from .guardrails import check_numeric_fidelity
            if enable_numeric_fidelity and check_numeric_fidelity:
                nf = check_numeric_fidelity(result.generated_answer, [synthetic])
                if nf:
                    result.metadata.setdefault("numeric_fidelity", {})
                    result.metadata["numeric_fidelity"].update({
                        "present": sorted(list(nf.present)),
                        "missing": sorted(list(nf.missing)),
                        "source_numbers": sorted(list(nf.union_source_numbers))[:100],
                    })
                    if nf.missing and numeric_fidelity_behavior in {"retry", "ask", "decline"}:
                        if numeric_fidelity_behavior == "ask":
                            note = "\n\n[Note] Some numeric values could not be verified against sources. Please clarify or provide references."
                            result.generated_answer = (result.generated_answer or "") + note
                        elif numeric_fidelity_behavior == "decline":
                            result.generated_answer = "Insufficient evidence to verify numeric claims in the current context."
                        elif numeric_fidelity_behavior == "retry":
                            try:
                                if media_db_path:
                                    mdr = MultiDatabaseRetriever({"media_db": media_db_path}, user_id="rag_agentic", media_db=media_db, chacha_db=chacha_db)
                                    conf = RetrievalConfig(max_results=min(10, top_k), min_score=min_score, use_fts=True, use_vector=True, include_metadata=True, fts_level=fts_level)
                                    added = []
                                    for tok in list(nf.missing)[:3]:
                                        try:
                                            added.extend(await mdr.retrieve(query=f"{query} {tok}", sources=[DataSource.MEDIA_DB], config=conf, index_namespace=index_namespace))
                                        except Exception:
                                            continue
                                    if added:
                                        by_id: Dict[str, Document] = {getattr(d, 'id', ''): d for d in (result.documents or [])}
                                        for d in added:
                                            cur = by_id.get(getattr(d, 'id', ''))
                                            if cur is None or float(getattr(d, 'score', 0.0)) > float(getattr(cur, 'score', 0.0)):
                                                by_id[getattr(d, 'id', '')] = d
                                        result.documents = list(by_id.values())
                            except Exception:
                                pass
        except Exception as _enf:
            result.errors.append(f"Numeric fidelity check failed: {str(_enf)}")

        # NLI low-confidence gate (lightweight, optional)
        try:
            if enable_claims and result.generated_answer:
                from .post_generation_verifier import PostGenerationVerifier as _PGV
                verifier = _PGV(max_retries=0, unsupported_threshold=float(adaptive_unsupported_threshold or 0.15), max_claims=min(10, int(claims_max or 25)))
                vres = await verifier.verify_and_maybe_fix(
                    query=query,
                    answer=result.generated_answer,
                    base_documents=result.documents or [],
                    media_db_path=media_db_path,
                    notes_db_path=notes_db_path,
                    character_db_path=character_db_path,
                    user_id="rag_agentic",
                    generation_model=generation_model,
                    existing_claims=None,
                    existing_summary=None,
                    search_mode=search_mode,
                    hybrid_alpha=hybrid_alpha,
                    top_k=top_k,
                )
                result.metadata.setdefault("post_verification", {})
                result.metadata["post_verification"].update({
                    "unsupported_ratio": vres.unsupported_ratio,
                    "total_claims": vres.total_claims,
                    "unsupported_count": vres.unsupported_count,
                    "fixed": vres.fixed,
                    "reason": vres.reason,
                })
                # Gauge and gate behavior
                try:
                    from tldw_Server_API.app.core.Metrics.metrics_manager import set_gauge, increment_counter
                    set_gauge("rag_nli_unsupported_ratio", float(vres.unsupported_ratio or 0.0), labels={"strategy": "agentic"})
                except Exception:
                    pass
                low_conf = (vres.unsupported_ratio > float(adaptive_unsupported_threshold or 0.15)) and (not vres.fixed)
                if low_conf:
                    result.metadata.setdefault("generation_gate", {})
                    result.metadata["generation_gate"].update({
                        "reason": "nli_low_confidence",
                        "unsupported_ratio": float(vres.unsupported_ratio or 0.0),
                        "threshold": float(adaptive_unsupported_threshold or 0.15),
                        "at": time.time(),
                    })
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                        increment_counter("rag_nli_low_confidence_total", 1)
                    except Exception:
                        pass
                    if low_confidence_behavior == "ask":
                        note = "\n\n[Note] Evidence is insufficient; please clarify or provide more context."
                        result.generated_answer = (result.generated_answer or "") + note
                    elif low_confidence_behavior == "decline":
                        result.generated_answer = "Insufficient evidence found to answer confidently."
        except Exception as _enlv:
            result.errors.append(f"NLI verification failed: {str(_enlv)}")

    # Include tool trace on debug
    if (debug_mode or cfg.debug_trace) and (not cached_hit) and cfg.enable_tools:
        try:
            result.metadata["tool_trace"] = tool_trace
        except Exception:
            pass

    # Timings
    result.total_time = time.time() - t0
    result.timings["total"] = result.total_time
    result.timings["agentic_chunking"] = result.total_time
    if debug_mode or cfg.debug_trace:
        logger.info(
            f"Agentic RAG built synthetic chunk of {len(chunk_text)} chars from {len(docs)} docs in {result.total_time:.3f}s"
        )

    # Sentence-level chunk citations (align sentences to chunk spans)
    try:
        if result.generated_answer:
            import re as _re
            sents = [s.strip() for s in _re.split(r"(?<=[\.!?])\s+", result.generated_answer.strip()) if s.strip()]
            chunk = synthetic.content or ""
            def _find_off(full: str, t: str) -> Tuple[int, int]:
                i = full.find(t)
                return (i, i + len(t)) if i >= 0 else (0, 0)
            entries: List[Dict[str, Any]] = []
            for s in sents:
                st, en = _find_off(chunk, s)
                entry = {"text": s, "citations": []}
                if en > st:
                    entry["citations"].append({
                        "doc_id": synthetic.id,
                        "start": int(st),
                        "end": int(en),
                    })
                entries.append(entry)
            result.metadata["chunk_citations"] = {"sentences": entries}
    except Exception:
        pass

    return result
