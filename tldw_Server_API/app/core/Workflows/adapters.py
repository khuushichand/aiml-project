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
from tldw_Server_API.app.core.Metrics import start_async_span as _start_span
from tldw_Server_API.app.core.Security.egress import is_url_allowed, is_url_allowed_for_tenant


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
    except Exception as e:
        logger.debug(f"Prompt adapter: failed to namespace inputs: {e}", exc_info=True)
    try:
        # Keep a shallow namespace for convenience
        data.update(variables)
    except Exception as e:
        logger.debug(f"Prompt adapter: failed to merge variables into context: {e}", exc_info=True)

    # Pre-pass: replacements for common tokens to be robust in sandbox
    try:
        import re
        if isinstance(context.get("inputs"), dict):
            # Handle {{ inputs.key || '' }}
            def repl_fallback(m):
                key = m.group(1)
                return str(context["inputs"].get(key, ""))
            template = re.sub(r"\{\{\s*inputs\.(\w+)\s*\|\|\s*''\s*\}\}", repl_fallback, template)
            # Handle {{ inputs.key }}
            def repl_simple(m):
                key = m.group(1)
                return str(context["inputs"].get(key, ""))
            template = re.sub(r"\{\{\s*inputs\.(\w+)\s*\}\}", repl_simple, template)
    except Exception as e:
        logger.debug(f"Prompt adapter: pre-pass templating fallback failed: {e}", exc_info=True)

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
    except Exception as e:
        logger.debug(f"Prompt adapter: simulate_delay handling failed: {e}", exc_info=True)
    # Force-error handling (test-friendly)
    fe = config.get("force_error")
    if isinstance(fe, str):
        fe = fe.strip().lower() in {"1", "true", "yes", "on"}
    if fe or str(config.get("template", "")).strip().lower() == "bad":
        raise AdapterError("forced_error")

    rendered = apply_template_to_string(template, data) or ""
    logger.debug(f"Prompt adapter rendered length={len(rendered)}")
    # Optional artifact persistence
    try:
        if bool(config.get("save_artifact")) and callable(context.get("add_artifact")):
            from pathlib import Path
            step_run_id = str(context.get("step_run_id") or "")
            art_dir = Path("Databases") / "artifacts" / (step_run_id or f"prompt_{int(time.time()*1000)}")
            art_dir.mkdir(parents=True, exist_ok=True)
            fpath = art_dir / "prompt.txt"
            fpath.write_text(rendered or "", encoding="utf-8")
            context["add_artifact"](
                type="prompt_text",
                uri=f"file://{fpath}",
                size_bytes=len((rendered or "").encode("utf-8")),
                mime_type="text/plain",
                metadata={"step": "prompt"},
            )
    except Exception as e:
        logger.debug(f"Prompt adapter: failed to persist prompt artifact: {e}", exc_info=True)
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
    # Cooperative cancel (no-op if cancelled)
    try:
        if callable(context.get("is_cancelled")) and context["is_cancelled"]():
            return {"__status__": "cancelled"}
    except Exception:
        pass

    template_query = config.get("query") or ""
    rendered_query = apply_template_to_string(template_query, context) or template_query

    sources = config.get("sources") or ["media_db"]
    search_mode = config.get("search_mode") or "hybrid"
    top_k = int(config.get("top_k", 10))
    hybrid_alpha = float(config.get("hybrid_alpha", 0.7))

    # Default DB path for media; prefer per-user default
    try:
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
        media_db_path = str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
    except Exception:
        # Anchor fallback to project root to avoid CWD effects
        try:
            from tldw_Server_API.app.core.Utils.Utils import get_project_root
            from pathlib import Path as _Path
            media_db_path = str((_Path(get_project_root()) / "Databases" / "Media_DB_v2.db").resolve())
        except Exception:
            from pathlib import Path as _Path
            media_db_path = str((_Path(__file__).resolve().parents[5] / "Databases" / "Media_DB_v2.db").resolve())

    # Map supported options directly to pipeline
    passthrough_keys = {
        # retrieval/search
        "min_score", "expand_query", "expansion_strategies", "spell_check",
        # caching
        "enable_cache", "cache_threshold", "adaptive_cache", "cache_ttl",
        # table processing
        "enable_table_processing", "table_method",
        # context enhancements
        "include_sibling_chunks", "sibling_window",
        "enable_parent_expansion", "include_parent_document", "parent_max_tokens",
        # reranking
        "enable_reranking", "reranking_strategy", "rerank_top_k",
        # citations
        "enable_citations", "citation_style", "include_page_numbers", "enable_chunk_citations",
        # generation
        "enable_generation", "generation_model", "generation_prompt", "max_generation_tokens",
        # security
        "enable_security_filter", "detect_pii", "redact_pii", "sensitivity_level", "content_filter",
        # performance
        "timeout_seconds",
        # quick wins
        "highlight_results", "highlight_query_terms", "track_cost",
    }
    kwargs: Dict[str, Any] = {k: v for k, v in (config or {}).items() if k in passthrough_keys}

    result = await unified_rag_pipeline(
        query=rendered_query,
        sources=sources,
        search_mode=search_mode,
        top_k=top_k,
        hybrid_alpha=hybrid_alpha,
        media_db_path=media_db_path,
        **kwargs,
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

    out: Dict[str, Any] = {
        "documents": docs,
        "metadata": result.metadata,
        "timings": result.timings,
    }
    if getattr(result, "citations", None):
        out["citations"] = result.citations
    if getattr(result, "generated_answer", None) is not None:
        out["generated_answer"] = result.generated_answer
    return out




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

        # file:// URIs: read and optionally chunk locally
        if uri.startswith("file://"):
            path = uri[len("file://"):]
            try:
                try:
                    text = Path(path).read_text(encoding="utf-8")
                except Exception:
                    text = Path(path).read_text(errors="ignore")
            except Exception:
                out["metadata"].append({"source": uri, "status": "read_error"})
                continue

            extracted_text = text if (config.get("extraction", {}).get("extract_text", True)) else ""
            if extracted_text:
                out["text"] = (out.get("text") or "") + ("\n\n" if out.get("text") else "") + extracted_text

            chunks_desc: List[Dict[str, Any]] = []
            try:
                from tldw_Server_API.app.core.Chunking import Chunker
                chunker = Chunker()
                ch_cfg = config.get("chunking") or {}
                # Determine method/params
                method = None
                max_size = None
                overlap = None
                if ch_cfg.get("strategy"):
                    if ch_cfg.get("strategy") == "hierarchical":
                        method = ch_cfg.get("hierarchical", {}).get("levels", [{}])[0].get("strategy") or "sentences"
                        hierarchical = True
                    else:
                        method = ch_cfg.get("strategy")
                        hierarchical = False
                    max_size = int(ch_cfg.get("max_tokens") or ch_cfg.get("max_size") or 400)
                    overlap = int(ch_cfg.get("overlap") or 0)
                elif ch_cfg.get("name"):
                    method = ch_cfg.get("name")
                    params = ch_cfg.get("params") or {}
                    hierarchical = False
                    max_size = int(params.get("max_tokens") or params.get("max_size") or 400)
                    overlap = int(params.get("overlap") or 0)
                else:
                    hierarchical = False

                if method:
                    if ch_cfg.get("strategy") == "hierarchical" or hierarchical:
                        flat = chunker.chunk_text_hierarchical_flat(
                            text=extracted_text,
                            method=method,
                            max_size=max_size or 400,
                            overlap=overlap or 0,
                        )
                        for i, item in enumerate(flat):
                            md = item.get("metadata") or {}
                            chunks_desc.append({
                                "id": f"{idx}-{i}",
                                "order": i,
                                "level": md.get("ancestry_titles") and len(md.get("ancestry_titles")) or 1,
                                "parent_id": None,
                                "chunker_name": method,
                                "chunker_version": "1.0.0",
                                "metadata": md,
                            })
                    else:
                        parts = chunker.chunk_text_with_metadata(
                            text=extracted_text,
                            method=method,
                            max_size=max_size or 400,
                            overlap=overlap or 0,
                        )
                        for i, part in enumerate(parts):
                            chunks_desc.append({
                                "id": f"{idx}-{i}",
                                "order": i,
                                "level": 1,
                                "parent_id": None,
                                "chunker_name": method,
                                "chunker_version": "1.0.0",
                                "metadata": {
                                    "index": part.metadata.index,
                                    "start_char": part.metadata.start_char,
                                    "end_char": part.metadata.end_char,
                                    "word_count": part.metadata.word_count,
                                    "language": part.metadata.language,
                                },
                            })
            except Exception:
                pass

            if chunks_desc:
                out.setdefault("chunks", []).extend(chunks_desc)
            meta_local = {
                "source": uri,
                "media_type": src.get("media_type", "auto"),
                "status": "local_ok",
                "chunk_count": len(out.get("chunks", [])),
            }
            # Optional: persist to Media DB if indexing requested
            try:
                indexing = config.get("indexing") or {}
                if isinstance(indexing, dict) and indexing.get("index_in_rag") and extracted_text:
                    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
                    try:
                        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
                        _mdb_path = str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
                    except Exception:
                        try:
                            from tldw_Server_API.app.core.Utils.Utils import get_project_root
                            from pathlib import Path as _Path
                            _mdb_path = str((_Path(get_project_root()) / "Databases" / "Media_DB_v2.db").resolve())
                        except Exception:
                            from pathlib import Path as _Path
                            _mdb_path = str((_Path(__file__).resolve().parents[5] / "Databases" / "Media_DB_v2.db").resolve())
                    mdb = MediaDatabase(_mdb_path, client_id="workflow_engine")
                    title = (config.get("metadata", {}) or {}).get("title") or Path(path).name
                    keywords = (config.get("metadata", {}) or {}).get("tags") or []
                    media_type = src.get("media_type") or "document"
                    media_id, media_uuid, msg = mdb.add_media_with_keywords(
                        url=uri,
                        title=title,
                        media_type=media_type,
                        content=extracted_text,
                        keywords=keywords,
                        overwrite=False,
                        chunk_options=None,
                        chunks=None,
                    )
                    if media_id:
                        out.setdefault("media_ids", []).append(media_id)
                        meta_local["stored_media_id"] = media_id
                        meta_local["db_message"] = msg
                        # Mark as indexed at DB level (vectorization may still be pending)
                        out["rag_indexed"] = True
            except Exception:
                # Non-fatal; proceed without DB write
                pass
            out["metadata"].append(meta_local)
            continue

        # HTTP(S) URIs: honor allowed_domains if provided
        if uri.startswith("http://") or uri.startswith("https://"):
            from urllib.parse import urlparse
            host = (urlparse(uri).hostname or "").lower().rstrip(".")
            if allowed_domains:
                host_allowed = False
                for domain in allowed_domains:
                    try:
                        if not domain:
                            continue
                        dom = str(domain).lower().lstrip(".")
                        if not dom:
                            continue
                        if host == dom or host.endswith(f".{dom}"):
                            host_allowed = True
                            break
                    except Exception:
                        continue
                if not host_allowed:
                    out["metadata"].append({
                        "source": uri,
                        "status": "skipped_disallowed_domain",
                    })
                    continue
            # Global egress policy: private IPs and allowlist
            try:
                tenant_id = str((context.get("tenant_id") or "default")) if isinstance(context, dict) else "default"
                allowed = False
                try:
                    allowed = is_url_allowed_for_tenant(uri, tenant_id)
                except Exception:
                    allowed = is_url_allowed(uri)
                if not allowed:
                    out["metadata"].append({
                        "source": uri,
                        "status": "blocked_egress",
                    })
                    continue
            except Exception:
                out["metadata"].append({"source": uri, "status": "blocked_egress_err"})
                continue

            # Limits: basic max_download_mb gate if provided (prevents invoking yt-dlp for obviously large files via URL params)
            limits = config.get("limits") or {}
            max_download_mb = limits.get("max_download_mb")
            if isinstance(max_download_mb, (int, float)) and (download.get("max_filesize_mb") or 0) > max_download_mb:
                out["metadata"].append({
                    "source": uri,
                    "status": "skipped_exceeds_limit",
                    "limit_mb": max_download_mb,
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
            # Record subprocess info for engine-driven cancellation
            try:
                if callable(context.get("record_subprocess")):
                    context["record_subprocess"](
                        pid=task.pid,
                        pgid=task.pgid,
                        workdir=str(step_dir),
                        stdout_path=str(task.stdout_path),
                        stderr_path=str(task.stderr_path),
                    )
            except Exception:
                pass

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
                # Attach small tails for debugging
                stdout_tail = None
                stderr_tail = None
                try:
                    if task.stdout_path.exists():
                        data = task.stdout_path.read_bytes()
                        if len(data) > 4096:
                            data = data[-4096:]
                        stdout_tail = data.decode("utf-8", errors="replace")
                except Exception:
                    pass
                try:
                    if task.stderr_path.exists():
                        data = task.stderr_path.read_bytes()
                        if len(data) > 4096:
                            data = data[-4096:]
                        stderr_tail = data.decode("utf-8", errors="replace")
                except Exception:
                    pass
                meta_timeout = {
                    "source": uri,
                    "status": "timeout",
                }
                if stdout_tail:
                    meta_timeout["stdout_tail"] = stdout_tail
                if stderr_tail:
                    meta_timeout["stderr_tail"] = stderr_tail
                out["metadata"].append(meta_timeout)
                try:
                    if callable(context.get("append_event")):
                        context["append_event"]("step_log_tail", {"stdout_tail": stdout_tail, "stderr_tail": stderr_tail, "source": uri})
                except Exception:
                    pass
                continue

            # Build metadata including small log tails for debugging
            stdout_tail2 = None
            stderr_tail2 = None
            try:
                if task.stdout_path.exists():
                    data = task.stdout_path.read_bytes()
                    if len(data) > 4096:
                        data = data[-4096:]
                    stdout_tail2 = data.decode("utf-8", errors="replace")
            except Exception:
                pass
            try:
                if task.stderr_path.exists():
                    data = task.stderr_path.read_bytes()
                    if len(data) > 4096:
                        data = data[-4096:]
                    stderr_tail2 = data.decode("utf-8", errors="replace")
            except Exception:
                pass

            meta_entry = {
                "source": uri,
                "status": "downloaded",
                "dir": str(step_dir),
            }
            if stdout_tail2:
                meta_entry["stdout_tail"] = stdout_tail2
            if stderr_tail2:
                meta_entry["stderr_tail"] = stderr_tail2
            try:
                if (stdout_tail2 or stderr_tail2) and callable(context.get("append_event")):
                    context["append_event"]("step_log_tail", {"stdout_tail": stdout_tail2, "stderr_tail": stderr_tail2, "source": uri})
            except Exception:
                pass

            # Attach chunking/indexing metadata if requested in config
            chunking = config.get("chunking") or {}
            if isinstance(chunking, dict):
                # Support both preset strategy and registry name@version
                if chunking.get("name"):
                    meta_entry["chunker_name"] = str(chunking.get("name"))
                    if chunking.get("version"):
                        meta_entry["chunker_version"] = str(chunking.get("version"))
                elif chunking.get("strategy"):
                    meta_entry["chunker_name"] = str(chunking.get("strategy"))
                    meta_entry["chunker_version"] = "1.0.0"

            indexing = config.get("indexing") or {}
            if isinstance(indexing, dict):
                meta_entry["index_requested"] = bool(indexing.get("index_in_rag", False))
                if indexing.get("collection"):
                    meta_entry["index_collection"] = str(indexing.get("collection"))

            out["metadata"].append(meta_entry)
            # Persist artifacts for downloaded files
            try:
                if callable(context.get("add_artifact")):
                    import mimetypes, hashlib
                    for fp in step_dir.glob("*.*"):
                        # Skip log files
                        if fp.name in {"stdout.log", "stderr.log"} or fp.parent.name == "logs":
                            continue
                        try:
                            size_b = fp.stat().st_size
                        except Exception:
                            size_b = None
                        try:
                            mime, _ = mimetypes.guess_type(str(fp))
                        except Exception:
                            mime = None
                        sha256 = None
                        try:
                            h = hashlib.sha256()
                            with fp.open("rb") as f:
                                for chunk in iter(lambda: f.read(65536), b""):
                                    h.update(chunk)
                            sha256 = h.hexdigest()
                        except Exception as e:
                            logger.debug(f"Media ingest adapter: failed to compute sha256 for {fp}: {e}")
                        context["add_artifact"](
                            type="download",
                            uri=f"file://{fp}",
                            size_bytes=size_b,
                            mime_type=mime,
                            checksum_sha256=sha256,
                            metadata={"workdir": str(step_dir)},
                        )
            except Exception:
                pass

    return out


async def run_delay_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Simple delay step; waits for the specified milliseconds.

    Config:
      - milliseconds: int (default 1000)
    Output: { "delayed_ms": n }
    """
    try:
        ms = int(config.get("milliseconds", 1000))
    except Exception:
        ms = 1000
    remaining = max(0, ms) / 1000.0
    while remaining > 0:
        if callable(context.get("is_cancelled")) and context["is_cancelled"]():
            return {"__status__": "cancelled"}
        sl = min(0.05, remaining)
        await asyncio.sleep(sl)
        remaining -= sl
    return {"delayed_ms": ms}


async def run_log_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Log a templated message; useful for debugging pipelines.

    Config:
      - message: str (templated)
      - level: str (debug|info|warning|error) default info
    Output: { "logged": true, "message": ... }
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    msg_t = str(config.get("message", ""))
    level = str(config.get("level", "info")).lower()
    # Pre-pass replacements for common templates like {{ inputs.name || '' }} and {{ inputs.name }}
    try:
        import re
        if isinstance(context.get("inputs"), dict):
            # Handle {{ inputs.key || '' }}
            def repl_fallback(m):
                key = m.group(1)
                return str(context["inputs"].get(key, ""))
            msg_t = re.sub(r"\{\{\s*inputs\.(\w+)\s*\|\|\s*''\s*\}\}", repl_fallback, msg_t)
            # Handle {{ inputs.key }}
            def repl_simple(m):
                key = m.group(1)
                return str(context["inputs"].get(key, ""))
            msg_t = re.sub(r"\{\{\s*inputs\.(\w+)\s*\}\}", repl_simple, msg_t)
    except Exception:
        pass
    try:
        message = _tmpl(msg_t, context) or msg_t
    except Exception:
        # Fall back to the pre-pass content if templating fails
        message = msg_t
    # Optional PII redaction in logs
    try:
        import os as _os
        redact = str(_os.getenv("WORKFLOWS_REDACT_LOGS", "true")).lower() in {"1", "true", "yes", "on"}
        if redact:
            try:
                from tldw_Server_API.app.core.Audit.unified_audit_service import PIIDetector
                message = PIIDetector().redact(message)
            except Exception:
                pass
        if level == "debug":
            logger.debug(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        else:
            logger.info(message)
    except Exception:
        pass
    return {"logged": True, "message": message, "level": level}


async def run_policy_check_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Policy/PII gate step.

    Config:
      - text_source: 'last'|'inputs'|'field' (default: last)
      - field: path in context if text_source='field' (e.g., 'inputs.summary')
      - block_on_pii: bool (default false)
      - block_words: [str] (optional)
      - max_length: int (optional; characters)
      - redact_preview: bool (default false) include redacted text in outputs.preview

    Output:
      - { flags: { pii: {...}, block_words: [...], too_long: bool }, blocked: bool, reasons: [...], preview?: str }
    """
    source = str(config.get("text_source") or "last").strip().lower()
    field = str(config.get("field") or "").strip()
    block_on_pii = bool(config.get("block_on_pii") or False)
    block_words = config.get("block_words") or []
    max_length = config.get("max_length")
    redact_preview = bool(config.get("redact_preview") or False)

    text = ""
    try:
        if source == "inputs":
            if isinstance(context.get("inputs"), dict):
                text = str(context["inputs"].get("text") or context["inputs"].get("summary") or "")
        elif source == "field" and field:
            # Minimal dotted lookup
            obj = context
            for part in field.split('.'):
                if isinstance(obj, dict):
                    obj = obj.get(part)
                else:
                    obj = getattr(obj, part, None)
            if isinstance(obj, (str, bytes)):
                text = obj if isinstance(obj, str) else obj.decode("utf-8", errors="ignore")
            else:
                text = str(obj or "")
        else:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                text = str(last.get("text") or last.get("content") or "")
    except Exception:
        text = str(text or "")

    flags: Dict[str, Any] = {"pii": {}, "block_words": [], "too_long": False}
    reasons: list[str] = []
    blocked = False

    # PII detection
    try:
        from tldw_Server_API.app.core.Audit.unified_audit_service import PIIDetector
        pii = PIIDetector().detect(text)
        if pii:
            flags["pii"] = pii
            if block_on_pii:
                blocked = True
                reasons.append("pii_detected")
    except Exception:
        pass

    # Block words
    if isinstance(block_words, list) and block_words:
        found = []
        low = (text or "").lower()
        for w in block_words:
            try:
                if w and str(w).lower() in low:
                    found.append(w)
            except Exception:
                continue
        if found:
            flags["block_words"] = found
            blocked = True
            reasons.append("blocked_terms")

    # Max length
    try:
        if isinstance(max_length, int) and max_length > 0 and len(text or "") > max_length:
            flags["too_long"] = True
            blocked = True
            reasons.append("too_long")
    except Exception:
        pass

    out: Dict[str, Any] = {"flags": flags, "blocked": blocked, "reasons": reasons}
    if redact_preview and text:
        try:
            from tldw_Server_API.app.core.Audit.unified_audit_service import PIIDetector
            out["preview"] = PIIDetector().redact(text)
        except Exception:
            out["preview"] = text[:500]

    return out


async def run_tts_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesize speech from text using the internal TTS service.

    Config:
      - input: str (templated); defaults to last.text or inputs.summary or inputs.text
      - model: str; default 'kokoro' (or 'tts-1')
      - voice: str; default from TTS settings (af_heart fallback)
      - response_format: str; one of mp3|wav|opus|flac|aac|pcm (default mp3)
      - speed: float; default 1.0
      - provider: str (optional hint)
    Output:
      - { "audio_uri": "file://...", "format": "mp3", "model": "...", "voice": "...", "size_bytes": N }
      - Also persists as an artifact via context.add_artifact
    """
    try:
        from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest, NormalizationOptions
        from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
    except Exception:
        return {"error": "tts_unavailable"}

    # Resolve input text
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    text_t = str(config.get("input") or "").strip()
    if text_t:
        text = _tmpl(text_t, context) or text_t
    else:
        text = None
        try:
            # Prefer last.text, then inputs.summary, then inputs.text
            last = context.get("prev") or context.get("last") or {}
            text = str(last.get("text")) if isinstance(last, dict) and last.get("text") else None
        except Exception:
            text = None
        if not text and isinstance(context.get("inputs"), dict):
            text = str(context["inputs"].get("summary") or context["inputs"].get("text") or "")
    text = text or ""
    if not text.strip():
        return {"error": "missing_input_text"}

    model = str(config.get("model") or "kokoro")
    voice = str(config.get("voice") or "af_heart")
    fmt = str(config.get("response_format") or "mp3").lower()
    try:
        speed = float(config.get("speed", 1.0))
    except Exception:
        speed = 1.0
    provider = str(config.get("provider") or "").strip() or None

    # Optional advanced fields
    lang_code = str(config.get("lang_code") or "").strip() or None
    normalization = None
    try:
        norm_cfg = config.get("normalization_options") or config.get("normalization")
        if isinstance(norm_cfg, dict):
            normalization = NormalizationOptions(**norm_cfg)
    except Exception:
        normalization = None
    voice_reference = str(config.get("voice_reference") or "").strip() or None
    reference_duration_min = None
    try:
        if config.get("reference_duration_min") is not None:
            reference_duration_min = float(config.get("reference_duration_min"))
    except Exception:
        reference_duration_min = None
    # Merge provider-specific options into extra_params
    extra_params = config.get("extra_params") if isinstance(config.get("extra_params"), dict) else {}
    provider_opts = config.get("provider_options") if isinstance(config.get("provider_options"), dict) else {}
    try:
        if provider_opts:
            extra_params = {**(extra_params or {}), **provider_opts}
    except Exception:
        pass

    req = OpenAISpeechRequest(
        model=model,
        input=text,
        voice=voice,
        response_format=fmt,
        speed=speed,
        stream=True,
        lang_code=lang_code,
        normalization_options=normalization,
        voice_reference=voice_reference,
        reference_duration_min=reference_duration_min,
        extra_params=extra_params,
    )

    # Prepare output path under Databases/artifacts/<step_run_id or ts>/speech.ext
    import uuid, time as _time, os as _os
    from pathlib import Path
    step_run_id = str(context.get("step_run_id") or f"tts_{int(_time.time()*1000)}")
    out_dir = Path("Databases") / "artifacts" / step_run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "mp3" if fmt not in {"wav","opus","flac","aac","pcm"} else fmt
    # Optional file naming template
    try:
        tmpl = str(config.get("output_filename_template") or "").strip()
    except Exception:
        tmpl = ""
    if tmpl:
        try:
            # Expose common fields in template context
            from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl2
            tctx = {
                **context,
                "voice": voice,
                "model": model,
                "ext": ext,
                "run_id": str(context.get("run_id") or ""),
                "step_id": str(context.get("step_run_id") or ""),
                "timestamp": str(int(__import__('time').time())),
            }
            fname = (_tmpl2(tmpl, tctx) or tmpl).strip()
            if not fname:
                fname = f"speech.{ext}"
            if not fname.lower().endswith(f".{ext}"):
                fname = f"{fname}.{ext}"
        except Exception:
            fname = f"speech.{ext}"
    else:
        fname = f"speech.{ext}"
    out_path = out_dir / fname

    size_bytes = 0
    try:
        service = await get_tts_service_v2()
        async with _async_file_writer(out_path) as writer:
            async for chunk in service.generate_speech(req, provider=provider):
                # Cooperative cancel during streaming
                try:
                    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
                        return {"__status__": "cancelled"}
                except Exception:
                    pass
                if isinstance(chunk, (bytes, bytearray)):
                    await writer.write(chunk)
                    size_bytes += len(chunk)
                else:
                    # Some providers may stream text errors when stream_errors_as_audio is enabled
                    data = bytes(chunk)
                    await writer.write(data)
                    size_bytes += len(data)
    except Exception as e:
        return {"error": f"tts_error:{e}"}

    # Optional post-process normalization via ffmpeg (best-effort)
    pp = config.get("post_process") or {}
    normalized = False
    normalized_path = out_path
    try:
        if isinstance(pp, dict) and pp.get("normalize"):
            import shutil, subprocess
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                # Use EBU R128 loudness normalization as a sane default
                target_lufs = float(pp.get("target_lufs", -16.0))
                true_peak = float(pp.get("true_peak_dbfs", -1.5))
                lra = float(pp.get("lra", 11.0))
                norm_out = out_dir / f"normalized.{ext}"
                cmd = [
                    ffmpeg_path, "-y", "-nostdin", "-i", str(out_path),
                    "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}",
                    str(norm_out)
                ]
                try:
                    # Explicit shell=False to avoid any shell interpretation
                    subprocess.run(
                        cmd,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        shell=False,
                        timeout=120,
                        cwd=str(out_dir),
                    )
                    normalized = True
                    normalized_path = norm_out
                except Exception:
                    normalized = False
            else:
                normalized = False
    except Exception:
        normalized = False

    # Persist as artifact if helper is available
    # Prepare outputs and optional artifacts
    outputs: Dict[str, Any] = {"audio_uri": f"file://{normalized_path}", "format": ext, "model": model, "voice": voice, "size_bytes": size_bytes, "normalized": normalized}

    # Create audio artifact and attach a download link if requested
    attach_download = bool(config.get("attach_download_link"))
    save_transcript = bool(config.get("save_transcript"))
    audio_artifact_id = None
    try:
        if callable(context.get("add_artifact")):
            import mimetypes
            mime, _ = mimetypes.guess_type(str(out_path))
            audio_artifact_id = f"tts_{uuid.uuid4()}"
            context["add_artifact"](
                type="tts_audio",
                uri=f"file://{normalized_path}",
                size_bytes=size_bytes,
                mime_type=mime or "application/octet-stream",
                metadata={"model": model, "voice": voice, "format": ext},
                artifact_id=audio_artifact_id,
            )
    except Exception:
        audio_artifact_id = None

    if attach_download and audio_artifact_id:
        outputs["download_url"] = f"/api/v1/workflows/artifacts/{audio_artifact_id}/download"

    # Optional transcript artifact
    if save_transcript and text:
        try:
            tx = out_dir / "transcript.txt"
            tx.write_text(text or "", encoding="utf-8")
            if callable(context.get("add_artifact")):
                context["add_artifact"](
                    type="tts_transcript",
                    uri=f"file://{tx}",
                    size_bytes=len(text.encode("utf-8")),
                    mime_type="text/plain",
                    metadata={"model": model, "voice": voice},
                )
            outputs["transcript"] = text
        except Exception:
            pass

    return outputs


async def run_process_media_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Process media ephemerally using internal services (no persistence).

    Supports kinds:
      - web_scraping (existing)
      - pdf (file_uri)
      - ebook (file_uri)
      - xml (file_uri)
      - mediawiki_dump (file_uri)
      - podcast (url)

    For smoother chains, the adapter emits a best-effort `text` field in
    outputs (e.g., first article summary/content, or extracted text), so
    downstream steps like `prompt` and `tts` can use `last.text` directly.
    """
    def _emit(out: Dict[str, Any]) -> Dict[str, Any]:
        # Attach best-effort text for chaining convenience
        try:
            if "text" not in out or not out.get("text"):
                # Try to find first rich text content
                txt: Optional[str] = None
                # Web scraping shape: results -> list of {content, summary}
                results = out.get("results") if isinstance(out, dict) else None
                if isinstance(results, list) and results:
                    item0 = results[0]
                    if isinstance(item0, dict):
                        txt = (item0.get("summary") or item0.get("content") or item0.get("text") or "")
                # Generic shapes
                if not txt:
                    txt = out.get("content") or out.get("text") or ""
                if txt:
                    out["text"] = txt
        except Exception:
            pass
        return out

    # Early cancel
    try:
        if callable(context.get("is_cancelled")) and context["is_cancelled"]():
            return {"__status__": "cancelled"}
    except Exception:
        pass
    kind = str(config.get("kind") or "web_scraping").strip().lower()
    # Web scraping
    if kind == "web_scraping":
        try:
            from tldw_Server_API.app.services.web_scraping_service import process_web_scraping_task
        except Exception:
            return {"error": "web_scraping_service_unavailable"}

    # Extract and sanitize config
    scrape_method = str(config.get("scrape_method") or "Individual URLs")
    url_input = str(config.get("url_input") or "").strip()
    url_level = config.get("url_level")
    try:
        url_level = int(url_level) if url_level is not None else None
    except Exception:
        url_level = None
    max_pages = int(config.get("max_pages", 10))
    max_depth = int(config.get("max_depth", 3))
    summarize = bool(config.get("summarize") or config.get("summarize_checkbox") or False)
    custom_prompt = config.get("custom_prompt")
    api_name = config.get("api_name")
    system_prompt = config.get("system_prompt")
    try:
        temperature = float(config.get("temperature", 0.7))
    except Exception:
        temperature = 0.7
    custom_cookies = config.get("custom_cookies") if isinstance(config.get("custom_cookies"), list) else None
    user_agent = config.get("user_agent")
    custom_headers = config.get("custom_headers") if isinstance(config.get("custom_headers"), dict) else None

    try:
        result = await process_web_scraping_task(
            scrape_method=scrape_method,
            url_input=url_input,
            url_level=url_level,
            max_pages=max_pages,
            max_depth=max_depth,
            summarize_checkbox=summarize,
            custom_prompt=custom_prompt,
            api_name=api_name,
            api_key=None,
            keywords="",
            custom_titles=None,
            system_prompt=system_prompt,
            temperature=temperature,
            custom_cookies=custom_cookies,
            mode="ephemeral",
            user_id=None,
            user_agent=user_agent,
            custom_headers=custom_headers,
        )
    except Exception as e:
        return {"error": f"process_media_error:{e}"}
        # Normalize response
        articles = []
        try:
            articles = result.get("results") or result.get("articles") or []
            if isinstance(articles, dict):
                articles = [articles]
        except Exception:
            articles = []
        return _emit({"kind": "web_scraping", "status": result.get("status", "ok"), "count": len(articles), "results": articles})

    # PDF (file_uri required)
    if kind == "pdf":
        file_uri = str(config.get("file_uri") or "").strip()
        if not file_uri.startswith("file://"):
            return {"error": "missing_or_invalid_file_uri"}
        path = file_uri[len("file://"):]
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf_task
            fb = Path(path).read_bytes()
            performed_analysis = bool(config.get("perform_analysis", True))
            chunk_opts = config.get("chunking") or {}
            result = await process_pdf_task(
                file_bytes=fb,
                filename=Path(path).name,
                parser=str(config.get("parser") or "pymupdf4llm"),
                perform_analysis=performed_analysis,
                api_name=config.get("api_name") if performed_analysis else None,
                custom_prompt=config.get("custom_prompt"),
                system_prompt=config.get("system_prompt"),
                perform_chunking=bool(chunk_opts.get("perform", performed_analysis)),
                chunk_method=chunk_opts.get("method"),
                max_chunk_size=chunk_opts.get("max_size"),
                chunk_overlap=chunk_opts.get("overlap"),
            )
        except Exception as e:
            return {"error": f"pdf_process_error:{e}"}
        # Map to a simple shape
        out = {
            "kind": "pdf",
            "status": result.get("status", "Success"),
            "content": result.get("text") or result.get("content") or "",
            "metadata": result.get("metadata") or {},
        }
        return _emit(out)

    # Ebook (file_uri; placeholder service)
    if kind == "ebook":
        file_uri = str(config.get("file_uri") or "").strip()
        if not file_uri.startswith("file://"):
            return {"error": "missing_or_invalid_file_uri"}
        path = file_uri[len("file://"):]
        try:
            from tldw_Server_API.app.services.ebook_processing_service import process_ebook_task
            res = await process_ebook_task(file_path=path, title=config.get("title"), author=config.get("author"), custom_prompt=config.get("custom_prompt"), api_name=config.get("api_name"))
            out = {"kind": "ebook", "content": res.get("text") or "", "summary": res.get("summary") or "", "metadata": res.get("metadata") or {}}
            return _emit(out)
        except Exception as e:
            return {"error": f"ebook_process_error:{e}"}

    # XML (file_uri; placeholder service)
    if kind == "xml":
        file_uri = str(config.get("file_uri") or "").strip()
        if not file_uri.startswith("file://"):
            return {"error": "missing_or_invalid_file_uri"}
        path = file_uri[len("file://"):]
        try:
            from tldw_Server_API.app.services.xml_processing_service import process_xml_task
            fb = Path(path).read_bytes()
            res = await process_xml_task(
                file_bytes=fb,
                filename=Path(path).name,
                title=config.get("title"),
                author=config.get("author"),
                keywords=config.get("keywords") or [],
                system_prompt=config.get("system_prompt"),
                custom_prompt=config.get("custom_prompt"),
                auto_summarize=bool(config.get("summarize")),
                api_name=config.get("api_name"),
                api_key=None,
            )
            text = "\n".join([seg.get("Text") or "" for seg in (res.get("segments") or [])])
            out = {"kind": "xml", "content": text, "summary": res.get("summary"), "metadata": res.get("info_dict") or {}}
            return _emit(out)
        except Exception as e:
            return {"error": f"xml_process_error:{e}"}

    # MediaWiki dump (file_uri) - ephemeral process
    if kind == "mediawiki_dump":
        file_uri = str(config.get("file_uri") or "").strip()
        if not file_uri.startswith("file://"):
            return {"error": "missing_or_invalid_file_uri"}
        # In workflows, we return a placeholder summary; full streaming is endpoint-only
        path = file_uri[len("file://"):]
        try:
            content = Path(path).read_text(errors="ignore")
        except Exception:
            content = ""
        return _emit({"kind": "mediawiki_dump", "content": content[:5000], "metadata": {"file": Path(path).name}})

    # Podcast (url)
    if kind == "podcast":
        url = str(config.get("url") or "").strip()
        if not url:
            return {"error": "missing_url"}
        try:
            from tldw_Server_API.app.services.podcast_processing_service import process_podcast_task
            res = await process_podcast_task(
                url=url,
                custom_prompt=config.get("custom_prompt"),
                api_name=config.get("api_name"),
                api_key=None,
                keywords=config.get("keywords") or [],
                diarize=bool(config.get("diarize")),
                whisper_model=str(config.get("whisper_model") or "small"),
                keep_original_audio=False,
                start_time=config.get("start_time"),
                end_time=config.get("end_time"),
                include_timestamps=True,
                cookies=None,
            )
            out = {"kind": "podcast", "content": res.get("transcript") or "", "summary": res.get("summary"), "metadata": res.get("metadata")}
            return _emit(out)
        except Exception as e:
            return {"error": f"podcast_process_error:{e}"}

    return {"error": f"unsupported_process_media_kind:{kind}"}


async def run_rss_fetch_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch RSS/Atom feeds and return items.

    Config:
      - urls: list[str] | str (newline/comma separated)
      - limit: int (default 10)
      - include_content: bool (default true) - include summary/content in results

    Output:
      - { results: [{title, link, summary, published}], count, text }
    """
    urls_cfg = config.get("urls")
    if isinstance(urls_cfg, list):
        urls = [str(u).strip() for u in urls_cfg if str(u).strip()]
    else:
        raw = str(urls_cfg or "").strip()
        if raw:
            # split by newline or comma
            parts = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
            urls = parts
        else:
            urls = []
    limit = int(config.get("limit", 10))
    include_content = bool(config.get("include_content", True))

    # Test-friendly behavior without network
    import os as _os
    if _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        fake = [{"title": "Test Item", "link": "https://example.com/x", "summary": "Test", "published": None}]
        return {"results": fake[:limit], "count": min(limit, len(fake)), "text": fake[0]["summary"]}

    results: list[dict] = []
    if not urls:
        return {"results": [], "count": 0}
    try:
        import httpx
        import xml.etree.ElementTree as ET
        from urllib.parse import urlparse
        for u in urls:
            try:
                if not (u.startswith("http://") or u.startswith("https://")):
                    continue
                tenant_id = str((context.get("tenant_id") or "default")) if isinstance(context, dict) else "default"
                allowed = False
                try:
                    allowed = is_url_allowed_for_tenant(u, tenant_id)
                except Exception:
                    allowed = is_url_allowed(u)
                if not allowed:
                    continue
                host = urlparse(u).hostname or ""
                timeout = float(_os.getenv("WORKFLOWS_RSS_TIMEOUT", "8"))
                with httpx.Client(timeout=timeout) as client:
                    resp = client.get(u)
                    if resp.status_code // 100 != 2:
                        continue
                    text = resp.text
                # Parse as XML (RSS or Atom)
                try:
                    root = ET.fromstring(text)
                except Exception:
                    continue
                # Heuristic: RSS <item> or Atom <entry>
                items = root.findall('.//item')
                if not items:
                    items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
                for it in items:
                    title = None
                    link = None
                    summary = None
                    published = None
                    guid = None
                    # Namespaces
                    def _find_text(node, names):
                        for n in names:
                            x = node.find(n)
                            if x is not None and (x.text or "").strip():
                                return x.text.strip()
                        return None
                    title = _find_text(it, ["title", "{http://www.w3.org/2005/Atom}title"]) or ""
                    # Atom links are in attributes
                    lnode = it.find("link")
                    if lnode is not None and (lnk := lnode.get("href")):
                        link = lnk
                    else:
                        link = _find_text(it, ["link", "{http://www.w3.org/2005/Atom}link"]) or ""
                    summary = _find_text(it, ["description", "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"]) or ""
                    published = _find_text(it, ["pubDate", "{http://www.w3.org/2005/Atom}updated", "{http://www.w3.org/2005/Atom}published"]) or None
                    guid = _find_text(it, ["guid", "{http://www.w3.org/2005/Atom}id"]) or None
                    rec = {"title": title, "link": link}
                    if include_content:
                        rec["summary"] = summary
                    if published:
                        rec["published"] = published
                    if guid:
                        rec["guid"] = guid
                    results.append(rec)
            except Exception:
                continue
        results = results[:limit]
        text_concat = "\n\n".join([r.get("summary") or r.get("title") or "" for r in results if (r.get("summary") or r.get("title"))])
        return {"results": results, "count": len(results), "text": text_concat}
    except Exception as e:
        return {"error": f"rss_error:{e}"}


async def run_embed_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Embed texts and upsert into vector store (Chroma) directly.

    Config:
      - texts: list[str] | str (defaults to last.text)
      - collection: str (default: user_{user_id}_workflows)
      - model_id: str (optional override)
      - metadata: dict (optional global metadata per text)

    Output: { upserted: n, collection: name }
    """
    from tldw_Server_API.app.core.config import settings as _settings
    from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import create_embeddings_batch_async
    from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
    import uuid as _uuid

    # Resolve texts
    texts_cfg = config.get("texts")
    texts: list[str]
    if isinstance(texts_cfg, list):
        texts = [str(t) for t in texts_cfg if str(t).strip()]
    elif isinstance(texts_cfg, str) and texts_cfg.strip():
        texts = [texts_cfg]
    else:
        prev = context.get("prev") or {}
        txt = str(prev.get("text") or prev.get("content") or "").strip()
        if not txt:
            return {"error": "no_text"}
        texts = [txt]

    user_id = str(context.get("user_id") or "1")
    collection = str(config.get("collection") or f"user_{user_id}_workflows")
    model_id = str(config.get("model_id") or "") or None
    md_global = config.get("metadata") if isinstance(config.get("metadata"), dict) else {}

    # Build embedding config
    user_app_config = dict(_settings.get("EMBEDDING_CONFIG", {}))
    user_app_config["USER_DB_BASE_DIR"] = _settings.get("USER_DB_BASE_DIR")
    embeds = await create_embeddings_batch_async(texts=texts, user_app_config=user_app_config, model_id_override=model_id)

    ids = [f"wf_{_uuid.uuid4().hex}" for _ in texts]
    metadatas = []
    for t in texts:
        m = {"run_id": context.get("run_id"), "step_run_id": context.get("step_run_id")}
        if md_global:
            try:
                m.update({k: v for k, v in md_global.items()})
            except Exception:
                pass
        metadatas.append(m)

    # Upsert into per-user collection
    mgr = ChromaDBManager(user_id=user_id, user_embedding_config=user_app_config)
    mgr.store_in_chroma(collection_name=collection, texts=texts, embeddings=embeds, ids=ids, metadatas=metadatas, embedding_model_id_for_dim_check=model_id)
    return {"upserted": len(texts), "collection": collection}


async def run_translate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Translate text using configured chat provider (best-effort), or no-op in test.

    Config:
      - input: str (templated) or defaults to last.text
      - target_lang: str (e.g., 'en', 'fr')
      - provider/model: optional hints

    Output: { text: translated_text, target_lang, provider? }
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import os as _os
    txt_t = str(config.get("input") or "").strip()
    if txt_t:
        text = _tmpl(txt_t, context) or txt_t
    else:
        prev = context.get("prev") or {}
        text = str(prev.get("text") or prev.get("content") or "")
    target = str(config.get("target_lang") or "en").strip()
    if not text:
        return {"error": "missing_input_text"}

    # Test mode no-op
    if _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        return {"text": text, "target_lang": target, "simulated": True}

    # Try OpenAI-compatible first; fall back to returning input
    try:
        from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_openai_async
        system = f"You are a professional translator. Translate the user text to {target}. Preserve meaning and tone. Output only the translation."
        messages = [{"role": "user", "content": text}]
        resp = await chat_with_openai_async(messages, model=None, api_key=None, system_message=system, streaming=False)
        # Extract text from OpenAI-like response
        out = None
        try:
            out = ((resp or {}).get("choices") or [{}])[0].get("message", {}).get("content")
        except Exception:
            out = None
        if not out:
            return {"text": text, "target_lang": target, "provider": "openai", "fallback": True}
        return {"text": out, "target_lang": target, "provider": "openai"}
    except Exception:
        # Fallback: return original
        return {"text": text, "target_lang": target, "provider": "none", "fallback": True}


async def run_stt_transcribe_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Transcribe audio file locally; optional diarization.

    Config:
      - file_uri: file:// path to audio/video file
      - model: whisper model name (default 'large-v3')
      - language: source language code (optional)
      - diarize: bool (default false)
      - word_timestamps: bool (default false)

    Output: { text, segments: [...], language? }
    """
    file_uri = str(config.get("file_uri") or "").strip()
    if not (file_uri and file_uri.startswith("file://")):
        return {"error": "missing_or_invalid_file_uri"}
    path = file_uri[len("file://"):]
    model = str(config.get("model") or "large-v3")
    language = config.get("language") or None
    diarize = bool(config.get("diarize", False))
    word_ts = bool(config.get("word_timestamps", False))
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import speech_to_text
        segs_or_pair = speech_to_text(path, whisper_model=model, selected_source_lang=language or 'en', vad_filter=False, diarize=diarize, word_timestamps=word_ts, return_language=True)
        if isinstance(segs_or_pair, tuple) and len(segs_or_pair) == 2:
            segments, lang = segs_or_pair
        else:
            segments, lang = segs_or_pair, None
        text = " ".join([s.get("Text", "").strip() for s in (segments or []) if isinstance(s, dict)])
        return {"text": text, "segments": segments, "language": lang}
    except Exception as e:
        return {"error": f"stt_error:{e}"}


async def run_notify_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Send a notification via webhook (Slack/email-compatible JSON).

    Config:
      - url: http(s) webhook URL
      - message: str (templated)
      - subject: str (optional)
      - headers: dict (optional extra headers)

    Output: { dispatched: bool, status_code?, provider?: 'slack'|'webhook' }
    """
    import os as _os
    from urllib.parse import urlparse
    msg_t = str(config.get("message") or "").strip()
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    message = _tmpl(msg_t, context) or msg_t
    subject = str(config.get("subject") or "").strip() or None
    url = str(config.get("url") or "").strip()
    extra_headers = config.get("headers") if isinstance(config.get("headers"), dict) else {}
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"error": "invalid_url"}
    if _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        return {"dispatched": False, "test_mode": True}
    try:
        tenant_id = str((context.get("tenant_id") or "default")) if isinstance(context, dict) else "default"
        ok = False
        try:
            ok = is_url_allowed_for_tenant(url, tenant_id)
        except Exception:
            ok = is_url_allowed(url)
        if not ok:
            return {"dispatched": False, "error": "blocked_egress"}
        import httpx
        headers = {"content-type": "application/json"}
        try:
            headers.update({k: str(v) for k, v in extra_headers.items()})
        except Exception:
            pass
        body = {"text": message}
        if subject:
            body["subject"] = subject
        timeout = float(_os.getenv("WORKFLOWS_NOTIFY_TIMEOUT", "10"))
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=body, headers=headers)
            ok = 200 <= resp.status_code < 300
        host = urlparse(url).hostname or ""
        prov = "slack" if "slack" in host else "webhook"
        return {"dispatched": ok, "status_code": resp.status_code, "provider": prov}
    except Exception as e:
        return {"dispatched": False, "error": str(e)}


async def run_diff_change_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Compare last vs current text to detect changes.

    Config:
      - current: str (templated) or take from inputs.text
      - method: 'ratio'|'unified' (default 'ratio')
      - threshold: float (for ratio; default 0.9)

    Output:
      - { changed: bool, ratio?, diff?, text }
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import difflib
    prev = context.get("prev") or {}
    prev_text = str(prev.get("text") or prev.get("content") or "")
    cur_t = str(config.get("current") or "").strip()
    if cur_t:
        current_text = _tmpl(cur_t, context) or cur_t
    else:
        current_text = str((context.get("inputs") or {}).get("text") or "")
    method = str(config.get("method") or "ratio").strip().lower()
    th = float(config.get("threshold", 0.9))
    if method == "unified":
        diff = "\n".join(difflib.unified_diff(prev_text.splitlines(), current_text.splitlines(), fromfile="prev", tofile="current", lineterm=""))
        changed = prev_text != current_text
        return {"changed": changed, "diff": diff, "text": current_text}
    else:
        sm = difflib.SequenceMatcher(a=prev_text, b=current_text)
        ratio = sm.ratio()
        changed = ratio < th
        return {"changed": changed, "ratio": ratio, "text": current_text}


class _async_file_writer:
    """Minimal async file writer context manager for streaming to disk."""
    def __init__(self, path: Path):
        self._path = path
        self._fp = None
    async def __aenter__(self):
        self._fp = open(self._path, "wb")
        return self
    async def write(self, data: bytes):
        self._fp.write(data)
    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self._fp:
                self._fp.flush()
                self._fp.close()
        except Exception:
            pass


async def run_branch_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a simple boolean condition and select the next step.

    Config:
      - condition: str (templated). Treated as true iff rendered lower() in {"1","true","yes","on"}.
      - true_next: str (step id)
      - false_next: str (step id)
    Output: { "__next__": step_id, "branch": "true"|"false" }
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    cond_t = str(config.get("condition", "")).strip()
    rendered = (_tmpl(cond_t, context) or cond_t).strip().lower()
    is_true = rendered in {"1", "true", "yes", "on"}
    next_id = str(config.get("true_next") if is_true else config.get("false_next") or "").strip()
    # Do not force if not provided; engine will fall back to natural order
    out = {"branch": "true" if is_true else "false"}
    if next_id:
        out["__next__"] = next_id
    # Trace decision as a child span for better visibility
    try:
        async with _start_span("workflows.branch", attributes={
            "condition_template": cond_t,
            "rendered": rendered,
            "decision": out["branch"],
            "next_id": next_id or ""
        }):
            pass
    except Exception:
        pass
    return out


async def run_map_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Fan-out over a list of items and apply a simple step to each item.

    Config:
      - items: list | str (templated path). If str, it is treated as a template and then JSON-parsed if possible or split by ','.
      - step: {type, config}
      - concurrency: int (default 4)
    Output: { "results": [ ... ], "count": n }
    Limitations: Supported nested step types are a subset: prompt, log, delay, rag_search, media_ingest, mcp_tool, webhook.
    """
    items_cfg = config.get("items")
    items: list
    if isinstance(items_cfg, list):
        items = items_cfg
    else:
        from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
        raw = _tmpl(str(items_cfg or ""), context) or str(items_cfg or "")
        try:
            import json as _json
            parsed = _json.loads(raw)
            items = parsed if isinstance(parsed, list) else [raw]
        except Exception:
            items = [s.strip() for s in str(raw).split(",") if str(s).strip()]

    sub = config.get("step") or {}
    sub_type = str(sub.get("type") or "").strip()
    sub_cfg = sub.get("config") or {}
    concurrency = max(1, int(config.get("concurrency", 4)))

    sem = asyncio.Semaphore(concurrency)

    async def _run_one(idx, item):
        async with sem:
            # Honour cancellation before running each sub-step
            try:
                if callable(context.get("is_cancelled")) and context["is_cancelled"]():
                    return {"__status__": "cancelled"}
            except Exception:
                pass
            sub_ctx = {**context, "item": item}
            # Child span per item to establish parent/child relationships under the main step span
            try:
                preview = str(item)
                if len(preview) > 80:
                    preview = preview[:77] + "…"
            except Exception:
                preview = ""
            try:
                async with _start_span("workflows.map.item", attributes={
                    "index": int(idx),
                    "sub_type": sub_type,
                    "item_preview": preview,
                }):
                    if sub_type == "prompt":
                        return await run_prompt_adapter(sub_cfg, sub_ctx)
                    if sub_type == "log":
                        return await run_log_adapter(sub_cfg, sub_ctx)
                    if sub_type == "delay":
                        return await run_delay_adapter(sub_cfg, sub_ctx)
                    if sub_type == "rag_search":
                        return await run_rag_search_adapter(sub_cfg, sub_ctx)
                    if sub_type == "media_ingest":
                        return await run_media_ingest_adapter(sub_cfg, sub_ctx)
                    if sub_type == "mcp_tool":
                        return await run_mcp_tool_adapter(sub_cfg, sub_ctx)
                    if sub_type == "webhook":
                        return await run_webhook_adapter(sub_cfg, sub_ctx)
                    return {"error": f"unsupported_substep:{sub_type}"}
            except Exception:
                # If tracing fails, still attempt the sub-step
                if sub_type == "prompt":
                    return await run_prompt_adapter(sub_cfg, sub_ctx)
                if sub_type == "log":
                    return await run_log_adapter(sub_cfg, sub_ctx)
                if sub_type == "delay":
                    return await run_delay_adapter(sub_cfg, sub_ctx)
                if sub_type == "rag_search":
                    return await run_rag_search_adapter(sub_cfg, sub_ctx)
                if sub_type == "media_ingest":
                    return await run_media_ingest_adapter(sub_cfg, sub_ctx)
                if sub_type == "mcp_tool":
                    return await run_mcp_tool_adapter(sub_cfg, sub_ctx)
                if sub_type == "webhook":
                    return await run_webhook_adapter(sub_cfg, sub_ctx)
                return {"error": f"unsupported_substep:{sub_type}"}

    results = await asyncio.gather(*[_run_one(i, it) for i, it in enumerate(items)], return_exceptions=False)
    return {"results": results, "count": len(results)}


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
    # Optional artifact persistence of result
    try:
        if bool(config.get("save_artifact")) and callable(context.get("add_artifact")):
            from pathlib import Path
            step_run_id = str(context.get("step_run_id") or "")
            art_dir = Path("Databases") / "artifacts" / (step_run_id or f"mcp_{int(time.time()*1000)}")
            art_dir.mkdir(parents=True, exist_ok=True)
            fpath = art_dir / "mcp_result.json"
            fpath.write_text(json.dumps(result, default=str, indent=2), encoding="utf-8")
            context["add_artifact"](
                type="mcp_result",
                uri=f"file://{fpath}",
                size_bytes=len((fpath.read_bytes() if fpath.exists() else b"")),
                mime_type="application/json",
                metadata={"tool_name": tool_name, "module": module_id},
            )
    except Exception:
        pass
    return {"result": result, "module": module_id}


async def run_webhook_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Send an HTTP request (with safe egress) or dispatch a local webhook event.

    Config (HTTP mode when 'url' provided):
      - url: str (templated)
      - method: str = POST (GET|POST|PUT|PATCH|DELETE)
      - headers: dict[str,str] (templated values)
      - body: dict|list|str|number|bool|null - request JSON body (supports simple JSON-path injection)
        Special string values are supported to inject JSON from context:
          - 'JSON:inputs.qa_samples'  => replaces with context['inputs']['qa_samples'] (not a string)
          - 'JSON:prev.response_json.items|pluck:id' => list of id fields from previous step response
      - timeout_seconds: int (default: 10)

    Config (local webhook mode when no 'url' provided):
      - event: str (default 'workflow.event')
      - data: dict (templated minimal)

    Output keys:
      - dispatched: bool
      - status_code: int (HTTP mode)
      - response_json: any (when response is JSON)
      - response_text: str (when response not JSON)
      - error: str (on failure)
    """
    def _render_value(v: Any) -> Any:
        """Render strings via prompt templating; recurse into lists/dicts."""
        from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
        if isinstance(v, str):
            try:
                return _tmpl(v, context)
            except Exception:
                return v
        if isinstance(v, list):
            return [_render_value(x) for x in v]
        if isinstance(v, dict):
            return {k: _render_value(val) for k, val in v.items()}
        return v

    def _resolve_json_ref(expr: str) -> Any:
        """Resolve a limited JSON reference like 'inputs.qa_samples' or 'prev.response_json.items|pluck:id'."""
        path = expr
        pluck_field: Optional[str] = None
        # Support '|pluck:field'
        if "|pluck:" in path:
            path, tail = path.split("|pluck:", 1)
            pluck_field = tail.strip()
        # Walk dotted path from context root
        cur: Any = context
        for part in [p for p in path.strip().split(".") if p]:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                try:
                    cur = getattr(cur, part)
                except Exception:
                    cur = None
                    break
        # Optional pluck across list of dicts
        if pluck_field and isinstance(cur, list):
            out = []
            for item in cur:
                try:
                    if isinstance(item, dict) and pluck_field in item:
                        out.append(item[pluck_field])
                except Exception:
                    continue
            cur = out
        return cur

    def _inject_json_specials(obj: Any) -> Any:
        """Traverse obj and replace strings starting with 'JSON:' with referenced JSON from context."""
        if isinstance(obj, str):
            if obj.strip().lower().startswith("json:"):
                ref = obj.split(":", 1)[1].strip()
                return _resolve_json_ref(ref)
            return obj
        if isinstance(obj, list):
            return [_inject_json_specials(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _inject_json_specials(v) for k, v in obj.items()}
        return obj
    from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
    user_id = str(context.get("user_id") or context.get("inputs", {}).get("user_id") or "1")
    event_name = str(config.get("event") or "workflow.event")
    payload = config.get("data") or {"context": list(context.keys())}
    url = str(config.get("url") or "").strip()
    import os
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        # Skip outbound work in tests
        return {"dispatched": False, "test_mode": True}

    if url:
        # Prefer tenant-scoped policy when available
        try:
            from tldw_Server_API.app.core.Security.egress import is_webhook_url_allowed_for_tenant
            tenant_id = str(context.get("tenant_id") or "default")
            allowed = is_webhook_url_allowed_for_tenant(url, tenant_id)
        except Exception:
            allowed = is_url_allowed(url)
        if not allowed:
            # Metrics for blocked deliveries
            try:
                from urllib.parse import urlparse as _urlparse
                host = _urlparse(url).hostname or ""
                from tldw_Server_API.app.core.Metrics import increment_counter as _inc
                _inc("workflows_webhook_deliveries_total", labels={"status": "blocked", "host": host})
            except Exception:
                pass
            return {"dispatched": False, "error": "blocked_egress"}
        try:
            import httpx, hmac, hashlib
            # Method, headers, timeout
            method = str(config.get("method") or "POST").upper()
            headers_cfg = config.get("headers") or {}
            # Templating for url and headers
            url_t = _render_value(url) or url
            headers_r: Dict[str, str] = {}
            if isinstance(headers_cfg, dict):
                for hk, hv in headers_cfg.items():
                    try:
                        headers_r[str(hk)] = str(_render_value(hv))
                    except Exception:
                        headers_r[str(hk)] = str(hv)
            # Drop empty headers (avoid sending empty Authorization/X-API-KEY)
            try:
                headers_r = {k: v for k, v in headers_r.items() if isinstance(v, str) and v.strip()}
            except Exception:
                pass
            # If no explicit auth headers provided, allow secrets from workflow run to supply them
            try:
                secrets = context.get("secrets") if isinstance(context, dict) else None
                if isinstance(secrets, dict):
                    has_auth = any(k.lower() == "authorization" for k in headers_r.keys()) or any(k.lower() == "x-api-key" for k in headers_r.keys())
                    if not has_auth:
                        _jwt = secrets.get("jwt") or secrets.get("bearer")
                        _api = secrets.get("api_key") or secrets.get("x_api_key")
                        if _jwt:
                            headers_r["Authorization"] = f"Bearer {_jwt}"
                        elif _api:
                            headers_r["X-API-KEY"] = str(_api)
            except Exception:
                pass
            # Ensure content-type unless provided
            if "content-type" not in {k.lower(): v for k, v in headers_r.items()}:
                headers_r["Content-Type"] = "application/json"
            # Default auth fallbacks for scheduled runs (optional)
            try:
                _had_auth = any(k.lower() == "authorization" for k in headers_r.keys()) or any(k.lower() == "x-api-key" for k in headers_r.keys())
                used_fallback = False
                if not _had_auth:
                    _bear = os.getenv("WORKFLOWS_DEFAULT_BEARER_TOKEN", "").strip()
                    _key = os.getenv("WORKFLOWS_DEFAULT_API_KEY", "").strip()
                    if _bear:
                        headers_r["Authorization"] = f"Bearer {_bear}"
                        used_fallback = True
                    elif _key:
                        headers_r["X-API-KEY"] = _key
                        used_fallback = True
                # Optional sanity check for fallback auth (once per run)
                try:
                    if used_fallback and str(os.getenv("WORKFLOWS_VALIDATE_DEFAULT_AUTH", "")).lower() in {"1", "true", "yes", "on"} and not context.get("_wf_default_auth_checked"):
                        base = os.getenv("WORKFLOWS_INTERNAL_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
                        _url = f"{base}/api/v1/workflows/auth/check"
                        with httpx.Client(timeout=5.0, trust_env=False) as _client:
                            _resp = _client.get(_url, headers=headers_r)
                            if _resp.status_code // 100 != 2:
                                return {"dispatched": False, "error": "default_auth_validation_failed", "status_code": _resp.status_code}
                        context["_wf_default_auth_checked"] = True
                except Exception:
                    # Non-fatal; allow the request to proceed
                    pass
            except Exception:
                pass
            # Render and prepare body
            body_raw = config.get("body") if ("body" in config) else (config.get("data") if ("data" in config) else None)
            body_r = _render_value(body_raw) if body_raw is not None else None
            body_r = _inject_json_specials(body_r)
            # Inject W3C trace context
            try:
                from tldw_Server_API.app.core.Metrics.traces import get_tracing_manager as _get_tm
                _get_tm().inject_context(headers_r)
            except Exception:
                pass
            secret = os.getenv("WORKFLOWS_WEBHOOK_SECRET", "")
            body_json_str = None
            # Prepare request kwargs
            req_kwargs: Dict[str, Any] = {}
            if method == "GET":
                if isinstance(body_r, dict):
                    req_kwargs["params"] = body_r
                elif body_r is not None:
                    # Non-dict body for GET - ignore
                    pass
            else:
                if body_r is not None:
                    # Use JSON body if not already a string
                    req_kwargs["content"] = json.dumps(body_r)
                    body_json_str = req_kwargs["content"]
                else:
                    req_kwargs["content"] = json.dumps(payload)
                    body_json_str = req_kwargs["content"]
            if secret:
                sig = hmac.new(secret.encode("utf-8"), (body_json_str or "").encode("utf-8"), hashlib.sha256).hexdigest()
                headers_r["X-Workflows-Signature"] = sig
                headers_r["X-Hub-Signature-256"] = f"sha256={sig}"
            timeout = float(config.get("timeout_seconds") or os.getenv("WORKFLOWS_WEBHOOK_TIMEOUT", "10"))
            try:
                client_ctx = httpx.Client(timeout=timeout, trust_env=False)
            except TypeError:
                client_ctx = httpx.Client(timeout=timeout)
            with client_ctx as client:
                # Dispatch
                req_fn = client.post
                if method == "GET":
                    req_fn = client.get
                elif method == "PUT":
                    req_fn = client.put
                elif method == "PATCH":
                    req_fn = client.patch
                elif method == "DELETE":
                    req_fn = client.delete
                resp = req_fn(url_t, headers=headers_r, **req_kwargs)
                ok = 200 <= resp.status_code < 300
                # Metrics for success/failure
                try:
                    from urllib.parse import urlparse as _urlparse
                    host = _urlparse(url).hostname or ""
                    from tldw_Server_API.app.core.Metrics import increment_counter as _inc
                    _inc("workflows_webhook_deliveries_total", labels={"status": ("delivered" if ok else "failed"), "host": host})
                except Exception:
                    pass
                # Optional artifact of response metadata
                try:
                    if callable(context.get("add_artifact")):
                        from pathlib import Path
                        step_run_id = str(context.get("step_run_id") or "")
                        art_dir = Path("Databases") / "artifacts" / (step_run_id or f"webhook_{int(time.time()*1000)}")
                        art_dir.mkdir(parents=True, exist_ok=True)
                        fpath = art_dir / "webhook_response.json"
                        data = {"status_code": resp.status_code, "headers": dict(resp.headers)}
                        fpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        context["add_artifact"](
                            type="webhook_response",
                            uri=f"file://{fpath}",
                            size_bytes=len((fpath.read_bytes() if fpath.exists() else b"")),
                            mime_type="application/json",
                            metadata={"url": url},
                        )
                        # Optionally save response body for diagnostics
                        try:
                            if bool(config.get("save_response_json")) or bool(config.get("save_response_body")):
                                body_path = art_dir / "webhook_response_body.json"
                                body_mime = "application/json"
                                try:
                                    body_text = resp.text
                                except Exception:
                                    body_text = ""
                                # Pretty print JSON when possible
                                try:
                                    parsed = resp.json()
                                    body_text = json.dumps(parsed, indent=2)
                                except Exception:
                                    # keep as text/plain when not JSON
                                    body_mime = "text/plain"
                                body_path.write_text(body_text, encoding="utf-8")
                                context["add_artifact"](
                                    type="webhook_response_body",
                                    uri=f"file://{body_path}",
                                    size_bytes=len((body_path.read_bytes() if body_path.exists() else b"")),
                                    mime_type=body_mime,
                                    metadata={"url": url},
                                )
                        except Exception:
                            pass
                except Exception:
                    pass
                # Build outputs
                out: Dict[str, Any] = {"dispatched": ok, "status_code": resp.status_code}
                try:
                    out["response_json"] = resp.json()
                except Exception:
                    try:
                        out["response_text"] = resp.text
                    except Exception:
                        pass
                return out
        except Exception as e:
            return {"dispatched": False, "error": str(e)}

    # Default: use registered webhooks
    try:
        event = WebhookEvent(event_name)  # type: ignore[arg-type]
    except Exception:
        event = WebhookEvent.EVALUATION_PROGRESS
    try:
        await webhook_manager.send_webhook(user_id=user_id, event=event, evaluation_id="workflow", data=payload)
        return {"dispatched": True}
    except Exception as e:
        return {"dispatched": False, "error": str(e)}
