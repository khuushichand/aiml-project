from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path as PathlibPath
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path as FastAPIPath
from pydantic import BaseModel
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.outputs_schemas import OutputArtifact, OutputCreateRequest, OutputListResponse, OutputUpdateRequest
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.endpoints.outputs_templates import _build_items_context_from_media_ids, _select_media_ids_for_run
from tldw_Server_API.app.core.Chat.prompt_template_manager import safe_render
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from starlette.responses import FileResponse
import re
import json
from tldw_Server_API.app.services.outputs_service import (
    update_output_artifact_db,
    find_outputs_to_purge,
    delete_outputs_by_ids,
)


router = APIRouter(prefix="/outputs", tags=["outputs"])


@router.get("", response_model=OutputListResponse, summary="List outputs with filters")
async def list_outputs(
    page: int = 1,
    size: int = 50,
    job_id: int | None = None,
    run_id: int | None = None,
    type: str | None = None,
    include_deleted: bool = False,
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    limit = max(1, min(200, size))
    offset = (max(1, page) - 1) * limit
    rows, total = cdb.list_output_artifacts(limit=limit, offset=offset, job_id=job_id, run_id=run_id, type_=type, include_deleted=include_deleted)
    items = [
        OutputArtifact(
            id=r.id,
            title=r.title,
            type=r.type,
            format=r.format,  # type: ignore[arg-type]
            storage_path=r.storage_path,
            created_at=datetime.fromisoformat(r.created_at),
        )
        for r in rows
    ]
    return OutputListResponse(items=items, total=total, page=page, size=limit)


@router.get("/deleted", response_model=OutputListResponse, summary="List only soft-deleted outputs")
async def list_deleted_outputs(
    page: int = 1,
    size: int = 50,
    current_user: User = Depends(get_request_user),
    cdb = Depends(get_collections_db_for_user),
):
    limit = max(1, min(200, size))
    offset = (max(1, page) - 1) * limit
    rows, total = cdb.list_output_artifacts(limit=limit, offset=offset, include_deleted=True, only_deleted=True)
    items = [
        OutputArtifact(
            id=r.id,
            title=r.title,
            type=r.type,
            format=r.format,  # type: ignore[arg-type]
            storage_path=r.storage_path,
            created_at=datetime.fromisoformat(r.created_at),
        )
        for r in rows
    ]
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

    # Render
    try:
        rendered = safe_render(tpl.body, context)
    except Exception as e:
        logger.error(f"render failed: {e}")
        raise HTTPException(status_code=422, detail="render_failed")

    # Persist to file under user outputs dir
    user_dir = DatabasePaths.get_user_base_directory(int(current_user.id or 0))
    out_dir = user_dir / "outputs"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"failed to create outputs dir: {e}")
        raise HTTPException(status_code=500, detail="storage_unavailable")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ext = "mp3" if tpl.format == "mp3" else (tpl.format if tpl.format in ("md", "html") else "md")
    base = (payload.title or tpl.name or "output").strip().replace(" ", "_")[:50]
    filename = f"{base}_{ts}.{ext}"
    path = out_dir / filename

    if tpl.format == "mp3":
        # Synthesize speech from rendered text using default model/voice
        try:
            from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
            from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
            tts = await get_tts_service_v2()
            # Choose defaults; callers can override via context['tts'] later if needed
            # Extract defaults from template metadata when present
            tpl_model = None
            tpl_voice = None
            tpl_speed = None
            try:
                # Resolve template metadata via Collections DB directly if available
                tpl_md = None
                row = cdb.get_output_template(payload.template_id)
                if getattr(row, 'metadata_json', None):
                    tpl_md = json.loads(row.metadata_json) if row.metadata_json else None
                if isinstance(tpl_md, dict):
                    tpl_model = tpl_md.get("tts_default_model")
                    tpl_voice = tpl_md.get("tts_default_voice")
                    tpl_speed = tpl_md.get("tts_default_speed")
            except Exception:
                pass
            req = OpenAISpeechRequest(
                model=(payload.tts_model or tpl_model or "kokoro"),
                input=rendered,
                voice=(payload.tts_voice or tpl_voice or "af_heart"),
                response_format="mp3",
                stream=True,
            )
            if payload.tts_speed is not None:
                req.speed = payload.tts_speed
            elif tpl_speed is not None:
                try:
                    req.speed = float(tpl_speed)
                except Exception:
                    pass
            # Collect stream to file
            total = 0
            with open(path, "wb") as fh:
                async for chunk in tts.generate_speech(req):
                    if isinstance(chunk, (bytes, bytearray)):
                        fh.write(chunk)
                        total += len(chunk)
            if total <= 0:
                raise RuntimeError("tts_no_audio_generated")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise HTTPException(status_code=500, detail="tts_generation_failed")
    else:
        try:
            path.write_text(rendered, encoding="utf-8")
        except Exception as e:
            logger.error(f"failed to write output file: {e}")
            raise HTTPException(status_code=500, detail="write_failed")

    # Persist metadata row in outputs table
    try:
        meta = {
            "template_id": tpl.id,
            "item_ids": payload.item_ids or [],
            "run_id": payload.run_id,
            "tags": context.get("tags", []),
            "item_count": len(context.get("items", [])),
        }
        row = cdb.create_output_artifact(
            type_=tpl.type,
            title=payload.title or tpl.name,
            format_=tpl.format,
            storage_path=str(path),
            metadata_json=json.dumps(meta),
            job_id=None,
            run_id=payload.run_id,
            media_item_id=None,
        )
    except Exception as e:
        logger.error(f"failed to insert output row: {e}")
        # Try to clean up the file on failure
        try:
            os.remove(path)
        except Exception as _cleanup_err:
            logger.warning(f"failed to cleanup output file after DB insert failure: {path} err={_cleanup_err}")
        raise HTTPException(status_code=500, detail="db_insert_failed")

    return OutputArtifact(
        id=row.id,
        title=row.title,
        type=row.type,
        format=tpl.format,  # constrained to Literal
        storage_path=row.storage_path,
        created_at=datetime.fromisoformat(row.created_at),
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

    path = PathlibPath(row.storage_path)
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
    path = PathlibPath(row.storage_path)
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
    path = PathlibPath(row.storage_path)
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
    fs_deleted = False
    if hard and delete_file:
        try:
            row = cdb.get_output_artifact(output_id)
            p = PathlibPath(row.storage_path)
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

    new_path: str | None = None
    new_title: str | None = None
    new_format: str | None = None
    if payload.title and payload.title != row.title:
        # Attempt to rename the file keeping timestamp suffix if present
        p = PathlibPath(row.storage_path)
        ext = p.suffix
        stem = p.stem
        m = re.search(r"_(\d{8}_\d{6})$", stem)
        ts = m.group(1) if m else None
        base = _sanitize_title_for_filename(payload.title)
        new_name = f"{base}_{ts}{ext}" if ts else f"{base}{ext}"
        new_full = p.with_name(new_name)
        try:
            if p.exists():
                p.rename(new_full)
            new_path = str(new_full)
            new_title = payload.title
        except Exception as e:
            # If FS rename fails, keep old path and only update title in DB
            new_path = None
            new_title = payload.title

    # If format change requested, re-encode between md/html
    if payload.format and payload.format != row.format:
        if row.format not in ("md", "html") or payload.format not in ("md", "html"):
            raise HTTPException(status_code=422, detail="unsupported_format_change")
        source_path = PathlibPath(new_path or row.storage_path)
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
        target_path = source_path.with_name(new_filename)
        try:
            target_path.write_text(converted, encoding="utf-8")
            if target_path.resolve() != source_path.resolve() and source_path.exists():
                try:
                    source_path.unlink()
                except Exception as _unlink_err:
                    logger.warning(f"failed to remove old output file {source_path}: {_unlink_err}")
            new_path = str(target_path)
            new_format = payload.format
        except Exception:
            raise HTTPException(status_code=500, detail="write_failed")

    # Apply DB updates via service
    try:
        final = update_output_artifact_db(
            cdb=cdb,
            output_id=output_id,
            user_id=row.user_id,
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
                p = PathlibPath(pth)
                if p.exists():
                    p.unlink()
                    files_deleted += 1
            except Exception as del_err:
                logger.warning(f"outputs.purge: failed to delete file {pth}: {del_err}")
                continue

    removed = 0
    if ids:
        placeholders = ",".join(["?"] * len(ids))
        try:
            removed = delete_outputs_by_ids(cdb=cdb, user_id=cdb.user_id, ids=list(ids))
        except Exception as e:
            logger.error(f"outputs.purge: DB delete failed: {e}")
            removed = 0

    return {"removed": removed, "files_deleted": files_deleted}
