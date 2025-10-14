"""
Post-generation verification and adaptive repair for RAG answers.

This module provides a lightweight interface to verify a generated answer
against retrieved documents, and optionally attempt a targeted repair pass
when evidence is insufficient.

Design goals:
- Pluggable: accept an injected claims runner for unit tests
- Minimal coupling: reuse existing ClaimsEngine when available
- Guarded by feature flags and strict time/attempt budgets
- Export central metrics for observability
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable

from loguru import logger

# Prefer RAG types if available, else fallback
try:
    from .types import Document, DataSource
except Exception:  # pragma: no cover - fallback for isolated tests
    from dataclasses import dataclass as _dc
    @_dc
    class Document:  # type: ignore
        id: str
        content: str
        metadata: Dict[str, Any]
        score: float = 0.0
    class DataSource:  # type: ignore
        MEDIA_DB = "media_db"


try:
    # Claims engine used for extraction and verification
    from .claims import ClaimsEngine
except Exception:
    ClaimsEngine = None  # type: ignore

try:
    # Retrieval building blocks
    from .database_retrievers import MultiDatabaseRetriever, RetrievalConfig
except Exception:
    MultiDatabaseRetriever = None  # type: ignore
    RetrievalConfig = None  # type: ignore

try:
    # Answer generation used for repair regeneration
    from .generation import AnswerGenerator
except Exception:
    AnswerGenerator = None  # type: ignore

try:
    # Central metrics registry (Prometheus/OTel)
    from tldw_Server_API.app.core.Metrics.metrics_manager import (
        increment_counter,
        observe_histogram,
    )
except Exception:  # pragma: no cover
    def increment_counter(*args, **kwargs):  # type: ignore
        return None
    def observe_histogram(*args, **kwargs):  # type: ignore
        return None


@dataclass
class VerificationOutcome:
    unsupported_ratio: float
    total_claims: int
    unsupported_count: int
    fixed: bool
    reason: str = ""
    new_answer: Optional[str] = None
    claims: Optional[List[Dict[str, Any]]] = None
    summary: Optional[Dict[str, Any]] = None


class PostGenerationVerifier:
    """Verify a generated answer and optionally perform an adaptive repair pass."""

    def __init__(
        self,
        claims_runner: Optional[Callable[..., Any]] = None,
        max_retries: int = 1,
        unsupported_threshold: float = 0.15,
        max_claims: int = 20,
        time_budget_sec: Optional[float] = None,
    ):
        self._claims_runner = claims_runner
        self._max_retries = max(0, int(max_retries or 0))
        try:
            self._threshold = float(unsupported_threshold)
        except Exception:
            self._threshold = 0.15
        self._max_claims = max(1, int(max_claims or 1))
        self._time_budget = float(time_budget_sec) if time_budget_sec is not None else None

    async def verify_and_maybe_fix(
        self,
        query: str,
        answer: Optional[str],
        base_documents: List[Document],
        *,
        media_db_path: Optional[str] = None,
        notes_db_path: Optional[str] = None,
        character_db_path: Optional[str] = None,
        user_id: Optional[str] = None,
        generation_model: Optional[str] = None,
        existing_claims: Optional[List[Dict[str, Any]]] = None,
        existing_summary: Optional[Dict[str, Any]] = None,
        search_mode: str = "hybrid",
        hybrid_alpha: float = 0.7,
        top_k: int = 10,
    ) -> VerificationOutcome:
        """Run post-generation verification and, if needed, a single repair attempt.

        Returns a VerificationOutcome with summary and optional new answer.
        """
        start_ts = time.time()
        outcome = VerificationOutcome(
            unsupported_ratio=0.0,
            total_claims=0,
            unsupported_count=0,
            fixed=False,
            reason="",
            new_answer=None,
            claims=None,
            summary=None,
        )

        if not answer or not isinstance(answer, str) or answer.strip() == "":
            observe_histogram("rag_postcheck_duration_seconds", time.time() - start_ts, labels={"outcome": "skipped"})
            outcome.reason = "empty_answer"
            return outcome

        # Run or reuse claims verification
        claims_payload: Optional[List[Dict[str, Any]]] = existing_claims
        summary_payload: Optional[Dict[str, Any]] = existing_summary
        try:
            if (claims_payload is None or summary_payload is None):
                if self._claims_runner is not None:
                    # Injectable runner (testing)
                    run = await _maybe_await(self._claims_runner(
                        query=query,
                        answer=answer,
                        documents=base_documents,
                        claims_max=self._max_claims,
                    ))
                    claims_payload = (run or {}).get("claims")
                    summary_payload = (run or {}).get("summary")
                elif ClaimsEngine is not None:
                    # Use default analyze function
                    import tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib as sgl  # type: ignore
                    def _analyze(api_name: str, input_data: Any, custom_prompt_arg: Optional[str] = None,
                                 api_key: Optional[str] = None, system_message: Optional[str] = None,
                                 temp: Optional[float] = None, **kwargs):
                        return sgl.analyze(api_name, input_data, custom_prompt_arg, api_key, system_message, temp, **kwargs)

                    engine = ClaimsEngine(_analyze)

                    # Build a claim-level retrieval function
                    async def _retrieve_for_claim(c_text: str, top: int = 5):
                        try:
                            if MultiDatabaseRetriever is None:
                                return base_documents[:top]
                            db_paths = {}
                            if media_db_path:
                                db_paths["media_db"] = media_db_path
                            if notes_db_path:
                                db_paths["notes_db"] = notes_db_path
                            if character_db_path:
                                db_paths["character_cards_db"] = character_db_path
                            mdr = MultiDatabaseRetriever(
                                db_paths,
                                user_id=user_id or "0",
                            )
                            med = mdr.retrievers.get(getattr(DataSource, "MEDIA_DB", "media_db"))
                            docs: List[Document] = []
                            if med is not None:
                                rh = getattr(med, 'retrieve_hybrid', None)
                                if rh is not None and asyncio.iscoroutinefunction(rh) and search_mode == "hybrid":
                                    docs.extend(await rh(query=c_text, alpha=hybrid_alpha))
                                else:
                                    docs.extend(await med.retrieve(query=c_text))
                            # Other sources could be added similarly
                            docs = sorted(docs, key=lambda d: getattr(d, 'score', 0.0), reverse=True)
                            return docs[:top]
                        except Exception:
                            return base_documents[:top]

                    run = await engine.run_verification(
                        answer=answer,
                        query=query,
                        documents=base_documents,
                        claim_extractor="auto",
                        claim_verifier="hybrid",
                        claims_top_k=5,
                        claims_conf_threshold=0.7,
                        claims_max=self._max_claims,
                        retrieve_fn=_retrieve_for_claim,
                        nli_model=os.getenv("RAG_NLI_MODEL") or os.getenv("RAG_NLI_MODEL_PATH"),
                        claims_concurrency=8,
                    )
                    claims_payload = (run or {}).get("claims")
                    summary_payload = (run or {}).get("summary")
        except Exception as e:
            logger.warning(f"Post-check claims verification failed: {e}")

        # Compute unsupported ratio
        unsupported = 0
        total = 0
        try:
            if isinstance(summary_payload, dict):
                supported = int(summary_payload.get("supported") or 0)
                refuted = int(summary_payload.get("refuted") or 0)
                nei = int(summary_payload.get("nei") or 0)
                total = max(0, supported + refuted + nei)
                unsupported = max(0, refuted + nei)
        except Exception:
            pass
        ratio = (unsupported / total) if total else 0.0

        outcome.unsupported_ratio = ratio
        outcome.total_claims = total
        outcome.unsupported_count = unsupported
        outcome.claims = claims_payload
        outcome.summary = summary_payload

        # Record metrics for unsupported claims
        try:
            if unsupported > 0:
                increment_counter("rag_unsupported_claims_total", unsupported)
        except Exception:
            pass

        # Decide if we should attempt a repair
        if ratio <= self._threshold or self._max_retries <= 0:
            observe_histogram("rag_postcheck_duration_seconds", time.time() - start_ts, labels={"outcome": "ok"})
            outcome.reason = "threshold_not_exceeded" if ratio <= self._threshold else "no_retries"
            return outcome

        # Attempt a single adaptive retrieval + regeneration pass (bounded)
        retries = 0
        fixed = False
        new_answer: Optional[str] = None
        while retries < self._max_retries:
            retries += 1
            increment_counter("rag_adaptive_retries_total", 1)

            if self._time_budget is not None and (time.time() - start_ts) > self._time_budget:
                outcome.reason = "time_budget_exhausted"
                break

            # Minimal second-chance retrieval: run hybrid over media_db if available
            new_docs: List[Document] = base_documents[:]
            try:
                if MultiDatabaseRetriever is not None and media_db_path:
                    mdr = MultiDatabaseRetriever({"media_db": media_db_path}, user_id=user_id or "0")
                    med = mdr.retrievers.get(getattr(DataSource, "MEDIA_DB", "media_db"))
                    if med is not None:
                        rh = getattr(med, 'retrieve_hybrid', None)
                        if rh is not None and asyncio.iscoroutinefunction(rh) and search_mode == "hybrid":
                            new_docs = await rh(query=query, alpha=min(max(hybrid_alpha, 0.1), 0.9))
                        else:
                            new_docs = await med.retrieve(query=query)
                        # Cap docs
                        new_docs = new_docs[: max(5, min(15, top_k))]
            except Exception as e:
                logger.debug(f"Adaptive retrieval failed; using base docs. Reason: {e}")
                new_docs = base_documents[:]

            # Regenerate if possible
            try:
                if AnswerGenerator is not None:
                    gen = AnswerGenerator(model=generation_model)
                    context = "\n\n".join([getattr(d, 'content', '') for d in new_docs[:5]])
                    maybe = await gen.generate(query=query, context=context, prompt_template=None, max_tokens=500)
                    new_answer = maybe.get("answer") if isinstance(maybe, dict) else str(maybe)
                else:
                    new_answer = None
            except Exception as e:
                logger.debug(f"Adaptive regeneration failed: {e}")
                new_answer = None

            # If we couldn't regenerate, stop
            if not new_answer:
                outcome.reason = "regen_failed"
                break

            # Re-check quickly with limited claims
            try:
                # Use same runner to compute a small verification sample
                if self._claims_runner is not None:
                    run2 = await _maybe_await(self._claims_runner(
                        query=query,
                        answer=new_answer,
                        documents=new_docs,
                        claims_max=max(5, min(10, self._max_claims)),
                    ))
                    sum2 = (run2 or {}).get("summary") or {}
                elif ClaimsEngine is not None:
                    import tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib as sgl  # type: ignore
                    def _analyze2(api_name: str, input_data: Any, custom_prompt_arg: Optional[str] = None,
                                   api_key: Optional[str] = None, system_message: Optional[str] = None,
                                   temp: Optional[float] = None, **kwargs):
                        return sgl.analyze(api_name, input_data, custom_prompt_arg, api_key, system_message, temp, **kwargs)
                    eng2 = ClaimsEngine(_analyze2)
                    run2 = await eng2.run_verification(
                        answer=new_answer,
                        query=query,
                        documents=new_docs,
                        claim_extractor="auto",
                        claim_verifier="hybrid",
                        claims_top_k=5,
                        claims_conf_threshold=0.7,
                        claims_max=max(5, min(10, self._max_claims)),
                        retrieve_fn=None,
                        nli_model=os.getenv("RAG_NLI_MODEL") or os.getenv("RAG_NLI_MODEL_PATH"),
                        claims_concurrency=4,
                    )
                    sum2 = (run2 or {}).get("summary") or {}
                else:
                    sum2 = {}
            except Exception as e:
                logger.debug(f"Adaptive recheck failed: {e}")
                sum2 = {}

            try:
                s2_supported = int(sum2.get("supported") or 0)
                s2_refuted = int(sum2.get("refuted") or 0)
                s2_nei = int(sum2.get("nei") or 0)
                s2_total = max(0, s2_supported + s2_refuted + s2_nei)
                s2_ratio = ((s2_refuted + s2_nei) / s2_total) if s2_total else 0.0
            except Exception:
                s2_ratio = 0.0

            if s2_ratio <= self._threshold:
                fixed = True
                break
            else:
                # Try next retry if allowed
                continue

        outcome.fixed = fixed
        if fixed and new_answer:
            outcome.new_answer = new_answer
            try:
                increment_counter("rag_adaptive_fix_success_total", 1)
            except Exception:
                pass
            observe_histogram("rag_postcheck_duration_seconds", time.time() - start_ts, labels={"outcome": "fixed"})
        else:
            observe_histogram("rag_postcheck_duration_seconds", time.time() - start_ts, labels={"outcome": "unfixed"})

        return outcome


async def _maybe_await(value):  # pragma: no cover - trivial helper
    if asyncio.iscoroutine(value):
        return await value
    return value

