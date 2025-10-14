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

        # LLM-based extractor via unified chat API (LLM_Calls)
        else:
            sents = []
            try:
                from tldw_Server_API.app.core.Chat.Chat_Functions import chat_api_call  # type: ignore

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
                    "Return JSON: {\"claims\":[{\"text\":str}]}. Do not include explanations.\n\nANSWER:\n{answer}"
                )
                prompt = base.format(max_claims=max_per_chunk, answer=txt)

                # Sync call to provider
                messages = [{"role": "user", "content": prompt}]
                resp = chat_api_call(
                    api_endpoint=provider,
                    messages_payload=messages,
                    api_key=None,
                    temp=temperature,
                    system_message=system,
                    streaming=False,
                    model=model_override,
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

                # Extract JSON block
                m = re.search(r"\{[\s\S]*\}\s*$", text)
                jtxt = m.group(0) if m else text
                import json as _json
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
