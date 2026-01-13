"""
Embeddings stream message schema helpers.

This module provides a lightweight validator for embeddings pipeline payloads
used by DLQ tooling. It intentionally stays permissive to avoid blocking
requeue operations while still catching obviously malformed payloads.
"""

from __future__ import annotations

from typing import Any, Mapping, Dict, Optional

from pydantic import BaseModel, Field

from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat

VALID_STAGES = {"chunking", "embedding", "storage", "content"}

CURRENT_VERSION = 1
CURRENT_SCHEMA = "tldw.embeddings.v1"
SCHEMA_URL = "https://schemas.tldw.ai/embeddings/v1.json"


class ChunkingConfigModel(BaseModel):
    chunk_size: int = Field(..., ge=100)
    overlap: int = Field(..., ge=0)
    separator: Optional[str] = None


def normalize_message(stage: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize an embeddings pipeline message payload.

    Adds envelope defaults (schema/version) and validates chunking_config.
    """
    validate_schema(stage, payload)

    message: Dict[str, Any] = dict(payload)
    schema_value = message.get("msg_schema") or message.get("schema") or CURRENT_SCHEMA
    message.pop("schema", None)
    message["msg_schema"] = schema_value
    message["msg_version"] = CURRENT_VERSION
    message.setdefault("schema_url", SCHEMA_URL)

    if stage.strip().lower() == "chunking" and message.get("chunking_config") is not None:
        cfg = ChunkingConfigModel(**message["chunking_config"])
        message["chunking_config"] = model_dump_compat(cfg)

    return message


def validate_schema(stage: str, payload: Mapping[str, Any]) -> None:
    """Validate a DLQ payload for a given stage."""
    if not isinstance(stage, str):
        raise ValueError("stage must be a string")
    stage_normalized = stage.strip().lower()
    if stage_normalized not in VALID_STAGES:
        raise ValueError(f"invalid stage '{stage}' (expected one of: {', '.join(sorted(VALID_STAGES))})")

    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    if not payload:
        raise ValueError("payload is empty")

    if stage_normalized == "content":
        if payload.get("content") is None and payload.get("text") is None:
            raise ValueError("payload missing content/text for content stage")
        return

    try:
        import jsonschema  # type: ignore
    except Exception:
        return

    schema = {
        "type": "object",
        "required": ["job_id", "user_id", "media_id"],
        "properties": {
            "job_id": {"type": "string"},
            "user_id": {"type": "string"},
            "media_id": {"type": "integer"},
        },
    }

    try:
        jsonschema.validate(payload, schema)
    except Exception as exc:
        raise ValueError(str(exc)) from exc
