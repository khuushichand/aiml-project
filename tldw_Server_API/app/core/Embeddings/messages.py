"""
messages.py
Helper utilities for message schema versioning, validation, and dedupe key construction
for the embeddings pipeline queues.

We deliberately keep validation lightweight by leveraging the existing Pydantic
models defined in queue_schemas.py, and standardize the `msg_version` and `schema`
fields for all messages.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from loguru import logger

from .queue_schemas import (
    ChunkingMessage,
    EmbeddingMessage,
    StorageMessage,
)


CURRENT_SCHEMA = "tldw.embeddings.v1"
CURRENT_SCHEMA_URL = "https://tldw.local/schemas/tldw.embeddings.v1.json"
CURRENT_VERSION = 1

# Minimal JSON Schema bundle for ingress validation
_SCHEMAS = {
    CURRENT_SCHEMA: {
        "$id": CURRENT_SCHEMA_URL,
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": CURRENT_SCHEMA,
        "type": "object",
        "required": ["job_id", "user_id", "media_id"],
        "properties": {
            "msg_version": {"type": "integer", "minimum": 1},
            "msg_schema": {"type": "string"},
            "schema_url": {"type": "string"},
            "job_id": {"type": "string", "minLength": 1},
            "user_id": {"type": "string", "minLength": 1},
            "media_id": {"type": ["integer", "string"]},
            "retry_count": {"type": "integer", "minimum": 0},
            "max_retries": {"type": "integer", "minimum": 0},
            "idempotency_key": {"type": ["string", "null"]},
            "dedupe_key": {"type": ["string", "null"]},
            "operation_id": {"type": ["string", "null"]},
        },
        "additionalProperties": True,
    }
}

def validate_schema(stage: str, data: Dict[str, Any]) -> None:
    """Validate basic envelope with bundled JSON Schema.

    Raises ValueError if invalid. We keep this lightweight and permissive,
    only checking core envelope fields at ingress.
    """
    try:
        import jsonschema  # type: ignore
    except Exception:
        # If jsonschema unavailable, skip validation (non-fatal)
        return
    schema = _SCHEMAS.get(CURRENT_SCHEMA)
    if not schema:
        return
    # Coerce schema defaults
    d = dict(data or {})
    d.setdefault("msg_version", CURRENT_VERSION)
    d.setdefault("msg_schema", CURRENT_SCHEMA)
    d.setdefault("schema_url", CURRENT_SCHEMA_URL)
    try:
        jsonschema.validate(d, schema)  # type: ignore
    except Exception as e:
        raise ValueError(f"Schema validation failed: {e}")


def normalize_message(stage: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a raw message dict for a given stage.

    Behavior is intentionally permissive at ingress:
    - Always injects envelope defaults (`msg_version`, `msg_schema`, `schema_url`).
    - Performs lightweight JSON Schema validation of core fields when available.
    - Only instantiates the full stage Pydantic model when the stage-defining fields
      are present (e.g., chunking requires `content` and `content_type`). This allows
      callers/tests to pass partial payloads with extra fields without raising.
    - Returns a normalized dict suitable for enqueue/processing.
    """
    stage = (stage or "").strip().lower()
    if not isinstance(data, dict):
        raise ValueError("Message must be a dict")

    # Ensure envelope defaults
    if "msg_version" not in data:
        data["msg_version"] = CURRENT_VERSION
    # Support both legacy 'schema' and new 'msg_schema'
    if "msg_schema" not in data and "schema" not in data:
        data["msg_schema"] = CURRENT_SCHEMA
    if "schema_url" not in data:
        data["schema_url"] = CURRENT_SCHEMA_URL

    # Validate basic envelope via bundled JSON schema (non-fatal if dependency missing)
    try:
        validate_schema(stage, data)
    except ValueError:
        # Surface envelope errors as permanent input issues
        raise
    except Exception:
        # Ignore when jsonschema is not present
        pass

    # Conditionally validate with the appropriate stage model only when core fields are present
    def _to_dict(model) -> Dict[str, Any]:
        return json.loads(model.model_dump_json())  # type: ignore[attr-defined]

    if stage == "chunking":
        if "content" in data and "content_type" in data:
            return _to_dict(ChunkingMessage(**data))
        return data
    elif stage == "embedding":
        # embedding messages generally carry a non-empty 'chunks' array
        if isinstance(data.get("chunks"), list):
            return _to_dict(EmbeddingMessage(**data))
        return data
    elif stage == "storage":
        # storage messages carry an 'embeddings' array
        if isinstance(data.get("embeddings"), list):
            return _to_dict(StorageMessage(**data))
        return data
    else:
        raise ValueError(f"Unknown stage '{stage}' for message normalization")


