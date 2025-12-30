"""
claims_engine.py - Claim extraction and verification (moved from RAG module)

This module centralizes claim extraction & verification logic under the
Claims_Extraction module so it can be used at ingestion time and by RAG
pipelines. It mirrors the functionality that existed in
app/core/RAG/rag_service/claims.py and is designed to be extended.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple

from loguru import logger
from tldw_Server_API.app.core.Claims_Extraction.budget_guard import (
    ClaimsJobBudget,
    ClaimsJobContext,
    estimate_claims_tokens,
    resolve_claims_job_budget,
)
from tldw_Server_API.app.core.Claims_Extraction.monitoring import (
    estimate_claims_cost,
    record_claims_budget_exhausted,
    record_claims_provider_request,
    record_claims_throttle,
    should_throttle_claims_provider,
    suggest_claims_concurrency,
)
from tldw_Server_API.app.core.Claims_Extraction.span_alignment import find_text_span
from tldw_Server_API.app.core.Utils.prompt_loader import load_prompt

# Prefer importing Document from RAG types to keep consistency in pipelines
try:
    from tldw_Server_API.app.core.RAG.rag_service.types import Document
except Exception:
    # Lightweight fallback type for non-RAG usage
    @dataclass
    class Document:  # type: ignore
        id: str
        content: str
        metadata: Dict[str, Any] = field(default_factory=dict)
        score: float = 0.0


# --------------------------- Data Models ---------------------------

@dataclass
class Claim:
    id: str
    text: str
    span: Optional[Tuple[int, int]] = None


@dataclass
class Evidence:
    doc_id: str
    snippet: str
    score: float = 0.0


@dataclass
class ClaimVerification:
    claim: Claim
    label: str  # supported | refuted | nei
    confidence: float
    evidence: List[Evidence] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    rationale: Optional[str] = None


# --------------------------- Interfaces ---------------------------

class ClaimExtractor(Protocol):
    async def extract(
        self,
        answer: str,
        max_claims: int = 25,
        *,
        budget: Optional[ClaimsJobBudget] = None,
        job_context: Optional[ClaimsJobContext] = None,
    ) -> List[Claim]:
        ...


class ClaimVerifier(Protocol):
    async def verify(
        self,
        claim: Claim,
        query: str,
        base_documents: List[Document],
        retrieve_fn: Optional[Any] = None,
        top_k: int = 5,
        conf_threshold: float = 0.7,
        mode: str = "hybrid",
        budget: Optional[ClaimsJobBudget] = None,
        job_context: Optional[ClaimsJobContext] = None,
    ) -> ClaimVerification:
        ...


# --------------------------- Utilities ---------------------------

_NUMERIC_RE = re.compile(r"\b(\d{1,3}(?:[\,\._]\d{3})*|\d+)(?:\s*(%|k|m|b))?\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{4})\b")


def _extract_numbers_and_dates(text: str) -> Dict[str, List[str]]:
    nums = [m.group(0) for m in _NUMERIC_RE.finditer(text or "")]
    dates = [m.group(0) for m in _DATE_RE.finditer(text or "")]
    return {"numbers": nums, "dates": dates}


def _contains_any(hay: str, needles: List[str]) -> bool:
    hay_l = (hay or "").lower()
    return any(n.lower() in hay_l for n in needles if n)


def _first_n_snippets(docs: List[Document], n: int = 3, snippet_len: int = 480) -> List[Evidence]:
    out: List[Evidence] = []
    for d in docs[:n]:
        txt = d.content or ""
        snip = txt[:snippet_len] + ("..." if len(txt) > snippet_len else "")
        out.append(Evidence(doc_id=getattr(d, "id", ""), snippet=snip, score=getattr(d, "score", 0.0)))
    return out


def _find_offsets(doc_text: str, claim_text: str, snippet: str) -> Tuple[int, int]:
    """Best-effort exact offsets into the full document.

    Strategy:
    1) Exact match on claim_text/snippet
    2) Normalized match (case/whitespace)
    3) Anchored window match for long text
    4) Fallback to (0, min(len(doc_text), len(snippet)))
    """
    if not isinstance(doc_text, str) or not doc_text:
        return (0, 0)
    ct = (claim_text or "").strip()
    snip = (snippet or "").strip()
    if snip.endswith("..."):
        snip = snip[:-3]
    if snip.endswith("…"):
        snip = snip[:-1]

    span = find_text_span(doc_text, ct, fallback_text=snip)
    if span is not None:
        return span

    return (0, min(len(doc_text), max(len(ct), len(snip))))


def _resolve_claims_llm_config() -> Tuple[str, Optional[str], float]:
    try:
        from tldw_Server_API.app.core.config import settings as _settings  # type: ignore
    except Exception:
        _settings = {}

    provider = None
    model_override = None
    temperature = 0.1
    try:
        provider = str(_settings.get("CLAIMS_LLM_PROVIDER", "")).strip() or None
    except Exception:
        provider = None
    try:
        model_override = str(_settings.get("CLAIMS_LLM_MODEL", "")).strip() or None
    except Exception:
        model_override = None
    try:
        temperature = float(_settings.get("CLAIMS_LLM_TEMPERATURE", 0.1))
    except Exception:
        temperature = 0.1

    if provider is None:
        try:
            rag_cfg = _settings.get("RAG", {}) or {}
            provider = str(rag_cfg.get("default_llm_provider", "")).strip() or None
        except Exception:
            provider = None
    if provider is None:
        try:
            provider = str(_settings.get("default_api", "openai")).strip() or "openai"
        except Exception:
            provider = "openai"
    if model_override is None:
        try:
            rag_cfg = _settings.get("RAG", {}) or {}
            model_override = str(rag_cfg.get("default_llm_model", "")).strip() or None
        except Exception:
            model_override = None

    return provider or "openai", model_override, temperature


async def _log_claims_llm_usage(
    *,
    job_context: Optional[ClaimsJobContext],
    operation: str,
    provider: str,
    model: str,
    prompt_text: str,
    response_text: str,
    latency_ms: int,
    status: int,
    estimated: bool = True,
) -> None:
    try:
        from tldw_Server_API.app.core.Usage.usage_tracker import log_llm_usage
    except Exception:
        return
    try:
        user_id = job_context.user_id if job_context else None
    except Exception:
        user_id = None
    try:
        api_key_id = job_context.api_key_id if job_context else None
    except Exception:
        api_key_id = None
    try:
        request_id = job_context.request_id if job_context else None
    except Exception:
        request_id = None
    endpoint = None
    try:
        endpoint = job_context.endpoint if job_context else None
    except Exception:
        endpoint = None
    await log_llm_usage(
        user_id=user_id,
        key_id=api_key_id,
        endpoint=endpoint or "claims_engine",
        operation=operation,
        provider=provider,
        model=model or "",
        status=int(status),
        latency_ms=int(latency_ms),
        prompt_tokens=estimate_claims_tokens(prompt_text),
        completion_tokens=estimate_claims_tokens(response_text),
        total_tokens=None,
        request_id=request_id,
        estimated=estimated,
    )


# --------------------------- Extractors ---------------------------

class HeuristicSentenceExtractor:
    async def extract(self, answer: str, max_claims: int = 25) -> List[Claim]:
        if not answer or not isinstance(answer, str):
            return []
        # naive sentence split; keep manageable count
        parts = re.split(r"(?<=[\.!?])\s+", answer.strip())
        claims: List[Claim] = []
        for i, p in enumerate(parts):
            t = p.strip()
            if not t:
                continue
            # filter very short lines
            if len(t) < 12:
                continue
            claims.append(Claim(id=f"c{i+1}", text=t, span=None))
            if len(claims) >= max_claims:
                break
        return claims


class LLMBasedClaimExtractor:
    """Prompt an LLM to extract decontextualized atomic propositions as JSON."""

    def __init__(self, analyze_fn: Any):
        self._analyze = analyze_fn

    async def extract(
        self,
        answer: str,
        max_claims: int = 25,
        *,
        budget: Optional[ClaimsJobBudget] = None,
        job_context: Optional[ClaimsJobContext] = None,
    ) -> List[Claim]:
        if not answer:
            return []
        system = load_prompt("ingestion", "claims_extractor_system") or (
            "You extract specific, verifiable, decontextualized factual propositions. Output strict JSON."
        )
        base = load_prompt("ingestion", "claims_extractor_prompt") or (
            "Extract up to {max_claims} atomic factual propositions from the ANSWER. "
            "Each proposition should stand alone without the surrounding context, be specific and checkable. "
            "Return JSON: {{\"claims\":[{{\"text\": str}}]}}. Do not include explanations.\n\nANSWER:\n{answer}"
        )
        # Safely format template that may contain JSON braces
        try:
            prompt = base.format(max_claims=max_claims, answer=answer)
        except Exception:
            # Escape all braces then restore placeholders
            _tmpl = base.replace('{', '{{').replace('}', '}}')
            _tmpl = _tmpl.replace('{{max_claims}}', '{max_claims}').replace('{{answer}}', '{answer}')
            prompt = _tmpl.format(max_claims=max_claims, answer=answer)

        provider, model_override, temperature = _resolve_claims_llm_config()
        cost_estimate = estimate_claims_cost(
            provider=provider or "openai",
            model=model_override or "",
            text=prompt,
        )
        budget_ratio = budget.remaining_ratio() if budget is not None else None
        throttle, reason = should_throttle_claims_provider(
            provider=provider or "openai",
            model=model_override or "",
            budget_ratio=budget_ratio,
        )
        if throttle:
            record_claims_throttle(
                provider=provider or "openai",
                model=model_override or "",
                mode="extract",
                reason=reason or "throttle",
            )
            return await HeuristicSentenceExtractor().extract(answer, max_claims)
        if budget is not None:
            prompt_tokens = estimate_claims_tokens(prompt)
            if not budget.reserve(cost_usd=cost_estimate, tokens=prompt_tokens):
                record_claims_budget_exhausted(
                    provider=provider or "openai",
                    model=model_override or "",
                    mode="extract",
                    reason=budget.exhausted_reason or "budget",
                )
                if budget.strict:
                    return []
                return await HeuristicSentenceExtractor().extract(answer, max_claims)
        try:
            start_time = time.time()
            raw = await asyncio.to_thread(
                self._analyze,
                provider or "openai",
                answer,
                prompt,
                None,
                system,
                temperature,
                streaming=False,
                recursive_summarization=False,
                chunked_summarization=False,
                chunk_options=None,
                model_override=model_override,
            )
            latency_s = time.time() - start_time
            record_claims_provider_request(
                provider=provider or "openai",
                model=model_override or "",
                mode="extract",
                latency_s=latency_s,
                estimated_cost=cost_estimate,
            )
            text = raw if isinstance(raw, str) else str(raw)
            if budget is not None:
                budget.add_usage(tokens=estimate_claims_tokens(text))
            try:
                await _log_claims_llm_usage(
                    job_context=job_context,
                    operation="claims_extract",
                    provider=provider or "openai",
                    model=model_override or "",
                    prompt_text=prompt,
                    response_text=text,
                    latency_ms=int(latency_s * 1000),
                    status=200,
                    estimated=True,
                )
            except Exception:
                pass
            # find JSON block (support fenced blocks)
            jtxt = None
            fence_json = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
            for block in fence_json or []:
                try:
                    _ = json.loads(block)
                    jtxt = block
                    break
                except Exception:
                    continue
            if jtxt is None:
                m = re.search(r"\{[\s\S]*\}\s*$", text)
                jtxt = m.group(0) if m else text
            data = json.loads(jtxt)
            out: List[Claim] = []
            for i, c in enumerate((data.get("claims") or [])[:max_claims]):
                t = (c or {}).get("text")
                if isinstance(t, str) and len(t.strip()) > 0:
                    out.append(Claim(id=f"c{i+1}", text=t.strip()))
            if not out:
                logger.debug("LLM extractor returned no claims; falling back to heuristics")
                return await HeuristicSentenceExtractor().extract(answer, max_claims)
            return out
        except Exception as e:
            record_claims_provider_request(
                provider=provider or "openai",
                model=model_override or "",
                mode="extract",
                latency_s=None,
                error=str(e),
                estimated_cost=cost_estimate,
            )
            try:
                await _log_claims_llm_usage(
                    job_context=job_context,
                    operation="claims_extract",
                    provider=provider or "openai",
                    model=model_override or "",
                    prompt_text=prompt,
                    response_text="",
                    latency_ms=0,
                    status=500,
                    estimated=True,
                )
            except Exception:
                pass
            logger.warning(f"Claim extraction via LLM failed: {e}")
            return await HeuristicSentenceExtractor().extract(answer, max_claims)


# --------------------------- Verifier ---------------------------

class HybridClaimVerifier:
    """Verify with numeric/date checks, retrieve evidence, then LLM-judge entailment."""

    def __init__(self, analyze_fn: Any, nli_model: Optional[str] = None):
        self._analyze = analyze_fn
        self._nli = None
        # Try to initialize local NLI model if available
        try:
            from transformers import pipeline  # type: ignore
            import os
            model_name = nli_model or os.environ.get("RAG_NLI_MODEL") or os.environ.get("RAG_NLI_MODEL_PATH") or "roberta-large-mnli"
            def _load():
                try:
                    return pipeline("text-classification", model=model_name, return_all_scores=True)
                except Exception as e:
                    logger.warning(f"NLI model load failed ({model_name}): {e}.")
                    return None
            loop = asyncio.get_event_loop()
            self._nli = loop.run_in_executor(None, _load)
        except Exception:
            self._nli = None

    async def _get_nli(self):
        if asyncio.isfuture(self._nli) or hasattr(self._nli, "__await__"):
            try:
                self._nli = await self._nli  # type: ignore
            except Exception:
                self._nli = None
        return self._nli

    @staticmethod
    def _nli_best_label(nli_scores: List[Dict[str, Any]]) -> Tuple[str, float]:
        label_map = {"entailment": "supported", "contradiction": "refuted", "neutral": "nei"}
        best = max(nli_scores, key=lambda x: x.get("score", 0.0))
        lab = label_map.get(str(best.get("label", "")).lower(), "nei")
        return lab, float(best.get("score", 0.0))

    async def verify(
        self,
        claim: Claim,
        query: str,
        base_documents: List[Document],
        retrieve_fn: Optional[Any] = None,
        top_k: int = 5,
        conf_threshold: float = 0.7,
        mode: str = "hybrid",
        budget: Optional[ClaimsJobBudget] = None,
        job_context: Optional[ClaimsJobContext] = None,
    ) -> ClaimVerification:
        claim_text = claim.text.strip()
        nums_dates = _extract_numbers_and_dates(claim_text)

        candidate_docs: List[Document] = []
        try:
            if retrieve_fn is not None:
                candidate_docs = await retrieve_fn(claim_text, top_k=top_k)
            else:
                candidate_docs = base_documents[:top_k] if base_documents else []
        except Exception as e:
            logger.warning(f"Claim-level retrieval failed, using base docs: {e}")
            candidate_docs = base_documents[:top_k] if base_documents else []

        def _score_doc(d: Document) -> float:
            score = float(getattr(d, "score", 0.0) or 0.0)
            bonus = 0.0
            if nums_dates["numbers"] and _contains_any(d.content, nums_dates["numbers"]):
                bonus += 0.2
            if nums_dates["dates"] and _contains_any(d.content, nums_dates["dates"]):
                bonus += 0.2
            return score + bonus

        candidate_docs = sorted(candidate_docs, key=_score_doc, reverse=True)
        evidence_snips = _first_n_snippets(candidate_docs, n=min(3, top_k))
        evidence_text = "\n\n".join([f"[doc:{e.doc_id}] {e.snippet}" for e in evidence_snips])
        # Map doc_id -> full text for citation offsets
        _doc_map: Dict[str, str] = {}
        try:
            for d in candidate_docs:
                _doc_map[str(getattr(d, "id", ""))] = getattr(d, "content", "") or ""
        except Exception:
            _doc_map = {}

        # NLI verification path (optional depending on mode)
        nli = None
        if mode in ("hybrid", "nli"):
            nli = await self._get_nli()
            nli_decision: Optional[Tuple[str, float, int]] = None
            if nli is not None:
                try:
                    best_tuple = ("nei", 0.0, -1)
                    for i, ev in enumerate(evidence_snips):
                        scores = nli({"text": ev.snippet, "text_pair": claim_text})
                        if isinstance(scores, list) and scores:
                            lab, sc = self._nli_best_label(scores[0])
                            if sc > best_tuple[1]:
                                best_tuple = (lab, sc, i)
                    if best_tuple[1] >= conf_threshold:
                        # Populate citations only for supported/refuted with best-effort exact offsets
                        cit: List[Dict[str, Any]] = []
                        if best_tuple[0] in {"supported", "refuted"}:
                            for ev in evidence_snips:
                                full = _doc_map.get(ev.doc_id, "")
                                s, e = _find_offsets(full, claim_text, ev.snippet)
                                cit.append({"doc_id": ev.doc_id, "start": int(s), "end": int(e)})
                        return ClaimVerification(
                            claim=claim,
                            label=best_tuple[0],
                            confidence=best_tuple[1],
                            evidence=evidence_snips,
                            citations=cit,
                            rationale=f"NLI-{best_tuple[0]} {best_tuple[1]:.2f}",
                        )
                    else:
                        nli_decision = best_tuple
                except Exception as e:
                    if mode == "hybrid":
                        logger.warning(f"NLI verification failed; falling back to LLM judge: {e}")
                    else:
                        logger.warning(f"NLI verification failed under nli mode: {e}")

            # If mode is strict NLI and we didn't return, finish with NEI (no LLM fallback)
            if mode == "nli":
                conf = 0.0
                if nli_decision is not None:
                    conf = float(nli_decision[1])
                return ClaimVerification(
                    claim=claim,
                    label="nei",
                    confidence=conf,
                    evidence=evidence_snips,
                    citations=[],
                    rationale="NLI unavailable/low confidence",
                )

        system = "You are a precise fact-checking judge. Output strict JSON only."
        judge_prompt = (
            "Given the EVIDENCE snippets and a CLAIM, decide if the claim is Supported, Refuted, or NotEnoughInfo. "
            "Return JSON as {\"label\": \"supported|refuted|nei\", \"confidence\": float, \"rationale\": str}.\n\n"
            f"CLAIM: {claim_text}\n\nEVIDENCE:\n{evidence_text}"
        )
        label = "nei"
        confidence = 0.5
        rationale = None
        provider, model_override, temperature = _resolve_claims_llm_config()
        cost_estimate = estimate_claims_cost(
            provider=provider or "openai",
            model=model_override or "",
            text=f"{system}\n{judge_prompt}",
        )
        budget_ratio = budget.remaining_ratio() if budget is not None else None
        throttle, reason = should_throttle_claims_provider(
            provider=provider or "openai",
            model=model_override or "",
            budget_ratio=budget_ratio,
        )
        if throttle:
            record_claims_throttle(
                provider=provider or "openai",
                model=model_override or "",
                mode="verify",
                reason=reason or "throttle",
            )
            return ClaimVerification(
                claim=claim,
                label="nei",
                confidence=0.0,
                evidence=evidence_snips,
                citations=[],
                rationale="Throttled by provider health",
            )
        if budget is not None:
            prompt_tokens = estimate_claims_tokens(judge_prompt)
            if not budget.reserve(cost_usd=cost_estimate, tokens=prompt_tokens):
                record_claims_budget_exhausted(
                    provider=provider or "openai",
                    model=model_override or "",
                    mode="verify",
                    reason=budget.exhausted_reason or "budget",
                )
                return ClaimVerification(
                    claim=claim,
                    label="nei",
                    confidence=0.0,
                    evidence=evidence_snips,
                    citations=[],
                    rationale="Budget exhausted",
                )
        try:
            start_time = time.time()
            raw = await asyncio.to_thread(
                self._analyze,
                provider or "openai",
                claim_text,
                judge_prompt,
                None,
                system,
                temperature,
                model_override=model_override,
            )
            latency_s = time.time() - start_time
            record_claims_provider_request(
                provider=provider or "openai",
                model=model_override or "",
                mode="verify",
                latency_s=latency_s,
                estimated_cost=cost_estimate,
            )
            text = raw if isinstance(raw, str) else str(raw)
            if budget is not None:
                budget.add_usage(tokens=estimate_claims_tokens(text))
            try:
                await _log_claims_llm_usage(
                    job_context=job_context,
                    operation="claims_verify",
                    provider=provider or "openai",
                    model=model_override or "",
                    prompt_text=judge_prompt,
                    response_text=text,
                    latency_ms=int(latency_s * 1000),
                    status=200,
                    estimated=True,
                )
            except Exception:
                pass
            # Parse fenced JSON if present
            jtxt = None
            fence_json = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
            for block in fence_json or []:
                try:
                    _ = json.loads(block)
                    jtxt = block
                    break
                except Exception:
                    continue
            if jtxt is None:
                m = re.search(r"\{[\s\S]*\}\s*$", text)
                jtxt = m.group(0) if m else text
            data = json.loads(jtxt)
            lab = str(data.get("label", "nei")).lower().strip()
            if lab in {"supported", "refuted", "nei"}:
                label = lab
            confidence = float(data.get("confidence", confidence))
            rationale = data.get("rationale")
        except Exception as e:
            record_claims_provider_request(
                provider=provider or "openai",
                model=model_override or "",
                mode="verify",
                latency_s=None,
                error=str(e),
                estimated_cost=cost_estimate,
            )
            try:
                await _log_claims_llm_usage(
                    job_context=job_context,
                    operation="claims_verify",
                    provider=provider or "openai",
                    model=model_override or "",
                    prompt_text=judge_prompt,
                    response_text="",
                    latency_ms=0,
                    status=500,
                    estimated=True,
                )
            except Exception:
                pass
            logger.warning(f"LLM judge failed; defaulting to NEI: {e}")
        # Construct citations for traceability (doc IDs with snippet offsets)
        citations: List[Dict[str, Any]] = []
        if label in {"supported", "refuted"}:
            for ev in evidence_snips:
                full = _doc_map.get(ev.doc_id, "")
                s, e = _find_offsets(full, claim_text, ev.snippet)
                citations.append({"doc_id": ev.doc_id, "start": int(s), "end": int(e)})

        return ClaimVerification(
            claim=claim,
            label=label,
            confidence=max(0.0, min(1.0, confidence)),
            evidence=evidence_snips,
            citations=citations,
            rationale=rationale,
        )


class ClaimsEngine:
    """High-level entry: extracts and verifies claims for a generated answer."""

    def __init__(self, analyze_fn: Any):
        self.extractor_llm = LLMBasedClaimExtractor(analyze_fn)
        self.extractor_heur = HeuristicSentenceExtractor()
        self._analyze = analyze_fn
        self.verifier = HybridClaimVerifier(analyze_fn)

    async def run(
        self,
        answer: str,
        query: str,
        documents: List[Document],
        claim_extractor: str = "auto",
        claim_verifier: str = "hybrid",
        claims_top_k: int = 5,
        claims_conf_threshold: float = 0.7,
        claims_max: int = 25,
        retrieve_fn: Optional[Any] = None,
        nli_model: Optional[str] = None,
        claims_concurrency: int = 8,
        job_budget: Optional[ClaimsJobBudget] = None,
        job_context: Optional[ClaimsJobContext] = None,
    ) -> Dict[str, Any]:
        if not answer or not isinstance(answer, str):
            return {"claims": [], "summary": {}}

        budget = job_budget
        if budget is None:
            try:
                from tldw_Server_API.app.core.config import settings as _settings  # type: ignore
            except Exception:
                _settings = {}
            budget = resolve_claims_job_budget(settings=_settings)

        # choose extractor
        claims: List[Claim] = []
        extractor_mode = (claim_extractor or "auto").strip().lower()

        if extractor_mode == "ner":
            # NER-assisted sentence selection: keep sentences with named entities
            try:
                import spacy  # type: ignore
                try:
                    from tldw_Server_API.app.core.config import settings as _settings  # type: ignore
                except Exception:
                    _settings = {}
                model_name = None
                try:
                    model_name = str(_settings.get("CLAIMS_LOCAL_NER_MODEL", "en_core_web_sm") or "en_core_web_sm")
                except Exception:
                    model_name = "en_core_web_sm"

                try:
                    nlp = spacy.load(model_name)
                except Exception:
                    nlp = spacy.blank("en")
                    if not nlp.has_pipe("sentencizer"):
                        nlp.add_pipe("sentencizer")

                doc = nlp(answer)
                sents_text: List[str] = []
                for sent in getattr(doc, "sents", [doc]):
                    has_ent = any(getattr(ent, "label_", "") for ent in getattr(sent, "ents", []))
                    if has_ent:
                        st = sent.text.strip()
                        if len(st) >= 12:
                            sents_text.append(st)
                    if len(sents_text) >= claims_max:
                        break
                claims = [Claim(id=f"c{i+1}", text=t) for i, t in enumerate(sents_text[:claims_max])]
                if not claims:
                    # If no entities detected, fall back to LLM extractor
                    claims = await self.extractor_llm.extract(
                        answer,
                        max_claims=claims_max,
                        budget=budget,
                        job_context=job_context,
                    )
            except Exception as e:
                logger.warning(f"NER extractor unavailable/failed: {e}; falling back to LLM extractor")
                claims = await self.extractor_llm.extract(
                    answer,
                    max_claims=claims_max,
                    budget=budget,
                    job_context=job_context,
                )

        elif extractor_mode == "aps":
            # APS-style proposition extraction via PropositionChunkingStrategy (LLM engine, gemma_aps prompt)
            try:
                from tldw_Server_API.app.core.Chunking.strategies.propositions import (
                    PropositionChunkingStrategy,
                )

                # Load provider/model/temp from config.txt with sensible fallbacks
                try:
                    from tldw_Server_API.app.core.config import settings as _settings  # type: ignore
                except Exception:
                    _settings = {}

                provider = None
                model_override = None
                temperature = 0.2
                try:
                    provider = str(_settings.get("CLAIMS_LLM_PROVIDER", "")).strip() or None
                except Exception:
                    provider = None
                try:
                    model_override = str(_settings.get("CLAIMS_LLM_MODEL", "")).strip() or None
                except Exception:
                    model_override = None
                try:
                    temperature = float(_settings.get("CLAIMS_LLM_TEMPERATURE", 0.2))
                except Exception:
                    temperature = 0.2

                # Fallbacks to RAG defaults then global default_api
                if provider is None:
                    try:
                        rag_cfg = _settings.get("RAG", {}) or {}
                        provider = str(rag_cfg.get("default_llm_provider", "")).strip() or None
                    except Exception:
                        provider = None
                if provider is None:
                    try:
                        provider = str(_settings.get("default_api", "openai")).strip() or "openai"
                    except Exception:
                        provider = "openai"
                if model_override is None:
                    try:
                        rag_cfg = _settings.get("RAG", {}) or {}
                        model_override = str(rag_cfg.get("default_llm_model", "")).strip() or None
                    except Exception:
                        model_override = None

                strategy = PropositionChunkingStrategy(
                    language="en",
                    llm_call_func=self._analyze,
                    llm_config={
                        "window_chars": 1200,
                        "api_name": provider or "openai",
                        "temp": temperature,
                        "model_override": model_override,
                    },
                )
                # Use max_size=1 so each proposition becomes its own unit
                prop_chunks = strategy.chunk(
                    text=answer,
                    max_size=1,
                    overlap=0,
                    engine="llm",
                    proposition_prompt_profile="gemma_aps",
                )
                for i, ptxt in enumerate((prop_chunks or [])[:claims_max]):
                    if isinstance(ptxt, str) and ptxt.strip():
                        claims.append(Claim(id=f"c{i+1}", text=ptxt.strip()))
            except Exception as e:
                logger.warning(f"APS extractor failed, falling back to LLM extractor: {e}")
                claims = await self.extractor_llm.extract(
                    answer,
                    max_claims=claims_max,
                    budget=budget,
                    job_context=job_context,
                )
        else:
            # default to LLM-based claim extraction (claimify/generic)
            claims = await self.extractor_llm.extract(
                answer,
                max_claims=claims_max,
                budget=budget,
                job_context=job_context,
            )
        verifications: List[ClaimVerification] = []

        # Initialize verifier once if a specific NLI model is requested
        if nli_model:
            self.verifier = HybridClaimVerifier(self._analyze, nli_model=nli_model)

        async def _verify_one(c: Claim) -> ClaimVerification:
            return await self.verifier.verify(
                claim=c,
                query=query,
                base_documents=documents,
                retrieve_fn=retrieve_fn,
                top_k=claims_top_k,
                conf_threshold=claims_conf_threshold,
                mode=(claim_verifier or "hybrid").strip().lower(),
                budget=budget,
                job_context=job_context,
            )

        # Concurrency cap to avoid over-parallelization of verifications
        try:
            max_conc = int(claims_concurrency)
        except Exception:
            max_conc = 8
        max_conc = max(1, min(32, max_conc))
        try:
            provider, model_override, _ = _resolve_claims_llm_config()
            budget_ratio = budget.remaining_ratio() if budget is not None else None
            max_conc = suggest_claims_concurrency(
                provider=provider,
                model=model_override or "",
                requested=max_conc,
                budget_ratio=budget_ratio,
            )
        except Exception:
            pass
        sem = asyncio.Semaphore(max_conc)

        async def _bounded_verify(c: Claim) -> ClaimVerification:
            async with sem:
                return await _verify_one(c)

        tasks = [_bounded_verify(c) for c in claims]
        if tasks:
            verifications = await asyncio.gather(*tasks)

        supported = sum(1 for v in verifications if v.label == "supported")
        refuted = sum(1 for v in verifications if v.label == "refuted")
        nei = sum(1 for v in verifications if v.label == "nei")
        total = max(1, len(verifications))
        precision = supported / total
        coverage = (supported + refuted) / total

        claims_out: List[Dict[str, Any]] = []
        for v in verifications:
            claims_out.append(
                {
                    "id": v.claim.id,
                    "text": v.claim.text,
                    "span": list(v.claim.span) if v.claim.span else None,
                    "label": v.label,
                    "confidence": v.confidence,
                    "evidence": [
                        {"doc_id": e.doc_id, "snippet": e.snippet, "score": e.score} for e in v.evidence
                    ],
                    "citations": v.citations,
                    "rationale": v.rationale,
                }
            )

        return {
            "claims": claims_out,
            "summary": {
                "supported": supported,
                "refuted": refuted,
                "nei": nei,
                "precision": precision,
                "coverage": coverage,
                # claim_faithfulness: fraction of supported among all verified claims
                "claim_faithfulness": (supported / total) if total else 0.0,
                "budget": (budget.snapshot() if budget is not None else None),
            },
        }
