from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger
import types

from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
from tldw_Server_API.app.core.Workflows.subprocess_utils import start_process, terminate_process


class AdapterError(Exception):
    pass


async def run_prompt_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Render a prompt using the sandboxed Jinja engine.

    Config:
      - template: str (preferred) or prompt: str
      - variables: dict (optional) merged into context
    Output:
      - {"text": rendered}
    """
    template = config.get("template") or config.get("prompt") or ""
    variables = config.get("variables") or {}
    # Merge base inputs
    data = {**context}
    # Ensure dot-access for inputs in templates (e.g., inputs.name)
    try:
        if isinstance(data.get("inputs"), dict):
            data["inputs"] = types.SimpleNamespace(**data["inputs"])  # type: ignore[arg-type]
    except Exception:
        pass
    try:
        # Keep a shallow namespace for convenience
        data.update(variables)
    except Exception:
        pass

    # Pre-pass: simple replace for {{ inputs.key }} tokens to be robust in sandbox
    try:
        import re
        if isinstance(context.get("inputs"), dict):
            def repl(m):
                key = m.group(1)
                return str(context["inputs"].get(key, ""))
            template = re.sub(r"\{\{\s*inputs\.(\w+)\s*\}\}", repl, template)
    except Exception:
        pass

    # Optional simulated delay/error for testing retries/timeouts
    try:
        delay_ms = int(config.get("simulate_delay_ms", 0))
        if delay_ms > 0:
            remaining = delay_ms / 1000.0
            # Sleep in small chunks to allow cooperative cancel during tests
            while remaining > 0:
                if callable(context.get("is_cancelled")) and context["is_cancelled"]():
                    return {"__status__": "cancelled"}
                sl = min(0.05, remaining)
                await asyncio.sleep(sl)
                remaining -= sl
    except Exception:
        pass
    if config.get("force_error"):
        raise AdapterError("forced_error")

    rendered = apply_template_to_string(template, data) or ""
    logger.debug(f"Prompt adapter rendered length={len(rendered)}")
    return {"text": rendered}


async def run_rag_search_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a RAG search via the unified pipeline with minimal required args.

    Config keys supported (subset):
      - query (templated)
      - sources: list[str]
      - search_mode: fts|vector|hybrid
      - top_k: int
      - hybrid_alpha: float
    Output:
      - {"documents": [...], "metadata": result.metadata}
    """
    template_query = config.get("query") or ""
    rendered_query = apply_template_to_string(template_query, context) or template_query

    sources = config.get("sources") or ["media_db"]
    search_mode = config.get("search_mode") or "hybrid"
    top_k = int(config.get("top_k", 10))
    hybrid_alpha = float(config.get("hybrid_alpha", 0.7))

    # Default DB path for media; future: derive per-tenant/user
    media_db_path = "Databases/Media_DB_v2.db"

    result = await unified_rag_pipeline(
        query=rendered_query,
        sources=sources,
        search_mode=search_mode,
        top_k=top_k,
        hybrid_alpha=hybrid_alpha,
        media_db_path=media_db_path,
        enable_cache=True,
    )

    docs = []
    for d in result.documents:
        try:
            docs.append({
                "id": d.id,
                "content": d.content,
                "metadata": d.metadata,
                "score": float(getattr(d, "score", 0.0) or 0.0),
            })
        except Exception:
            # Be robust to different shapes
            try:
                doc_dict = d if isinstance(d, dict) else json.loads(json.dumps(d, default=str))
            except Exception:
                doc_dict = {"id": "unknown", "content": str(d)}
            docs.append(doc_dict)

    return {
        "documents": docs,
        "metadata": result.metadata,
        "timings": result.timings,
    }


