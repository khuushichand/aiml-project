from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
from tldw_Server_API.app.api.v1.schemas.audiobook_schemas import AlignmentPayload, ChapterPreview
from tldw_Server_API.app.core.Audiobooks.subtitle_generator import generate_subtitles
from tldw_Server_API.app.core.Audiobooks.alignment_utils import (
    AlignmentAnchor,
    apply_alignment_anchors_to_payload,
    scale_alignment_payload,
    stitch_alignment_payloads,
)
from tldw_Server_API.app.core.Audiobooks.tag_parser import (
    TagParseResult,
    build_chapters_from_markers,
    parse_tagged_text,
)
from tldw_Server_API.app.core.Chunking.strategies.ebook_chapters import EbookChapterChunkingStrategy
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib import (
    extract_epub_metadata_from_text,
    process_epub,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import (
    extract_text_and_format_from_pdf,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.path_utils import resolve_safe_local_path
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter, log_histogram
from tldw_Server_API.app.core.TTS.audio_converter import AudioConverter
from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
from tldw_Server_API.app.core.TTS.tts_validation import TTSInputValidator
from tldw_Server_API.app.core.Usage.audio_quota import can_start_job, finish_job, increment_jobs_started
from tldw_Server_API.app.core.config import get_config_value

DOMAIN = "audiobooks"
JOB_TYPE = "audiobook_generate"

OUTPUT_TYPE_AUDIO = "audiobook_audio"
OUTPUT_TYPE_SUBTITLE = "audiobook_subtitle"
OUTPUT_TYPE_ALIGNMENT = "audiobook_alignment"
OUTPUT_TYPE_PACKAGE = "audiobook_package"

AUDIOBOOK_OUTPUT_TYPES = (
    OUTPUT_TYPE_AUDIO,
    OUTPUT_TYPE_SUBTITLE,
    OUTPUT_TYPE_ALIGNMENT,
    OUTPUT_TYPE_PACKAGE,
)

OUTPUT_TO_ARTIFACT_TYPE = {
    OUTPUT_TYPE_AUDIO: "audio",
    OUTPUT_TYPE_SUBTITLE: "subtitle",
    OUTPUT_TYPE_ALIGNMENT: "alignment",
    OUTPUT_TYPE_PACKAGE: "package",
}

SUPPORTED_TTS_FORMATS = {"mp3", "wav", "flac", "opus", "aac", "pcm"}


@dataclass
class ChapterPlanItem:
    chapter_id: str
    title: Optional[str]
    text: str
    start_offset: int
    end_offset: int
    voice: Optional[str]
    speed: Optional[float]
    voice_profile_id: Optional[str]
    index: int
    total: int
    alignment_anchors: List[AlignmentAnchor]


@dataclass
class VoiceProfileConfig:
    profile_id: str
    default_voice: Optional[str]
    default_speed: Optional[float]
    overrides: Dict[str, Dict[str, Optional[Any]]]


@dataclass
class AudiobookArtifactQuota:
    limit_bytes: int
    used_bytes: int = 0

    def check_add(self, add_bytes: int) -> None:
        if add_bytes <= 0:
            return
        if self.used_bytes + add_bytes > self.limit_bytes:
            raise AudiobookJobError("audiobook_artifact_quota_exceeded", retryable=False)

    def apply_add(self, add_bytes: int) -> None:
        if add_bytes > 0:
            self.used_bytes += add_bytes


@dataclass(frozen=True)
class ChapterSegment:
    text: str
    start_offset: int
    end_offset: int


class AudiobookJobError(Exception):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def _sanitize_filename(value: str) -> str:
    cleaned = value.replace("\x00", "").strip()
    cleaned = cleaned.replace(os.sep, "_")
    if os.altsep:
        cleaned = cleaned.replace(os.altsep, "_")
    out = []
    for ch in cleaned:
        if ch.isalnum() or ch in {"_", "-", "."}:
            out.append(ch)
        else:
            out.append("_")
    name = "".join(out).strip("._")
    while "__" in name:
        name = name.replace("__", "_")
    return name[:80] or "output"


def _resolve_audiobook_artifact_quota_bytes() -> Optional[int]:
    env_val = os.getenv("AUDIOBOOK_ARTIFACT_QUOTA_MB")
    cfg_val = get_config_value("Audiobooks", "artifact_quota_mb")
    raw = env_val if env_val not in (None, "") else cfg_val
    if raw is None:
        return None
    try:
        mb_val = float(raw)
    except (TypeError, ValueError):
        return None
    if mb_val <= 0:
        return None
    return int(mb_val * 1024 * 1024)


def _extract_metadata_byte_size(metadata_json: Optional[str]) -> Optional[int]:
    if not metadata_json:
        return None
    try:
        payload = json.loads(metadata_json)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get("byte_size")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _resolve_output_size_bytes(row: CollectionsDatabase.OutputArtifactRow, outputs_dir: Path) -> Optional[int]:
    cached = _extract_metadata_byte_size(row.metadata_json)
    if cached is not None:
        return cached
    try:
        return (outputs_dir / row.storage_path).stat().st_size
    except FileNotFoundError:
        logger.warning("audiobook_quota: missing output file for %s", row.storage_path)
    except OSError as exc:
        logger.warning("audiobook_quota: failed to stat %s: %s", row.storage_path, exc)
    return None


def _sum_existing_audiobook_output_bytes(
    collections_db: CollectionsDatabase,
    outputs_dir: Path,
) -> int:
    total_bytes = 0
    offset = 0
    limit = 200
    while True:
        rows, total = collections_db.list_output_artifacts_by_types(
            types=list(AUDIOBOOK_OUTPUT_TYPES),
            limit=limit,
            offset=offset,
        )
        for row in rows:
            size = _resolve_output_size_bytes(row, outputs_dir)
            if size:
                total_bytes += size
        offset += len(rows)
        if offset >= total or not rows:
            break
    return total_bytes


def _init_audiobook_quota(
    collections_db: CollectionsDatabase,
    outputs_dir: Path,
) -> Optional[AudiobookArtifactQuota]:
    limit_bytes = _resolve_audiobook_artifact_quota_bytes()
    if limit_bytes is None:
        return None
    used_bytes = _sum_existing_audiobook_output_bytes(collections_db, outputs_dir)
    logger.debug(
        "audiobook_quota: user=%s used=%s limit=%s",
        collections_db.user_id,
        used_bytes,
        limit_bytes,
    )
    return AudiobookArtifactQuota(limit_bytes=limit_bytes, used_bytes=used_bytes)


def _merge_metadata_with_bytes(metadata_json: Optional[str], size_bytes: Optional[int]) -> Optional[str]:
    if size_bytes is None:
        return metadata_json
    payload: Dict[str, Any]
    if metadata_json:
        try:
            raw = json.loads(metadata_json)
        except Exception:
            raw = None
        if isinstance(raw, dict):
            payload = raw
        else:
            payload = {"metadata": raw}
    else:
        payload = {}
    payload["byte_size"] = int(size_bytes)
    return json.dumps(payload)


def _build_filename(prefix: str, suffix: str, ext: str) -> str:
    base = _sanitize_filename(prefix)
    tag = _sanitize_filename(suffix)
    ext_clean = _sanitize_filename(ext)
    return f"{base}_{tag}.{ext_clean}"


def _resolve_item_title(item_metadata: Dict[str, Any], source_metadata: Dict[str, Any]) -> Optional[str]:
    for key in ("title", "project_title", "name"):
        value = item_metadata.get(key)
        if value:
            return str(value)
    value = source_metadata.get("title")
    if value:
        return str(value)
    return None


def _build_item_tag(item_index: int, item_title: Optional[str]) -> str:
    tag = f"item_{item_index + 1}"
    if item_title:
        tag = f"{tag}_{item_title}"
    return tag


def _resolve_item_requests(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = payload.get("items")
    default_output = payload.get("output") or {}
    default_subtitles = payload.get("subtitles") or {}
    default_metadata = payload.get("metadata") or {}
    default_voice_profile_id = payload.get("voice_profile_id")

    if items is None:
        source = payload.get("source") or {}
        if not source:
            raise AudiobookJobError("missing_source", retryable=False)
        if not default_output:
            raise AudiobookJobError("missing_output", retryable=False)
        if not default_subtitles:
            raise AudiobookJobError("missing_subtitles", retryable=False)
        return [
            {
                "source": source,
                "output": default_output,
                "subtitles": default_subtitles,
                "chapters": payload.get("chapters"),
                "voice_profile_id": default_voice_profile_id,
                "metadata": default_metadata,
            }
        ]

    if not isinstance(items, list) or not items:
        raise AudiobookJobError("items_empty", retryable=False)

    resolved: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise AudiobookJobError("invalid_item", retryable=False)
        source = item.get("source") or {}
        if not source:
            raise AudiobookJobError("missing_item_source", retryable=False)
        output_cfg = item.get("output") or default_output
        subtitle_cfg = item.get("subtitles") or default_subtitles
        if not output_cfg:
            raise AudiobookJobError("missing_item_output", retryable=False)
        if not subtitle_cfg:
            raise AudiobookJobError("missing_item_subtitles", retryable=False)
        item_metadata = {}
        if default_metadata:
            item_metadata.update(default_metadata)
        item_override = item.get("metadata") or {}
        if item_override:
            item_metadata.update(item_override)
        resolved.append(
            {
                "source": source,
                "output": output_cfg,
                "subtitles": subtitle_cfg,
                "chapters": item.get("chapters"),
                "voice_profile_id": item.get("voice_profile_id") or default_voice_profile_id,
                "metadata": item_metadata,
                "item_index": idx,
            }
        )
    return resolved


def _progress_percent(
    item_index: int,
    item_total: int,
    chapter_index: int,
    chapter_total: int,
    offset: float,
) -> int:
    item_total = max(1, item_total)
    chapter_total = max(1, chapter_total)
    within = (chapter_index + offset) / chapter_total
    return int(((item_index + within) / item_total) * 100)


def _progress_message(
    stage: str,
    *,
    chapter_index: Optional[int] = None,
    chapters_total: Optional[int] = None,
    item_index: Optional[int] = None,
    items_total: Optional[int] = None,
) -> str:
    payload: Dict[str, Any] = {"stage": stage}
    if chapter_index is not None:
        payload["chapter_index"] = int(chapter_index)
    if chapters_total is not None:
        payload["chapters_total"] = int(chapters_total)
    if item_index is not None:
        payload["item_index"] = int(item_index)
    if items_total is not None:
        payload["items_total"] = int(items_total)
    return json.dumps(payload)


def _get_chapter_chunk_max_chars() -> Optional[int]:
    env_val = os.getenv("AUDIOBOOK_CHAPTER_MAX_CHARS")
    cfg_val = get_config_value("Audiobooks", "chapter_max_chars")
    raw = env_val if env_val is not None else cfg_val
    if raw is None:
        return None
    try:
        max_chars = int(raw)
    except (TypeError, ValueError):
        return None
    if max_chars <= 0:
        return None
    return max_chars


def _split_text_by_max_chars(text: str, max_chars: int) -> List[ChapterSegment]:
    if max_chars <= 0 or len(text) <= max_chars:
        return [ChapterSegment(text=text, start_offset=0, end_offset=len(text))]
    segments: List[ChapterSegment] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            window = text[start:end]
            split_candidates = [
                window.rfind("\n"),
                window.rfind(". "),
                window.rfind("! "),
                window.rfind("? "),
                window.rfind(" "),
            ]
            best = max(split_candidates)
            split_at = start + best + 1 if best > 0 else end
        else:
            split_at = end
        if split_at <= start:
            split_at = end
        segments.append(
            ChapterSegment(
                text=text[start:split_at],
                start_offset=start,
                end_offset=split_at,
            )
        )
        start = split_at
    return segments


async def _resolve_segment_duration_ms(
    alignment_payload: Optional[dict],
    audio_path: Optional[Path],
) -> int:
    if alignment_payload:
        words = alignment_payload.get("words") or []
        if words:
            try:
                end_ms = int(words[-1].get("end_ms") or 0)
                if end_ms > 0:
                    return end_ms
            except Exception:
                pass
    if audio_path is not None:
        duration = await AudioConverter.get_duration(audio_path)
        if duration > 0:
            return int(round(duration * 1000))
    return 0


def _build_segment_offsets_ms(durations_ms: List[int]) -> List[int]:
    offsets: List[int] = []
    total = 0
    for duration in durations_ms:
        offsets.append(total)
        total += max(0, int(duration))
    return offsets


def _resolve_upload_path(upload_id: str, user_id: int) -> Optional[Path]:
    if not upload_id:
        return None
    base_dir = DatabasePaths.get_user_temp_outputs_dir(user_id)
    safe_path = resolve_safe_local_path(Path(upload_id), base_dir)
    if safe_path is None:
        return None
    if not safe_path.exists():
        return None
    return safe_path


def _strip_srt_vtt(text: str) -> str:
    cleaned: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("webvtt"):
            continue
        if stripped.isdigit():
            continue
        if "-->" in stripped:
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned).strip()


def _strip_ass(text: str) -> str:
    cleaned: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("dialogue:") or stripped.lower().startswith("comment:"):
            parts = stripped.split(",", 9)
            if len(parts) >= 10:
                cleaned.append(parts[9].strip())
            else:
                cleaned.append(stripped)
    return "\n".join(cleaned).strip()


def _normalize_subtitles(text: str, input_type: str) -> str:
    if input_type in {"srt", "vtt"}:
        return _strip_srt_vtt(text)
    if input_type == "ass":
        return _strip_ass(text)
    return text


def _detect_chapters(
    text: str,
    *,
    language: Optional[str] = None,
    custom_pattern: Optional[str] = None,
) -> list[ChapterPreview]:
    if not text or not text.strip():
        return []
    lang = language or "en"
    strategy = EbookChapterChunkingStrategy(language=lang)
    word_count = max(1, len(text.split()))
    results = strategy.chunk_with_metadata(
        text,
        max_size=word_count,
        overlap=0,
        custom_chapter_pattern=custom_pattern,
    )
    chapters: list[ChapterPreview] = []
    for result in results:
        options = getattr(result.metadata, "options", {}) or {}
        title = options.get("chapter_title")
        chapter_id = f"ch_{result.metadata.index + 1:03d}"
        chapters.append(
            ChapterPreview(
                chapter_id=chapter_id,
                title=title,
                start_offset=result.metadata.start_char,
                end_offset=result.metadata.end_char,
                word_count=result.metadata.word_count,
            )
        )
    return chapters


def _load_source_text(source: Dict[str, Any], user_id: int) -> Tuple[str, Dict[str, Any], TagParseResult]:
    input_type = source.get("input_type")
    metadata: Dict[str, Any] = {"source_type": input_type}
    text: Optional[str] = None

    raw_text = source.get("raw_text")
    if raw_text:
        text = raw_text
        title, author = extract_epub_metadata_from_text(text)
        if title:
            metadata["title"] = title
        if author:
            metadata["author"] = author
    else:
        media_id = source.get("media_id")
        upload_id = source.get("upload_id")
        if media_id is not None:
            try:
                media_id_int = int(media_id)
            except (TypeError, ValueError) as exc:
                raise AudiobookJobError("invalid_media_id", retryable=False) from exc
            db_path = DatabasePaths.get_media_db_path(user_id)
            media_db = MediaDatabase(db_path=str(db_path), client_id="audiobook_worker")
            record = media_db.get_media_by_id(media_id_int)
            if not record:
                raise AudiobookJobError("media_not_found", retryable=False)
            text = record.get("content") or ""
            metadata["title"] = record.get("title")
            if record.get("author"):
                metadata["author"] = record.get("author")
        elif upload_id:
            upload_path = _resolve_upload_path(upload_id, user_id)
            if upload_path is None:
                raise AudiobookJobError("upload_not_found", retryable=False)
            try:
                if input_type == "epub":
                    result = process_epub(str(upload_path), perform_chunking=False)
                    text = result.get("content") or ""
                    meta = result.get("metadata") or {}
                    if meta.get("title"):
                        metadata["title"] = meta.get("title")
                    if meta.get("author"):
                        metadata["author"] = meta.get("author")
                elif input_type == "pdf":
                    text = extract_text_and_format_from_pdf(str(upload_path))
                else:
                    text = upload_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                raise AudiobookJobError("parse_failed", retryable=False) from exc

    if text is None:
        raise AudiobookJobError("no_source_text", retryable=False)
    normalized = _normalize_subtitles(text, str(input_type or "txt").lower())
    tag_result = parse_tagged_text(normalized)
    if tag_result.chapter_markers or tag_result.voice_markers or tag_result.speed_markers or tag_result.ts_markers:
        metadata["tag_markers"] = tag_result.as_metadata()
    return tag_result.clean_text, metadata, tag_result


def _build_chapter_plan(
    text: str,
    chapter_specs: Optional[List[Dict[str, Any]]],
    *,
    language: Optional[str] = None,
    custom_pattern: Optional[str] = None,
    tag_result: Optional[TagParseResult] = None,
    voice_profile: Optional[VoiceProfileConfig] = None,
) -> List[ChapterPlanItem]:
    detected: List[ChapterPreview]
    if tag_result and tag_result.chapter_markers:
        detected = build_chapters_from_markers(text, tag_result.chapter_markers)
    else:
        detected = _detect_chapters(text, language=language, custom_pattern=custom_pattern)
    if not detected:
        detected = [
            ChapterPreview(
                chapter_id="ch_001",
                title=None,
                start_offset=0,
                end_offset=len(text),
                word_count=max(1, len(text.split())),
            )
        ]
    chapter_map = {chapter.chapter_id: chapter for chapter in detected}

    selected: List[Dict[str, Any]]
    if chapter_specs:
        selected = [spec for spec in chapter_specs if spec.get("include") is not False]
    else:
        selected = [
            {"chapter_id": chapter.chapter_id, "include": True}
            for chapter in detected
        ]

    plan: List[ChapterPlanItem] = []
    for spec in selected:
        chapter_id = spec.get("chapter_id") or "ch_001"
        preview = chapter_map.get(chapter_id)
        if preview:
            chapter_text = text[preview.start_offset : preview.end_offset]
            title = preview.title
            start_offset = preview.start_offset
            end_offset = preview.end_offset
            tag_voice = _resolve_marker_value(
                tag_result.voice_markers if tag_result else [],
                preview.start_offset,
            )
            tag_speed = _resolve_marker_value(
                tag_result.speed_markers if tag_result else [],
                preview.start_offset,
            )
            anchors = _extract_alignment_anchors(
                tag_result.ts_markers if tag_result else [],
                preview.start_offset,
                preview.end_offset,
            )
        else:
            chapter_text = text
            title = None
            start_offset = 0
            end_offset = len(text)
            tag_voice = None
            tag_speed = None
            anchors = []
        profile_voice = voice_profile.default_voice if voice_profile else None
        profile_speed = voice_profile.default_speed if voice_profile else None
        if voice_profile and chapter_id in voice_profile.overrides:
            override = voice_profile.overrides[chapter_id]
            if override.get("voice") is not None:
                profile_voice = override.get("voice")
            if override.get("speed") is not None:
                profile_speed = override.get("speed")
        voice_override = (
            spec.get("voice")
            if spec.get("voice") is not None
            else tag_voice if tag_voice is not None else profile_voice
        )
        speed_override = (
            spec.get("speed")
            if spec.get("speed") is not None
            else tag_speed if tag_speed is not None else profile_speed
        )
        plan.append(
            ChapterPlanItem(
                chapter_id=chapter_id,
                title=title,
                text=chapter_text,
                start_offset=start_offset,
                end_offset=end_offset,
                voice=voice_override,
                speed=speed_override,
                voice_profile_id=voice_profile.profile_id if voice_profile else None,
                index=len(plan),
                total=len(selected),
                alignment_anchors=anchors,
            )
        )

    if not plan:
        raise AudiobookJobError("no_chapters_selected", retryable=False)
    total = len(plan)
    plan = [
        ChapterPlanItem(
            chapter_id=item.chapter_id,
            title=item.title,
            text=item.text,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            voice=item.voice,
            speed=item.speed,
            voice_profile_id=item.voice_profile_id,
            index=i,
            total=total,
            alignment_anchors=item.alignment_anchors,
        )
        for i, item in enumerate(plan)
    ]
    return plan


def _sanitize_source_ref(source: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    input_type = source.get("input_type")
    if input_type:
        sanitized["input_type"] = input_type
    if source.get("upload_id"):
        sanitized["upload_id"] = source.get("upload_id")
    if source.get("media_id") is not None:
        sanitized["media_id"] = source.get("media_id")
    if source.get("raw_text"):
        sanitized["raw_text_len"] = len(str(source.get("raw_text")))
    return sanitized


def _build_project_source_ref(item_requests: List[Dict[str, Any]]) -> Optional[str]:
    if not item_requests:
        return None
    if len(item_requests) == 1:
        source = item_requests[0].get("source") or {}
        return json.dumps(_sanitize_source_ref(source))
    items: List[Dict[str, Any]] = []
    for idx, item in enumerate(item_requests):
        item_meta = item.get("metadata") or {}
        item_title = _resolve_item_title(item_meta, {})
        items.append(
            {
                "item_index": idx,
                "title": item_title,
                "source": _sanitize_source_ref(item.get("source") or {}),
            }
        )
    return json.dumps({"mode": "batch", "items": items})


def _load_voice_profile(
    collections_db: CollectionsDatabase,
    profile_id: Optional[str],
) -> Optional[VoiceProfileConfig]:
    if not profile_id:
        return None
    try:
        row = collections_db.get_voice_profile(str(profile_id))
    except KeyError as exc:
        raise AudiobookJobError("voice_profile_not_found", retryable=False) from exc
    overrides: Dict[str, Dict[str, Optional[Any]]] = {}
    raw_overrides: list[Any] = []
    if row.chapter_overrides_json:
        try:
            raw_overrides = json.loads(row.chapter_overrides_json) or []
        except Exception:
            raw_overrides = []
    for entry in raw_overrides:
        if not isinstance(entry, dict):
            continue
        chapter_id = entry.get("chapter_id")
        if not chapter_id:
            continue
        overrides[str(chapter_id)] = {
            "voice": entry.get("voice"),
            "speed": entry.get("speed"),
        }
    return VoiceProfileConfig(
        profile_id=str(row.profile_id),
        default_voice=row.default_voice,
        default_speed=float(row.default_speed) if row.default_speed is not None else None,
        overrides=overrides,
    )


def _create_output_and_link(
    collections_db: CollectionsDatabase,
    *,
    output_type: str,
    title: str,
    format_: str,
    storage_path: str,
    metadata_json: Optional[str],
    job_id: Optional[int],
    project_db_id: Optional[int],
    outputs_dir: Optional[Path] = None,
    quota_tracker: Optional[AudiobookArtifactQuota] = None,
) -> CollectionsDatabase.OutputArtifactRow:
    normalized_path = collections_db.resolve_output_storage_path(storage_path)
    size_bytes: Optional[int] = None
    file_path: Optional[Path] = None
    if outputs_dir is not None:
        file_path = outputs_dir / normalized_path
        try:
            size_bytes = file_path.stat().st_size
        except FileNotFoundError:
            logger.warning("audiobook output missing for quota check: %s", normalized_path)
        except OSError as exc:
            logger.warning("audiobook output stat failed: %s error=%s", normalized_path, exc)

    if quota_tracker is not None and size_bytes is not None:
        try:
            quota_tracker.check_add(size_bytes)
        except AudiobookJobError:
            if file_path is not None:
                try:
                    file_path.unlink()
                except OSError as exc:
                    logger.warning("audiobook output cleanup failed: %s error=%s", file_path, exc)
            raise

    metadata_json = _merge_metadata_with_bytes(metadata_json, size_bytes)

    row = collections_db.create_output_artifact(
        type_=output_type,
        title=title,
        format_=format_,
        storage_path=normalized_path,
        metadata_json=metadata_json,
        job_id=job_id,
    )
    if quota_tracker is not None and size_bytes is not None:
        quota_tracker.apply_add(size_bytes)
    if project_db_id is None:
        return row
    artifact_type = OUTPUT_TO_ARTIFACT_TYPE.get(output_type)
    if artifact_type:
        collections_db.create_audiobook_artifact(
            project_id=project_db_id,
            artifact_type=artifact_type,
            format_=format_,
            output_id=row.id,
            metadata_json=metadata_json,
        )
    return row


def _resolve_marker_value(markers: List[Any], start_offset: int) -> Optional[Any]:
    if not markers:
        return None
    value = None
    for marker in sorted(markers, key=lambda m: m.offset):
        if marker.offset > start_offset:
            break
        value = marker.value
    return value


def _extract_alignment_anchors(
    markers: List[Any],
    start_offset: int,
    end_offset: int,
) -> List[AlignmentAnchor]:
    anchors: List[AlignmentAnchor] = []
    for marker in markers:
        if marker.offset < start_offset or marker.offset >= end_offset:
            continue
        anchors.append(
            AlignmentAnchor(
                offset=marker.offset - start_offset,
                time_ms=marker.time_ms,
            )
        )
    return anchors


def _get_time_stretch_max_ratio() -> Optional[float]:
    env_val = os.getenv("AUDIOBOOK_TIME_STRETCH_MAX_RATIO")
    cfg_val = get_config_value("Audiobooks", "time_stretch_max_ratio")
    raw = env_val if env_val is not None else cfg_val
    if raw is None:
        return None
    try:
        ratio = float(raw)
    except (TypeError, ValueError):
        return None
    if ratio <= 1.0:
        return None
    return ratio


def _resolve_time_stretch_ratio(speed: Optional[float]) -> Optional[float]:
    if speed is None:
        return None
    max_ratio = _get_time_stretch_max_ratio()
    if max_ratio is None:
        return None
    if speed == 1.0:
        return None
    lower = 1.0 / max_ratio
    upper = max_ratio
    if lower <= speed <= upper:
        return speed
    return None


def _resolve_output_formats(output_cfg: Dict[str, Any]) -> Tuple[List[str], bool]:
    formats = output_cfg.get("formats") or []
    resolved: List[str] = []
    wants_m4b = False
    for fmt in formats:
        fmt_lower = str(fmt).lower()
        if fmt_lower == "m4b":
            wants_m4b = True
            continue
        resolved.append(fmt_lower)
    return resolved, wants_m4b


def _validate_text(text: str) -> str:
    validator = TTSInputValidator({"strict_validation": True})
    sanitized = validator.sanitize_text(text, provider="kokoro")
    if not sanitized or not sanitized.strip():
        raise AudiobookJobError("empty_text_after_sanitization", retryable=False)
    return sanitized


async def _generate_tts_audio(
    *,
    text: str,
    model: Optional[str],
    voice: Optional[str],
    speed: Optional[float],
    response_format: str,
    user_id: Optional[int],
) -> Tuple[bytes, Optional[dict]]:
    request = OpenAISpeechRequest(
        model=model or "kokoro",
        input=text,
        voice=voice or "af_heart",
        response_format=response_format,
        speed=float(speed) if speed is not None else 1.0,
        stream=False,
    )
    tts_service = await get_tts_service_v2()
    audio_iter = tts_service.generate_speech(
        request,
        provider=None,
        fallback=True,
        user_id=user_id,
    )
    chunks = b""
    async for chunk in audio_iter:
        chunks += chunk
    metadata = getattr(request, "_tts_metadata", None)
    alignment = metadata.get("alignment") if isinstance(metadata, dict) else None
    return chunks, alignment


async def process_audiobook_job(
    job: Dict[str, Any],
    *,
    job_manager: Optional[JobManager] = None,
    worker_id: str = "audiobook-worker",
) -> None:
    jm = job_manager or JobManager()
    job_id = int(job.get("id"))
    lease_id = str(job.get("lease_id"))

    owner = job.get("owner_user_id")
    if not owner:
        jm.fail_job(
            job_id,
            error="missing owner_user_id",
            retryable=False,
            worker_id=worker_id,
            lease_id=lease_id,
            completion_token=lease_id,
        )
        return

    try:
        user_id = int(owner)
    except (TypeError, ValueError) as exc:
        jm.fail_job(
            job_id,
            error="invalid owner_user_id",
            retryable=False,
            worker_id=worker_id,
            lease_id=lease_id,
            completion_token=lease_id,
        )
        raise AudiobookJobError("invalid_owner", retryable=False) from exc

    payload = job.get("payload") or {}
    if not isinstance(payload, dict):
        jm.fail_job(
            job_id,
            error="invalid payload",
            retryable=False,
            worker_id=worker_id,
            lease_id=lease_id,
            completion_token=lease_id,
        )
        return

    project_id = payload.get("project_id") or f"abk_{job_id}"
    project_title = payload.get("project_title") or project_id

    language = payload.get("language")
    custom_pattern = payload.get("custom_chapter_pattern")
    item_requests = _resolve_item_requests(payload)
    total_items = len(item_requests)

    ok_job, msg = await can_start_job(user_id)
    if not ok_job:
        jm.fail_job(
            job_id,
            error=msg or "concurrency limit",
            retryable=True,
            worker_id=worker_id,
            lease_id=lease_id,
            completion_token=lease_id,
        )
        return
    acquired_slot = False
    try:
        await increment_jobs_started(user_id)
        acquired_slot = True
    except Exception:
        acquired_slot = False

    collections_db = CollectionsDatabase(user_id)
    outputs_dir = DatabasePaths.get_user_outputs_dir(user_id)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    temp_outputs_dir = DatabasePaths.get_user_temp_outputs_dir(user_id)
    temp_outputs_dir.mkdir(parents=True, exist_ok=True)
    quota_tracker = _init_audiobook_quota(collections_db, outputs_dir)

    outputs: List[Dict[str, Any]] = []
    project_db_id: Optional[int] = None
    try:
        project_source_ref = _build_project_source_ref(item_requests)
        project_settings = {
            "project_id": project_id,
            "project_title": project_title,
            "language": language,
            "custom_chapter_pattern": custom_pattern,
            "output": payload.get("output"),
            "subtitles": payload.get("subtitles"),
            "items_count": total_items,
            "metadata": payload.get("metadata") or {},
            "voice_profile_id": payload.get("voice_profile_id"),
        }
        project_row = collections_db.create_audiobook_project(
            project_id=project_id,
            title=project_title,
            source_ref=project_source_ref,
            status="processing",
            settings_json=json.dumps(project_settings),
        )
        project_db_id = int(project_row.id)
        global_chapter_index = 0

        jm.update_job_progress(
            job_id,
            progress_message=_progress_message("audiobook_parse"),
            progress_percent=0,
        )
        for item_pos, item in enumerate(item_requests):
            item_index = int(item.get("item_index", item_pos))
            item_source = item.get("source") or {}
            item_output_cfg = item.get("output") or {}
            item_subtitle_cfg = item.get("subtitles") or {}
            item_chapter_specs = item.get("chapters")
            item_voice_profile_id = item.get("voice_profile_id")
            item_metadata = item.get("metadata") or {}

            jm.update_job_progress(
                job_id,
                progress_message=_progress_message(
                    "audiobook_parse",
                    item_index=item_index,
                    items_total=total_items,
                ),
                progress_percent=_progress_percent(item_index, total_items, 0, 1, 0.0),
            )
            text, source_metadata, tag_result = _load_source_text(item_source, user_id)
            normalized_text = _validate_text(text)
            voice_profile = _load_voice_profile(collections_db, item_voice_profile_id)
            chapter_plan = _build_chapter_plan(
                normalized_text,
                item_chapter_specs,
                language=language,
                custom_pattern=custom_pattern,
                tag_result=tag_result,
                voice_profile=voice_profile,
            )

            item_title = _resolve_item_title(item_metadata, source_metadata)
            item_tag = _build_item_tag(item_index, item_title)
            item_prefix = f"{project_title}_{item_tag}"
            item_display_title = f"{project_title} {item_tag}"

            per_chapter = bool(item_output_cfg.get("per_chapter", True))
            output_formats, wants_m4b = _resolve_output_formats(item_output_cfg)
            merge = bool(item_output_cfg.get("merge", False) or wants_m4b)
            effective_per_chapter = bool(per_chapter and output_formats)
            if not output_formats and not wants_m4b:
                raise AudiobookJobError("no_output_formats", retryable=False)
            if not effective_per_chapter and not merge:
                raise AudiobookJobError("no_output_targets", retryable=False)
            if output_formats:
                if len(output_formats) > 1 and "wav" in output_formats:
                    base_format = "wav"
                else:
                    base_format = next((fmt for fmt in output_formats if fmt in SUPPORTED_TTS_FORMATS), None)
            else:
                base_format = "wav"
            if base_format is None or base_format not in SUPPORTED_TTS_FORMATS:
                raise AudiobookJobError("no_supported_output_formats", retryable=False)

            subtitle_formats = [str(fmt).lower() for fmt in (item_subtitle_cfg.get("formats") or [])]
            chapter_audio_paths: List[Path] = []
            chapter_titles: List[str] = []

            total_chapters = len(chapter_plan)
            for chapter in chapter_plan:
                chapter_global_index = global_chapter_index
                global_chapter_index += 1
                chapter_metadata = {
                    "chapter_id": chapter.chapter_id,
                    "chapter_index": chapter_global_index,
                    "item_index": item_index,
                    "item_tag": item_tag,
                    "item_title": item_title,
                    "voice": chapter.voice,
                    "speed": chapter.speed,
                    "voice_profile_id": chapter.voice_profile_id,
                }
                collections_db.create_audiobook_chapter(
                    project_id=project_db_id,
                    chapter_index=chapter_global_index,
                    title=chapter.title,
                    start_offset=chapter.start_offset,
                    end_offset=chapter.end_offset,
                    voice_profile_id=chapter.voice_profile_id,
                    speed=chapter.speed,
                    metadata_json=json.dumps(chapter_metadata),
                )
                jm.update_job_progress(
                    job_id,
                    progress_message=_progress_message(
                        "audiobook_tts",
                        chapter_index=chapter.index,
                        chapters_total=total_chapters,
                        item_index=item_index,
                        items_total=total_items,
                    ),
                    progress_percent=_progress_percent(
                        item_index,
                        total_items,
                        chapter.index,
                        total_chapters,
                        0.0,
                    ),
                )
                chapter_voice = chapter.voice
                requested_speed = chapter.speed
                time_stretch_ratio = _resolve_time_stretch_ratio(requested_speed)
                tts_speed = 1.0 if time_stretch_ratio else requested_speed
                alignment_payload = None
                chapter_title = chapter.title or f"Chapter {chapter.index + 1}"
                chapter_titles.append(chapter_title)

                if effective_per_chapter:
                    base_filename = _build_filename(item_prefix, f"{chapter.chapter_id}_audio", base_format)
                    base_path = outputs_dir / base_filename
                else:
                    base_filename = _build_filename(item_prefix, f"{chapter.chapter_id}_audio_tmp", base_format)
                    base_path = temp_outputs_dir / base_filename

                max_chars = _get_chapter_chunk_max_chars()
                segments = (
                    _split_text_by_max_chars(chapter.text, max_chars)
                    if max_chars is not None
                    else [ChapterSegment(text=chapter.text, start_offset=0, end_offset=len(chapter.text))]
                )
                segment_paths: List[Path] = []
                segment_alignments: List[Optional[dict]] = []
                segment_durations: List[int] = []
                segment_offsets: List[int] = []
                for seg_idx, segment in enumerate(segments):
                    if base_format not in SUPPORTED_TTS_FORMATS:
                        raise AudiobookJobError("unsupported_base_format", retryable=False)
                    seg_audio_bytes, seg_alignment = await _generate_tts_audio(
                        text=segment.text,
                        model=str(item_metadata.get("tts_model") or "kokoro"),
                        voice=chapter_voice,
                        speed=tts_speed,
                        response_format=base_format,
                        user_id=user_id,
                    )
                    if len(segments) == 1:
                        segment_path = base_path
                    else:
                        segment_filename = _build_filename(
                            item_prefix,
                            f"{chapter.chapter_id}_seg{seg_idx + 1}",
                            base_format,
                        )
                        segment_path = temp_outputs_dir / segment_filename
                    await asyncio.to_thread(segment_path.write_bytes, seg_audio_bytes)
                    segment_paths.append(segment_path)
                    segment_offsets.append(segment.start_offset)
                    segment_alignments.append(seg_alignment)
                    segment_durations.append(await _resolve_segment_duration_ms(seg_alignment, segment_path))

                if len(segment_paths) > 1:
                    ok_concat = await AudioConverter.concat_audio_files(segment_paths, base_path, base_format)
                    if not ok_concat:
                        raise AudiobookJobError("merge_failed", retryable=True)
                    for path in segment_paths:
                        if path == base_path:
                            continue
                        try:
                            path.unlink(missing_ok=True)
                        except Exception:
                            pass

                if segment_alignments and all(segment_alignments):
                    payloads = [AlignmentPayload(**payload) for payload in segment_alignments if payload]
                    offsets_ms = _build_segment_offsets_ms(segment_durations)
                    if len(payloads) == len(segment_alignments):
                        alignment_payload = stitch_alignment_payloads(
                            payloads,
                            segment_offsets_ms=offsets_ms,
                            segment_offsets_chars=segment_offsets,
                        ).model_dump()
                elif len(segment_alignments) == 1 and segment_alignments[0]:
                    alignment_payload = segment_alignments[0]
                elif segment_alignments and not all(segment_alignments):
                    logger.warning(
                        "audiobook worker: missing alignment for one or more segments in %s",
                        chapter.chapter_id,
                    )

                if alignment_payload and chapter.alignment_anchors:
                    alignment_model = AlignmentPayload(**alignment_payload)
                    alignment_model = apply_alignment_anchors_to_payload(
                        alignment_model,
                        chapter.alignment_anchors,
                    )
                    alignment_payload = alignment_model.model_dump()

                chapter_audio_paths.append(base_path)

                if time_stretch_ratio:
                    stretched_path = base_path.with_name(f"{base_path.stem}_stretch{base_path.suffix}")
                    ok_stretch = await AudioConverter.time_stretch(
                        base_path,
                        stretched_path,
                        time_stretch_ratio,
                    )
                    if ok_stretch:
                        replaced = False
                        try:
                            base_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                        try:
                            stretched_path.replace(base_path)
                            replaced = True
                        except Exception:
                            replaced = False
                        if not replaced:
                            logger.warning(
                                "audiobook worker: time-stretch replace failed for %s",
                                chapter.chapter_id,
                            )
                            try:
                                stretched_path.unlink(missing_ok=True)
                            except Exception:
                                pass
                        if replaced and alignment_payload:
                            alignment_model = AlignmentPayload(**alignment_payload)
                            alignment_model = scale_alignment_payload(alignment_model, time_stretch_ratio)
                            alignment_payload = alignment_model.model_dump()
                    else:
                        logger.warning(
                            "audiobook worker: time-stretch failed for %s (ratio=%s)",
                            chapter.chapter_id,
                            time_stretch_ratio,
                        )

                if effective_per_chapter:
                    if base_format not in SUPPORTED_TTS_FORMATS:
                        raise AudiobookJobError("unsupported_base_format", retryable=False)
                    base_meta = {
                        "project_id": project_id,
                        "chapter_id": chapter.chapter_id,
                        "chapter_index": chapter_global_index,
                        "scope": "chapter",
                        "artifact_type": "audio",
                        "source": source_metadata,
                        "format": base_format,
                        "item_index": item_index,
                        "item_tag": item_tag,
                        "item_title": item_title,
                    }
                    base_row = await asyncio.to_thread(
                        _create_output_and_link,
                        collections_db,
                        output_type=OUTPUT_TYPE_AUDIO,
                        title=f"{item_display_title} {chapter.chapter_id}",
                        format_=base_format,
                        storage_path=base_filename,
                        metadata_json=json.dumps(base_meta),
                        job_id=job_id,
                        project_db_id=project_db_id,
                        outputs_dir=outputs_dir,
                        quota_tracker=quota_tracker,
                    )
                    outputs.append(
                        {
                            "output_id": base_row.id,
                            "type": OUTPUT_TYPE_AUDIO,
                            "format": base_format,
                            "item_index": item_index,
                        }
                    )

                    for fmt in output_formats:
                        if fmt == base_format:
                            continue
                        if fmt not in SUPPORTED_TTS_FORMATS:
                            logger.warning(f"audiobook worker: unsupported tts format {fmt}; skipping")
                            continue
                        target_filename = _build_filename(item_prefix, f"{chapter.chapter_id}_audio", fmt)
                        target_path = outputs_dir / target_filename
                        conv_labels = {
                            "from_format": base_format,
                            "to_format": fmt,
                            "chapter_id": chapter.chapter_id,
                        }
                        log_counter("audiobook_audio_convert_attempt", labels=conv_labels)
                        start_convert = time.perf_counter()
                        ok_convert = await AudioConverter.convert_format(base_path, target_path, fmt)
                        duration = time.perf_counter() - start_convert
                        log_histogram("audiobook_audio_convert_duration_seconds", duration, labels=conv_labels)
                        if not ok_convert:
                            log_counter(
                                "audiobook_audio_convert_error",
                                labels={**conv_labels, "error": "conversion_failed"},
                            )
                            logger.warning(
                                f"audiobook worker: conversion failed for {base_format} -> {fmt} ({chapter.chapter_id})"
                            )
                            continue
                        log_counter("audiobook_audio_convert_success", labels=conv_labels)
                        try:
                            size_bytes = target_path.stat().st_size
                            log_histogram("audiobook_audio_convert_bytes", size_bytes, labels=conv_labels)
                        except Exception:
                            pass
                        meta = {
                            "project_id": project_id,
                            "chapter_id": chapter.chapter_id,
                            "chapter_index": chapter_global_index,
                            "scope": "chapter",
                            "artifact_type": "audio",
                            "source": source_metadata,
                            "format": fmt,
                            "converted_from": base_format,
                            "item_index": item_index,
                            "item_tag": item_tag,
                            "item_title": item_title,
                        }
                        row = await asyncio.to_thread(
                            _create_output_and_link,
                            collections_db,
                            output_type=OUTPUT_TYPE_AUDIO,
                            title=f"{item_display_title} {chapter.chapter_id}",
                            format_=fmt,
                            storage_path=target_filename,
                            metadata_json=json.dumps(meta),
                            job_id=job_id,
                            project_db_id=project_db_id,
                            outputs_dir=outputs_dir,
                            quota_tracker=quota_tracker,
                        )
                        outputs.append(
                            {
                                "output_id": row.id,
                                "type": OUTPUT_TYPE_AUDIO,
                                "format": fmt,
                                "item_index": item_index,
                            }
                        )

                if alignment_payload:
                    jm.update_job_progress(
                        job_id,
                        progress_message=_progress_message(
                            "audiobook_alignment",
                            chapter_index=chapter.index,
                            chapters_total=total_chapters,
                            item_index=item_index,
                            items_total=total_items,
                        ),
                        progress_percent=_progress_percent(
                            item_index,
                            total_items,
                            chapter.index,
                            total_chapters,
                            0.5,
                        ),
                    )
                    alignment_filename = _build_filename(item_prefix, f"{chapter.chapter_id}_alignment", "json")
                    alignment_path = outputs_dir / alignment_filename
                    await asyncio.to_thread(
                        alignment_path.write_text,
                        json.dumps(alignment_payload),
                        "utf-8",
                    )
                    align_meta = {
                        "project_id": project_id,
                        "chapter_id": chapter.chapter_id,
                        "chapter_index": chapter_global_index,
                        "scope": "chapter",
                        "artifact_type": "alignment",
                        "format": "json",
                        "item_index": item_index,
                        "item_tag": item_tag,
                        "item_title": item_title,
                    }
                    align_row = await asyncio.to_thread(
                        _create_output_and_link,
                        collections_db,
                        output_type=OUTPUT_TYPE_ALIGNMENT,
                        title=f"{item_display_title} {chapter.chapter_id} alignment",
                        format_="json",
                        storage_path=alignment_filename,
                        metadata_json=json.dumps(align_meta),
                        job_id=job_id,
                        project_db_id=project_db_id,
                        outputs_dir=outputs_dir,
                        quota_tracker=quota_tracker,
                    )
                    outputs.append(
                        {
                            "output_id": align_row.id,
                            "type": OUTPUT_TYPE_ALIGNMENT,
                            "format": "json",
                            "item_index": item_index,
                        }
                    )

                    if subtitle_formats:
                        jm.update_job_progress(
                            job_id,
                            progress_message=_progress_message(
                                "audiobook_subtitles",
                                chapter_index=chapter.index,
                                chapters_total=total_chapters,
                                item_index=item_index,
                                items_total=total_items,
                            ),
                            progress_percent=_progress_percent(
                                item_index,
                                total_items,
                                chapter.index,
                                total_chapters,
                                0.75,
                            ),
                        )
                        alignment_model = AlignmentPayload(**alignment_payload)
                        for fmt in subtitle_formats:
                            subtitle_text = generate_subtitles(
                                alignment_model,
                                format=fmt,
                                mode=item_subtitle_cfg.get("mode", "sentence"),
                                variant=item_subtitle_cfg.get("variant", "wide"),
                                source_text=chapter.text,
                                words_per_cue=item_subtitle_cfg.get("words_per_cue"),
                                max_chars=item_subtitle_cfg.get("max_chars"),
                                max_lines=item_subtitle_cfg.get("max_lines"),
                            )
                            subtitle_filename = _build_filename(
                                item_prefix,
                                f"{chapter.chapter_id}_subtitle",
                                fmt,
                            )
                            subtitle_path = outputs_dir / subtitle_filename
                            await asyncio.to_thread(subtitle_path.write_text, subtitle_text, "utf-8")
                            subtitle_meta = {
                                "project_id": project_id,
                                "chapter_id": chapter.chapter_id,
                                "chapter_index": chapter_global_index,
                                "scope": "chapter",
                                "artifact_type": "subtitle",
                                "format": fmt,
                                "item_index": item_index,
                                "item_tag": item_tag,
                                "item_title": item_title,
                            }
                            subtitle_row = await asyncio.to_thread(
                                _create_output_and_link,
                                collections_db,
                                output_type=OUTPUT_TYPE_SUBTITLE,
                                title=f"{item_display_title} {chapter.chapter_id} subtitle",
                                format_=fmt,
                                storage_path=subtitle_filename,
                                metadata_json=json.dumps(subtitle_meta),
                                job_id=job_id,
                                project_db_id=project_db_id,
                                outputs_dir=outputs_dir,
                                quota_tracker=quota_tracker,
                            )
                            outputs.append(
                                {
                                    "output_id": subtitle_row.id,
                                    "type": OUTPUT_TYPE_SUBTITLE,
                                    "format": fmt,
                                    "item_index": item_index,
                                }
                            )

                jm.update_job_progress(
                    job_id,
                    progress_message=_progress_message(
                        "audiobook_chapter_complete",
                        chapter_index=chapter.index,
                        chapters_total=total_chapters,
                        item_index=item_index,
                        items_total=total_items,
                    ),
                    progress_percent=_progress_percent(
                        item_index,
                        total_items,
                        chapter.index,
                        total_chapters,
                        1.0,
                    ),
                )

            if merge and not per_chapter:
                logger.info("audiobook worker: merge-only output requested for %s", item_tag)

            if merge:
                merged_base_path: Optional[Path] = None
                merged_base_filename: Optional[str] = None
                if output_formats:
                    merged_base_filename = _build_filename(item_prefix, "merged_audio", base_format)
                    merged_base_path = outputs_dir / merged_base_filename
                    ok_merge = await AudioConverter.concat_audio_files(
                        chapter_audio_paths,
                        merged_base_path,
                        base_format,
                    )
                    if not ok_merge:
                        raise AudiobookJobError("merge_failed", retryable=True)

                    merged_meta = {
                        "project_id": project_id,
                        "scope": "merged",
                        "artifact_type": "audio",
                        "format": base_format,
                        "item_index": item_index,
                        "item_tag": item_tag,
                        "item_title": item_title,
                    }
                    merged_row = await asyncio.to_thread(
                        _create_output_and_link,
                        collections_db,
                        output_type=OUTPUT_TYPE_AUDIO,
                        title=f"{item_display_title} merged audio",
                        format_=base_format,
                        storage_path=merged_base_filename,
                        metadata_json=json.dumps(merged_meta),
                        job_id=job_id,
                        project_db_id=project_db_id,
                        outputs_dir=outputs_dir,
                        quota_tracker=quota_tracker,
                    )
                    outputs.append(
                        {
                            "output_id": merged_row.id,
                            "type": OUTPUT_TYPE_AUDIO,
                            "format": base_format,
                            "item_index": item_index,
                        }
                    )

                    for fmt in output_formats:
                        if fmt == base_format:
                            continue
                        if fmt not in SUPPORTED_TTS_FORMATS:
                            logger.warning("audiobook worker: unsupported merged format %s; skipping", fmt)
                            continue
                        merged_filename = _build_filename(item_prefix, "merged_audio", fmt)
                        merged_path = outputs_dir / merged_filename
                        ok_convert = await AudioConverter.convert_format(merged_base_path, merged_path, fmt)
                        if not ok_convert:
                            logger.warning("audiobook worker: merge conversion failed for %s -> %s", base_format, fmt)
                            continue
                        merged_meta = {
                            "project_id": project_id,
                            "scope": "merged",
                            "artifact_type": "audio",
                            "format": fmt,
                            "converted_from": base_format,
                            "item_index": item_index,
                            "item_tag": item_tag,
                            "item_title": item_title,
                        }
                        merged_row = await asyncio.to_thread(
                            _create_output_and_link,
                            collections_db,
                            output_type=OUTPUT_TYPE_AUDIO,
                            title=f"{item_display_title} merged audio",
                            format_=fmt,
                            storage_path=merged_filename,
                            metadata_json=json.dumps(merged_meta),
                            job_id=job_id,
                            project_db_id=project_db_id,
                            outputs_dir=outputs_dir,
                            quota_tracker=quota_tracker,
                        )
                        outputs.append(
                            {
                                "output_id": merged_row.id,
                                "type": OUTPUT_TYPE_AUDIO,
                                "format": fmt,
                                "item_index": item_index,
                            }
                        )

                if wants_m4b:
                    m4b_filename = _build_filename(item_prefix, "merged_audio", "m4b")
                    m4b_path = outputs_dir / m4b_filename
                    m4b_metadata = {
                        "title": item_title or project_title,
                        "artist": source_metadata.get("author"),
                    }
                    ok_m4b = await AudioConverter.package_m4b_with_chapters(
                        chapter_audio_paths,
                        m4b_path,
                        chapter_titles,
                        metadata=m4b_metadata,
                    )
                    if not ok_m4b:
                        logger.warning("audiobook worker: m4b packaging failed for %s", item_tag)
                    else:
                        m4b_meta = {
                            "project_id": project_id,
                            "scope": "merged",
                            "artifact_type": "package",
                            "format": "m4b",
                            "item_index": item_index,
                            "item_tag": item_tag,
                            "item_title": item_title,
                        }
                        m4b_row = await asyncio.to_thread(
                            _create_output_and_link,
                            collections_db,
                            output_type=OUTPUT_TYPE_PACKAGE,
                            title=f"{item_display_title} m4b",
                            format_="m4b",
                            storage_path=m4b_filename,
                            metadata_json=json.dumps(m4b_meta),
                            job_id=job_id,
                            project_db_id=project_db_id,
                            outputs_dir=outputs_dir,
                            quota_tracker=quota_tracker,
                        )
                        outputs.append(
                            {
                                "output_id": m4b_row.id,
                                "type": OUTPUT_TYPE_PACKAGE,
                                "format": "m4b",
                                "item_index": item_index,
                            }
                        )

                if not effective_per_chapter:
                    for path in chapter_audio_paths:
                        try:
                            if path.exists():
                                path.unlink()
                        except Exception:
                            pass

        if project_db_id is not None:
            try:
                collections_db.update_audiobook_project_status(project_db_id, status="completed")
            except Exception as exc:
                logger.warning("audiobook worker: failed to update project status: %s", exc)
        jm.complete_job(
            job_id,
            result={"project_id": project_id, "outputs": outputs},
            worker_id=worker_id,
            lease_id=lease_id,
            completion_token=lease_id,
        )
    except AudiobookJobError as exc:
        if project_db_id is not None:
            try:
                collections_db.update_audiobook_project_status(project_db_id, status="failed")
            except Exception as status_exc:
                logger.warning("audiobook worker: failed to update project status: %s", status_exc)
        jm.fail_job(
            job_id,
            error=str(exc),
            retryable=exc.retryable,
            worker_id=worker_id,
            lease_id=lease_id,
            completion_token=lease_id,
        )
    except Exception as exc:
        if project_db_id is not None:
            try:
                collections_db.update_audiobook_project_status(project_db_id, status="failed")
            except Exception as status_exc:
                logger.warning("audiobook worker: failed to update project status: %s", status_exc)
        jm.fail_job(
            job_id,
            error=str(exc),
            retryable=True,
            worker_id=worker_id,
            lease_id=lease_id,
            completion_token=lease_id,
        )
    finally:
        if acquired_slot:
            try:
                await finish_job(user_id)
            except Exception as exc:
                logger.warning(f"Failed to release audiobook job slot: {exc}")


async def run_audiobook_jobs_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    jm = JobManager()
    worker_id = "audiobook-worker"
    poll_sleep = float(os.getenv("JOBS_POLL_INTERVAL_SECONDS", "1.0") or "1.0")

    logger.info("Starting Audiobook Jobs worker")
    while True:
        if stop_event and stop_event.is_set():
            logger.info("Stopping Audiobook Jobs worker on shutdown signal")
            return
        try:
            lease_seconds = int(os.getenv("JOBS_LEASE_SECONDS", "120") or "120")
            job = jm.acquire_next_job(domain=DOMAIN, queue="default", lease_seconds=lease_seconds, worker_id=worker_id)
            if not job:
                await asyncio.sleep(poll_sleep)
                continue
            if str(job.get("job_type", "")).lower() != JOB_TYPE:
                jm.fail_job(
                    int(job["id"]),
                    error="unsupported job type",
                    retryable=False,
                    worker_id=worker_id,
                    lease_id=str(job.get("lease_id")),
                    completion_token=str(job.get("lease_id")),
                )
                continue
            await process_audiobook_job(job, job_manager=jm, worker_id=worker_id)
        except Exception as exc:
            logger.error(f"Audiobook worker loop error: {exc}")


if __name__ == "__main__":
    try:
        asyncio.run(run_audiobook_jobs_worker())
    except KeyboardInterrupt:
        pass
