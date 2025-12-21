"""
HTTP error mapping helpers for API v1.

This module centralizes translation of internal exceptions
(especially database-related ones) into FastAPI HTTPException
instances with consistent status codes and messages.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from loguru import logger

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    ConflictError,
    DatabaseError,
    InputError,
    SchemaError,
)


def map_db_error_to_http(
    exc: Exception,
    *,
    not_found_status: Optional[int] = None,
    default_detail: str = "Database error occurred",
) -> HTTPException:
    """
    Map a database-layer exception to a FastAPI HTTPException.

    Mapping rules (aligned with Media refactor PRD):
    - InputError       -> 400 Bad Request
    - ConflictError    -> 409 Conflict
    - SchemaError      -> 500 Internal Server Error (schema/migration issue)
    - DatabaseError    -> 500 Internal Server Error
    - other Exception  -> 500 Internal Server Error

    `not_found_status` is reserved for contexts where callers already know an
    absence case should be treated as 404; this function does not infer it by
    itself but allows future refinement without changing call sites.
    """
    if isinstance(exc, InputError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or "Invalid input",
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Conflict detected",
        )
    if isinstance(exc, SchemaError):
        # Schema issues are serious; log with stack trace.
        logger.error(f"SchemaError from DB layer: {exc}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database schema error",
        )
    if isinstance(exc, DatabaseError):
        logger.error(f"DatabaseError from DB layer: {exc}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=default_detail,
        )

    # Fallback for unexpected errors.
    logger.error(f"Unexpected exception mapped to HTTP 500: {exc}", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


__all__ = ["map_db_error_to_http"]
