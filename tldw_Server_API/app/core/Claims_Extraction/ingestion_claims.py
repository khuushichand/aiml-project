"""
ingestion_claims.py - Ingestion-time claim (factual statement) extraction utilities.

Stage 2 MVP: Heuristic extraction of short factual sentences from chunks,
with storage in MediaDatabase.Claims. Optional, behind config flags.
"""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
from tldw_Server_API.app.core.Claims_Extraction.budget_guard import (
    ClaimsJobBudget,
    ClaimsJobContext,
    estimate_claims_tokens,
)
from tldw_Server_API.app.core.Claims_Extraction.extractor_catalog import (
    LLM_PROVIDER_MODES,
    detect_claims_language,
    get_spacy_pipeline,
    resolve_claims_extractor_mode,
    resolve_ner_model_name,
    split_claims_sentences,
)
from tldw_Server_API.app.core.Claims_Extraction.monitoring import (
    estimate_claims_cost,
    record_claims_budget_exhausted,
    record_claims_provider_request,
    record_claims_throttle,
    should_throttle_claims_provider,
)
from tldw_Server_API.app.core.Claims_Extraction.review_assignment import apply_review_rules
from tldw_Server_API.app.core.config import settings as _settings
from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
from tldw_Server_API.app.core.LLM_Calls.adapter_utils import (
    ensure_app_config,
    normalize_provider,
    resolve_provider_api_key_from_config,
    resolve_provider_model,
    split_system_message,
)
from tldw_Server_API.app.core.Utils.prompt_loader import load_prompt

try:
    # Local import for DB helper
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
except Exception:  # pragma: no cover
    MediaDatabase = None  # type: ignore




