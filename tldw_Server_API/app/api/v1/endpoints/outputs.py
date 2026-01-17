from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path as PathlibPath

from fastapi import APIRouter, Body, Depends, HTTPException, Path as FastAPIPath
from pydantic import BaseModel
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.outputs_schemas import OutputArtifact, OutputCreateRequest, OutputListResponse, OutputUpdateRequest
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    User,
    get_request_user,
    resolve_user_id_for_request,
)
from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.endpoints.outputs_templates import _build_items_context_from_media_ids, _select_media_ids_for_run
from tldw_Server_API.app.core.Chat.prompt_template_manager import safe_render
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.exceptions import InvalidStoragePathError
from starlette.responses import FileResponse
from tldw_Server_API.app.services.outputs_service import (
    update_output_artifact_db,
    find_outputs_to_purge,
    delete_outputs_by_ids,
    normalize_output_storage_path,
)


router = APIRouter(prefix="/outputs", tags=["outputs"])


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


def _normalize_output_storage_path_for_user(
    *,
    cdb,
    user_id: int,
    output_id: int,
    storage_path: str,
    update_db: bool = True,
) -> str:
    try:
        normalized = normalize_output_storage_path(user_id, storage_path)
    except InvalidStoragePathError as exc:
        raise HTTPException(status_code=400, detail="invalid_path") from exc
    if update_db and normalized != storage_path:
        try:
            update_output_artifact_db(
                cdb=cdb,
                output_id=output_id,
                new_title=None,
                new_path=normalized,
                new_format=None,
                retention_until=None,
            )
        except Exception as exc:
            logger.error(f"outputs: failed to normalize storage_path for {output_id}: {exc}")
            raise HTTPException(status_code=500, detail="db_update_failed") from exc
    return normalized


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
    return re.sub(r"<[^>]+>", "", text or "")


def _extract_tts_defaults(template_row) -> tuple[str | None, str | None, float | None]:
    if not template_row or not getattr(template_row, "metadata_json", None):
        return None, None, None
    try:
        tpl_md = json.loads(template_row.metadata_json) if template_row.metadata_json else None
    except Exception:
        tpl_md = None
    if not isinstance(tpl_md, dict):
        return None, None, None
    tpl_model = tpl_md.get("tts_default_model")
    tpl_voice = tpl_md.get("tts_default_voice")
    tpl_speed = tpl_md.get("tts_default_speed")
    try:
        tpl_speed_val = float(tpl_speed) if tpl_speed is not None else None
    except Exception:
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
        from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
        from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
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


