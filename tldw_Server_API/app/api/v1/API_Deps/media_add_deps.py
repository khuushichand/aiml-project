from __future__ import annotations

import json
from typing import List, Optional

from fastapi import Form, HTTPException, status
from loguru import logger
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.media_request_models import (
    AddMediaForm,
    ChunkMethod,
    MediaType,
    OcrMode,
    PdfEngine,
    TRANSCRIPTION_MODEL_ENUM,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
    resolve_default_transcription_model,
)

try:
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT
except AttributeError:  # Starlette < 0.27
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY


async def get_add_media_form(
    # Replicate ALL Form(...) fields from the endpoint signature
    # Accept string here so AddMediaForm can control error messaging for invalid values
    media_type: str = Form(
        ...,
        description="Type of media (e.g., 'audio', 'video', 'pdf')",
    ),
    urls: Optional[List[str]] = Form(
        None,
        description="List of URLs of the media items to add",
    ),
    title: Optional[str] = Form(
        None,
        description="Optional title (applied if only one item processed)",
    ),
    author: Optional[str] = Form(
        None,
        description="Optional author (applied similarly to title)",
    ),
    keywords: str = Form(
        "",
        description="Comma-separated keywords (applied to all processed items)",
    ),
    custom_prompt: Optional[str] = Form(
        None,
        description="Optional custom prompt (applied to all)",
    ),
    system_prompt: Optional[str] = Form(
        None,
        description="Optional system prompt (applied to all)",
    ),
    overwrite_existing: bool = Form(False, description="Overwrite existing media"),
    keep_original_file: bool = Form(
        False,
        description="Retain original uploaded files",
    ),
    perform_analysis: bool = Form(
        True,
        description="Perform analysis (default=True)",
    ),
    perform_claims_extraction: Optional[bool] = Form(
        None,
        description=(
            "Extract factual claims during analysis "
            "(defaults to server configuration)."
        ),
    ),
    claims_extractor_mode: Optional[str] = Form(
        None,
        description=(
            "Override claims extractor mode (heuristic|ner|provider id)."
        ),
    ),
    claims_max_per_chunk: Optional[int] = Form(
        None,
        description=(
            "Maximum number of claims to extract per chunk "
            "(uses config default when unset)."
        ),
    ),
    api_name: Optional[str] = Form(
        None,
        description="Optional API name",
    ),
    # api_key removed - SECURITY: Never accept API keys from client
    use_cookies: bool = Form(
        False,
        description="Use cookies for URL download requests",
    ),
    cookies: Optional[str] = Form(
        None,
        description="Cookie string if `use_cookies` is True",
    ),
    transcription_model: Optional[str] = Form(
        None,
        description="Transcription model (defaults to config when omitted)",
        json_schema_extra={"enum": TRANSCRIPTION_MODEL_ENUM},
    ),
    transcription_language: str = Form(
        "en",
        description="Transcription language",
    ),
    diarize: bool = Form(False, description="Enable speaker diarization"),
    timestamp_option: bool = Form(
        True,
        description="Include timestamps in transcription",
    ),
    vad_use: bool = Form(False, description="Enable VAD filter"),
    perform_confabulation_check_of_analysis: bool = Form(
        False,
        description="Enable confabulation check",
    ),
    start_time: Optional[str] = Form(
        None,
        description="Optional start time (HH:MM:SS or seconds)",
    ),
    end_time: Optional[str] = Form(
        None,
        description="Optional end time (HH:MM:SS or seconds)",
    ),
    pdf_parsing_engine: Optional[PdfEngine] = Form(
        "pymupdf4llm",
        description="PDF parsing engine",
    ),
    perform_chunking: bool = Form(True, description="Enable chunking"),
    chunk_method: Optional[ChunkMethod] = Form(
        None,
        description="Chunking method",
    ),
    use_adaptive_chunking: bool = Form(
        False,
        description="Enable adaptive chunking",
    ),
    use_multi_level_chunking: bool = Form(
        False,
        description="Enable multi-level chunking",
    ),
    chunk_language: Optional[str] = Form(
        None,
        description="Chunking language override",
    ),
    chunk_size: int = Form(500, description="Target chunk size"),
    chunk_overlap: int = Form(200, description="Chunk overlap size"),
    custom_chapter_pattern: Optional[str] = Form(
        None,
        description="Regex pattern for custom chapter splitting",
    ),
    perform_rolling_summarization: bool = Form(
        False,
        description="Perform rolling summarization",
    ),
    # Email options
    ingest_attachments: bool = Form(
        False,
        description=(
            "For emails: parse nested .eml attachments and ingest as "
            "separate items"
        ),
    ),
    max_depth: int = Form(
        2,
        description=(
            "Max depth for nested email parsing when ingest_attachments is true"
        ),
    ),
    accept_archives: bool = Form(
        False,
        description="Accept .zip archives of EMLs and expand/process members",
    ),
    accept_mbox: bool = Form(
        False,
        description="Accept .mbox mailboxes and expand/process messages",
    ),
    accept_pst: bool = Form(
        False,
        description=(
            "Accept .pst/.ost containers (feature-flag; parsing may require "
            "external tools)"
        ),
    ),
    # Contextual chunking options
    enable_contextual_chunking: bool = Form(
        False,
        description="Enable contextual chunking",
    ),
    contextual_llm_model: Optional[str] = Form(
        None,
        description="LLM model for contextual chunking",
    ),
    context_window_size: Optional[int] = Form(
        None,
        description="Context window size (chars)",
    ),
    context_strategy: Optional[str] = Form(
        None,
        description="Context strategy: auto|full|window|outline_window",
    ),
    context_token_budget: Optional[int] = Form(
        None,
        description="Approx token budget for auto strategy",
    ),
    summarize_recursively: bool = Form(
        False,
        description="Perform recursive summarization",
    ),
    # Embedding options
    generate_embeddings: bool = Form(
        False,
        description="Generate embeddings after media processing",
    ),
    embedding_model: Optional[str] = Form(
        None,
        description="Specific embedding model to use",
    ),
    embedding_provider: Optional[str] = Form(
        None,
        description="Embedding provider (huggingface, openai, etc)",
    ),
) -> AddMediaForm:
    """
    Dependency function to parse form data for the /media/add endpoint and
    validate it against the AddMediaForm model.
    """
    transcription_model_value = (transcription_model or "").strip()
    if not transcription_model_value:
        transcription_model_value = resolve_default_transcription_model("whisper-large-v3")
    elif transcription_model_value not in TRANSCRIPTION_MODEL_ENUM:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail=[
                {
                    "loc": ["body", "transcription_model"],
                    "msg": f"Invalid transcription model: {transcription_model_value}",
                    "type": "value_error.enum",
                    "ctx": {"enum_values": TRANSCRIPTION_MODEL_ENUM},
                }
            ],
        )

    try:
        # Coerce JSON string inputs for urls into a list for robustness
        if isinstance(urls, str):
            try:
                parsed = json.loads(urls)
                urls = parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                urls = [urls]
        elif isinstance(urls, list) and len(urls) == 1 and isinstance(urls[0], str):
            first = urls[0]
            stripped = first.strip()
            if stripped.startswith("[") or stripped.startswith('"'):
                try:
                    parsed = json.loads(first)
                    urls = parsed if isinstance(parsed, list) else [parsed]
                except Exception:
                    pass

        # Normalize common boolean/integer coercions for robust form handling
        if isinstance(enable_contextual_chunking, str):
            enable_contextual_chunking = (
                enable_contextual_chunking.strip().lower()
                in {"true", "1", "yes", "on"}
            )
        if isinstance(use_adaptive_chunking, str):
            use_adaptive_chunking = (
                use_adaptive_chunking.strip().lower()
                in {"true", "1", "yes", "on"}
            )
        if isinstance(use_multi_level_chunking, str):
            use_multi_level_chunking = (
                use_multi_level_chunking.strip().lower()
                in {"true", "1", "yes", "on"}
            )
        if isinstance(perform_chunking, str):
            perform_chunking = (
                perform_chunking.strip().lower() in {"true", "1", "yes", "on"}
            )
        try:
            if isinstance(context_window_size, str):
                context_window_size = int(context_window_size)
        except Exception:
            pass
        if isinstance(context_strategy, str):
            context_strategy = context_strategy.strip().lower() or None
        try:
            if isinstance(context_token_budget, str):
                context_token_budget = int(context_token_budget)
        except Exception:
            context_token_budget = None

        form_instance = AddMediaForm(
            media_type=media_type,
            urls=urls,
            title=title,
            author=author,
            keywords=keywords,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            overwrite_existing=overwrite_existing,
            keep_original_file=keep_original_file,
            perform_analysis=perform_analysis,
            perform_claims_extraction=perform_claims_extraction,
            claims_extractor_mode=claims_extractor_mode,
            claims_max_per_chunk=claims_max_per_chunk,
            start_time=start_time,
            end_time=end_time,
            api_name=api_name,
            use_cookies=use_cookies,
            cookies=cookies,
            transcription_model=transcription_model_value,
            transcription_language=transcription_language,
            diarize=diarize,
            timestamp_option=timestamp_option,
            vad_use=vad_use,
            perform_confabulation_check_of_analysis=(
                perform_confabulation_check_of_analysis
            ),
            pdf_parsing_engine=pdf_parsing_engine,
            perform_chunking=perform_chunking,
            chunk_method=chunk_method,
            use_adaptive_chunking=use_adaptive_chunking,
            use_multi_level_chunking=use_multi_level_chunking,
            chunk_language=chunk_language,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            custom_chapter_pattern=custom_chapter_pattern,
            perform_rolling_summarization=perform_rolling_summarization,
            summarize_recursively=summarize_recursively,
            enable_contextual_chunking=enable_contextual_chunking,
            contextual_llm_model=contextual_llm_model,
            context_window_size=context_window_size,
            context_strategy=context_strategy,
            context_token_budget=context_token_budget,
            ingest_attachments=ingest_attachments,
            max_depth=max_depth,
            accept_archives=accept_archives,
            accept_mbox=accept_mbox,
            accept_pst=accept_pst,
            generate_embeddings=generate_embeddings,
            embedding_model=embedding_model,
            embedding_provider=embedding_provider,
        )
        return form_instance
    except ValidationError as exc:
        serializable_errors = []
        for error in exc.errors():
            serializable_error = error.copy()
            if isinstance(serializable_error.get("ctx"), dict):
                new_ctx = {}
                for k, v in serializable_error["ctx"].items():
                    new_ctx[k] = str(v) if isinstance(v, Exception) else v
                serializable_error["ctx"] = new_ctx
            serializable_errors.append(serializable_error)
        logger.warning(
            "Pydantic validation failed for /media/add: {}",
            json.dumps(serializable_errors),
        )
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail=serializable_errors,
        ) from exc
    except Exception as exc:
        logger.error(
            "Unexpected error creating AddMediaForm: {}",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Internal server error during form processing: "
                f"{type(exc).__name__}"
            ),
        ) from exc


__all__ = ["get_add_media_form"]
