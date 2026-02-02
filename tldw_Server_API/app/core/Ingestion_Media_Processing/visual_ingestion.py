"""
Helpers for Visual RAG ingestion.

This module loads Visual RAG configuration from environment and config files,
then persists visual detections (currently from PDF VLM summaries) into the
Media DB as VisualDocuments rows for downstream retrieval and analysis.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, Optional

from loguru import logger
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.Utils.common import parse_boolean


@lru_cache(maxsize=1)
def _visual_rag_settings() -> Dict[str, Any]:
    """
    Load Visual RAG settings from env/config.

    Env takes precedence; falls back to [Visual-RAG] in config.txt when present.
    """
    settings: Dict[str, Any] = {
        "enable_visual_rag": False,
        "max_images_per_media": 32,
    }

    # Env overrides
    env_enable = os.getenv("VISUAL_RAG_ENABLE")
    if env_enable is not None:
        settings["enable_visual_rag"] = parse_boolean(env_enable, default=False)

    env_max_images = os.getenv("VISUAL_RAG_MAX_IMAGES_PER_MEDIA")
    if env_max_images is not None:
        try:
            settings["max_images_per_media"] = max(1, int(env_max_images))
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid VISUAL_RAG_MAX_IMAGES_PER_MEDIA value, using default: {e}")

    # Config [Visual-RAG] section (only if env didn't override)
    try:
        cfg = load_comprehensive_config()
        if cfg is not None and cfg.has_section("Visual-RAG"):
            section = dict(cfg.items("Visual-RAG"))
            if env_enable is None:
                raw_enable = section.get("enable_visual_rag")
                if raw_enable is not None:
                    settings["enable_visual_rag"] = parse_boolean(str(raw_enable), default=False)
            if env_max_images is None:
                raw_max = section.get("max_images_per_media")
                if raw_max is not None:
                    try:
                        settings["max_images_per_media"] = max(1, int(str(raw_max)))
                    except (ValueError, TypeError) as exc:
                        logger.debug(
                            f"Invalid max_images_per_media in [Visual-RAG] section, using default: {exc}"
                        )
    except Exception as exc:
        logger.debug(f"visual_ingestion: config load skipped/failed: {exc}")

    return settings


def persist_visual_documents_from_analysis(
    *,
    db_path: str,
    client_id: str,
    media_id: int,
    analysis_details: Optional[Dict[str, Any]],
) -> int:
    """
    Best-effort helper that extracts visual detections (currently from PDF VLM
    summaries) and persists them as VisualDocuments rows.

    This is gated by Visual RAG settings and is safe to call even when visual
    analysis is absent.

    Returns:
        Number of VisualDocuments created for this media item.
    """
    settings = _visual_rag_settings()
    if not settings.get("enable_visual_rag", False):
        return 0
    if not analysis_details:
        return 0

    vlm_summary = analysis_details.get("vlm") or {}
    if not isinstance(vlm_summary, dict):
        return 0

    by_page = vlm_summary.get("by_page") or []
    if not by_page:
        return 0

    max_images = int(settings.get("max_images_per_media") or 32)
    created = 0

    db = MediaDatabase(db_path=db_path, client_id=client_id)
    try:
        for entry in by_page:
            if created >= max_images:
                break
            page_no = entry.get("page")
            detections = entry.get("detections") or []
            for det in detections:
                if created >= max_images:
                    break
                try:
                    label = str(det.get("label", "") or "")
                    score = float(det.get("score", 0.0) or 0.0)
                    bbox = det.get("bbox") or [0.0, 0.0, 0.0, 0.0]
                    caption = f"Detected {label}" if label else "Detected region"
                    tags = label if label else None
                    extra = {
                        "label": label,
                        "score": score,
                        "bbox": bbox,
                        "page": page_no,
                    }
                    db.insert_visual_document(
                        media_id=media_id,
                        caption=caption,
                        ocr_text=None,
                        tags=tags,
                        location=f"page:{page_no}" if page_no is not None else None,
                        page_number=int(page_no) if page_no is not None and isinstance(page_no, (int, float)) else None,
                        frame_index=None,
                        timestamp_seconds=None,
                        thumbnail_path=None,
                        extra_metadata=json.dumps(extra),
                    )
                    created += 1
                except (ValueError, TypeError, KeyError, json.JSONDecodeError) as det_err:
                    logger.debug(f"visual_ingestion: skipping detection due to data error: {det_err}")
                    continue
                except Exception as det_err:
                    logger.exception(
                        "visual_ingestion: unexpected error while persisting detection",  # noqa: TRY401
                        exc_info=det_err,
                    )
                    raise
    finally:
        try:
            db.close_connection()
        except Exception:
            logger.debug("visual_ingestion: failed to close MediaDatabase connection")

    return created