@router.get("", response_model=OutputListResponse, summary="List outputs with filters")
async def list_outputs(
    page: int = 1,
    size: int = 50,
    job_id: int | None = None,
    run_id: int | None = None,
    type: str | None = None,
    include_deleted: bool = False,
    _current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    limit = max(1, min(200, size))
    offset = (max(1, page) - 1) * limit
    rows, total = cdb.list_output_artifacts(limit=limit, offset=offset, job_id=job_id, run_id=run_id, type_=type, include_deleted=include_deleted)
    items = []
    for r in rows:
        try:
            storage_path = _normalize_output_storage_path_for_user(
                cdb=cdb,
                user_id=resolve_user_id_for_request(
                    _current_user,
                    as_int=True,
                    error_status=500,
                    invalid_detail="invalid user_id",
                ),
                output_id=r.id,
                storage_path=r.storage_path,
            )
        except HTTPException as exc:
            logger.warning(f"outputs.list: invalid storage path for {r.id}: {exc.detail}")
            storage_path = r.storage_path
        items.append(
            OutputArtifact(
                id=r.id,
                title=r.title,
                type=r.type,
                format=r.format,  # type: ignore[arg-type]
                storage_path=storage_path,
                media_item_id=r.media_item_id,
                created_at=datetime.fromisoformat(r.created_at),
            )
        )
    return OutputListResponse(items=items, total=total, page=page, size=limit)


@router.get("/deleted", response_model=OutputListResponse, summary="List only soft-deleted outputs")
async def list_deleted_outputs(
    page: int = 1,
    size: int = 50,
    _current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    limit = max(1, min(200, size))
    offset = (max(1, page) - 1) * limit
    rows, total = cdb.list_output_artifacts(limit=limit, offset=offset, include_deleted=True, only_deleted=True)
    items = []
    for r in rows:
        try:
            storage_path = _normalize_output_storage_path_for_user(
                cdb=cdb,
                user_id=resolve_user_id_for_request(
                    _current_user,
                    as_int=True,
                    error_status=500,
                    invalid_detail="invalid user_id",
                ),
                output_id=r.id,
                storage_path=r.storage_path,
                update_db=False,
            )
        except HTTPException as exc:
            logger.warning(f"outputs.list_deleted: invalid storage path for {r.id}: {exc.detail}")
            storage_path = r.storage_path
        items.append(
            OutputArtifact(
                id=r.id,
                title=r.title,
                type=r.type,
                format=r.format,  # type: ignore[arg-type]
                storage_path=storage_path,
                media_item_id=r.media_item_id,
                created_at=datetime.fromisoformat(r.created_at),
            )
        )
    return OutputListResponse(items=items, total=total, page=page, size=limit)


@router.post("", response_model=OutputArtifact, summary="Generate and persist a rendered output artifact")
async def create_output(
    payload: OutputCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
    media_db = Depends(get_media_db_for_user),
):
    # Resolve template
    try:
        tpl = cdb.get_output_template(payload.template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="template_not_found")

    # Build rendering context (shared by text + TTS)

    # Build rendering context
    if payload.data:
        try:
            context = dict(payload.data)
            context.setdefault("date", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
            if "items" not in context:
                # If no items within context, try to resolve from item_ids
                if payload.item_ids:
                    context["items"] = _build_items_context_from_media_ids(media_db, payload.item_ids, 1000)
                else:
                    context["items"] = []
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"invalid_inline_data: {e}")
    else:
        if not payload.item_ids and not payload.run_id:
            raise HTTPException(status_code=422, detail="Provide item_ids, run_id, or inline data")
        if payload.item_ids:
            items = _build_items_context_from_media_ids(media_db, payload.item_ids or [], 1000)
        elif payload.run_id is not None:
            mids = _select_media_ids_for_run(media_db, payload.run_id, 1000)
            if not mids:
                # When runs tables are not provisioned yet
                raise HTTPException(status_code=422, detail="run_selection_not_supported")
            items = _build_items_context_from_media_ids(media_db, mids, 1000)
        else:
            items = []
        context = {
            "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "job": {"name": "Output", "run_id": payload.run_id, "selection": {"item_ids": payload.item_ids or [], "count": len(items)}},
            "items": items,
            "tags": sorted({t for it in items for t in it.get("tags", []) if isinstance(it.get("tags", []), list)}),
        }

    # Render base template
    try:
        rendered = safe_render(tpl.body, context)
    except Exception as e:
        logger.error(f"render failed: {e}")
        raise HTTPException(status_code=422, detail="render_failed")

    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    out_dir = _outputs_dir_for_user(user_id)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"failed to create outputs dir: {e}")
        raise HTTPException(status_code=500, detail="storage_unavailable")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_title = payload.title or tpl.name or "output"
    base_meta = {
        "item_ids": payload.item_ids or [],
        "run_id": payload.run_id,
        "tags": context.get("tags", []),
        "item_count": len(context.get("items", [])),
    }
    outputs_created: list[tuple[int, PathlibPath]] = []

    async def _persist_output(
        *,
        output_title: str,
        output_type: str,
        output_format: str,
        rendered_text: str,
        template_row,
        filename_suffix: str | None,
        meta_extra: dict[str, object] | None,
        variant_of: int | None,
    ):
        filename = _build_output_filename(output_title, filename_suffix, ts, output_format)
        path = _resolve_output_path_for_user(user_id, filename)

        if output_format == "mp3":
            try:
                await _write_tts_audio_file(
                    rendered=rendered_text,
                    path=path,
                    tts_model=payload.tts_model,
                    tts_voice=payload.tts_voice,
                    tts_speed=payload.tts_speed,
                    template_row=template_row,
                )
            except HTTPException:
                raise
            except Exception as exc:
                logger.error(f"TTS generation failed: {exc}")
                raise HTTPException(status_code=500, detail="tts_generation_failed")
        else:
            try:
                path.write_text(rendered_text, encoding="utf-8")
            except Exception as exc:
                logger.error(f"failed to write output file: {exc}")
                raise HTTPException(status_code=500, detail="write_failed")

        meta = dict(base_meta)
        if meta_extra:
            meta.update(meta_extra)
        meta["template_id"] = getattr(template_row, "id", None)
        try:
            row = cdb.create_output_artifact(
                type_=output_type,
                title=output_title,
                format_=output_format,
                # Store only the filename; absolute path is reconstructed on read.
                storage_path=filename,
                metadata_json=json.dumps(meta),
                job_id=None,
                run_id=payload.run_id,
                media_item_id=None,
            )
        except Exception as exc:
            logger.error(f"failed to insert output row: {exc}")
            try:
                os.remove(path)
            except Exception as cleanup_err:
                logger.warning(f"failed to cleanup output file after DB insert failure: {path} err={cleanup_err}")
            raise HTTPException(status_code=500, detail="db_insert_failed")

        outputs_created.append((row.id, path))

        if payload.ingest_to_media_db:
            media_id = await _ingest_output_to_media_db(
                media_db=media_db,
                output_id=row.id,
                title=output_title,
                content=rendered_text,
                output_type=output_type,
                output_format=output_format,
                storage_path=filename,
                template_id=getattr(template_row, "id", None),
                run_id=payload.run_id,
                item_ids=payload.item_ids or [],
                tags=context.get("tags", []),
                variant_of=variant_of,
            )
            row = cdb.update_output_media_item_id(row.id, media_id)
        return row

    def _cleanup_outputs():
        for oid, opath in outputs_created:
            try:
                if opath.exists():
                    opath.unlink()
            except Exception as cleanup_err:
                logger.warning(f"failed to cleanup output file {opath}: {cleanup_err}")
            try:
                cdb.delete_output_artifact(oid, hard=True)
            except Exception as cleanup_err:
                logger.warning(f"failed to cleanup output row {oid}: {cleanup_err}")

    def _resolve_variant_template(template_id: int | None, template_type: str, detail: str):
        if template_id is not None:
            try:
                tpl_row = cdb.get_output_template(template_id)
            except KeyError:
                raise HTTPException(status_code=404, detail=detail)
            if tpl_row.type != template_type:
                raise HTTPException(status_code=422, detail="invalid_variant_template")
            return tpl_row
        tpl_row = cdb.get_default_output_template_by_type(template_type)
        if not tpl_row:
            raise HTTPException(status_code=404, detail=detail)
        return tpl_row

    try:
        base_row = await _persist_output(
            output_title=base_title,
            output_type=tpl.type,
            output_format=tpl.format,
            rendered_text=rendered,
            template_row=tpl,
            filename_suffix=None,
            meta_extra=None,
            variant_of=None,
        )

        if payload.generate_mece and tpl.type != "mece_markdown":
            mece_tpl = _resolve_variant_template(
                payload.mece_template_id,
                "mece_markdown",
                "mece_template_not_found",
            )
            try:
                mece_rendered = safe_render(mece_tpl.body, context)
            except Exception as exc:
                raise HTTPException(status_code=422, detail="mece_render_failed") from exc
            await _persist_output(
                output_title=f"{base_title} (MECE)",
                output_type=mece_tpl.type,
                output_format=mece_tpl.format,
                rendered_text=mece_rendered,
                template_row=mece_tpl,
                filename_suffix="mece",
                meta_extra={"variant_of": base_row.id, "variant_kind": "mece"},
                variant_of=base_row.id,
            )

        if payload.generate_tts and tpl.format != "mp3":
            tts_tpl = None
            if payload.tts_template_id is not None:
                try:
                    tts_tpl = cdb.get_output_template(payload.tts_template_id)
                except KeyError:
                    raise HTTPException(status_code=404, detail="tts_template_not_found")
                if tts_tpl.type != "tts_audio":
                    raise HTTPException(status_code=422, detail="invalid_variant_template")
            else:
                tts_tpl = cdb.get_default_output_template_by_type("tts_audio")

            if tts_tpl:
                try:
                    tts_rendered = safe_render(tts_tpl.body, context)
                except Exception as exc:
                    raise HTTPException(status_code=422, detail="tts_render_failed") from exc
                tts_template_row = tts_tpl
            else:
                tts_template_row = tpl
                tts_rendered = _strip_html_for_tts(rendered) if tpl.format == "html" else rendered

            await _persist_output(
                output_title=f"{base_title} (Audio)",
                output_type="tts_audio",
                output_format="mp3",
                rendered_text=tts_rendered,
                template_row=tts_template_row,
                filename_suffix="audio",
                meta_extra={"variant_of": base_row.id, "variant_kind": "tts"},
                variant_of=base_row.id,
            )

    except HTTPException:
        _cleanup_outputs()
        raise
    except Exception as e:
        _cleanup_outputs()
        logger.error(f"outputs.create failed: {e}")
        raise HTTPException(status_code=500, detail="output_create_failed")

    return OutputArtifact(
        id=base_row.id,
        title=base_row.title,
        type=base_row.type,
        format=tpl.format,  # constrained to Literal
        storage_path=base_row.storage_path,
        media_item_id=base_row.media_item_id,
        created_at=datetime.fromisoformat(base_row.created_at),
    )


@router.get("/{output_id}", response_model=OutputArtifact, summary="Get output metadata")
async def get_output(
    output_id: int = FastAPIPath(..., ge=1),
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    try:
        row = cdb.get_output_artifact(output_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="output_not_found")
    return OutputArtifact(
        id=row.id,
        title=row.title,
        type=row.type,
        format=row.format,  # type: ignore[assignment]
        storage_path=row.storage_path,
        media_item_id=row.media_item_id,
        created_at=datetime.fromisoformat(row.created_at),
    )


@router.get("/{output_id}/download", summary="Download output artifact")
async def download_output(
    output_id: int = FastAPIPath(..., ge=1),
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    try:
        row = cdb.get_output_artifact(output_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="output_not_found")

    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    storage_name = _normalize_output_storage_path_for_user(
        cdb=cdb,
        user_id=user_id,
        output_id=row.id,
        storage_path=row.storage_path,
    )
    path = _resolve_output_path_for_user(user_id, storage_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file_missing")

    media_types = {
        "md": "text/markdown; charset=utf-8",
        "html": "text/html; charset=utf-8",
        "mp3": "audio/mpeg",
    }
    mt = media_types.get(row.format.lower(), "application/octet-stream")
    return FileResponse(
        str(path),
        media_type=mt,
        filename=path.name,
    )


@router.get("/download/by-name", summary="Download output artifact by title")
async def download_output_by_name(
    title: str,
    format: str | None = None,
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    try:
        row = cdb.get_output_artifact_by_title(title, format_=(format if format else None))
    except KeyError:
        raise HTTPException(status_code=404, detail="output_not_found")
    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    storage_name = _normalize_output_storage_path_for_user(
        cdb=cdb,
        user_id=user_id,
        output_id=row.id,
        storage_path=row.storage_path,
    )
    path = _resolve_output_path_for_user(user_id, storage_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file_missing")
    media_types = {
        "md": "text/markdown; charset=utf-8",
        "html": "text/html; charset=utf-8",
        "mp3": "audio/mpeg",
    }
    mt = media_types.get(row.format.lower(), "application/octet-stream")
    return FileResponse(
        str(path),
        media_type=mt,
        filename=path.name,
    )


@router.head("/{output_id}/download", summary="Check output artifact availability")
async def head_download_output(
    output_id: int = FastAPIPath(..., ge=1),
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    try:
        row = cdb.get_output_artifact(output_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="output_not_found")
    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    storage_name = _normalize_output_storage_path_for_user(
        cdb=cdb,
        user_id=user_id,
        output_id=row.id,
        storage_path=row.storage_path,
    )
    path = _resolve_output_path_for_user(user_id, storage_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file_missing")
    # Return headers; FastAPI will send no body
    media_types = {
        "md": "text/markdown; charset=utf-8",
        "html": "text/html; charset=utf-8",
        "mp3": "audio/mpeg",
    }
    mt = media_types.get(row.format.lower(), "application/octet-stream")
    from fastapi import Response
    headers = {"Content-Type": mt, "Content-Length": str(path.stat().st_size)}
    return Response(status_code=200, headers=headers)


@router.delete("/{output_id}", summary="Delete output metadata (and file)")
async def delete_output(
    output_id: int = FastAPIPath(..., ge=1),
    hard: bool = False,
    delete_file: bool = False,
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    # If hard delete and delete_file requested, remove file first
    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    fs_deleted = False
    if hard and delete_file:
        try:
            row = cdb.get_output_artifact(output_id)
            try:
                storage_name = _normalize_output_storage_path_for_user(
                    cdb=cdb,
                    user_id=user_id,
                    output_id=row.id,
                    storage_path=row.storage_path,
                    update_db=False,
                )
                p = _resolve_output_path_for_user(user_id, storage_name)
            except HTTPException as e:
                logger.warning(f"outputs.delete: invalid output path for {output_id}: {e.detail}")
            else:
                if p.exists():
                    p.unlink()
                    fs_deleted = True
        except KeyError:
            raise HTTPException(status_code=404, detail="output_not_found")
        except Exception:
            fs_deleted = False
    # Delete metadata (soft by default)
    ok = cdb.delete_output_artifact(output_id, hard=hard)
    if not ok:
        raise HTTPException(status_code=404, detail="output_not_found")
    return {"success": True, "file_deleted": fs_deleted}


def _sanitize_title_for_filename(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", title.strip())
    s = re.sub(r"\.+", ".", s).strip(".")
    return s[:80] or "output"


@router.patch("/{output_id}", response_model=OutputArtifact, summary="Rename/change format/update metadata for an output")
async def update_output(
    output_id: int = FastAPIPath(..., ge=1),
    payload: OutputUpdateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    try:
        row = cdb.get_output_artifact(output_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="output_not_found")

    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    storage_name = _normalize_output_storage_path_for_user(
        cdb=cdb,
        user_id=user_id,
        output_id=row.id,
        storage_path=row.storage_path,
    )
    source_path = _resolve_output_path_for_user(user_id, storage_name)
    new_path: str | None = None
    new_title: str | None = None
    new_format: str | None = None
    if payload.title and payload.title != row.title:
        # Attempt to rename the file keeping timestamp suffix if present
        p = source_path
        ext = p.suffix
        stem = p.stem
        m = re.search(r"_(\d{8}_\d{6})$", stem)
        ts = m.group(1) if m else None
        base = _sanitize_title_for_filename(payload.title)
        new_name = f"{base}_{ts}{ext}" if ts else f"{base}{ext}"
        new_full = _resolve_output_path_for_user(user_id, new_name)
        try:
            if p.exists():
                p.rename(new_full)
            new_path = new_name
            new_title = payload.title
        except Exception as e:
            # If FS rename fails, keep old path and only update title in DB
            new_path = None
            new_title = payload.title

    # If format change requested, re-encode between md/html
    if payload.format and payload.format != row.format:
        if row.format not in ("md", "html") or payload.format not in ("md", "html"):
            raise HTTPException(status_code=422, detail="unsupported_format_change")
        if new_path is not None:
            source_path = _resolve_output_path_for_user(user_id, new_path)
        try:
            src_text = source_path.read_text(encoding="utf-8")
        except Exception:
            raise HTTPException(status_code=500, detail="read_failed")
        if row.format == "md" and payload.format == "html":
            try:
                import markdown as _md  # type: ignore
                converted = _md.markdown(src_text)
            except Exception:
                # Minimal fallback: escape angle brackets
                converted = f"<html><body>\n{re.sub(r'<', '&lt;', src_text)}\n</body></html>"
        elif row.format == "html" and payload.format == "md":
            converted = re.sub(r"<[^>]+>", "", src_text)
        else:
            converted = src_text
        # Write new file with changed extension
        ext = ".html" if payload.format == "html" else ".md"
        base_title = _sanitize_title_for_filename(payload.title or row.title)
        stem = source_path.stem
        m = re.search(r"_(\d{8}_\d{6})$", stem)
        ts = m.group(1) if m else None
        new_filename = f"{base_title}_{ts}{ext}" if ts else f"{base_title}{ext}"
        target_path = _resolve_output_path_for_user(user_id, new_filename)
        try:
            target_path.write_text(converted, encoding="utf-8")
            if target_path.resolve() != source_path.resolve() and source_path.exists():
                try:
                    source_path.unlink()
                except Exception as _unlink_err:
                    logger.warning(f"failed to remove old output file {source_path}: {_unlink_err}")
            new_path = new_filename
            new_format = payload.format
        except Exception:
            raise HTTPException(status_code=500, detail="write_failed")

    # Apply DB updates via service
    try:
        final = update_output_artifact_db(
            cdb=cdb,
            output_id=output_id,
            new_title=new_title,
            new_path=new_path,
            new_format=new_format,
            retention_until=payload.retention_until,
        )
    except Exception as e:
        logger.error(f"outputs.update conflict or DB error: {e}")
        raise HTTPException(status_code=409, detail="conflict_on_update")

    return OutputArtifact(
        id=final.id,
        title=final.title,
        type=final.type,
        format=final.format,  # type: ignore[arg-type]
        storage_path=final.storage_path,
        media_item_id=final.media_item_id,
        created_at=datetime.fromisoformat(final.created_at),
    )


class OutputsPurgeRequest(BaseModel):
    delete_files: bool = False
    soft_deleted_grace_days: int = 30
    include_retention: bool = True


@router.post("/purge", summary="Purge expired and aged soft-deleted outputs")
async def purge_outputs(
    payload: OutputsPurgeRequest = Body(default=OutputsPurgeRequest()),
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    ids: set[int] = set()
    paths: dict[int, str] = {}

    try:
        candidate_paths = find_outputs_to_purge(
            cdb=cdb,
            now_iso=now,
            soft_deleted_grace_days=payload.soft_deleted_grace_days,
            include_retention=payload.include_retention,
        )
        for rid, pth in candidate_paths.items():
            ids.add(rid)
            paths[rid] = pth
    except Exception as e:
        logger.error(f"outputs.purge: failed to enumerate purge candidates: {e}")

    files_deleted = 0
    if payload.delete_files and ids:
        for rid, pth in list(paths.items()):
            try:
                storage_name = _normalize_output_storage_path_for_user(
                    cdb=cdb,
                    user_id=user_id,
                    output_id=rid,
                    storage_path=pth,
                    update_db=False,
                )
                p = _resolve_output_path_for_user(user_id, storage_name)
                if p.exists():
                    p.unlink()
                    files_deleted += 1
            except HTTPException as e:
                logger.warning(f"outputs.purge: invalid output path for {rid}: {e.detail}")
            except Exception as del_err:
                logger.warning(f"outputs.purge: failed to delete file {pth}: {del_err}")
                continue

    removed = 0
    if ids:
        try:
            removed = delete_outputs_by_ids(cdb=cdb, user_id=cdb.user_id, ids=list(ids))
        except Exception as e:
            logger.error(f"outputs.purge: DB delete failed: {e}")
            removed = 0

    return {"removed": removed, "files_deleted": files_deleted}