def build_dedupe_key(stage: str, data: Dict[str, Any]) -> str:
    """Construct a conservative dedupe key.

    Priority:
    1) Explicit `dedupe_key`
    2) Explicit `idempotency_key`
    3) Fallbacks by stage using job_id and salient identifiers
    """
    if not isinstance(data, dict):
        return ""
    # Prefer explicit operation_id for replay prevention
    if data.get("operation_id"):
        return f"op:{data['operation_id']}"
    if data.get("dedupe_key"):
        return str(data["dedupe_key"])  # operator-provided, trust as-is
    if data.get("idempotency_key"):
        return f"{stage}:{data['idempotency_key']}"

    job_id = str(data.get("job_id", ""))
    if stage == "chunking":
        # chunking: job_id is adequate
        return f"chunking:{job_id}"
    elif stage == "embedding":
        # embedding: job_id + number of chunks
        try:
            n = len(data.get("chunks", []) or [])
        except Exception:
            n = 0
        return f"embedding:{job_id}:{n}"
    elif stage == "storage":
        # storage: job_id + total_chunks
        tc = data.get("total_chunks")
        return f"storage:{job_id}:{tc}"
    return job_id


# ---------------------------------------------------------------------------
# Failure classification helpers
# ---------------------------------------------------------------------------

def classify_failure(exc: Exception) -> tuple[str, str]:
    """Classify an exception as transient or permanent and return an error code.

    Returns a tuple: (failure_type, error_code)
    - failure_type: 'transient' or 'permanent'
    - error_code: short machine-readable reason (e.g., 'TIMEOUT', 'NETWORK', 'INVALID_INPUT')

    Heuristics are conservative: default to 'transient' unless we confidently
    detect a permanent/user/input error.
    """
    try:
        # Fast path by type
        from pydantic import ValidationError  # local import to avoid hard dep at import-time
    except Exception:
        ValidationError = tuple()  # type: ignore

    name = type(exc).__name__
    msg = str(exc).lower()

    # Provider HTTP client errors with status
    status_code = None
    try:
        # aiohttp.ClientResponseError has .status
        import aiohttp  # type: ignore
        if isinstance(exc, aiohttp.ClientResponseError):  # type: ignore[attr-defined]
            status_code = getattr(exc, "status", None)
    except Exception:
        pass
    try:
        # httpx exceptions
        import httpx  # type: ignore
        if isinstance(exc, httpx.HTTPStatusError):  # type: ignore[attr-defined]
            try:
                status_code = getattr(exc.response, "status_code", None)
            except Exception:
                status_code = None
        elif isinstance(exc, httpx.RequestError):  # network class
            return ("transient", "NETWORK")
    except Exception:
        pass

    # Generic access for objects carrying status/status_code
    if status_code is None:
        for attr in ("status", "status_code"):
            try:
                v = getattr(exc, attr, None)
                if isinstance(v, int):
                    status_code = v
                    break
            except Exception:
                pass

    if isinstance(status_code, int):
        sc = status_code
        if sc == 408:
            return ("transient", "TIMEOUT")
        if sc == 429:
            return ("transient", "RATE_LIMIT")
        if 500 <= sc <= 599:
            return ("transient", "UPSTREAM_5XX")
        if 400 <= sc <= 499:
            # map selected 4xx to more precise codes
            mapping = {
                400: "BAD_REQUEST",
                401: "UNAUTHORIZED",
                403: "FORBIDDEN",
                404: "NOT_FOUND",
                409: "CONFLICT",
                413: "PAYLOAD_TOO_LARGE",
                415: "UNSUPPORTED_MEDIA_TYPE",
                422: "UNPROCESSABLE_ENTITY",
            }
            return ("permanent", mapping.get(sc, "CLIENT_ERROR"))

    # Timeouts and connection issues → transient
    if isinstance(exc, TimeoutError):
        return ("transient", "TIMEOUT")
    if name in {"ClientConnectionError", "ClientOSError", "ServerDisconnectedError", "ClientError"}:
        return ("transient", "NETWORK")
    if isinstance(exc, ConnectionError) or isinstance(exc, ConnectionResetError):
        return ("transient", "NETWORK")

    # Rate limits and server overload signals
    if "rate limit" in msg or "429" in msg or "too many requests" in msg:
        return ("transient", "RATE_LIMIT")
    if "503" in msg or "service unavailable" in msg or "server overloaded" in msg:
        return ("transient", "UPSTREAM_UNAVAILABLE")

    # Input/schema/data issues → permanent
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return ("permanent", "INVALID_INPUT")
    if ValidationError and isinstance(exc, ValidationError):
        return ("permanent", "VALIDATION")
    if name in {"JSONDecodeError"} or "invalid json" in msg:
        return ("permanent", "BAD_JSON")
    if "unsupported model" in msg or "unknown provider" in msg:
        return ("permanent", "CONFIG")
    if "authentication" in msg or "invalid api key" in msg:
        return ("permanent", "AUTH")

    # Storage-specific conflicts or bounds
    if "duplicate key" in msg or "unique constraint" in msg:
        return ("permanent", "CONFLICT")
    if "payload too large" in msg or "request entity too large" in msg:
        return ("permanent", "PAYLOAD_TOO_LARGE")

    # Default: assume transient
    return ("transient", name.upper()[:32] or "ERROR")
