"""
ingestion_claims.py - Ingestion-time claim (factual statement) extraction utilities.

Stage 2 MVP: Heuristic extraction of short factual sentences from chunks,
with storage in MediaDatabase.Claims. Optional, behind config flags.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from loguru import logger
from tldw_Server_API.app.core.config import settings as _settings
from tldw_Server_API.app.core.Utils.prompt_loader import load_prompt

try:
    # Local import for DB helper
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
except Exception:  # pragma: no cover
    MediaDatabase = None  # type: ignore




def extract_claims_for_chunks(
    chunks: List[Dict[str, Any]],
    *,
    extractor_mode: str = "heuristic",
    max_per_chunk: int = 3,
) -> List[Dict[str, Any]]:
    """
    Extract a small set of candidate factual statements per chunk.

    Returns items with: chunk_index, claim_text.
    """
    claims: List[Dict[str, Any]] = []
    for ch in chunks or []:
        txt = (ch or {}).get("text") or (ch or {}).get("content") or ""
        meta = (ch or {}).get("metadata", {}) or {}
        idx = int(meta.get("chunk_index") or meta.get("index") or 0)
        mode = (extractor_mode or "heuristic").strip().lower()

        # Heuristic (default)
        if mode in {"heuristic", "simple"}:
            # Deterministic sync path: replicate heuristic sentence splitting without asyncio
            sents: List[str] = []
            parts = re.split(r"(?<=[\.!?])\s+", (txt or "").strip())
            for p in parts:
                t = (p or "").strip()
                if len(t) >= 12:
                    sents.append(t)
                if len(sents) >= max_per_chunk:
                    break
        elif mode == "ner":
            # NER-assisted selection: keep sentences with named entities
            sents = []
            try:
                import spacy  # type: ignore
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
                    parts = re.split(r"(?<=[\.!?])\s+", (txt or "").strip())
                    for p in parts:
                        t = (p or "").strip()
                        if len(t) >= 12:
                            sents.append(t)
                        if len(sents) >= max_per_chunk:
                            break
            except Exception as e:
                logger.debug(f"NER-assisted extraction failed: {e}; falling back to heuristic")
                sents = []
                parts = re.split(r"(?<=[\.!?])\s+", (txt or "").strip())
                for p in parts:
                    t = (p or "").strip()
                    if len(t) >= 12:
                        sents.append(t)
                    if len(sents) >= max_per_chunk:
                        break

        # LLM-based extractor via unified chat API (LLM_Calls)
        else:
            sents = []
            try:
                import concurrent.futures as _futures
                import threading as _threading

                # Resolve chat API call with a module-level override for tests
                def _resolve_chat_call():
                    fn = globals().get("chat_api_call")
                    if callable(fn):
                        return fn
                    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call as _cac  # type: ignore
                    return _cac

                # Determine provider: explicit mode may be a provider name; otherwise use config
                provider = mode if mode in {
                    "openai", "anthropic", "cohere", "google", "groq", "huggingface",
                    "openrouter", "deepseek", "mistral", "ollama", "kobold", "ooba",
                    "tabbyapi", "vllm", "custom-openai-api", "custom-openai-api-2", "local-llm", "llama.cpp"
                } else str(_settings.get("CLAIMS_LLM_PROVIDER", "openai")).lower()

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

                def _call_provider():
                    _cac = _resolve_chat_call()
                    return _cac(
                        api_endpoint=provider,
                        messages_payload=messages,
                        api_key=None,
                        temp=temperature,
                        system_message=system,
                        streaming=False,
                        model=model_override,
                    )

                with _futures.ThreadPoolExecutor(max_workers=1) as _exec:
                    fut = _exec.submit(_call_provider)
                    try:
                        resp = fut.result(timeout=timeout_sec)
                    except _futures.TimeoutError:
                        try:
                            fut.cancel()
                        except Exception:
                            pass
                        raise TimeoutError(f"LLM extraction timed out after {timeout_sec:.1f}s for provider '{provider}'.")

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
                    parts = re.split(r"(?<=[\.!?])\s+", (txt or "").strip())
                    for p in parts:
                        t = (p or "").strip()
                        if len(t) >= 12:
                            sents.append(t)
                        if len(sents) >= max_per_chunk:
                            break
            except Exception as e:
                logger.debug(f"LLM-based claim extraction failed ({mode}): {e}; falling back to heuristic")
                sents = []
                parts = re.split(r"(?<=[\.!?])\s+", (txt or "").strip())
                for p in parts:
                    t = (p or "").strip()
                    if len(t) >= 12:
                        sents.append(t)
                    if len(sents) >= max_per_chunk:
                        break
        for s in sents:
            claims.append({"chunk_index": idx, "claim_text": s})
    return claims


def store_claims(
    db: "MediaDatabase",
    *,
    media_id: int,
    chunk_texts_by_index: Dict[int, str],
    claims: List[Dict[str, Any]],
    extractor: str = "heuristic",
    extractor_version: str = "v1",
) -> int:
    """
    Store extracted claims into Claims table via MediaDatabase.upsert_claims.
    Computes chunk_hash from the chunk text for linkage.
    """
    if not claims:
        return 0
    rows: List[Dict[str, Any]] = []
    for c in claims:
        idx = int(c.get("chunk_index", 0))
        ctext = str(c.get("claim_text", ""))
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
        })
    try:
        inserted = db.upsert_claims(rows)
        return inserted
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to store claims for media_id={media_id}: {e}")
        return 0
