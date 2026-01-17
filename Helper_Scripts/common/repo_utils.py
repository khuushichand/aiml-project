"""Helper utilities shared across Helper_Scripts."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger


def ensure_repo_root() -> None:
    """Find the repo root and prepend it to sys.path."""
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "tldw_Server_API").is_dir():
            parent_str = str(parent)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)
            return


def configure_local_egress(url: str) -> None:
    """Allow local-host egress defaults for helper scripts."""
    try:
        parsed = urlparse(url)
    except Exception as exc:
        logger.error("Failed to parse egress URL; url={url!r} exc={exc!r}", url=url, exc=exc)
        return
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "0.0.0.0"} or host.startswith("127.") or host == "::1":
        if "WORKFLOWS_EGRESS_BLOCK_PRIVATE" not in os.environ:
            logger.info(
                "Applying local egress override; host={host} scheme={scheme}",
                host=host,
                scheme=parsed.scheme,
            )
            os.environ["WORKFLOWS_EGRESS_BLOCK_PRIVATE"] = "false"
        if "WORKFLOWS_EGRESS_ALLOWED_PORTS" not in os.environ:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            allowed_ports = f"{port},80,443"
            logger.info(
                "Applying local egress allowed ports; host={host} scheme={scheme} port={port}",
                host=host,
                scheme=parsed.scheme,
                port=port,
            )
            os.environ["WORKFLOWS_EGRESS_ALLOWED_PORTS"] = allowed_ports
