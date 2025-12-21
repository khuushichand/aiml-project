from __future__ import annotations

from typing import List, Optional

from fastapi import Form, HTTPException, status
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.media_request_models import ProcessCodeForm

try:
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT
except AttributeError:  # Starlette < 0.27
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY


async def get_process_code_form(
    urls: Optional[List[str]] = Form(None),
    perform_chunking: bool = Form(True),
    chunk_method: Optional[str] = Form("code"),
    chunk_size: int = Form(4000),
    chunk_overlap: int = Form(200),
) -> ProcessCodeForm:
    """
    Dependency that parses multipart/form-data into a ProcessCodeForm.

    Mirrors the legacy behaviour while centralising validation so both
    legacy and modular endpoints share the same semantics.
    """
    try:
        return ProcessCodeForm(
            urls=urls,
            perform_chunking=perform_chunking,
            chunk_method=chunk_method,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except ValidationError as exc:
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


__all__ = ["get_process_code_form"]