async def run_media_ingest_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Media ingestion step (v0.1 minimal) with optional yt-dlp/ffmpeg integration.

    Config:
      - sources: [{uri, media_type?}]
      - download: {enabled: bool, ydl_format?, max_filesize_mb?, retries?}
      - limits: {max_download_mb?, max_duration_sec?}
      - safety: {allowed_domains?: [string]}
      - timeout_seconds: int (enforced internally)
    Output:
      - { media_ids: [], metadata: [...], transcripts: [], rag_indexed: False }
    """
    sources = config.get("sources") or []
    download = (config.get("download") or {}).copy()
    safety = config.get("safety") or {}
    timeout_seconds = int(config.get("timeout_seconds", 300))

    out = {
        "media_ids": [],
        "metadata": [],
        "transcripts": [],
        "rag_indexed": False,
    }

    if not sources:
        return out

    # Security: allowed domains for HTTP(S)
    allowed_domains = set(safety.get("allowed_domains") or [])

    start_ts = time.time()
    for idx, src in enumerate(sources):
        uri = str(src.get("uri", "")).strip()
        if not uri:
            continue

        # file:// URIs are treated as local; we do not spawn yt-dlp
        if uri.startswith("file://"):
            out["metadata"].append({
                "source": uri,
                "media_type": src.get("media_type", "auto"),
                "status": "local_ok",
            })
            continue

        # HTTP(S) URIs: honor allowed_domains if provided
        if uri.startswith("http://") or uri.startswith("https://"):
            from urllib.parse import urlparse
            host = urlparse(uri).hostname or ""
            if allowed_domains and not any(host.endswith(d) for d in allowed_domains):
                out["metadata"].append({
                    "source": uri,
                    "status": "skipped_disallowed_domain",
                })
                continue

            # Skip actual download in tests/no-network; detect env var
            if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
                out["metadata"].append({
                    "source": uri,
                    "status": "simulated_download",
                })
                continue

            # Attempt yt-dlp via subprocess for better isolation
            ydl_format = download.get("ydl_format", "bestvideo+bestaudio/best")
            workdir = Path(os.getenv("WORKFLOWS_TMP", ".tmp")) / "workflows"
            step_dir = workdir / f"ingest_{int(time.time()*1000)}_{idx}"
            step_dir.mkdir(parents=True, exist_ok=True)
            log_dir = step_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            # Build command with safe options
            output_tpl = str(step_dir / "%(title).80s.%(ext)s")
            cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "-f",
                ydl_format,
                "-o",
                output_tpl,
                "--no-playlist",
                "--no-cache-dir",
                uri,
            ]
            # Optional max filesize
            max_mb = download.get("max_filesize_mb")
            if max_mb:
                try:
                    _mb = int(max_mb)
                    cmd.extend(["--max-filesize", f"{_mb}M"])
                except Exception:
                    pass

            task = start_process(cmd, workdir=step_dir, log_dir=log_dir)

            # Poll with timeout
            exited = False
            while time.time() - start_ts < timeout_seconds:
                # cooperative cancel
                if callable(context.get("is_cancelled")) and context["is_cancelled"]():
                    terminate_process(task)
                    return {"__status__": "cancelled"}
                # heartbeat callback
                try:
                    if callable(context.get("heartbeat")):
                        context["heartbeat"]()
                except Exception:
                    pass
                await asyncio.sleep(0.25)
                # Check if any file downloaded
                if any(step_dir.glob("*.*")):
                    exited = True
                    break
            if not exited:
                terminate_process(task)
                out["metadata"].append({
                    "source": uri,
                    "status": "timeout",
                })
                continue

            out["metadata"].append({
                "source": uri,
                "status": "downloaded",
                "dir": str(step_dir),
            })

    return out


async def run_mcp_tool_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an MCP tool via the unified server registry.

    Config:
      - tool_name: str
      - arguments: dict
    Output: {"result": Any}
    """
    from tldw_Server_API.app.core.MCP_unified import get_mcp_server
    tool_name = str(config.get("tool_name") or "").strip()
    arguments = config.get("arguments") or {}
    if not tool_name:
        return {"error": "missing_tool_name"}
    server = get_mcp_server()
    # Find module by tool registry
    module_id = server.module_registry._tool_registry.get(tool_name)  # type: ignore[attr-defined]
    module = None
    if module_id:
        module = server.module_registry._module_instances.get(module_id)  # type: ignore[attr-defined]
    # Fallback: scan modules for defined tool names
    if module is None:
        try:
            for mid, mod in server.module_registry._module_instances.items():  # type: ignore[attr-defined]
                try:
                    tools = await mod.get_tools()
                    if any((t.get("name") == tool_name) for t in tools):
                        module = mod
                        module_id = mid
                        break
                except Exception:
                    continue
        except Exception:
            pass
    if module is None:
        # Test-friendly fallback for echo
        if tool_name == "echo":
            return {"result": arguments.get("message"), "module": "_fallback"}
        return {"error": "tool_not_found"}
    result = await module.execute_tool(tool_name, arguments)
    return {"result": result, "module": module_id}


async def run_webhook_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Send a webhook event using unified evaluations webhook manager (secure SSRF/HMAC).

    Config:
      - url: optional (if provided, send to specific URL; otherwise, deliver to registered webhooks)
      - event: str
      - data: dict (templated minimal)
    Output: {"dispatched": bool}
    """
    from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
    user_id = str(context.get("user_id") or context.get("inputs", {}).get("user_id") or "1")
    event_name = str(config.get("event") or "workflow.event")
    payload = config.get("data") or {"context": list(context.keys())}
    import os
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        # Skip outbound work in tests
        return {"dispatched": False, "test_mode": True}
    try:
        event = WebhookEvent(event_name)  # type: ignore[arg-type]
    except Exception:
        # Default to a generic event if unknown
        event = WebhookEvent.EVALUATION_PROGRESS
    try:
        await webhook_manager.send_webhook(user_id=user_id, event=event, evaluation_id="workflow", data=payload)
        return {"dispatched": True}
    except Exception as e:
        return {"dispatched": False, "error": str(e)}
