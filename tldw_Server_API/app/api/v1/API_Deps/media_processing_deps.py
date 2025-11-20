from __future__ import annotations

from typing import List, Optional

import json
from fastapi import Form, HTTPException, status
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.media_request_models import (
    ProcessAudiosForm,
    ProcessDocumentsForm,
    ProcessVideosForm,
)

try:
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT
except AttributeError:  # Starlette < 0.27
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY


def _coerce_urls(urls: Optional[List[str]]) -> Optional[List[str]]:
    """
    Normalize urls form input into a list of strings.

    Allows clients to send:
      - a single string
      - a JSON-encoded list string
      - a list of strings
    """
    if urls is None:
        return None
    if isinstance(urls, list):
        if len(urls) == 1 and isinstance(urls[0], str):
            first = urls[0]
            stripped = first.strip()
            if stripped.startswith("[") or stripped.startswith('"'):
                try:
                    parsed = json.loads(first)
                    if isinstance(parsed, list):
                        return [str(u) for u in parsed]
                    return [str(parsed)]
                except Exception:
                    return [first]
        return [str(u) for u in urls]
    if isinstance(urls, str):
        stripped = urls.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(u) for u in parsed]
            return [str(parsed)]
        except Exception:
            return [urls]
    return [str(urls)]


def _raise_422(exc: ValidationError) -> None:
    serializable_errors = []
    for error in exc.errors():
        err = error.copy()
        ctx = err.get("ctx")
        if isinstance(ctx, dict):
            err["ctx"] = {
                k: (str(v) if isinstance(v, Exception) else v)
                for k, v in ctx.items()
            }
        serializable_errors.append(err)
    raise HTTPException(
        status_code=HTTP_422_UNPROCESSABLE,
        detail=serializable_errors,
    ) from exc


async def get_process_documents_form(
    urls: Optional[List[str]] = Form(None),
    title: Optional[str] = Form(None),
    titles: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    keywords: str = Form(""),
    custom_prompt: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None),
    keep_original_file: bool = Form(False),
    perform_analysis: bool = Form(True),
    perform_chunking: bool = Form(True),
    summarize_recursively: bool = Form(False),
    chunk_method: Optional[str] = Form(None),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(200),
    api_provider: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    api_name: Optional[str] = Form(None),
    use_cookies: bool = Form(False),
    cookies: Optional[str] = Form(None),
) -> ProcessDocumentsForm:
    """
    Dependency that parses multipart/form-data into a ProcessDocumentsForm.

    Used by /media/process-documents (no DB persistence).
    """
    try:
        urls_norm = _coerce_urls(urls)
        title_val = title or titles
        return ProcessDocumentsForm(
            urls=urls_norm,
            title=title_val,
            author=author,
            keywords=keywords,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            keep_original_file=keep_original_file,
            perform_analysis=perform_analysis,
            perform_chunking=perform_chunking,
            summarize_recursively=summarize_recursively,
            chunk_method=chunk_method,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            api_provider=api_provider,
            model_name=model_name,
            api_name=api_name,
            use_cookies=use_cookies,
            cookies=cookies,
        )
    except ValidationError as exc:
        _raise_422(exc)


async def get_process_videos_form(
    urls: Optional[List[str]] = Form(None),
    title: Optional[str] = Form(None),
    titles: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    keywords: str = Form(""),
    custom_prompt: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None),
    perform_analysis: bool = Form(True),
    perform_chunking: bool = Form(True),
    summarize_recursively: bool = Form(False),
    transcription_model: str = Form(
        "deepdml/faster-distil-whisper-large-v3.5",
        description="Transcription model for video audio tracks",
    ),
    transcription_language: str = Form("en"),
    diarize: bool = Form(False),
    timestamp_option: bool = Form(True),
    vad_use: bool = Form(False),
    perform_confabulation_check_of_analysis: bool = Form(False),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    api_provider: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    api_name: Optional[str] = Form(None),
    use_cookies: bool = Form(False),
    cookies: Optional[str] = Form(None),
    chunk_method: Optional[str] = Form(None),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(200),
) -> ProcessVideosForm:
    """
    Dependency that parses multipart/form-data into a ProcessVideosForm.

    Used by /media/process-videos (no DB persistence).
    """
    try:
        urls_norm = _coerce_urls(urls)
        title_val = title or titles
        return ProcessVideosForm(
            urls=urls_norm,
            title=title_val,
            author=author,
            keywords=keywords,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            perform_analysis=perform_analysis,
            perform_chunking=perform_chunking,
            summarize_recursively=summarize_recursively,
            transcription_model=transcription_model,
            transcription_language=transcription_language,
            diarize=diarize,
            timestamp_option=timestamp_option,
            vad_use=vad_use,
            perform_confabulation_check_of_analysis=perform_confabulation_check_of_analysis,
            start_time=start_time,
            end_time=end_time,
            api_provider=api_provider,
            model_name=model_name,
            api_name=api_name,
            use_cookies=use_cookies,
            cookies=cookies,
            chunk_method=chunk_method,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except ValidationError as exc:
        _raise_422(exc)


async def get_process_audios_form(
    urls: Optional[List[str]] = Form(None),
    title: Optional[str] = Form(None),
    titles: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    keywords: str = Form(""),
    custom_prompt: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None),
    perform_analysis: bool = Form(True),
    perform_chunking: bool = Form(True),
    summarize_recursively: bool = Form(False),
    transcription_model: str = Form(
        "deepdml/faster-distil-whisper-large-v3.5",
        description="Transcription model for audio inputs",
    ),
    transcription_language: str = Form("en"),
    diarize: bool = Form(False),
    timestamp_option: bool = Form(True),
    vad_use: bool = Form(False),
    perform_confabulation_check_of_analysis: bool = Form(False),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    api_provider: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    api_name: Optional[str] = Form(None),
    use_cookies: bool = Form(False),
    cookies: Optional[str] = Form(None),
    chunk_method: Optional[str] = Form(None),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(200),
) -> ProcessAudiosForm:
    """
    Dependency that parses multipart/form-data into a ProcessAudiosForm.

    Used by /media/process-audios (no DB persistence).
    """
    try:
        urls_norm = _coerce_urls(urls)
        title_val = title or titles
        return ProcessAudiosForm(
            urls=urls_norm,
            title=title_val,
            author=author,
            keywords=keywords,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            perform_analysis=perform_analysis,
            perform_chunking=perform_chunking,
            summarize_recursively=summarize_recursively,
            transcription_model=transcription_model,
            transcription_language=transcription_language,
            diarize=diarize,
            timestamp_option=timestamp_option,
            vad_use=vad_use,
            perform_confabulation_check_of_analysis=perform_confabulation_check_of_analysis,
            start_time=start_time,
            end_time=end_time,
            api_provider=api_provider,
            model_name=model_name,
            api_name=api_name,
            use_cookies=use_cookies,
            cookies=cookies,
            chunk_method=chunk_method,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except ValidationError as exc:
        _raise_422(exc)


__all__ = [
    "get_process_documents_form",
    "get_process_videos_form",
    "get_process_audios_form",
]

