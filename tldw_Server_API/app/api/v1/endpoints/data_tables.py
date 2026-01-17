from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from cachetools import LRUCache
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    rbac_rate_limit,
    require_permissions,
)
from tldw_Server_API.app.api.v1.schemas.data_tables_schemas import (
    DataTableColumn,
    DataTableContentUpdateRequest,
    DataTableDeleteResponse,
    DataTableDetailResponse,
    DataTableExportFormat,
    DataTableExportResponse,
    DataTableGenerateRequest,
    DataTableGenerateResponse,
    DataTableJobCancelResponse,
    DataTableJobStatus,
    DataTableRegenerateRequest,
    DataTableRow,
    DataTableSource,
    DataTableSummary,
    DataTablesListResponse,
    DataTableUpdateRequest,
)
from tldw_Server_API.app.api.v1.schemas.file_artifacts_schemas import (
    AsyncMode,
    ExportMode,
    FileCreateOptions,
    FileCreateRequest,
    FileExportRequest,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.permissions import (
    MEDIA_CREATE,
    MEDIA_DELETE,
    MEDIA_READ,
    MEDIA_UPDATE,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase, InputError
from tldw_Server_API.app.core.exceptions import FileArtifactsError, FileArtifactsValidationError
from tldw_Server_API.app.core.File_Artifacts.adapter_registry import get_registry
from tldw_Server_API.app.core.File_Artifacts.adapters.data_table_adapter import DataTableAdapter
from tldw_Server_API.app.core.File_Artifacts.file_artifacts_service import (
    DEFAULT_MAX_BYTES,
    FileArtifactsService,
)
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, ensure_traceparent
from tldw_Server_API.app.core.Utils.Utils import sanitize_filename


router = APIRouter(prefix="/data-tables", tags=["data-tables"])

MAX_CACHED_JOB_MANAGER_INSTANCES = 4
_job_manager_cache: LRUCache = LRUCache(maxsize=MAX_CACHED_JOB_MANAGER_INSTANCES)
_job_manager_lock = threading.Lock()

_FILE_ARTIFACTS_ERROR_STATUS = {
    "unsupported_file_type": status.HTTP_400_BAD_REQUEST,
    "persist_required": status.HTTP_400_BAD_REQUEST,
    "unsupported_export_format": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "invalid_async_mode": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "export_size_exceeded": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "row_limit_exceeded": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "cell_limit_exceeded": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "export_failed": status.HTTP_500_INTERNAL_SERVER_ERROR,
    "export_job_enqueue_failed": status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _file_artifacts_http_exception(exc: FileArtifactsError) -> HTTPException:
    detail = exc.detail if exc.detail is not None else exc.code
    status_code = _FILE_ARTIFACTS_ERROR_STATUS.get(exc.code)
    if status_code is None:
        if isinstance(exc, FileArtifactsValidationError):
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return HTTPException(status_code=status_code, detail=detail)


def get_job_manager() -> JobManager:
    cache_key = (os.getenv("JOBS_DB_URL", "default") or "default").strip() or "default"
    with _job_manager_lock:
        cached = _job_manager_cache.get(cache_key)
        if cached is not None:
            return cached

        db_url = (os.getenv("JOBS_DB_URL") or "").strip()
        if not db_url:
            job_manager = JobManager()
        else:
            backend = "postgres" if db_url.startswith("postgres") else None
            job_manager = JobManager(backend=backend, db_url=db_url)

        _job_manager_cache[cache_key] = job_manager
        return job_manager


def _parse_json_value(raw: Optional[str]) -> Any:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _model_dump(obj: Any) -> Dict[str, Any]:
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dump()
    dump = getattr(obj, "dict", None)
    if callable(dump):
        return dump()
    return dict(obj)


def _resolve_owner_id(principal: AuthPrincipal, current_user: User) -> Optional[Union[int, str]]:
    if principal.is_admin:
        return None
    owner_id = getattr(current_user, "id", None)
    if owner_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="owner_user_id_missing",
        )
    if isinstance(owner_id, int):
        return owner_id
    if isinstance(owner_id, UUID):
        return str(owner_id)
    if isinstance(owner_id, str):
        owner_id = owner_id.strip()
        if not owner_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="owner_user_id_empty",
            )
        try:
            return int(owner_id)
        except ValueError:
            try:
                return str(UUID(owner_id))
            except ValueError:
                return owner_id
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="owner_user_id_invalid",
    )


