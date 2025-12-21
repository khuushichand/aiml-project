from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Path, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit, require_permissions
from tldw_Server_API.app.api.v1.schemas.media_request_models import ReprocessMediaRequest
from tldw_Server_API.app.api.v1.schemas.media_response_models import ReprocessMediaResponse
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.permissions import MEDIA_UPDATE
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    ConflictError,
    DatabaseError,
    InputError,
    MediaDatabase,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (
    apply_chunking_template_if_any,
    prepare_chunking_options_dict,
)
from tldw_Server_API.app.core.Chunking import improved_chunking_process
from tldw_Server_API.app.core.Chunking.chunker import Chunker
from tldw_Server_API.app.core.config import settings

from tldw_Server_API.app.api.v1.endpoints import media_embeddings as embeddings_endpoint
from tldw_Server_API.app.core.Chunking.templates import TemplateClassifier


router = APIRouter(tags=["Media Management"])


def _normalize_chunks(raw_chunks: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(raw_chunks):
        if isinstance(chunk, str):
            text = chunk
            meta: Optional[Dict[str, Any]] = None
            start_char = None
            end_char = None
            chunk_type = None
        elif isinstance(chunk, dict):
            text = chunk.get("text") or chunk.get("chunk_text")
            meta = chunk.get("metadata")
            start_char = chunk.get("start_char") or chunk.get("start")
            end_char = chunk.get("end_char") or chunk.get("end")
            chunk_type = chunk.get("chunk_type")
        else:
            continue

        if not isinstance(text, str) or not text.strip():
            continue

        normalized.append(
            {
                "chunk_text": text,
                "chunk_index": idx,
                "start_char": start_char,
                "end_char": end_char,
                "chunk_type": chunk_type,
                "metadata": meta if isinstance(meta, dict) else None,
            }
        )
    return normalized


def _delete_embeddings_for_media(media_id: int, user_id: str) -> None:
    manager = embeddings_endpoint.ChromaDBManager(
        user_id=user_id,
        user_embedding_config=embeddings_endpoint._user_embedding_config(),
    )
    collection_name = f"user_{user_id}_media_embeddings"
    collection = manager.get_or_create_collection(collection_name)
    try:
        collection.delete(where={"media_id": str(media_id)})
    except Exception as exc:
        logger.warning(
            "Where-delete failed for media %s embeddings, falling back to id delete: %s",
            media_id,
            exc,
        )
        data = collection.get(where={"media_id": str(media_id)}, include=["metadatas"], limit=100000)
        ids = (data or {}).get("ids") or []
        if ids:
            collection.delete(ids=ids)


def _update_media_reprocess_state(
    db: MediaDatabase,
    media_id: int,
    *,
    chunking_status: Optional[str],
    reset_vector_processing: bool,
) -> None:
    with db.transaction() as conn:
        row = db._fetchone_with_connection(
            conn,
            "SELECT uuid, version FROM Media WHERE id = ? AND deleted = 0 AND is_trash = 0",
            (media_id,),
        )
        if not row:
            raise InputError(f"Media {media_id} not found or inactive.")
        media_uuid = row["uuid"]
        current_version = row["version"]
        next_version = current_version + 1
        now = db._get_current_utc_timestamp_str()

        set_parts = ["last_modified = ?", "version = ?", "client_id = ?"]
        params: List[Any] = [now, next_version, db.client_id]
        payload: Dict[str, Any] = {"last_modified": now}

        if chunking_status is not None:
            set_parts.append("chunking_status = ?")
            params.append(chunking_status)
            payload["chunking_status"] = chunking_status

        if reset_vector_processing:
            set_parts.append("vector_processing = ?")
            params.append(0)
            payload["vector_processing"] = 0

        update_sql = f"UPDATE Media SET {', '.join(set_parts)} WHERE id = ? AND version = ?"
        update_params = tuple(params + [media_id, current_version])
        cursor = conn.cursor()
        cursor.execute(update_sql, update_params)
        if cursor.rowcount == 0:
            raise ConflictError("Media", media_id)

        db._log_sync_event(conn, "Media", media_uuid, "update", next_version, payload)


async def _generate_embeddings(
    *,
    media_id: int,
    media_payload: Dict[str, Any],
    request: ReprocessMediaRequest,
    user_id: str,
) -> None:
    try:
        embedding_model = request.embedding_model or settings.get(
            "embedding_model",
            embeddings_endpoint.DEFAULT_EMBEDDING_MODEL,
        )
        embedding_provider = request.embedding_provider or settings.get(
            "embedding_provider",
            embeddings_endpoint.DEFAULT_EMBEDDING_PROVIDER,
        )
        await embeddings_endpoint.generate_embeddings_for_media(
            media_id=media_id,
            media_content=media_payload,
            embedding_model=embedding_model,
            embedding_provider=embedding_provider,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            user_id=user_id,
        )
    except Exception as exc:
        logger.error("Embeddings regeneration failed for media %s: %s", media_id, exc)


@router.post(
    "/{media_id:int}/reprocess",
    dependencies=[
        Depends(require_permissions(MEDIA_UPDATE)),
        Depends(rbac_rate_limit("media.update")),
    ],
    status_code=status.HTTP_200_OK,
    response_model=ReprocessMediaResponse,
    summary="Reprocess media chunks and embeddings",
)
async def reprocess_media_item(
    payload: ReprocessMediaRequest,
    media_id: int = Path(..., description="The ID of the media item"),
    db: MediaDatabase = Depends(get_media_db_for_user),
    current_user: User = Depends(get_request_user),
) -> ReprocessMediaResponse:
    media_item = db.get_media_by_id(media_id)
    if not media_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found.")

    content = media_item.get("content") or ""
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Media content is empty.")

    if not payload.perform_chunking and not payload.generate_embeddings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nothing to reprocess (chunking and embeddings both disabled).",
        )

    chunks_created: Optional[int] = None
    if payload.perform_chunking:
        chunk_request = SimpleNamespace(**payload.model_dump())
        chunk_request.media_type = media_item.get("type")
        chunk_request.title = media_item.get("title")
        chunk_request.url = media_item.get("url")

        chunk_options = prepare_chunking_options_dict(chunk_request)
        chunk_options = apply_chunking_template_if_any(
            chunk_request,
            db,
            chunk_options,
            TemplateClassifier=TemplateClassifier,
            first_url=media_item.get("url"),
            first_filename=media_item.get("filename"),
        )
        chunk_options = chunk_options or {}

        use_hier = bool(
            chunk_options.get("hierarchical")
            or isinstance(chunk_options.get("hierarchical_template"), dict)
        )
        if use_hier:
            ck = Chunker()
            raw_chunks = ck.chunk_text_hierarchical_flat(
                content,
                method=chunk_options.get("method") or "sentences",
                max_size=chunk_options.get("max_size") or 500,
                overlap=chunk_options.get("overlap") or 200,
                language=chunk_options.get("language"),
                template=chunk_options.get("hierarchical_template")
                if isinstance(chunk_options.get("hierarchical_template"), dict)
                else None,
            )
        else:
            raw_chunks = improved_chunking_process(content, chunk_options)

        normalized_chunks = _normalize_chunks(raw_chunks)
        db.execute_query(
            "DELETE FROM UnvectorizedMediaChunks WHERE media_id = ?",
            (media_id,),
            commit=True,
        )
        if normalized_chunks:
            db.process_unvectorized_chunks(media_id, normalized_chunks)
        chunks_created = len(normalized_chunks)

        try:
            _update_media_reprocess_state(
                db,
                media_id,
                chunking_status="completed",
                reset_vector_processing=bool(payload.generate_embeddings),
            )
        except (ConflictError, InputError) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except DatabaseError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    elif payload.generate_embeddings:
        try:
            _update_media_reprocess_state(
                db,
                media_id,
                chunking_status=None,
                reset_vector_processing=True,
            )
        except (ConflictError, InputError) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except DatabaseError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    embeddings_started = False
    if payload.generate_embeddings:
        user_id = str(getattr(current_user, "id", "1"))
        if payload.force_regenerate_embeddings:
            try:
                _delete_embeddings_for_media(media_id, user_id)
            except Exception as exc:
                logger.warning("Failed to delete embeddings for media %s: %s", media_id, exc)

        embeddings_started = True
        media_payload = {"media_item": media_item, "content": media_item}
        asyncio.create_task(
            _generate_embeddings(
                media_id=media_id,
                media_payload=media_payload,
                request=payload,
                user_id=user_id,
            )
        )

    message = "Reprocess completed."
    if payload.generate_embeddings:
        message = "Reprocess completed; embeddings regeneration started."

    return ReprocessMediaResponse(
        media_id=media_id,
        status="completed",
        message=message,
        chunks_created=chunks_created,
        embeddings_started=embeddings_started,
        job_id=None,
    )


__all__ = ["router"]
