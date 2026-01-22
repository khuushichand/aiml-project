from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
from tldw_Server_API.app.api.v1.schemas.audiobook_schemas import AlignmentPayload, ChapterPreview
from tldw_Server_API.app.core.Audiobooks.subtitle_generator import generate_subtitles
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
from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
from tldw_Server_API.app.core.TTS.tts_validation import TTSInputValidator
from tldw_Server_API.app.core.TTS.audio_converter import AudioConverter
from tldw_Server_API.app.core.Usage.audio_quota import can_start_job, finish_job, increment_jobs_started

DOMAIN = "audiobooks"
JOB_TYPE = "audiobook_generate"

OUTPUT_TYPE_AUDIO = "audiobook_audio"
OUTPUT_TYPE_SUBTITLE = "audiobook_subtitle"
OUTPUT_TYPE_ALIGNMENT = "audiobook_alignment"

SUPPORTED_TTS_FORMATS = {"mp3", "wav", "flac", "opus", "aac", "pcm"}


@dataclass
class ChapterPlanItem:
    chapter_id: str
    title: Optional[str]
    text: str
    voice: Optional[str]
    speed: Optional[float]
    index: int
    total: int


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


def _build_filename(prefix: str, suffix: str, ext: str) -> str:
    base = _sanitize_filename(prefix)
    tag = _sanitize_filename(suffix)
    ext_clean = _sanitize_filename(ext)
    return f"{base}_{tag}.{ext_clean}"


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


def _load_source_text(source: Dict[str, Any], user_id: int) -> Tuple[str, Dict[str, Any]]:
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
    return normalized, metadata


def _build_chapter_plan(
    text: str,
    chapter_specs: Optional[List[Dict[str, Any]]],
    *,
    language: Optional[str] = None,
    custom_pattern: Optional[str] = None,
) -> List[ChapterPlanItem]:
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
        else:
            chapter_text = text
            title = None
        plan.append(
            ChapterPlanItem(
                chapter_id=chapter_id,
                title=title,
                text=chapter_text,
                voice=spec.get("voice"),
                speed=spec.get("speed"),
                index=len(plan),
                total=len(selected),
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
            voice=item.voice,
            speed=item.speed,
            index=i,
            total=total,
        )
        for i, item in enumerate(plan)
    ]
    return plan