def _table_summary_from_row(
    row: Dict[str, Any],
    *,
    column_count: Optional[int] = None,
    source_count: Optional[int] = None,
) -> DataTableSummary:
    return DataTableSummary(
        uuid=str(row.get("uuid") or ""),
        name=str(row.get("name") or ""),
        description=row.get("description"),
        prompt=str(row.get("prompt") or ""),
        column_hints=_parse_json_value(row.get("column_hints_json")),
        status=str(row.get("status") or ""),
        row_count=int(row.get("row_count") or 0),
        column_count=column_count
        if column_count is not None
        else row.get("column_count"),
        generation_model=row.get("generation_model"),
        last_error=row.get("last_error"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        last_modified=row.get("last_modified"),
        version=int(row.get("version")) if row.get("version") is not None else None,
        source_count=source_count
        if source_count is not None
        else row.get("source_count"),
    )


def _column_from_row(row: Dict[str, Any]) -> DataTableColumn:
    return DataTableColumn(
        column_id=str(row.get("column_id") or ""),
        name=str(row.get("name") or ""),
        type=str(row.get("type") or ""),
        description=row.get("description"),
        format=row.get("format"),
        position=int(row.get("position") or 0),
    )


def _row_from_row(row: Dict[str, Any]) -> DataTableRow:
    return DataTableRow(
        row_id=str(row.get("row_id") or ""),
        row_index=int(row.get("row_index") or 0),
        data=_parse_json_value(row.get("row_json")),
        row_hash=row.get("row_hash"),
    )


def _source_from_row(row: Dict[str, Any]) -> DataTableSource:
    return DataTableSource(
        source_type=str(row.get("source_type") or ""),
        source_id=str(row.get("source_id") or ""),
        title=row.get("title"),
        snapshot=_parse_json_value(row.get("snapshot_json")),
        retrieval_params=_parse_json_value(row.get("retrieval_params_json")),
    )


def _row_values_from_json(
    row_json: Any,
    *,
    column_ids: List[str],
    column_names: List[str],
) -> List[Any]:
    if row_json is None:
        return [None] * len(column_ids)
    if isinstance(row_json, dict):
        values = []
        for col_id, col_name in zip(column_ids, column_names, strict=True):
            if col_id in row_json:
                values.append(row_json.get(col_id))
            elif col_name in row_json:
                values.append(row_json.get(col_name))
            else:
                values.append(None)
        return values
    if isinstance(row_json, (list, tuple)):
        row_values = list(row_json)
        if len(row_values) < len(column_ids):
            row_values.extend([None] * (len(column_ids) - len(row_values)))
        elif len(row_values) > len(column_ids):
            row_values = row_values[: len(column_ids)]
        return row_values
    return [row_json] + [None] * max(0, len(column_ids) - 1)


def _collect_export_rows(
    db: MediaDatabase,
    table_id: int,
    *,
    column_ids: List[str],
    column_names: List[str],
    owner_user_id: Optional[Union[int, str]] = None,
) -> List[List[Any]]:
    rows: List[List[Any]] = []
    offset = 0
    batch_size = 2000
    while True:
        batch = db.list_data_table_rows(
            table_id,
            limit=batch_size,
            offset=offset,
            owner_user_id=owner_user_id,
        )
        if not batch:
            break
        for row in batch:
            row_json = _parse_json_value(row.get("row_json"))
            rows.append(
                _row_values_from_json(
                    row_json,
                    column_ids=column_ids,
                    column_names=column_names,
                )
            )
        offset += len(batch)
        if len(batch) < batch_size:
            break
    return rows


def _build_export_filename(title: str, export_format: str) -> str:
    base = sanitize_filename(
        title or "data_table",
        max_total_length=80,
        extension=f".{export_format}",
    )
    if not base:
        base = "data_table"
    return f"{base}.{export_format}"


async def _export_structured(adapter, structured: Dict[str, Any], export_format: str):
    if export_format == "xlsx":
        return await asyncio.to_thread(adapter.export, structured, format=export_format)
    return adapter.export(structured, format=export_format)


async def _wait_for_job_completion(
    jm: JobManager,
    job_id: int,
    *,
    timeout_seconds: int = 300,
    poll_interval: float = 1.0,
) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        job = jm.get_job(int(job_id))
        if not job:
            raise HTTPException(status_code=404, detail="job_not_found")
        status_val = str(job.get("status") or "").lower()
        if status_val in {"completed", "failed", "cancelled"}:
            return job
        await asyncio.sleep(poll_interval)
    raise HTTPException(status_code=408, detail="data_table_job_timeout")


def _build_table_detail_response(
    table_row: Dict[str, Any],
    db: MediaDatabase,
    *,
    rows_limit: int = 200,
    rows_offset: int = 0,
    include_rows: bool = True,
    include_sources: bool = True,
    owner_user_id: Optional[Union[int, str]] = None,
) -> DataTableDetailResponse:
    table_id = int(table_row.get("id"))
    columns = [
        _column_from_row(row)
        for row in db.list_data_table_columns(table_id, owner_user_id=owner_user_id)
    ]
    rows: List[DataTableRow] = []
    if include_rows:
        rows = [
            _row_from_row(row)
            for row in db.list_data_table_rows(
                table_id,
                limit=rows_limit,
                offset=rows_offset,
                owner_user_id=owner_user_id,
            )
        ]
    sources: List[DataTableSource] = []
    source_count: Optional[int] = table_row.get("source_count")
    if include_sources:
        sources = [
            _source_from_row(row)
            for row in db.list_data_table_sources(table_id, owner_user_id=owner_user_id)
        ]
        source_count = len(sources)
    return DataTableDetailResponse(
        table=_table_summary_from_row(
            table_row,
            column_count=len(columns),
            source_count=source_count,
        ),
        columns=columns,
        rows=rows,
        sources=sources,
        rows_limit=rows_limit,
        rows_offset=rows_offset,
    )


@router.post(
    "/generate",
    response_model=Union[DataTableGenerateResponse, DataTableDetailResponse],
    summary="Submit a data table generation job",
    dependencies=[
        Depends(require_permissions(MEDIA_CREATE)),
        Depends(rbac_rate_limit("data_tables.generate")),
    ],
)
async def generate_data_table(
    req: DataTableGenerateRequest,
    response: Response,
    wait_for_completion: bool = Query(False, description="Wait for job completion"),
    wait_timeout_seconds: int = Query(300, ge=1, le=1800),
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db: MediaDatabase = Depends(get_media_db_for_user),
    jm: JobManager = Depends(get_job_manager),
    request: Request = None,
) -> Union[DataTableGenerateResponse, DataTableDetailResponse]:
    rid = ensure_request_id(request) if request is not None else None
    tp = ensure_traceparent(request) if request is not None else ""
    table_id = None
    table_uuid = None

    try:
        column_hints = None
        if req.column_hints:
            column_hints = [_model_dump(hint) for hint in req.column_hints]

        table_row = db.create_data_table(
            name=req.name.strip(),
            prompt=req.prompt.strip(),
            description=req.description,
            column_hints=column_hints,
            status="queued",
            row_count=0,
            generation_model=req.model,
        )
        table_id = int(table_row.get("id"))
        table_uuid = str(table_row.get("uuid"))

        sources_db_payload: List[Dict[str, Any]] = []
        job_sources: List[Dict[str, Any]] = []
        for source in req.sources:
            src = _model_dump(source)
            job_sources.append(
                {
                    "source_type": src.get("source_type"),
                    "source_id": src.get("source_id"),
                    "title": src.get("title"),
                    "snapshot": src.get("snapshot"),
                    "retrieval_params": src.get("retrieval_params"),
                }
            )
            sources_db_payload.append(
                {
                    "source_type": src.get("source_type"),
                    "source_id": src.get("source_id"),
                    "title": src.get("title"),
                    "snapshot_json": src.get("snapshot"),
                    "retrieval_params_json": src.get("retrieval_params"),
                }
            )
        if sources_db_payload:
            db.insert_data_table_sources(table_id, sources_db_payload)

        payload: Dict[str, Any] = {
            "table_id": table_id,
            "table_uuid": table_uuid,
            "prompt": req.prompt,
            "sources": job_sources,
            "column_hints": column_hints,
            "model": req.model,
            "max_rows": req.max_rows,
        }

        job = jm.create_job(
            domain="data_tables",
            queue="default",
            job_type="data_table_generate",
            payload=payload,
            owner_user_id=str(current_user.id),
            priority=5,
            max_retries=3,
            request_id=rid,
            trace_id=tp or None,
        )

        if wait_for_completion:
            job_state = await _wait_for_job_completion(jm, int(job.get("id")), timeout_seconds=wait_timeout_seconds)
            job_status = str(job_state.get("status") or "").lower()
            if job_status != "completed":
                raise HTTPException(
                    status_code=409,
                    detail=job_state.get("error_message") or "data_table_job_failed",
                )
            owner_user_id = _resolve_owner_id(principal, current_user)
            table_row = db.get_data_table_by_uuid(table_uuid, owner_user_id=owner_user_id)
            if not table_row:
                raise HTTPException(status_code=404, detail="data_table_not_found")
            response.status_code = status.HTTP_200_OK
            rows_limit = min(req.max_rows or 2000, 2000)
            return _build_table_detail_response(
                table_row,
                db,
                rows_limit=rows_limit,
                rows_offset=0,
                include_rows=True,
                include_sources=True,
            )

        response.status_code = status.HTTP_202_ACCEPTED
        return DataTableGenerateResponse(
            job_id=int(job.get("id")),
            job_uuid=job.get("uuid"),
            status=str(job.get("status") or "queued"),
            table=_table_summary_from_row(
                table_row,
                column_count=0,
                source_count=len(sources_db_payload),
            ),
        )
    except InputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("data_tables.generate failed")
        if table_id is not None:
            try:
                db.update_data_table(
                    table_id,
                    status="failed",
                    last_error=str(exc),
                )
            except Exception:
                logger.debug("data_tables.generate: failed to mark table as failed")
        raise HTTPException(status_code=500, detail="Failed to submit data table job") from exc


@router.get(
    "",
    response_model=DataTablesListResponse,
    summary="List data tables",
    dependencies=[Depends(require_permissions(MEDIA_READ))],
)
async def list_data_tables(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by name/description"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> DataTablesListResponse:
    owner_user_id = _resolve_owner_id(principal, current_user)
    rows = db.list_data_tables(
        status=status_filter,
        search=search,
        limit=limit,
        offset=offset,
        owner_user_id=owner_user_id,
    )
    total = db.count_data_tables(
        status=status_filter,
        search=search,
        owner_user_id=owner_user_id,
    )
    table_ids = []
    for row in rows:
        try:
            table_ids.append(int(row.get("id")))
        except Exception:
            continue
    counts_map = db.get_data_table_counts(table_ids)
    tables = []
    for row in rows:
        table_id = None
        try:
            table_id = int(row.get("id"))
        except Exception:
            table_id = None
        counts = counts_map.get(table_id or -1, {})
        tables.append(
            _table_summary_from_row(
                row,
                column_count=counts.get("column_count"),
                source_count=counts.get("source_count"),
            )
        )
    return DataTablesListResponse(
        tables=tables,
        items=tables,
        results=tables,
        count=len(tables),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{table_uuid}",
    response_model=DataTableDetailResponse,
    summary="Get a data table by UUID",
    dependencies=[Depends(require_permissions(MEDIA_READ))],
)
async def get_data_table(
    table_uuid: str,
    rows_limit: int = Query(200, ge=1, le=2000),
    rows_offset: int = Query(0, ge=0),
    include_rows: bool = Query(True),
    include_sources: bool = Query(True),
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> DataTableDetailResponse:
    owner_user_id = _resolve_owner_id(principal, current_user)
    table_row = db.get_data_table_by_uuid(table_uuid, owner_user_id=owner_user_id)
    if not table_row:
        raise HTTPException(status_code=404, detail="data_table_not_found")

    return _build_table_detail_response(
        table_row,
        db,
        rows_limit=rows_limit,
        rows_offset=rows_offset,
        include_rows=include_rows,
        include_sources=include_sources,
        owner_user_id=owner_user_id,
    )


@router.get(
    "/{table_uuid}/export",
    response_model=DataTableExportResponse,
    summary="Export a data table",
    dependencies=[
        Depends(require_permissions(MEDIA_READ)),
        Depends(rbac_rate_limit("data_tables.export")),
    ],
)
async def export_data_table(
    table_uuid: str,
    response: Response,
    request: Request = None,
    format: DataTableExportFormat = Query(..., description="Export format (csv|json|xlsx)"),
    async_mode: AsyncMode = Query("auto", description="auto defers large exports; async forces 202"),
    mode: ExportMode = Query("url", description="url returns a download link; inline returns base64 content"),
    download: bool = Query(False, description="Return file content directly"),
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db: MediaDatabase = Depends(get_media_db_for_user),
    cdb: CollectionsDatabase = Depends(get_collections_db_for_user),
) -> DataTableExportResponse:
    owner_user_id = _resolve_owner_id(principal, current_user)
    table_row = db.get_data_table_by_uuid(table_uuid, owner_user_id=owner_user_id)
    if not table_row:
        raise HTTPException(status_code=404, detail="data_table_not_found")
    if str(table_row.get("status") or "") != "ready":
        raise HTTPException(status_code=409, detail="data_table_not_ready")

    table_id = int(table_row.get("id"))
    column_rows = db.list_data_table_columns(table_id, owner_user_id=owner_user_id)
    if not column_rows:
        raise HTTPException(status_code=409, detail="data_table_missing_columns")

    column_rows = sorted(
        column_rows,
        key=lambda row: (int(row.get("position") or 0), int(row.get("id") or 0)),
    )
    column_ids = [str(row.get("column_id") or "") for row in column_rows]
    column_names = [str(row.get("name") or "") for row in column_rows]
    rows = _collect_export_rows(
        db,
        table_id,
        column_ids=column_ids,
        column_names=column_names,
        owner_user_id=owner_user_id,
    )
    structured = {"columns": column_names, "rows": rows}

    if download:
        adapter = DataTableAdapter()
        try:
            normalized = adapter.normalize(structured)
            export_result = await _export_structured(adapter, normalized, format)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if export_result.status != "ready" or not export_result.content:
            raise HTTPException(status_code=500, detail="export_failed")
        byte_count = len(export_result.content)
        max_bytes = DEFAULT_MAX_BYTES
        if byte_count > max_bytes:
            raise HTTPException(status_code=422, detail="export_size_exceeded")
        filename = _build_export_filename(str(table_row.get("name") or "data_table"), format)
        return Response(
            content=export_result.content,
            media_type=export_result.content_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
        )

    options_payload: Dict[str, Any] = {"persist": True}
    if rows:
        options_payload["max_rows"] = len(rows)
        options_payload["max_cells"] = len(rows) * len(column_names)
    options = FileCreateOptions(**options_payload)
    export_req = FileExportRequest(format=format, mode=mode, async_mode=async_mode)
    file_req = FileCreateRequest(
        file_type="data_table",
        title=str(table_row.get("name") or "data_table"),
        payload=structured,
        export=export_req,
        options=options,
    )
    request_id = ensure_request_id(request) if request is not None else None
    service = FileArtifactsService(cdb, user_id=current_user.id)
    should_async = async_mode == "async" or (
        async_mode == "auto"
        and service._should_export_async("data_table", structured, options, format)
    )
    if should_async:
        try:
            artifact, status_code = await service.create_artifact(file_req, request_id=request_id)
        except FileArtifactsError as exc:
            raise _file_artifacts_http_exception(exc) from exc
        response.status_code = status_code
        return DataTableExportResponse(
            table_uuid=table_uuid,
            file_id=artifact.file_id,
            export=artifact.export,
        )

    inline_max_bytes = service._resolve_inline_max_bytes()
    estimated_bytes = service._estimate_export_size("data_table", structured, format)
    if (
        mode == "url"
        and inline_max_bytes > 0
        and estimated_bytes is not None
        and estimated_bytes <= inline_max_bytes
    ):
        adapter = get_registry().get_adapter("data_table")
        if adapter is None:
            raise HTTPException(status_code=500, detail="export_adapter_unavailable")
        try:
            normalized = adapter.normalize(structured)
            export_result = await _export_structured(adapter, normalized, format)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if export_result.status != "ready" or not export_result.content:
            raise HTTPException(status_code=500, detail="export_failed")
        byte_count = len(export_result.content)
        max_bytes = options.max_bytes or DEFAULT_MAX_BYTES
        if byte_count > max_bytes:
            raise HTTPException(status_code=422, detail="export_size_exceeded")
        filename = _build_export_filename(str(table_row.get("name") or "data_table"), format)
        return Response(
            content=export_result.content,
            media_type=export_result.content_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    try:
        artifact, status_code = await service.create_artifact(file_req, request_id=request_id)
    except FileArtifactsError as exc:
        raise _file_artifacts_http_exception(exc) from exc
    response.status_code = status_code
    return DataTableExportResponse(
        table_uuid=table_uuid,
        file_id=artifact.file_id,
        export=artifact.export,
    )


@router.put(
    "/{table_uuid}/content",
    response_model=DataTableDetailResponse,
    summary="Update data table content",
    dependencies=[Depends(require_permissions(MEDIA_UPDATE))],
)
async def update_data_table_content(
    table_uuid: str,
    req: DataTableContentUpdateRequest,
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> DataTableDetailResponse:
    owner_user_id = _resolve_owner_id(principal, current_user)
    table_row = db.get_data_table_by_uuid(table_uuid, owner_user_id=owner_user_id)
    if not table_row:
        raise HTTPException(status_code=404, detail="data_table_not_found")

    table_id = int(table_row.get("id"))
    columns_payload: List[Dict[str, Any]] = []
    for idx, column in enumerate(req.columns):
        col = _model_dump(column)
        columns_payload.append(
            {
                "column_id": col.get("column_id"),
                "name": str(col.get("name") or "").strip(),
                "type": col.get("type"),
                "description": col.get("description"),
                "format": col.get("format"),
                "position": col.get("position", idx),
            }
        )

    rows_payload: List[Dict[str, Any]] = []
    for idx, row in enumerate(req.rows):
        if not isinstance(row, dict):
            raise HTTPException(status_code=400, detail="row_payload_invalid")
        row_index = row.get("row_index", idx)
        row_json = row.get("row_json")
        if row_json is None:
            row_json = row.get("data", row)
        rows_payload.append(
            {
                "row_id": row.get("row_id"),
                "row_index": row_index,
                "row_json": row_json,
            }
        )

    try:
        db.soft_delete_data_table_columns(table_id, owner_user_id=owner_user_id)
        db.soft_delete_data_table_rows(table_id, owner_user_id=owner_user_id)
        if columns_payload:
            db.insert_data_table_columns(table_id, columns_payload, owner_user_id=owner_user_id)
        if rows_payload:
            db.insert_data_table_rows(table_id, rows_payload, owner_user_id=owner_user_id)
        db.update_data_table(
            table_id,
            status="ready",
            row_count=len(rows_payload),
            owner_user_id=owner_user_id,
        )
    except InputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated_row = db.get_data_table(table_id, owner_user_id=owner_user_id) or table_row
    rows_limit = max(1, min(len(rows_payload) or 200, 2000))
    return _build_table_detail_response(
        updated_row,
        db,
        rows_limit=rows_limit,
        rows_offset=0,
        include_rows=True,
        include_sources=True,
        owner_user_id=owner_user_id,
    )


@router.patch(
    "/{table_uuid}",
    response_model=DataTableSummary,
    summary="Update data table metadata",
    dependencies=[Depends(require_permissions(MEDIA_UPDATE))],
)
async def update_data_table(
    table_uuid: str,
    req: DataTableUpdateRequest,
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> DataTableSummary:
    owner_user_id = _resolve_owner_id(principal, current_user)
    table_row = db.get_data_table_by_uuid(table_uuid, owner_user_id=owner_user_id)
    if not table_row:
        raise HTTPException(status_code=404, detail="data_table_not_found")
    updated = db.update_data_table(
        int(table_row.get("id")),
        name=req.name.strip() if req.name is not None else None,
        description=req.description,
        owner_user_id=owner_user_id,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="data_table_update_failed")
    counts = db.get_data_table_counts([int(updated.get("id"))]).get(int(updated.get("id")), {})
    return _table_summary_from_row(
        updated,
        column_count=counts.get("column_count"),
        source_count=counts.get("source_count"),
    )


@router.delete(
    "/{table_uuid}",
    response_model=DataTableDeleteResponse,
    summary="Delete a data table",
    dependencies=[
        Depends(require_permissions(MEDIA_DELETE)),
        Depends(rbac_rate_limit("data_tables.delete")),
    ],
)
async def delete_data_table(
    table_uuid: str,
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> DataTableDeleteResponse:
    owner_user_id = _resolve_owner_id(principal, current_user)
    table_row = db.get_data_table_by_uuid(table_uuid, owner_user_id=owner_user_id)
    if not table_row:
        raise HTTPException(status_code=404, detail="data_table_not_found")
    deleted = db.soft_delete_data_table(int(table_row.get("id")), owner_user_id=owner_user_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="data_table_delete_failed")
    return DataTableDeleteResponse(success=True)


@router.post(
    "/{table_uuid}/regenerate",
    response_model=DataTableGenerateResponse,
    summary="Regenerate a data table from stored sources",
    dependencies=[
        Depends(require_permissions(MEDIA_UPDATE)),
        Depends(rbac_rate_limit("data_tables.regenerate")),
    ],
)
async def regenerate_data_table(
    table_uuid: str,
    req: DataTableRegenerateRequest,
    response: Response,
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db: MediaDatabase = Depends(get_media_db_for_user),
    jm: JobManager = Depends(get_job_manager),
    request: Request = None,
) -> DataTableGenerateResponse:
    rid = ensure_request_id(request) if request is not None else None
    tp = ensure_traceparent(request) if request is not None else ""

    owner_user_id = _resolve_owner_id(principal, current_user)
    table_row = db.get_data_table_by_uuid(table_uuid, owner_user_id=owner_user_id)
    if not table_row:
        raise HTTPException(status_code=404, detail="data_table_not_found")

    table_id = int(table_row.get("id"))
    sources_rows = db.list_data_table_sources(table_id, owner_user_id=owner_user_id)
    job_sources = [
        {
            "source_type": row.get("source_type"),
            "source_id": row.get("source_id"),
            "title": row.get("title"),
            "snapshot": _parse_json_value(row.get("snapshot_json")),
            "retrieval_params": _parse_json_value(row.get("retrieval_params_json")),
        }
        for row in sources_rows
    ]
    if not job_sources:
        raise HTTPException(status_code=400, detail="data_table_missing_sources")

    prompt_override = req.prompt.strip() if req.prompt is not None else None
    if prompt_override == "":
        prompt_override = None

    payload: Dict[str, Any] = {
        "table_id": table_id,
        "table_uuid": table_uuid,
        "prompt": prompt_override or table_row.get("prompt"),
        "sources": job_sources,
        "column_hints": _parse_json_value(table_row.get("column_hints_json")),
        "model": req.model or table_row.get("generation_model"),
        "max_rows": req.max_rows,
        "regenerate": True,
    }

    job = jm.create_job(
        domain="data_tables",
        queue="default",
        job_type="data_table_generate",
        payload=payload,
        owner_user_id=str(current_user.id),
        priority=5,
        max_retries=3,
        request_id=rid,
        trace_id=tp or None,
    )
    db.update_data_table(
        table_id,
        status="queued",
        generation_model=req.model or table_row.get("generation_model"),
        prompt=prompt_override,
        owner_user_id=owner_user_id,
    )

    response.status_code = status.HTTP_202_ACCEPTED
    counts = db.get_data_table_counts([table_id]).get(table_id, {})
    return DataTableGenerateResponse(
        job_id=int(job.get("id")),
        job_uuid=job.get("uuid"),
        status=str(job.get("status") or "queued"),
        table=_table_summary_from_row(
            db.get_data_table(table_id, owner_user_id=owner_user_id) or table_row,
            column_count=counts.get("column_count"),
            source_count=counts.get("source_count"),
        ),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=DataTableJobStatus,
    summary="Get data table job status",
    dependencies=[Depends(require_permissions(MEDIA_READ))],
)
async def get_data_table_job(
    job_id: int,
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    jm: JobManager = Depends(get_job_manager),
) -> DataTableJobStatus:
    job = jm.get_job(int(job_id))
    if not job or str(job.get("domain") or "") != "data_tables":
        raise HTTPException(status_code=404, detail="job_not_found")
    owner = str(job.get("owner_user_id") or "")
    if not (principal.is_admin or owner == str(current_user.id)):
        raise HTTPException(status_code=403, detail="not_authorized")
    payload = job.get("payload") or {}
    return DataTableJobStatus(
        id=int(job.get("id")),
        uuid=job.get("uuid"),
        status=job.get("status"),
        job_type=job.get("job_type"),
        owner_user_id=job.get("owner_user_id"),
        created_at=job.get("created_at"),
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        cancelled_at=job.get("cancelled_at"),
        cancellation_reason=job.get("cancellation_reason"),
        progress_percent=job.get("progress_percent"),
        progress_message=job.get("progress_message"),
        result=job.get("result"),
        error_message=job.get("error_message"),
        table_uuid=payload.get("table_uuid"),
    )


@router.delete(
    "/jobs/{job_id}",
    response_model=DataTableJobCancelResponse,
    summary="Cancel a data table job",
    dependencies=[
        Depends(require_permissions(MEDIA_UPDATE)),
        Depends(rbac_rate_limit("data_tables.jobs.cancel")),
    ],
)
async def cancel_data_table_job(
    job_id: int,
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    jm: JobManager = Depends(get_job_manager),
    reason: Optional[str] = None,
) -> DataTableJobCancelResponse:
    job = jm.get_job(int(job_id))
    if not job or str(job.get("domain") or "") != "data_tables":
        raise HTTPException(status_code=404, detail="job_not_found")
    owner = str(job.get("owner_user_id") or "")
    if not (principal.is_admin or owner == str(current_user.id)):
        raise HTTPException(status_code=403, detail="not_authorized")
    status_val = str(job.get("status") or "").lower()
    if status_val in {"completed", "failed", "cancelled", "quarantined"}:
        raise HTTPException(status_code=400, detail="cannot_cancel_terminal_job")
    ok = jm.cancel_job(int(job_id), reason=reason)
    if not ok:
        raise HTTPException(status_code=400, detail="cancellation_failed")
    return DataTableJobCancelResponse(
        success=True,
        job_id=int(job_id),
        status="cancelled",
        message="Job cancellation requested",
    )


__all__ = ["router"]
