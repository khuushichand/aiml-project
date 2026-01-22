"""API endpoints for audiobook creation."""

from __future__ import annotations

import json
from pathlib import Path as PathlibPath
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import PlainTextResponse
from starlette import status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.audiobook_schemas import (
    ArtifactInfo,
    AudiobookArtifactsResponse,
    AudiobookJobCreateResponse,
    AudiobookJobRequest,
    AudiobookJobStatusResponse,
    AudiobookParseRequest,
    AudiobookParseResponse,
    ChapterPreview,
    SubtitleExportRequest,
    VoiceProfileCreateRequest,
    VoiceProfileDeleteResponse,
    VoiceProfileListResponse,
    VoiceProfileResponse,
)
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Chunking.strategies.ebook_chapters import EbookChapterChunkingStrategy
from tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib import (
    extract_epub_metadata_from_text,
    process_epub,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import (
    extract_text_and_format_from_pdf,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.path_utils import resolve_safe_local_path
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.Audiobooks.subtitle_generator import generate_subtitles
from tldw_Server_API.app.core.Jobs.manager import JobManager

router = APIRouter(prefix="/audiobooks", tags=["audiobooks"])


def _not_implemented(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


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


def _resolve_upload_path(upload_id: str, user_id: int) -> Optional[PathlibPath]:
    if not upload_id:
        return None
    base_dir = DatabasePaths.get_user_temp_outputs_dir(user_id)
    safe_path = resolve_safe_local_path(PathlibPath(upload_id), base_dir)
    if safe_path is None:
        return None
    if not safe_path.exists():
        return None
    return safe_path


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


def _get_job_manager() -> JobManager:
    return JobManager()


def _normalize_job_status(status: Optional[str]) -> str:
    if not status:
        return "queued"
    norm = status.lower()
    if norm == "cancelled":
        return "canceled"
    if norm == "quarantined":
        return "failed"
    return norm


def _job_project_id(job_row: dict) -> str:
    payload = job_row.get("payload") if isinstance(job_row, dict) else None
    if isinstance(payload, dict):
        project_id = payload.get("project_id")
        if isinstance(project_id, str) and project_id:
            return project_id
    return f"abk_{job_row.get('id', 0)}"


@router.post(
    "/parse",
    response_model=AudiobookParseResponse,
    summary="Parse audiobook source and detect chapters",
)
async def parse_audiobook_source(
    request: AudiobookParseRequest,
    _current_user: User = Depends(get_request_user),
    media_db=Depends(get_media_db_for_user),
) -> AudiobookParseResponse:
    source = request.source
    input_type = source.input_type
    text: Optional[str] = None
    metadata: dict = {"source_type": input_type}

    if source.raw_text:
        text = source.raw_text
        title, author = extract_epub_metadata_from_text(text)
        if title:
            metadata["title"] = title
        if author:
            metadata["author"] = author
    elif source.media_id is not None:
        try:
            media_id = int(source.media_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_media_id") from exc
        record = media_db.get_media_by_id(media_id)
        if not record:
            raise HTTPException(status_code=404, detail="media_not_found")
        text = record.get("content") or ""
        metadata["title"] = record.get("title")
        if record.get("author"):
            metadata["author"] = record.get("author")
    elif source.upload_id:
        upload_path = _resolve_upload_path(source.upload_id, int(_current_user.id))
        if upload_path is None:
            raise HTTPException(status_code=404, detail="upload_not_found")
        try:
            if input_type == "epub":
                result = process_epub(str(upload_path), perform_chunking=False)
                text = result.get("content") or ""
                if result.get("metadata"):
                    meta = result["metadata"]
                    if meta.get("title"):
                        metadata["title"] = meta.get("title")
                    if meta.get("author"):
                        metadata["author"] = meta.get("author")
            elif input_type == "pdf":
                text = extract_text_and_format_from_pdf(str(upload_path))
            else:
                text = upload_path.read_text(encoding="utf-8", errors="ignore")
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to parse upload for audiobook")
            raise HTTPException(status_code=500, detail="parse_failed") from exc

    if text is None:
        raise HTTPException(status_code=400, detail="no_source_text")

    normalized_text = _normalize_subtitles(text, input_type)
    if request.max_chars and len(normalized_text) > request.max_chars:
        normalized_text = normalized_text[: request.max_chars]

    chapters: list[ChapterPreview] = []
    if request.detect_chapters:
        try:
            chapters = _detect_chapters(
                normalized_text,
                language=request.language,
                custom_pattern=request.custom_chapter_pattern,
            )
        except Exception as exc:
            logger.warning(f"Chapter detection failed: {exc}")
            raise HTTPException(status_code=400, detail="chapter_detection_failed") from exc

    project_id = f"abk_{uuid4().hex[:12]}"
    return AudiobookParseResponse(
        project_id=project_id,
        normalized_text=normalized_text,
        chapters=chapters,
        metadata=metadata,
    )


@router.post(
    "/jobs",
    response_model=AudiobookJobCreateResponse,
    summary="Create an audiobook generation job",
)
async def create_audiobook_job(
    request: AudiobookJobRequest,
    _current_user: User = Depends(get_request_user),
) -> AudiobookJobCreateResponse:
    project_id = f"abk_{uuid4().hex[:12]}"
    priority = 5
    if request.queue is not None:
        try:
            priority = int(request.queue.priority)
        except Exception:
            priority = 5
    if priority < 1:
        priority = 1
    if priority > 10:
        priority = 10

    payload = request.model_dump()
    payload["project_id"] = project_id

    job_manager = _get_job_manager()
    job = job_manager.create_job(
        domain="audiobooks",
        queue="default",
        job_type="audiobook_generate",
        payload=payload,
        owner_user_id=str(getattr(_current_user, "id", "")),
        priority=priority,
    )

    return AudiobookJobCreateResponse(
        job_id=int(job["id"]),
        project_id=project_id,
        status=_normalize_job_status(job.get("status")),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=AudiobookJobStatusResponse,
    summary="Get audiobook job status",
)
async def get_audiobook_job_status(
    job_id: int = Path(..., ge=1, description="Audiobook job id"),
    _current_user: User = Depends(get_request_user),
) -> AudiobookJobStatusResponse:
    job_manager = _get_job_manager()
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")

    status = _normalize_job_status(job.get("status"))
    project_id = _job_project_id(job)

    errors: list[str] = []
    for key in ("error_message", "last_error", "error_code"):
        value = job.get(key)
        if value:
            errors.append(str(value))

    progress = None
    percent = job.get("progress_percent")
    stage = job.get("progress_message")
    if percent is not None or stage:
        try:
            percent_val = int(percent) if percent is not None else None
        except Exception:
            percent_val = None
        progress = {
            "stage": str(stage or "audiobook_job"),
            "percent": percent_val,
        }

    return AudiobookJobStatusResponse(
        job_id=int(job["id"]),
        project_id=project_id,
        status=status,
        progress=progress,
        errors=errors,
    )


@router.get(
    "/jobs/{job_id}/artifacts",
    response_model=AudiobookArtifactsResponse,
    summary="List audiobook job artifacts",
)
async def get_audiobook_job_artifacts(
    job_id: int = Path(..., ge=1, description="Audiobook job id"),
    _current_user: User = Depends(get_request_user),
) -> AudiobookArtifactsResponse:
    job_manager = _get_job_manager()
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    project_id = _job_project_id(job)
    user_id = getattr(_current_user, "id", None)
    if user_id is None:
        return AudiobookArtifactsResponse(project_id=project_id, artifacts=[])

    collections_db = CollectionsDatabase(user_id)
    rows, _total = collections_db.list_output_artifacts(job_id=int(job_id), limit=200, offset=0)
    artifacts: list[ArtifactInfo] = []
    type_map = {
        "audiobook_audio": "audio",
        "audiobook_subtitle": "subtitle",
        "audiobook_alignment": "alignment",
        "audiobook_package": "package",
    }
    for row in rows:
        metadata = {}
        if row.metadata_json:
            try:
                metadata = json.loads(row.metadata_json)
            except Exception:
                metadata = {}
        artifact_type = metadata.get("artifact_type")
        if not artifact_type:
            artifact_type = type_map.get(str(row.type), "audio")
        artifact_type = str(artifact_type)
        scope = metadata.get("scope")
        chapter_id = metadata.get("chapter_id")
        download_url = f"/api/v1/outputs/{row.id}/download"
        artifacts.append(
            ArtifactInfo(
                artifact_type=artifact_type,
                format=row.format,
                scope=scope,
                chapter_id=chapter_id,
                output_id=row.id,
                download_url=download_url,
            )
        )
    return AudiobookArtifactsResponse(project_id=project_id, artifacts=artifacts)


@router.post(
    "/voices/profiles",
    response_model=VoiceProfileResponse,
    summary="Create a voice profile",
)
async def create_voice_profile(
    request: VoiceProfileCreateRequest,
    _current_user: User = Depends(get_request_user),
) -> VoiceProfileResponse:
    _not_implemented("audiobook_voice_profile_create_not_implemented")


@router.get(
    "/voices/profiles",
    response_model=VoiceProfileListResponse,
    summary="List voice profiles",
)
async def list_voice_profiles(
    _current_user: User = Depends(get_request_user),
) -> VoiceProfileListResponse:
    _not_implemented("audiobook_voice_profile_list_not_implemented")


@router.delete(
    "/voices/profiles/{profile_id}",
    response_model=VoiceProfileDeleteResponse,
    summary="Delete a voice profile",
)
async def delete_voice_profile(
    profile_id: str = Path(..., min_length=1, description="Voice profile id"),
    _current_user: User = Depends(get_request_user),
) -> VoiceProfileDeleteResponse:
    _not_implemented("audiobook_voice_profile_delete_not_implemented")


@router.post(
    "/subtitles",
    response_class=PlainTextResponse,
    summary="Render subtitles from alignment data",
    responses={
        200: {
            "content": {
                "text/plain": {
                    "example": "1\n00:00:00,000 --> 00:00:00,900\nHello world",
                }
            }
        }
    },
)
async def export_subtitles(
    request: SubtitleExportRequest,
    _current_user: User = Depends(get_request_user),
) -> PlainTextResponse:
    try:
        content = generate_subtitles(
            request.alignment,
            format=request.format,
            mode=request.mode,
            variant=request.variant,
            words_per_cue=request.words_per_cue,
            max_chars=request.max_chars,
            max_lines=request.max_lines,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(content)