def _resolve_output_formats(output_cfg: Dict[str, Any]) -> List[str]:
    formats = output_cfg.get("formats") or []
    resolved = []
    for fmt in formats:
        fmt_lower = str(fmt).lower()
        if fmt_lower == "m4b":
            logger.warning("audiobook worker: m4b output not implemented; skipping")
            continue
        resolved.append(fmt_lower)
    return resolved


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

    source = payload.get("source") or {}
    output_cfg = payload.get("output") or {}
    subtitle_cfg = payload.get("subtitles") or {}
    chapter_specs = payload.get("chapters")
    metadata = payload.get("metadata") or {}
    language = payload.get("language")
    custom_pattern = payload.get("custom_chapter_pattern")

    per_chapter = bool(output_cfg.get("per_chapter", True))
    merge = bool(output_cfg.get("merge", False))
    output_formats = _resolve_output_formats(output_cfg)
    if not output_formats:
        raise AudiobookJobError("no_output_formats", retryable=False)
    base_format = next((fmt for fmt in output_formats if fmt in SUPPORTED_TTS_FORMATS), None)
    if base_format is None:
        raise AudiobookJobError("no_supported_output_formats", retryable=False)

    subtitle_formats = [str(fmt).lower() for fmt in (subtitle_cfg.get("formats") or [])]

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

    outputs: List[Dict[str, Any]] = []
    try:
        jm.update_job_progress(job_id, progress_message="audiobook_parse", progress_percent=0)
        text, source_metadata = _load_source_text(source, user_id)
        normalized_text = _validate_text(text)
        chapter_plan = _build_chapter_plan(
            normalized_text,
            chapter_specs,
            language=language,
            custom_pattern=custom_pattern,
        )

        total_chapters = len(chapter_plan)
        for chapter in chapter_plan:
            jm.update_job_progress(
                job_id,
                progress_message="audiobook_tts",
                progress_percent=int((chapter.index / max(1, total_chapters)) * 100),
            )
            chapter_voice = chapter.voice
            chapter_speed = chapter.speed
            alignment_payload = None

            if per_chapter:
                if base_format not in SUPPORTED_TTS_FORMATS:
                    raise AudiobookJobError("unsupported_base_format", retryable=False)
                audio_bytes, alignment_payload = await _generate_tts_audio(
                    text=chapter.text,
                    model=str(metadata.get("tts_model") or "kokoro"),
                    voice=chapter_voice,
                    speed=chapter_speed,
                    response_format=base_format,
                    user_id=user_id,
                )
                base_filename = _build_filename(project_title, f"{chapter.chapter_id}_audio", base_format)
                base_path = outputs_dir / base_filename
                await asyncio.to_thread(base_path.write_bytes, audio_bytes)
                base_meta = {
                    "project_id": project_id,
                    "chapter_id": chapter.chapter_id,
                    "scope": "chapter",
                    "artifact_type": "audio",
                    "source": source_metadata,
                    "format": base_format,
                }
                base_row = await asyncio.to_thread(
                    lambda: collections_db.create_output_artifact(
                        type_=OUTPUT_TYPE_AUDIO,
                        title=f"{project_title} {chapter.chapter_id}",
                        format_=base_format,
                        storage_path=base_filename,
                        metadata_json=json.dumps(base_meta),
                        job_id=job_id,
                    )
                )
                outputs.append({"output_id": base_row.id, "type": OUTPUT_TYPE_AUDIO, "format": base_format})

                for fmt in output_formats:
                    if fmt == base_format:
                        continue
                    if fmt not in SUPPORTED_TTS_FORMATS:
                        logger.warning(f"audiobook worker: unsupported tts format {fmt}; skipping")
                        continue
                    target_filename = _build_filename(project_title, f"{chapter.chapter_id}_audio", fmt)
                    target_path = outputs_dir / target_filename
                    ok_convert = await AudioConverter.convert_format(
                        base_path,
                        target_path,
                        fmt,
                    )
                    if not ok_convert:
                        logger.warning(
                            f"audiobook worker: conversion failed for {base_format} -> {fmt} ({chapter.chapter_id})"
                        )
                        continue
                    meta = {
                        "project_id": project_id,
                        "chapter_id": chapter.chapter_id,
                        "scope": "chapter",
                        "artifact_type": "audio",
                        "source": source_metadata,
                        "format": fmt,
                        "converted_from": base_format,
                    }
                    row = await asyncio.to_thread(
                        lambda: collections_db.create_output_artifact(
                            type_=OUTPUT_TYPE_AUDIO,
                            title=f"{project_title} {chapter.chapter_id}",
                            format_=fmt,
                            storage_path=target_filename,
                            metadata_json=json.dumps(meta),
                            job_id=job_id,
                        )
                    )
                    outputs.append({"output_id": row.id, "type": OUTPUT_TYPE_AUDIO, "format": fmt})

            if alignment_payload:
                jm.update_job_progress(
                    job_id,
                    progress_message="audiobook_alignment",
                    progress_percent=int(((chapter.index + 0.5) / max(1, total_chapters)) * 100),
                )
                alignment_filename = _build_filename(project_title, f"{chapter.chapter_id}_alignment", "json")
                alignment_path = outputs_dir / alignment_filename
                await asyncio.to_thread(
                    alignment_path.write_text,
                    json.dumps(alignment_payload),
                    "utf-8",
                )
                align_meta = {
                    "project_id": project_id,
                    "chapter_id": chapter.chapter_id,
                    "scope": "chapter",
                    "artifact_type": "alignment",
                    "format": "json",
                }
                align_row = await asyncio.to_thread(
                    lambda: collections_db.create_output_artifact(
                        type_=OUTPUT_TYPE_ALIGNMENT,
                        title=f"{project_title} {chapter.chapter_id} alignment",
                        format_="json",
                        storage_path=alignment_filename,
                        metadata_json=json.dumps(align_meta),
                        job_id=job_id,
                    )
                )
                outputs.append({"output_id": align_row.id, "type": OUTPUT_TYPE_ALIGNMENT, "format": "json"})

                if subtitle_formats:
                    jm.update_job_progress(
                        job_id,
                        progress_message="audiobook_subtitles",
                        progress_percent=int(((chapter.index + 0.75) / max(1, total_chapters)) * 100),
                    )
                    alignment_model = AlignmentPayload(**alignment_payload)
                    for fmt in subtitle_formats:
                        subtitle_text = generate_subtitles(
                            alignment_model,
                            format=fmt,
                            mode=subtitle_cfg.get("mode", "sentence"),
                            variant=subtitle_cfg.get("variant", "wide"),
                            words_per_cue=subtitle_cfg.get("words_per_cue"),
                            max_chars=subtitle_cfg.get("max_chars"),
                            max_lines=subtitle_cfg.get("max_lines"),
                        )
                        subtitle_filename = _build_filename(
                            project_title,
                            f"{chapter.chapter_id}_subtitle",
                            fmt,
                        )
                        subtitle_path = outputs_dir / subtitle_filename
                        await asyncio.to_thread(subtitle_path.write_text, subtitle_text, "utf-8")
                        subtitle_meta = {
                            "project_id": project_id,
                            "chapter_id": chapter.chapter_id,
                            "scope": "chapter",
                            "artifact_type": "subtitle",
                            "format": fmt,
                        }
                        subtitle_row = await asyncio.to_thread(
                            lambda: collections_db.create_output_artifact(
                                type_=OUTPUT_TYPE_SUBTITLE,
                                title=f"{project_title} {chapter.chapter_id} subtitle",
                                format_=fmt,
                                storage_path=subtitle_filename,
                                metadata_json=json.dumps(subtitle_meta),
                                job_id=job_id,
                            )
                        )
                        outputs.append({"output_id": subtitle_row.id, "type": OUTPUT_TYPE_SUBTITLE, "format": fmt})

            jm.update_job_progress(
                job_id,
                progress_message="audiobook_chapter_complete",
                progress_percent=int(((chapter.index + 1) / max(1, total_chapters)) * 100),
            )

        if merge and not per_chapter:
            logger.warning("audiobook worker: merge-only output not implemented; no merged artifact created")

        jm.complete_job(
            job_id,
            result={"project_id": project_id, "outputs": outputs},
            worker_id=worker_id,
            lease_id=lease_id,
            completion_token=lease_id,
        )
    except AudiobookJobError as exc:
        jm.fail_job(
            job_id,
            error=str(exc),
            retryable=exc.retryable,
            worker_id=worker_id,
            lease_id=lease_id,
            completion_token=lease_id,
        )
    except Exception as exc:
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