def extract_claims_for_chunks(
    chunks: list[dict[str, Any]],
    *,
    extractor_mode: str = "heuristic",
    max_per_chunk: int = 3,
    language: str | None = None,
    budget: ClaimsJobBudget | None = None,
    job_context: ClaimsJobContext | None = None,
) -> list[dict[str, Any]]:
    """
    Extract a small set of candidate factual statements per chunk.

    Returns items with: chunk_index, claim_text.
    """
    claims: list[dict[str, Any]] = []
    resolved_mode = (extractor_mode or "heuristic").strip().lower()
    resolved_language = (language or "").strip().lower() if language else None
    if resolved_mode in {"auto", "detect"}:
        combined_text = " ".join(
            str((ch or {}).get("text") or (ch or {}).get("content") or "").strip()
            for ch in (chunks or [])[:5]
        )
        resolved_mode, resolved_language = resolve_claims_extractor_mode(resolved_mode, combined_text)

    for ch in chunks or []:
        txt = (ch or {}).get("text") or (ch or {}).get("content") or ""
        meta = (ch or {}).get("metadata", {}) or {}
        idx = int(meta.get("chunk_index") or meta.get("index") or 0)
        mode = resolved_mode
        lang_hint = resolved_language or detect_claims_language(txt)

        # Heuristic (default)
        if mode in {"heuristic", "simple"}:
            # Deterministic sync path with language-aware sentence splitting
            sents = split_claims_sentences(txt, lang_hint, max_sentences=max_per_chunk)
        elif mode == "ner":
            # NER-assisted selection: keep sentences with named entities
            sents = []
            try:
                model_name = resolve_ner_model_name(lang_hint)
                nlp = get_spacy_pipeline(model_name, lang_hint)
                if nlp is None or not nlp.has_pipe("ner"):
                    raise RuntimeError("spaCy NER pipeline unavailable")
                doc = nlp(txt)
                for sent in getattr(doc, "sents", [doc]):
                    has_ent = any(getattr(ent, "label_", "") for ent in getattr(sent, "ents", []))
                    if has_ent:
                        st = sent.text.strip()
                        if len(st) >= 12:
                            sents.append(st)
                    if len(sents) >= max_per_chunk:
                        break
                if not sents:
                    # fallback to heuristic
                    sents = split_claims_sentences(txt, lang_hint, max_sentences=max_per_chunk)
            except Exception as e:
                logger.debug(f"NER-assisted extraction failed: {e}; falling back to heuristic")
                sents = split_claims_sentences(txt, lang_hint, max_sentences=max_per_chunk)

        # LLM-based extractor via unified chat API (LLM_Calls)
        else:
            sents = []
            try:
                cost_estimate = None
                import concurrent.futures as _futures

                # Determine provider: explicit mode may be a provider name; otherwise use config
                provider = mode if mode in LLM_PROVIDER_MODES else str(_settings.get("CLAIMS_LLM_PROVIDER", "openai")).lower()
                provider_name = normalize_provider(provider)

                model_override = str(_settings.get("CLAIMS_LLM_MODEL", "") or "") or None
                try:
                    temperature = float(_settings.get("CLAIMS_LLM_TEMPERATURE", 0.1))
                except Exception:
                    temperature = 0.1

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
                    prompt = base.format(max_claims=max_per_chunk, answer=txt)
                except Exception:
                    _tmpl = base.replace('{', '{{').replace('}', '}}')
                    _tmpl = _tmpl.replace('{{max_claims}}', '{max_claims}').replace('{{answer}}', '{answer}')
                    prompt = _tmpl.format(max_claims=max_per_chunk, answer=txt)

                # Sync call to provider
                messages = [{"role": "user", "content": prompt}]
                # Minimal timeout guard around provider call
                timeout_sec = 8.0
                try:
                    timeout_sec = float(_settings.get("CLAIMS_LLM_TIMEOUT_SEC", 8.0))
                except Exception:
                    timeout_sec = 8.0

                def _call_provider(
                    provider=provider,
                    messages=messages,
                    temperature=temperature,
                    system=system,
                    model_override=model_override,
                    provider_name=provider_name,
                    timeout_sec=timeout_sec,
                ):
                    override = globals().get("chat_api_call")
                    if callable(override):
                        return override(
                            api_endpoint=provider,
                            messages_payload=messages,
                            api_key=None,
                            temp=temperature,
                            system_message=system,
                            streaming=False,
                            model=model_override,
                        )

                    adapter = get_registry().get_adapter(provider_name)
                    if adapter is not None:
                        app_config = ensure_app_config()
                        resolved_model = model_override or resolve_provider_model(provider_name, app_config)
                        if not resolved_model:
                            raise ChatConfigurationError(
                                provider=provider_name,
                                message="Model is required for provider.",
                            )
                        system_message, cleaned_messages = split_system_message(
                            [{"role": "system", "content": system}] + messages if system else messages
                        )
                        request = {
                            "messages": cleaned_messages,
                            "system_message": system_message,
                            "model": resolved_model,
                            "api_key": resolve_provider_api_key_from_config(provider_name, app_config),
                            "temperature": temperature,
                            "app_config": app_config,
                        }
                        return adapter.chat(request, timeout=timeout_sec)

                    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call as _cac  # type: ignore
                    return _cac(
                        api_endpoint=provider,
                        messages_payload=messages,
                        api_key=None,
                        temp=temperature,
                        system_message=system,
                        streaming=False,
                        model=model_override,
                    )

                cost_estimate = estimate_claims_cost(
                    provider=provider,
                    model=model_override or "",
                    text=prompt,
                )
                skip_llm = False
                budget_ratio = budget.remaining_ratio() if budget is not None else None
                throttle, reason = should_throttle_claims_provider(
                    provider=provider,
                    model=model_override or "",
                    budget_ratio=budget_ratio,
                )
                if throttle:
                    record_claims_throttle(
                        provider=provider,
                        model=model_override or "",
                        mode="ingestion",
                        reason=reason or "throttle",
                    )
                    skip_llm = True
                if not skip_llm and budget is not None:
                    prompt_tokens = estimate_claims_tokens(prompt)
                    if not budget.reserve(cost_usd=cost_estimate, tokens=prompt_tokens):
                        record_claims_budget_exhausted(
                            provider=provider,
                            model=model_override or "",
                            mode="ingestion",
                            reason=budget.exhausted_reason or "budget",
                        )
                        skip_llm = True
                if skip_llm:
                    sents = split_claims_sentences(txt, lang_hint, max_sentences=max_per_chunk)
                else:
                    start_time = time.time()
                    with _futures.ThreadPoolExecutor(max_workers=1) as _exec:
                        fut = _exec.submit(_call_provider)
                        try:
                            resp = fut.result(timeout=timeout_sec)
                            record_claims_provider_request(
                                provider=provider,
                                model=model_override or "",
                                mode="ingestion",
                                latency_s=time.time() - start_time,
                                estimated_cost=cost_estimate,
                            )
                        except _futures.TimeoutError:
                            try:
                                fut.cancel()
                            except Exception:
                                pass
                            record_claims_provider_request(
                                provider=provider,
                                model=model_override or "",
                                mode="ingestion",
                                latency_s=None,
                                error="timeout",
                                estimated_cost=cost_estimate,
                            )
                            raise TimeoutError(
                                f"LLM extraction timed out after {timeout_sec:.1f}s for provider '{provider}'."
                            )

                    # Normalize response to string
                    if isinstance(resp, str):
                        text = resp
                    elif isinstance(resp, dict):
                        try:
                            choices = resp.get("choices") or []
                            if choices:
                                msg = choices[0].get("message") or {}
                                content = msg.get("content")
                                text = content if isinstance(content, str) else str(resp)
                            else:
                                text = str(resp)
                        except Exception:
                            text = str(resp)
                    else:
                        try:
                            text = "".join(list(resp))
                        except Exception:
                            text = str(resp)
                    if budget is not None:
                        budget.add_usage(tokens=estimate_claims_tokens(text))

                if not skip_llm:
                    # Extract JSON block (supports fenced code blocks and trailing text)
                    import json as _json
                    jtxt = None
                    # Prefer fenced blocks marked as json
                    fence_json = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
                    for block in fence_json or []:
                        try:
                            _ = _json.loads(block)
                            jtxt = block
                            break
                        except Exception:
                            continue
                    if jtxt is None:
                        # Fallback: last JSON-looking object in text
                        m = re.search(r"\{[\s\S]*\}\s*$", text)
                        jtxt = m.group(0) if m else text
                    data = _json.loads(jtxt)
                    for c in (data.get("claims") or [])[:max_per_chunk]:
                        t = (c or {}).get("text")
                        if isinstance(t, str) and t.strip():
                            sents.append(t.strip())
                    if not sents:
                        # fallback to heuristic
                        sents = split_claims_sentences(txt, lang_hint, max_sentences=max_per_chunk)
            except Exception as e:
                record_claims_provider_request(
                    provider=provider,
                    model=model_override or "",
                    mode="ingestion",
                    latency_s=None,
                    error=str(e),
                    estimated_cost=cost_estimate,
                )
                logger.debug(f"LLM-based claim extraction failed ({mode}): {e}; falling back to heuristic")
                sents = split_claims_sentences(txt, lang_hint, max_sentences=max_per_chunk)
        for s in sents:
            claims.append({"chunk_index": idx, "claim_text": s})
    return claims


