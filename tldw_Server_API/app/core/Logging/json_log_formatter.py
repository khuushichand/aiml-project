"""JSON log formatter for structured log shipping.

Provides a loguru-compatible formatter that emits one JSON object per line,
suitable for ingestion by Loki (via Promtail), ELK (via Filebeat), or any
JSONL-capable log aggregation pipeline.
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger


def json_log_format(record: dict[str, Any]) -> str:
    """Format a loguru record as a JSON line for Loki/ELK ingestion.

    Parameters
    ----------
    record:
        The loguru log record dict.

    Returns
    -------
    str
        A single JSON line (newline-terminated).
    """
    log_entry: dict[str, Any] = {
        "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
    }
    exc = record.get("exception")
    if exc is not None:
        log_entry["exception"] = str(exc)
    # Include extra fields attached via logger.bind()
    extra = record.get("extra", {})
    if extra:
        log_entry["extra"] = {k: str(v) for k, v in extra.items()}
    return json.dumps(log_entry, default=str) + "\n"


def configure_json_logging(log_file: str = "logs/tldw.jsonl") -> int:
    """Add a JSON log sink alongside existing loguru configuration.

    Call at startup to enable structured logging to a file that
    can be tailed by Promtail, Filebeat, or similar.

    Parameters
    ----------
    log_file:
        Path to the JSONL output file.  Rotated at 100 MB, kept for 7 days.

    Returns
    -------
    int
        The sink id returned by ``logger.add()``, useful for removal.
    """
    sink_id = logger.add(
        log_file,
        format=json_log_format,
        rotation="100 MB",
        retention="7 days",
        compression="gz",
        serialize=False,
    )
    logger.info("JSON structured logging enabled: {}", log_file)
    return sink_id
