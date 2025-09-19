"""
claims_engine.py - Claim extraction and verification (moved from RAG module)

This module centralizes claim extraction & verification logic under the
Ingestion_Media_Processing namespace so it can be used at ingestion time
and by RAG pipelines. It mirrors the functionality that existed in
app/core/RAG/rag_service/claims.py and is designed to be extended.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple

from loguru import logger
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
    async def extract(self, answer: str, max_claims: int = 25) -> List[Claim]:
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

    async def extract(self, answer: str, max_claims: int = 25) -> List[Claim]:
        if not answer:
            return []
        system = load_prompt("ingestion", "claims_extractor_system") or (
            "You extract specific, verifiable, decontextualized factual propositions. Output strict JSON."
        )
        base = load_prompt("ingestion", "claims_extractor_prompt") or (
            "Extract up to {max_claims} atomic factual propositions from the ANSWER. "
            "Each proposition should stand alone without the surrounding context, be specific and checkable. "
            "Return JSON: {\"claims\":[{\"text\":str}]}. Do not include explanations.\n\nANSWER:\n{answer}"
        )
        prompt = base.format(max_claims=max_claims, answer=answer)

        try:
            raw = await asyncio.to_thread(self._analyze, "openai", answer, prompt, None, system, 0.1)
            text = raw if isinstance(raw, str) else str(raw)
            # find JSON block
            jtxt = text
            m = re.search(r"\{[\s\S]*\}\s*$", text)
            if m:
                jtxt = m.group(0)
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

        # NLI first, if available
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
                    return ClaimVerification(
                        claim=claim,
                        label=best_tuple[0],
                        confidence=best_tuple[1],
                        evidence=evidence_snips,
                        citations=[],
                        rationale=f"NLI-{best_tuple[0]} {best_tuple[1]:.2f}",
                    )
                else:
                    nli_decision = best_tuple
            except Exception as e:
                logger.warning(f"NLI verification failed; falling back to LLM judge: {e}")

        system = "You are a precise fact-checking judge. Output strict JSON only."
        judge_prompt = (
            "Given the EVIDENCE snippets and a CLAIM, decide if the claim is Supported, Refuted, or NotEnoughInfo. "
            "Return JSON as {\"label\": \"supported|refuted|nei\", \"confidence\": float, \"rationale\": str}.\n\n"
            f"CLAIM: {claim_text}\n\nEVIDENCE:\n{evidence_text}"
        )
        label = "nei"
        confidence = 0.5
        rationale = None
        try:
            raw = await asyncio.to_thread(self._analyze, "openai", claim_text, judge_prompt, None, system, 0.1)
            text = raw if isinstance(raw, str) else str(raw)
            m = re.search(r"\{[\s\S]*\}\s*$", text)
            jtxt = m.group(0) if m else text
            data = json.loads(jtxt)
            lab = str(data.get("label", "nei")).lower().strip()
            if lab in {"supported", "refuted", "nei"}:
                label = lab
            confidence = float(data.get("confidence", confidence))
            rationale = data.get("rationale")
        except Exception as e:
            logger.warning(f"LLM judge failed; defaulting to NEI: {e}")
        return ClaimVerification(
            claim=claim,
            label=label,
            confidence=max(0.0, min(1.0, confidence)),
            evidence=evidence_snips,
            citations=[],
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
    ) -> Dict[str, Any]:
        if not answer or not isinstance(answer, str):
            return {"claims": [], "summary": {}}

        # choose extractor
        if claim_extractor == "claimify":
            extractor = self.extractor_llm
        elif claim_extractor == "aps":
            extractor = self.extractor_llm
        else:
            extractor = self.extractor_llm

        claims = await extractor.extract(answer, max_claims=claims_max)
        verifications: List[ClaimVerification] = []

        async def _verify_one(c: Claim) -> ClaimVerification:
            if nli_model:
                self.verifier = HybridClaimVerifier(self._analyze, nli_model=nli_model)
            return await self.verifier.verify(
                claim=c,
                query=query,
                base_documents=documents,
                retrieve_fn=retrieve_fn,
                top_k=claims_top_k,
                conf_threshold=claims_conf_threshold,
            )

        tasks = [_verify_one(c) for c in claims]
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
            },
        }