def store_claims(
    db: MediaDatabase,
    *,
    media_id: int,
    chunk_texts_by_index: dict[int, str],
    claims: list[dict[str, Any]],
    extractor: str = "heuristic",
    extractor_version: str = "v1",
) -> int:
    """
    Store extracted claims into Claims table via MediaDatabase.upsert_claims.
    Computes chunk_hash from the chunk text for linkage.
    """
    if not claims:
        return 0
    rows: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    for c in claims:
        idx = int(c.get("chunk_index", 0))
        ctext = str(c.get("claim_text", ""))
        claim_uuid = str(c.get("uuid") or uuid.uuid4())
        c["uuid"] = claim_uuid
        chunk_txt = chunk_texts_by_index.get(idx, "")
        chash = hashlib.sha256(chunk_txt.encode()).hexdigest() if chunk_txt else hashlib.sha256(b"").hexdigest()
        rows.append({
            "media_id": int(media_id),
            "chunk_index": idx,
            "span_start": None,
            "span_end": None,
            "claim_text": ctext,
            "confidence": None,
            "extractor": extractor,
            "extractor_version": extractor_version,
            "chunk_hash": chash,
            "uuid": claim_uuid,
        })
    try:
        rows = apply_review_rules(db=db, claims=rows)
        for row in rows:
            if row.get("reviewer_id") is not None or row.get("review_group"):
                assignments.append(
                    {
                        "uuid": row.get("uuid"),
                        "reviewer_id": row.get("reviewer_id"),
                        "review_group": row.get("review_group"),
                    }
                )
        inserted = db.upsert_claims(rows)
        if assignments:
            from tldw_Server_API.app.core.Claims_Extraction.claims_notifications import (
                record_review_assignment_notifications,
            )
            owner_row = db.execute_query(
                "SELECT owner_user_id, client_id FROM Media WHERE id = ?",
                (int(media_id),),
            ).fetchone()
            owner_user_id = None
            client_id = None
            if owner_row:
                try:
                    owner_user_id = owner_row["owner_user_id"]
                    client_id = owner_row["client_id"]
                except Exception:
                    try:
                        owner_user_id = owner_row[0]
                    except Exception:
                        owner_user_id = None
                    try:
                        client_id = owner_row[1]
                    except Exception:
                        client_id = None
            if owner_user_id is None:
                owner_user_id = client_id or db.client_id
            notification_ids = record_review_assignment_notifications(
                db=db,
                owner_user_id=str(owner_user_id),
                assignments=assignments,
            )
            if notification_ids:
                from tldw_Server_API.app.core.Claims_Extraction.claims_notifications import (
                    dispatch_claim_review_notifications,
                )
                dispatch_claim_review_notifications(
                    db_path=str(db.db_path_str),
                    owner_user_id=str(owner_user_id),
                    notification_ids=notification_ids,
                )
        return inserted
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to store claims for media_id={media_id}: {e}")
        return 0
