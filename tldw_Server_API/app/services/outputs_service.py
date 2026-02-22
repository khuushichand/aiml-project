from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path as PathlibPath
from typing import Any

from fastapi import HTTPException
from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment
from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import (
    DatabasePaths,
    normalize_output_storage_filename,
)
from tldw_Server_API.app.core.exceptions import InvalidStoragePathError

_OUTPUT_TEMPLATE_ENV = SandboxedEnvironment(autoescape=True, enable_async=False)
_OUTPUT_TEMPLATE_ENV.filters["markdown_link"] = lambda text, url: f"[{text}]({url})" if url else text

_OUTPUTS_JSON_PARSE_EXCEPTIONS = (TypeError, ValueError, json.JSONDecodeError)
_OUTPUTS_DB_FALLBACK_EXCEPTIONS = (
    AttributeError,
    KeyError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_OUTPUTS_TEMPLATE_EXCEPTIONS = (
    KeyError,
    TemplateError,
    TypeError,
    ValueError,
)


def _normalize_template_syntax(template_str: str) -> str:
    """Normalize JS-like operators inside Jinja blocks for output templates."""
    import re as _re

    def _norm_block(prefix: str, suffix: str, s: str) -> str:
        pattern = _re.compile(_re.escape(prefix) + r"\s*(.*?)\s*" + _re.escape(suffix), _re.DOTALL)

        def repl(m):
            inner = m.group(1)
            inner = inner.replace("||", " or ").replace("&&", " and ")
            return f"{prefix} {inner} {suffix}"

        return pattern.sub(repl, s)

    out = template_str
    out = _norm_block("{{", "}}", out)
    out = _norm_block("{%", "%}", out)
    return out


def _extract_output_byte_size(metadata_json: str | None) -> int | None:
    if not metadata_json:
        return None
    try:
        payload = json.loads(metadata_json)
    except _OUTPUTS_JSON_PARSE_EXCEPTIONS:
        return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get("byte_size")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _sum_audiobook_output_bytes_for_ids(cdb, user_id: int, ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join(["?"] * len(ids))
    total_bytes = 0
    try:
        rows = cdb.backend.execute(
            f"SELECT id, type, metadata_json, storage_path, deleted FROM outputs WHERE user_id = ? AND id IN ({placeholders})",  # nosec B608
            tuple([user_id] + list(ids)),
        ).rows
    except _OUTPUTS_DB_FALLBACK_EXCEPTIONS as exc:
        logger.warning("outputs_service: audiobook quota lookup failed: {}", exc)
        return 0
    outputs_dir = _outputs_dir_for_user(user_id)
    for row in rows:
        record = row if isinstance(row, dict) else {
            "type": row[1],
            "metadata_json": row[2],
            "storage_path": row[3],
            "deleted": row[4],
        }
        if int(record.get("deleted") or 0) != 0:
            continue
        type_value = record.get("type") or ""
        if not str(type_value).startswith("audiobook_"):
            continue
        size_bytes = _extract_output_byte_size(record.get("metadata_json"))
        if size_bytes is None:
            try:
                size_bytes = (outputs_dir / str(record.get("storage_path") or "")).stat().st_size
            except FileNotFoundError:
                continue
            except OSError as exc:
                logger.warning("outputs_service: failed to stat output for quota: {}", exc)
                continue
        if size_bytes:
            total_bytes += size_bytes
    return total_bytes


def render_output_template(template_str: str, context: dict[str, Any]) -> str:
    """Render output templates with a shared sandbox and normalization."""
    try:
        normalized = _normalize_template_syntax(template_str)
        template = _OUTPUT_TEMPLATE_ENV.from_string(normalized)
        return template.render(**context)
    except _OUTPUTS_TEMPLATE_EXCEPTIONS as exc:
        logger.error("outputs: template render failed: {}", exc)
        return template_str


def build_items_context_from_content_items(rows: Iterable[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        media_id = getattr(row, "media_id", None)
        item_id = media_id if media_id is not None else getattr(row, "id", None)
        tags = getattr(row, "tags", None)
        if callable(tags):
            try:
                tags = tags()
            except Exception:
                tags = []
        if not isinstance(tags, list):
            raw_json = getattr(row, "tags_json", None)
            if isinstance(raw_json, str):
                try:
                    tags = json.loads(raw_json)
                    if not isinstance(tags, list):
                        tags = []
                except (json.JSONDecodeError, TypeError, ValueError):
                    tags = []
            else:
                tags = []
        items.append(
            {
                "id": item_id,
                "content_item_id": getattr(row, "id", None),
                "media_id": media_id,
                "title": getattr(row, "title", None) or getattr(row, "url", None) or "Untitled",
                "url": getattr(row, "canonical_url", None) or getattr(row, "url", None) or "",
                "domain": getattr(row, "domain", None) or "",
                "summary": getattr(row, "summary", None) or "",
                "published_at": getattr(row, "published_at", None) or getattr(row, "created_at", None) or "",
                "tags": tags,
            }
        )
    return items


def normalize_output_storage_path(user_id: int, storage_path: str) -> str:
    """Normalize legacy storage paths to a safe filename under the user outputs directory."""
    if not storage_path:
        raise InvalidStoragePathError("invalid_path")

    try:
        base_dir = DatabasePaths.get_user_outputs_dir(user_id)
        base_resolved = base_dir.resolve(strict=False)
    except Exception as exc:
        raise InvalidStoragePathError("invalid_path") from exc

    return normalize_output_storage_filename(
        storage_path=storage_path,
        allow_absolute=True,
        reject_relative_with_separators=True,
        expand_user=True,
        base_resolved=base_resolved,
        check_relative_containment=True,
        require_parent_base=True,
    )


def _outputs_dir_for_user(user_id: int) -> PathlibPath:
    return DatabasePaths.get_user_outputs_dir(user_id)


def _resolve_output_path_for_user(user_id: int, path_value: str | PathlibPath) -> PathlibPath:
    """
    Resolve a path for a user's output, ensuring it stays within the user's outputs directory.

    The caller may pass either a string or a Path. Regardless of input, this function:
      * Disallows absolute paths and home-expansion.
      * Uses only the final path component (filename) to avoid directory traversal.
      * Resolves the final path under the per-user outputs directory.
    """
    base_dir = _outputs_dir_for_user(user_id)
    try:
        base_resolved = base_dir.resolve(strict=False)
    except Exception as e:
        logger.error(f"outputs: failed to resolve outputs base dir for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="storage_unavailable") from e

    # Defense-in-depth: treat path_value as untrusted and reduce to a safe filename under base_dir.
    # Normalize the candidate to a single relative filename component.
    candidate = path_value if isinstance(path_value, PathlibPath) else PathlibPath(path_value)
    if candidate.is_absolute():
        logger.warning(f"outputs: absolute paths are not allowed for outputs: {candidate}")
        raise HTTPException(status_code=400, detail="invalid_path")
    if len(candidate.parts) != 1:
        logger.warning(f"outputs: nested output paths are not allowed: {candidate}")
        raise HTTPException(status_code=400, detail="invalid_path")

    # Restrict to the final component to prevent directory traversal such as "../".
    candidate_name = candidate.name
    if not candidate_name or candidate_name in (".", ".."):
        logger.warning(f"outputs: empty output path component from {path_value!r}")
        raise HTTPException(status_code=400, detail="invalid_path")

    # Reject any path separators to ensure this remains a simple filename.
    if os.sep in candidate_name or (os.altsep and os.altsep in candidate_name):
        logger.warning(f"outputs: path separator detected in output filename: {candidate_name!r}")
        raise HTTPException(status_code=400, detail="invalid_path")

    # Enforce a conservative filename pattern (alphanumeric, underscore, dash, dot).
    if not re.match(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)*$", candidate_name):
        logger.warning(f"outputs: invalid characters in output filename: {candidate_name!r}")
        raise HTTPException(status_code=400, detail="invalid_path")

    safe_candidate = PathlibPath(candidate_name)
    try:
        resolved = (base_resolved / safe_candidate).resolve(strict=False)
    except Exception as e:
        logger.warning(f"outputs: invalid output path {path_value}: {e}")
        raise HTTPException(status_code=400, detail="invalid_path") from e

    if not resolved.is_relative_to(base_resolved):
        logger.warning(f"outputs: output path outside base dir: {resolved}")
        raise HTTPException(status_code=400, detail="invalid_path")
    return resolved


def _sanitize_title_for_filename(title: str) -> str:
    cleaned = title.replace("\x00", "")
    cleaned = cleaned.replace(os.sep, "_")
    if os.altsep:
        cleaned = cleaned.replace(os.altsep, "_")
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", cleaned.strip())
    s = re.sub(r"\.+", ".", s).strip(".")
    return s[:80] or "output"


def _output_extension(format_value: str) -> str:
    fmt = (format_value or "").lower()
    if fmt == "html":
        return "html"
    if fmt == "mp3":
        return "mp3"
    return "md"


def _build_output_filename(title: str, suffix: str | None, ts: str, format_value: str) -> str:
    base = _sanitize_title_for_filename(title)
    if suffix:
        base = f"{base}_{_sanitize_title_for_filename(suffix)}"
    ext = _output_extension(format_value)
    return f"{base}_{ts}.{ext}"


def _strip_html_for_tts(text: str) -> str:
    # Linear scan avoids regex backtracking on adversarial '<' sequences.
    if not text:
        return ""
    output: list[str] = []
    tag_buf: list[str] | None = None
    tag_has_content = False
    for ch in text:
        if tag_buf is None:
            if ch == "<":
                tag_buf = ["<"]
                tag_has_content = False
            else:
                output.append(ch)
        else:
            if ch == ">":
                if tag_has_content:
                    tag_buf = None
                else:
                    output.extend(tag_buf)
                    output.append(">")
                    tag_buf = None
                tag_has_content = False
            else:
                tag_buf.append(ch)
                tag_has_content = True
    if tag_buf is not None:
        output.extend(tag_buf)
    return "".join(output)


def _extract_tts_defaults(template_row) -> tuple[str | None, str | None, float | None]:
    if not template_row or not getattr(template_row, "metadata_json", None):
        return None, None, None
    try:
        tpl_md = json.loads(template_row.metadata_json) if template_row.metadata_json else None
    except _OUTPUTS_JSON_PARSE_EXCEPTIONS:
        tpl_md = None
    if not isinstance(tpl_md, dict):
        return None, None, None
    tpl_model = tpl_md.get("tts_default_model")
    tpl_voice = tpl_md.get("tts_default_voice")
    tpl_speed = tpl_md.get("tts_default_speed")
    try:
        tpl_speed_val = float(tpl_speed) if tpl_speed is not None else None
    except (TypeError, ValueError):
        tpl_speed_val = None
    return (
        str(tpl_model) if tpl_model is not None else None,
        str(tpl_voice) if tpl_voice is not None else None,
        tpl_speed_val,
    )


async def _write_tts_audio_file(
    *,
    rendered: str,
    path: PathlibPath,
    tts_model: str | None,
    tts_voice: str | None,
    tts_speed: float | None,
    template_row=None,
) -> None:
    try:
        from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
        from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
    except Exception as exc:
        logger.error(f"TTS import failed: {exc}")
        raise HTTPException(status_code=500, detail="tts_unavailable") from exc
    tts = await get_tts_service_v2()
    tpl_model, tpl_voice, tpl_speed = _extract_tts_defaults(template_row)
    req = OpenAISpeechRequest(
        model=(tts_model or tpl_model or "kokoro"),
        input=rendered,
        voice=(tts_voice or tpl_voice or "af_heart"),
        response_format="mp3",
        stream=True,
    )
    if tts_speed is not None:
        req.speed = tts_speed
    elif tpl_speed is not None:
        req.speed = tpl_speed
    total = 0
    with open(path, "wb") as fh:
        async for chunk in tts.generate_speech(req):
            if isinstance(chunk, (bytes, bytearray)):
                fh.write(chunk)
                total += len(chunk)
    if total <= 0:
        raise RuntimeError("tts_no_audio_generated")


async def _ingest_output_to_media_db(
    *,
    media_db,
    output_id: int,
    title: str,
    content: str,
    output_type: str,
    output_format: str,
    storage_path: str,
    template_id: int | None,
    run_id: int | None,
    item_ids: list[int],
    tags: list[str],
    variant_of: int | None = None,
) -> int:
    safe_metadata = {
        "output_id": output_id,
        "output_type": output_type,
        "output_format": output_format,
        "storage_path": storage_path,
        "template_id": template_id,
        "run_id": run_id,
        "item_ids": item_ids,
    }
    if variant_of is not None:
        safe_metadata["variant_of"] = variant_of
    ingestion_date = datetime.utcnow().replace(microsecond=0).isoformat()
    loop = asyncio.get_running_loop()
    try:
        media_id, _media_uuid, msg = await loop.run_in_executor(
            None,
            lambda: media_db.add_media_with_keywords(
                url=f"output://{output_id}",
                title=title,
                media_type=f"output_{output_type}",
                content=content,
                keywords=tags,
                prompt=None,
                analysis_content=None,
                safe_metadata=json.dumps(safe_metadata),
                transcription_model="output",
                ingestion_date=ingestion_date,
                overwrite=False,
            ),
        )
    except Exception as exc:
        logger.error(f"output media ingest failed for {output_id}: {exc}")
        raise HTTPException(status_code=500, detail="media_ingest_failed") from exc
    if not media_id:
        logger.error(f"output media ingest failed for {output_id}: {msg}")
        raise HTTPException(status_code=500, detail="media_ingest_failed")
    return int(media_id)


def update_output_artifact_db(
    cdb,
    output_id: int,
    new_title: str | None,
    new_path: str | None,
    new_format: str | None,
    retention_until: str | None,
):
    """Apply partial updates to an output artifact row and return the refreshed row.

    This function encapsulates the SQL UPDATE previously issued from the endpoint.
    """
    sets: list[str] = []
    params: list[object] = []
    if new_title is not None:
        sets.append("title = ?")
        params.append(new_title)
    if new_path is not None:
        new_path = cdb.resolve_output_storage_path(new_path)
        sets.append("storage_path = ?")
        params.append(new_path)
    if new_format is not None:
        sets.append("format = ?")
        params.append(new_format)
    if retention_until is not None:
        sets.append("retention_until = ?")
        params.append(retention_until)
    if sets:
        params.extend([output_id, cdb.user_id])
        set_clause = ", ".join(sets)
        update_output_sql_template = "UPDATE outputs SET {set_clause} WHERE id = ? AND user_id = ? AND deleted = 0"
        q = update_output_sql_template.format_map(locals())  # nosec B608
        try:
            cdb.backend.execute(q, tuple(params))
        except Exception as e:
            logger.error(f"outputs_service.update: DB update failed: {e}")
            raise
    try:
        return cdb.get_output_artifact(output_id)
    except Exception as e:
        logger.error(f"outputs_service.update: failed to fetch updated row: {e}")
        raise


def find_outputs_to_purge(
    cdb,
    now_iso: str,
    soft_deleted_grace_days: int,
    include_retention: bool,
) -> dict[int, str]:
    """Return a mapping of output_id -> storage_path for purge candidates.

    Combines retention-based and aged soft-deleted selections.
    """
    paths: dict[int, str] = {}
    # Retention-based candidates
    if include_retention:
        try:
            cur = cdb.backend.execute(
                "SELECT id, storage_path FROM outputs WHERE user_id = ? AND retention_until IS NOT NULL AND retention_until <= ?",
                (cdb.user_id, now_iso),
            )
            for row in cur.rows:
                rid = int(row["id"]) if isinstance(row, dict) else int(row[0])
                paths[rid] = row["storage_path"] if isinstance(row, dict) else row[1]
        except _OUTPUTS_DB_FALLBACK_EXCEPTIONS as e:
            logger.warning(f"outputs_service.purge: retention scan failed: {e}")
    # Soft-deleted grace candidates
    try:
        cur2 = cdb.backend.execute(
            "SELECT id, storage_path FROM outputs WHERE user_id = ? AND deleted = 1 AND deleted_at IS NOT NULL AND julianday(?) - julianday(deleted_at) >= ?",
            (cdb.user_id, now_iso, soft_deleted_grace_days),
        )
        for row in cur2.rows:
            rid = int(row["id"]) if isinstance(row, dict) else int(row[0])
            paths[rid] = row["storage_path"] if isinstance(row, dict) else row[1]
    except _OUTPUTS_DB_FALLBACK_EXCEPTIONS as e:
        logger.warning(f"outputs_service.purge: soft-deleted scan failed: {e}")
    return paths


def delete_outputs_by_ids(cdb, user_id: int, ids: list[int]) -> int:
    """Delete output rows by IDs for a user. Returns number of IDs requested (best-effort)."""
    if not ids:
        return 0
    placeholders = ",".join(["?"] * len(ids))
    audiobook_bytes = _sum_audiobook_output_bytes_for_ids(cdb, user_id, ids)
    try:
        cdb.backend.execute(
            f"DELETE FROM outputs WHERE user_id = ? AND id IN ({placeholders})",  # nosec B608
            tuple([user_id] + list(ids)),
        )
        if audiobook_bytes:
            try:
                cdb.update_audiobook_output_usage(-audiobook_bytes)
            except _OUTPUTS_DB_FALLBACK_EXCEPTIONS as exc:
                logger.warning("outputs_service: failed to decrement audiobook usage: {}", exc)
        return len(ids)
    except Exception as e:
        logger.error(f"outputs_service.purge: delete failed: {e}")
        raise


# ---------------------------------------------------------------------------
# LLM Summarization helpers for watchlist outputs
# ---------------------------------------------------------------------------

_SUMMARIZE_MAX_CHARS = 12_000
_SUMMARIZE_DEFAULT_PROMPT = "Summarize the following article in 2-3 concise sentences:\n\n{text}"


def _content_cache_key(content: str) -> str:
    """SHA256[:16] content hash for summary caching."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _get_cached_summary(metadata_json: str | None, content_hash: str) -> str | None:
    """Return a cached summary from item metadata if the content hash matches."""
    if not metadata_json:
        return None
    try:
        meta = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
        if not isinstance(meta, dict):
            return None
        # Format 1: flat keys
        if meta.get("cached_summary_hash") == content_hash:
            return meta.get("cached_summary")
        # Format 2: nested dict
        cached = meta.get("cached_summary")
        if isinstance(cached, dict) and cached.get("content_hash") == content_hash:
            return cached.get("text")
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return None


def _summarize_single_article(
    text: str,
    *,
    api_name: str,
    model_override: str | None = None,
    custom_prompt: str | None = None,
) -> str:
    """Synchronously call LLM to summarize a single article."""
    from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze

    truncated = text[:_SUMMARIZE_MAX_CHARS]
    prompt = (custom_prompt or _SUMMARIZE_DEFAULT_PROMPT).format(text=truncated)
    try:
        result = analyze(
            input_data=truncated,
            custom_prompt=prompt,
            api_name=api_name,
            api_key=None,
            model=model_override,
        )
        if isinstance(result, str) and result.strip():
            return result.strip()
    except Exception as exc:
        logger.warning(f"outputs_service: LLM summarize failed: {exc}")
    return text[:300]


async def summarize_items_for_output(
    items: list[dict[str, Any]],
    *,
    api_name: str,
    model_override: str | None = None,
    custom_prompt: str | None = None,
    db: Any = None,
) -> list[dict[str, Any]]:
    """Enrich items with LLM-generated 'llm_summary' field.

    Uses SHA256-keyed caching when metadata is available.
    """
    loop = asyncio.get_running_loop()
    for item in items:
        content = item.get("content") or item.get("summary") or item.get("title") or ""
        if not content.strip():
            item["llm_summary"] = ""
            continue
        content_hash = _content_cache_key(content)
        cached = _get_cached_summary(item.get("metadata_json"), content_hash)
        if cached:
            item["llm_summary"] = cached
            continue
        summary = await loop.run_in_executor(
            None,
            lambda text=content: _summarize_single_article(
                text, api_name=api_name, model_override=model_override, custom_prompt=custom_prompt,
            ),
        )
        item["llm_summary"] = summary
        if db and hasattr(db, "update_item_metadata"):
            try:
                item_id = item.get("id")
                if item_id is not None:
                    existing_meta = {}
                    raw = item.get("metadata_json")
                    if raw:
                        existing_meta = json.loads(raw) if isinstance(raw, str) else dict(raw)
                    existing_meta["cached_summary"] = summary
                    existing_meta["cached_summary_hash"] = content_hash
                    db.update_item_metadata(int(item_id), json.dumps(existing_meta))
            except Exception as exc:
                logger.debug(f"outputs_service: cache persist failed: {exc}")
    return items
