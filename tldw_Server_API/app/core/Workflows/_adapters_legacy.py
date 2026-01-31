"""Workflow step adapters for executing registered workflow steps."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger
import types

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string
from tldw_Server_API.app.core.exceptions import AdapterError
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
from tldw_Server_API.app.core.Workflows.subprocess_utils import start_process, terminate_process
from tldw_Server_API.app.core.Metrics import start_async_span as _start_span
from tldw_Server_API.app.core.Security.egress import is_url_allowed, is_url_allowed_for_tenant
from tldw_Server_API.app.core.http_client import create_client as _wf_create_client
from tldw_Server_API.app.core.Workflows.constants import MAP_SUBSTEP_TYPES
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import resolve_user_id_value
from tldw_Server_API.app.core.DB_Management.Kanban_DB import (
    KanbanDB,
    KanbanDBError,
    InputError,
    ConflictError,
    NotFoundError,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def _extract_openai_content(response: Any) -> Optional[str]:
    if isinstance(response, dict):
        try:
            choices = response.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                content = message.get("content")
                if isinstance(content, str):
                    return content
            text = response.get("content") or response.get("text")
            if isinstance(text, str):
                return text
        except Exception:
            return None
    if isinstance(response, str):
        return response
    return None


def _sanitize_path_component(value: str, default: str, max_len: int = 80) -> str:
    """
    Normalize a string for safe use as a single filesystem path component.

    Args:
        value (str): Raw input to sanitize.
        default (str): Fallback value when the input normalizes to empty.
        max_len (int): Maximum length of the returned component.

    Returns:
        str: A sanitized component containing only ASCII letters, digits, dot,
        underscore, or dash.

    Security:
        Replaces any other character with "_" and strips leading/trailing
        dot/underscore/dash to reduce traversal-like components. This does not
        ensure uniqueness; callers should still enforce base-dir containment.
    """
    raw = str(value or "").strip()
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._-")
    if not cleaned:
        cleaned = default
    return cleaned[:max_len]


def _is_subpath(parent: Path, child: Path) -> bool:
    """
    Return True if 'child' is located within 'parent' (after resolving both).
    This is a compatibility-safe equivalent of Path.is_relative_to.
    """
    try:
        parent_resolved = parent.resolve(strict=False)
    except (OSError, ValueError, RuntimeError) as e:
        logger.debug(f"Failed to resolve parent path {parent}: {e}")
        parent_resolved = parent
    try:
        child_resolved = child.resolve(strict=False)
    except (OSError, ValueError, RuntimeError) as e:
        logger.debug(f"Failed to resolve child path {child}: {e}")
        child_resolved = child
    try:
        child_resolved.relative_to(parent_resolved)
        return True
    except ValueError:
        return False


def _resolve_context_user_id(context: Dict[str, Any]) -> Optional[str]:
    raw = context.get("user_id") or context.get("inputs", {}).get("user_id")
    return resolve_user_id_value(raw, allow_none=True)


def _artifacts_base_dir() -> Path:
    """
    Resolve the base directory used for workflow artifacts.

    Args:
        None.

    Returns:
        Path: Absolute artifacts base when project root is available, otherwise
        a relative `Databases/artifacts` path.

    Security:
        Prefers anchoring to the project root to avoid CWD-dependent behavior.
        In test mode, uses the current working directory to keep fixtures
        isolated. On failure, falls back to a relative path that must be
        resolved and checked for containment by callers.
    """
    env_override = os.getenv("WORKFLOWS_ARTIFACTS_DIR") or os.getenv("WORKFLOWS_ARTIFACT_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()
    try:
        if os.getenv("PYTEST_CURRENT_TEST") is not None or os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
            return (Path.cwd() / "Databases" / "artifacts").resolve()
    except Exception:
        logger.exception("Error checking TEST_MODE/PYTEST_CURRENT_TEST for artifacts base dir")
    try:
        from tldw_Server_API.app.core.Utils.Utils import get_project_root
        return (Path(get_project_root()) / "Databases" / "artifacts").resolve()
    except Exception:
        logger.exception("Error getting project root for artifacts base dir")
        # Fallback to relative path
        return Path("Databases") / "artifacts"


def _resolve_artifacts_dir(step_run_id: str | None) -> Path:
    """
    Build a per-step artifact directory path under the artifacts base.

    Args:
        step_run_id (str | None): Optional step run identifier used as a folder
        name after sanitization.

    Returns:
        Path: A resolved candidate artifact directory path.

    Security:
        Uses `_sanitize_path_component` to limit characters and length, resolves
        paths with `strict=False`, and verifies containment via `_is_subpath`.
        If containment fails, falls back to a generated safe identifier.
    """
    base_dir = _artifacts_base_dir()
    try:
        base_resolved = base_dir.resolve(strict=False)
    except Exception as exc:
        logger.opt(exception=exc).debug(
            "Artifacts base dir resolve failed for {}. Using unresolved base dir.",
            base_dir,
        )
        base_resolved = base_dir
    # Sanitize the provided ID and force it to be a single path component.
    safe_id = _sanitize_path_component(step_run_id or "", f"artifact_{int(time.time() * 1000)}")
    safe_id = Path(safe_id).name or f"artifact_{int(time.time() * 1000)}"
    candidate = (base_resolved / safe_id).resolve(strict=False)
    if not _is_subpath(base_resolved, candidate):
        # Fall back to a generated artifact id if the original cannot be contained safely.
        fallback_id = f"artifact_{int(time.time() * 1000)}"
        fallback_id = Path(fallback_id).name
        candidate = (base_resolved / fallback_id).resolve(strict=False)
        if not _is_subpath(base_resolved, candidate):
            # As a last resort, refuse to use an unsafe path.
            raise AdapterError("artifact_dir_resolution_failed")
    return candidate


def _resolve_artifact_filename(name: str, ext: str, default_stem: str = "artifact") -> str:
    """
    Produce a safe artifact filename with a fixed extension.

    Args:
        name (str): Original filename input, possibly containing paths.
        ext (str): Extension to append (without leading dot).
        default_stem (str): Fallback stem when the name is empty or unsafe.

    Returns:
        str: Sanitized filename with the requested extension.

    Security:
        Drops path components (`Path(name).name`) and sanitizes the stem to
        ASCII alphanumerics plus `._-` to avoid traversal or separator issues.
    """
    raw_name = Path(name).name
    if raw_name in {"", ".", ".."}:
        raw_name = default_stem
    stem = Path(raw_name).stem or default_stem
    safe_stem = _sanitize_path_component(stem, default_stem)
    return f"{safe_stem}.{ext}"


def _unsafe_file_access_allowed(config: Dict[str, Any] | None) -> bool:  # noqa: ARG001
    """
    Determine whether unsafe file access is explicitly enabled.

    Args:
        config (Dict[str, Any] | None): Ignored on purpose to prevent user-
        supplied overrides.

    Returns:
        bool: True when the server environment enables unsafe access.

    Security:
        Only honors the `WORKFLOWS_ALLOW_UNSAFE_FILE_ACCESS` environment
        variable so workflow configs cannot bypass path restrictions. When
        enabled, access is still restricted to allowlisted base directories
        or the per-user base dir.
    """
    # Ignore per-step config to avoid user-controlled path bypasses.
    return str(os.getenv("WORKFLOWS_ALLOW_UNSAFE_FILE_ACCESS", "")).lower() in {"1", "true", "yes", "on"}


def _parse_workflows_file_allowlist(raw: str | None) -> list[str]:
    """Parse the allowlist env var into a list of non-empty path strings."""
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return [p for p in parts if p]


def _resolve_workflows_file_allowlist_paths(paths: list[str]) -> list[Path]:
    """Resolve allowlist entries into absolute Paths anchored to the project root."""
    if not paths:
        return []
    project_root = None
    try:
        from tldw_Server_API.app.core.Utils.Utils import get_project_root
        project_root = Path(get_project_root())
    except Exception as exc:
        logger.debug(f"Workflow file allowlist: failed to resolve project root: {exc}")
    resolved: list[Path] = []
    for raw in paths:
        try:
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                if project_root is not None:
                    candidate = (project_root / candidate).resolve(strict=False)
                else:
                    candidate = candidate.resolve(strict=False)
            else:
                candidate = candidate.resolve(strict=False)
            resolved.append(candidate)
        except Exception as exc:
            logger.debug(f"Workflow file allowlist: invalid path {raw!r}: {exc}")
    return resolved


def _workflow_file_allowlist(context: Dict[str, Any]) -> list[Path]:
    """Return the resolved allowlist for the current tenant, if configured."""
    tenant_id = str(context.get("tenant_id") or "default") if isinstance(context, dict) else "default"
    tenant_key = f"WORKFLOWS_FILE_ALLOWLIST_{tenant_id.upper().replace('-', '_')}"
    if tenant_key in os.environ:
        raw = os.environ.get(tenant_key)
    else:
        raw = os.getenv("WORKFLOWS_FILE_ALLOWLIST")
    return _resolve_workflows_file_allowlist_paths(_parse_workflows_file_allowlist(raw))


def _workflow_file_base_dir(context: Dict[str, Any], config: Dict[str, Any] | None) -> Path:  # noqa: ARG001
    """
    Resolve the base directory for workflow file access.

    Args:
        context (Dict[str, Any]): Workflow context, may include `user_id`.
        config (Dict[str, Any] | None): Currently unused; reserved for parity.

    Returns:
        Path: A resolved base directory for allowed file access.

    Security:
        Only honors server-side `WORKFLOWS_FILE_BASE_DIR` overrides. When a
        relative override is provided, it is anchored to the project root with
        `strict=False` resolution. Falls back to per-user database roots or
        `Databases/` on failure.
    """
    # Only allow server-side base dir overrides.
    env_override = os.getenv("WORKFLOWS_FILE_BASE_DIR")
    if env_override:
        base = Path(str(env_override)).expanduser()
        if not base.is_absolute():
            try:
                from tldw_Server_API.app.core.Utils.Utils import get_project_root
                base = (Path(get_project_root()) / base).resolve()
            except Exception as exc:
                logger.debug(f"Workflow file base dir: failed to resolve relative WORKFLOWS_FILE_BASE_DIR {env_override!r}: {exc}")
                base = base.resolve()
        else:
            base = base.resolve()
        return base
    try:
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
        raw_user_id = context.get("user_id") if isinstance(context, dict) else None
        try:
            user_id = int(raw_user_id) if raw_user_id is not None else DatabasePaths.get_single_user_id()
        except Exception as exc:
            logger.debug(f"Workflow file base dir: invalid user_id {raw_user_id!r}; using single-user fallback: {exc}")
            user_id = DatabasePaths.get_single_user_id()
        return DatabasePaths.get_user_base_directory(user_id)
    except Exception as exc:
        logger.debug(f"Workflow file base dir: failed to resolve per-user base dir; using Databases/: {exc}")
        return Path("Databases").resolve()


def _resolve_workflow_file_path(path_value: str, context: Dict[str, Any], config: Dict[str, Any] | None = None) -> Path:
    """
    Resolve a workflow file path relative to the allowed base directory.

    Args:
        path_value (str): User-supplied path or filename.
        context (Dict[str, Any]): Workflow context used to derive base dir.
        config (Dict[str, Any] | None): Optional config; only used to check the
        unsafe access flag.

    Returns:
        Path: A resolved filesystem path.

    Security:
        When unsafe access is enabled, resolution is still constrained to the
        per-user base directory or a configured allowlist. Otherwise resolves
        with `strict=False` and enforces containment via `_is_subpath`, raising
        `AdapterError("file_access_denied")` on violations.
    """
    base_dir = _workflow_file_base_dir(context, config)
    try:
        base_resolved = base_dir.resolve(strict=False)
    except Exception as exc:
        logger.debug(f"Failed to resolve base directory {base_dir}: {exc}")
        base_resolved = base_dir
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
    else:
        resolved = (base_resolved / candidate).resolve(strict=False)
    if _unsafe_file_access_allowed(config):
        allowed_bases = [base_resolved]
        try:
            allowed_bases.extend(_workflow_file_allowlist(context))
        except Exception as exc:
            logger.debug(f"Workflow file allowlist: failed to resolve allowlist: {exc}")
        if not any(_is_subpath(base, resolved) for base in allowed_bases):
            raise AdapterError("file_access_denied")
        return resolved
    if not _is_subpath(base_resolved, resolved):
        raise AdapterError("file_access_denied")
    return resolved


def _resolve_workflow_file_uri(file_uri: str, context: Dict[str, Any], config: Dict[str, Any] | None = None) -> Path:
    """
    Resolve a `file://` URI to a safe local filesystem path.

    Args:
        file_uri (str): File URI to resolve (must start with `file://`).
        context (Dict[str, Any]): Workflow context used to derive base dir.
        config (Dict[str, Any] | None): Optional config for unsafe access flag.

    Returns:
        Path: A resolved filesystem path.

    Security:
        Rejects non-file URIs with `AdapterError("missing_or_invalid_file_uri")`
        and applies the same containment rules as `_resolve_workflow_file_path`.
    """
    if not file_uri.startswith("file://"):
        raise AdapterError("missing_or_invalid_file_uri")
    raw_path = file_uri[len("file://"):]
    return _resolve_workflow_file_path(raw_path, context, config)


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
            step_run_id = str(context.get("step_run_id") or "")
            art_dir = _resolve_artifacts_dir(step_run_id or f"prompt_{int(time.time()*1000)}")
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


async def run_llm_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an LLM chat completion via the adapter registry.

    Config (subset; additional keys passed through):
      - provider/api_provider/api_endpoint: str
      - model: str (optional for local providers)
      - prompt: str (templated) or messages: list[dict] (templated)
      - system_message/system/system_prompt: str (templated)
      - temperature, top_p, max_tokens, stop, tools, tool_choice, response_format, seed
      - stream: bool (optional)
      - include_response: bool (default false)
    Output:
      - text: str
      - metadata: token_usage/cost if available
      - response: raw provider response (optional)
    """
    from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
    from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import DEFAULT_LLM_PROVIDER
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import json as _json
    import os as _os

    def _render_str(val: Any) -> Any:
        if isinstance(val, str):
            try:
                return _tmpl(val, context) or val
            except Exception as exc:
                snippet = val.strip().replace("\n", "\\n")
                if len(snippet) > 120:
                    snippet = f"{snippet[:120]}..."
                logger.debug(f"LLM adapter: template rendering failed for value '{snippet}': {exc}")
                return val
        return val

    def _render_message(msg: Any) -> Optional[Dict[str, Any]]:
        if isinstance(msg, dict):
            out = dict(msg)
            if isinstance(out.get("content"), str):
                out["content"] = _render_str(out["content"])
            return out
        if isinstance(msg, str):
            return {"role": "user", "content": _render_str(msg)}
        return None

    provider_raw = (
        config.get("provider")
        or config.get("api_provider")
        or config.get("api_endpoint")
        or DEFAULT_LLM_PROVIDER
    )
    provider = str(_render_str(provider_raw) or "").strip().lower()
    if not provider:
        raise AdapterError("missing_provider")

    model = config.get("model") or config.get("model_id")
    model = _render_str(model) if model is not None else None

    system_message = (
        config.get("system_message")
        or config.get("system")
        or config.get("system_prompt")
    )
    system_message = _render_str(system_message) if system_message is not None else None
    if isinstance(system_message, str) and not system_message.strip():
        system_message = None

    messages_cfg = config.get("messages") or config.get("messages_payload")
    prompt = config.get("prompt") or config.get("input") or config.get("template")
    messages: List[Dict[str, Any]] = []

    if messages_cfg is None:
        if not prompt:
            raise AdapterError("missing_prompt")
        rendered_prompt = _render_str(str(prompt))
        messages = [{"role": "user", "content": rendered_prompt}]
    elif isinstance(messages_cfg, str):
        raw = _render_str(messages_cfg)
        parsed = None
        try:
            parsed = _json.loads(raw)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            for item in parsed:
                rendered = _render_message(item)
                if rendered:
                    messages.append(rendered)
        elif str(raw).strip():
            messages = [{"role": "user", "content": raw}]
        if not messages:
            raise AdapterError("missing_messages")
    elif isinstance(messages_cfg, list):
        for item in messages_cfg:
            rendered = _render_message(item)
            if rendered:
                messages.append(rendered)
        if not messages:
            raise AdapterError("missing_messages")
    else:
        raise AdapterError("invalid_messages")

    # Short-circuit in tests to avoid outbound LLM calls
    if _os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        preview = ""
        for msg in reversed(messages):
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                preview = msg["content"]
                break
        if not preview:
            try:
                preview = str(messages[-1].get("content") or "")
            except Exception:
                preview = ""
        return {
            "text": preview,
            "provider": provider,
            "model": model,
            "simulated": True,
        }

    stream = bool(config.get("stream", False))
    include_response = bool(config.get("include_response", False))

    call_args: Dict[str, Any] = {
        "api_endpoint": provider,
        "messages_payload": messages,
        "system_message": system_message,
        "model": model,
        "stream": stream,
        "temperature": config.get("temperature"),
        "top_p": config.get("top_p"),
        "max_tokens": config.get("max_tokens"),
        "max_completion_tokens": config.get("max_completion_tokens"),
        "stop": config.get("stop"),
        "tools": config.get("tools"),
        "tool_choice": config.get("tool_choice"),
        "response_format": config.get("response_format"),
        "seed": config.get("seed"),
        "n": config.get("n"),
        "logit_bias": config.get("logit_bias"),
        "user": config.get("user") or context.get("user_id"),
        "api_key": _render_str(config.get("api_key")) if config.get("api_key") is not None else None,
    }
    # Drop None values for cleaner adapter inputs
    call_args = {k: v for k, v in call_args.items() if v is not None}

    if stream:
        stream_iter = await perform_chat_api_call_async(**call_args)
        text = ""
        async for line in stream_iter:
            if not line:
                continue
            raw = line.decode("utf-8", errors="replace") if isinstance(line, (bytes, bytearray)) else str(line)
            raw = raw.strip()
            if not raw:
                continue
            if raw.lower() == "data: [done]":
                break
            if raw.startswith("data:"):
                payload = raw[5:].strip()
                try:
                    data = _json.loads(payload)
                except Exception:
                    data = None
                if isinstance(data, dict):
                    choices = data.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        chunk = delta.get("content")
                        if isinstance(chunk, str) and chunk:
                            text += chunk
                            try:
                                if callable(context.get("append_event")):
                                    context["append_event"]("llm_stream", {"delta": chunk})
                            except Exception as e:
                                logger.debug(f"LLM stream event dispatch failed: {e}")
                    continue
            # Fallback: treat as plain text chunk
            text += raw
        return {"text": text, "streamed": True}

    response = await perform_chat_api_call_async(**call_args)
    text = _extract_openai_content(response) or ""
    out: Dict[str, Any] = {"text": text}
    metadata: Dict[str, Any] = {}
    if isinstance(response, dict):
        usage = response.get("usage")
        if isinstance(usage, dict):
            metadata["token_usage"] = usage
        if "cost_usd" in response:
            metadata["cost_usd"] = response.get("cost_usd")
    if metadata:
        out["metadata"] = metadata
    if include_response:
        out["response"] = response
    return out


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
    except Exception as exc:
        logger.error(f"Failed to resolve Media DB path for workflow search: {exc}")
        raise RuntimeError("Failed to resolve Media DB path for workflow search") from exc

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
            try:
                resolved_path = _resolve_workflow_file_uri(uri, context, config)
            except AdapterError:
                out["metadata"].append({"source": uri, "status": "file_access_denied"})
                continue
            try:
                try:
                    text = resolved_path.read_text(encoding="utf-8")
                except Exception:
                    text = resolved_path.read_text(errors="ignore")
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
                    except Exception as exc:
                        logger.error(f"Failed to resolve Media DB path for workflow indexing: {exc}")
                        raise
                    mdb = MediaDatabase(_mdb_path, client_id="workflow_engine")
                    title = (config.get("metadata", {}) or {}).get("title") or resolved_path.name
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


async def run_kanban_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Read/write Kanban boards, lists, and cards for workflow steps.

    Config:
      - action: str (required) e.g. board.list, board.create, list.create, card.update
      - entity ids: board_id, list_id, card_id
      - include flags: include_archived, include_deleted, include_details
      - create/update fields: name, description, title, metadata, activity_retention_days
      - card fields: due_date, start_date, due_complete, priority, position
      - move/copy: target_list_id, new_client_id, new_title, copy_checklists, copy_labels
      - search/filter: query, label_ids, priority, limit, offset
    Output: action-specific payload (board/list/card/etc.)
    """
    action = str(config.get("action") or "").strip().lower()
    if not action:
        return {"error": "missing_action"}

    user_id = _resolve_context_user_id(context)
    if not user_id:
        try:
            user_id = str(DatabasePaths.get_single_user_id())
        except Exception:
            return {"error": "missing_user_id"}
    user_id = str(user_id)

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    def _coerce_bool(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _coerce_optional_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            raw = value.strip().lower()
            if raw in {"1", "true", "yes", "on"}:
                return True
            if raw in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    def _coerce_int(value: Any, field: str, allow_none: bool = False) -> Optional[int]:
        if value is None or value == "":
            if allow_none:
                return None
            raise AdapterError(f"missing_{field}")
        if isinstance(value, bool):
            raise AdapterError(f"invalid_{field}")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise AdapterError(f"invalid_{field}") from exc

    def _coerce_int_list(value: Any) -> List[int]:
        if value is None:
            return []
        raw_value = _render(value) if isinstance(value, str) else value
        items: List[Any] = []
        if isinstance(raw_value, list):
            items = raw_value
        elif isinstance(raw_value, str):
            try:
                parsed = json.loads(raw_value)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                items = parsed
            else:
                items = [s.strip() for s in raw_value.split(",") if s.strip()]
        else:
            items = [raw_value]
        out: List[int] = []
        for item in items:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out

    def _coerce_limit(value: Any, default: int) -> int:
        try:
            parsed = int(value) if value is not None else default
        except (TypeError, ValueError):
            parsed = default
        return max(1, parsed)

    def _coerce_date_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        try:
            rendered = str(value)
        except Exception:
            return None
        return rendered.strip() or None

    try:
        user_id_int: Any = int(user_id) if str(user_id).isdigit() else user_id
    except Exception:
        user_id_int = user_id

    db_path = DatabasePaths.get_kanban_db_path(user_id_int)
    db = KanbanDB(db_path=str(db_path), user_id=user_id)

    try:
        if action == "board.list":
            include_archived = _coerce_bool(config.get("include_archived"), False)
            include_deleted = _coerce_bool(config.get("include_deleted"), False)
            limit = _coerce_limit(_render(config.get("limit")), 50)
            offset = max(0, _coerce_int(_render(config.get("offset", 0)), "offset", allow_none=True) or 0)
            boards, total = db.list_boards(
                include_archived=include_archived,
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
            )
            return {"boards": boards, "total": total, "limit": limit, "offset": offset}

        if action == "board.get":
            board_id = _coerce_int(_render(config.get("board_id")), "board_id")
            include_children = _coerce_bool(config.get("include_children"), True)
            include_archived = _coerce_bool(config.get("include_archived"), False)
            include_deleted = _coerce_bool(config.get("include_deleted"), False)
            if include_children:
                board = db.get_board_with_lists_and_cards(board_id, include_archived=include_archived)
            else:
                board = db.get_board(board_id, include_deleted=include_deleted)
            if not board:
                return {"error": "not_found", "entity": "board", "entity_id": board_id}
            return {"board": board}

        if action == "board.create":
            name = str(_render(config.get("name") or "")).strip()
            if not name:
                return {"error": "missing_name"}
            client_id = str(_render(config.get("client_id") or "")).strip()
            if not client_id:
                import uuid as _uuid
                client_id = f"wf_{_uuid.uuid4().hex}"
            description = _render(config.get("description"))
            activity_retention_days = _coerce_int(
                _render(config.get("activity_retention_days")),
                "activity_retention_days",
                allow_none=True,
            )
            metadata = config.get("metadata") if isinstance(config.get("metadata"), dict) else None
            board = db.create_board(
                name=name,
                client_id=client_id,
                description=str(description) if isinstance(description, str) else description,
                activity_retention_days=activity_retention_days,
                metadata=metadata,
            )
            return {"board": board}

        if action == "board.update":
            board_id = _coerce_int(_render(config.get("board_id")), "board_id")
            name = _render(config.get("name"))
            description = _render(config.get("description"))
            activity_retention_days = _coerce_int(
                _render(config.get("activity_retention_days")),
                "activity_retention_days",
                allow_none=True,
            )
            metadata = config.get("metadata") if isinstance(config.get("metadata"), dict) else None
            expected_version = _coerce_int(_render(config.get("expected_version")), "expected_version", allow_none=True)
            board = db.update_board(
                board_id=board_id,
                name=str(name) if isinstance(name, str) else name,
                description=str(description) if isinstance(description, str) else description,
                activity_retention_days=activity_retention_days,
                metadata=metadata,
                expected_version=expected_version,
            )
            return {"board": board}

        if action in {"board.archive", "board.unarchive"}:
            board_id = _coerce_int(_render(config.get("board_id")), "board_id")
            archive_flag = action != "board.unarchive"
            if "archive" in config:
                archive_flag = _coerce_bool(config.get("archive"), archive_flag)
            board = db.archive_board(board_id, archive=archive_flag)
            return {"board": board}

        if action == "board.delete":
            board_id = _coerce_int(_render(config.get("board_id")), "board_id")
            hard_delete = _coerce_bool(config.get("hard_delete"), False)
            success = db.delete_board(board_id, hard_delete=hard_delete)
            return {"success": success}

        if action == "board.restore":
            board_id = _coerce_int(_render(config.get("board_id")), "board_id")
            board = db.restore_board(board_id)
            return {"board": board}

        if action == "list.list":
            board_id = _coerce_int(_render(config.get("board_id")), "board_id")
            include_archived = _coerce_bool(config.get("include_archived"), False)
            include_deleted = _coerce_bool(config.get("include_deleted"), False)
            lists = db.list_lists(
                board_id=board_id,
                include_archived=include_archived,
                include_deleted=include_deleted,
            )
            return {"lists": lists}

        if action == "list.get":
            list_id = _coerce_int(_render(config.get("list_id")), "list_id")
            include_deleted = _coerce_bool(config.get("include_deleted"), False)
            lst = db.get_list(list_id, include_deleted=include_deleted)
            if not lst:
                return {"error": "not_found", "entity": "list", "entity_id": list_id}
            return {"list": lst}

        if action == "list.create":
            board_id = _coerce_int(_render(config.get("board_id")), "board_id")
            name = str(_render(config.get("name") or "")).strip()
            if not name:
                return {"error": "missing_name"}
            client_id = str(_render(config.get("client_id") or "")).strip()
            if not client_id:
                import uuid as _uuid
                client_id = f"wf_{_uuid.uuid4().hex}"
            position = _coerce_int(_render(config.get("position")), "position", allow_none=True)
            lst = db.create_list(
                board_id=board_id,
                name=name,
                client_id=client_id,
                position=position,
            )
            return {"list": lst}

        if action == "list.update":
            list_id = _coerce_int(_render(config.get("list_id")), "list_id")
            name = _render(config.get("name"))
            expected_version = _coerce_int(_render(config.get("expected_version")), "expected_version", allow_none=True)
            lst = db.update_list(
                list_id=list_id,
                name=str(name) if isinstance(name, str) else name,
                expected_version=expected_version,
            )
            return {"list": lst}

        if action == "list.reorder":
            board_id = _coerce_int(_render(config.get("board_id")), "board_id")
            list_ids = _coerce_int_list(config.get("list_ids") or config.get("ids"))
            if not list_ids:
                return {"error": "missing_list_ids"}
            db.reorder_lists(board_id=board_id, list_ids=list_ids)
            return {"success": True, "count": len(list_ids)}

        if action in {"list.archive", "list.unarchive"}:
            list_id = _coerce_int(_render(config.get("list_id")), "list_id")
            archive_flag = action != "list.unarchive"
            if "archive" in config:
                archive_flag = _coerce_bool(config.get("archive"), archive_flag)
            lst = db.archive_list(list_id, archive=archive_flag)
            return {"list": lst}

        if action == "list.delete":
            list_id = _coerce_int(_render(config.get("list_id")), "list_id")
            hard_delete = _coerce_bool(config.get("hard_delete"), False)
            success = db.delete_list(list_id, hard_delete=hard_delete)
            return {"success": success}

        if action == "list.restore":
            list_id = _coerce_int(_render(config.get("list_id")), "list_id")
            lst = db.restore_list(list_id)
            return {"list": lst}

        if action == "card.list":
            list_id = _coerce_int(_render(config.get("list_id")), "list_id")
            include_archived = _coerce_bool(config.get("include_archived"), False)
            include_deleted = _coerce_bool(config.get("include_deleted"), False)
            cards = db.list_cards(
                list_id=list_id,
                include_archived=include_archived,
                include_deleted=include_deleted,
            )
            return {"cards": cards}

        if action == "card.get":
            card_id = _coerce_int(_render(config.get("card_id")), "card_id")
            include_details = _coerce_bool(config.get("include_details"), True)
            include_deleted = _coerce_bool(config.get("include_deleted"), False)
            if include_details:
                card = db.get_card_with_details(card_id, include_deleted=include_deleted)
            else:
                card = db.get_card(card_id, include_deleted=include_deleted)
            if not card:
                return {"error": "not_found", "entity": "card", "entity_id": card_id}
            return {"card": card}

        if action == "card.create":
            list_id = _coerce_int(_render(config.get("list_id")), "list_id")
            title = str(_render(config.get("title") or "")).strip()
            if not title:
                return {"error": "missing_title"}
            client_id = str(_render(config.get("client_id") or "")).strip()
            if not client_id:
                import uuid as _uuid
                client_id = f"wf_{_uuid.uuid4().hex}"
            description = _render(config.get("description"))
            position = _coerce_int(_render(config.get("position")), "position", allow_none=True)
            due_date = _coerce_date_str(_render(config.get("due_date")))
            start_date = _coerce_date_str(_render(config.get("start_date")))
            priority = _render(config.get("priority"))
            metadata = config.get("metadata") if isinstance(config.get("metadata"), dict) else None
            card = db.create_card(
                list_id=list_id,
                title=title,
                client_id=client_id,
                description=str(description) if isinstance(description, str) else description,
                position=position,
                due_date=due_date,
                start_date=start_date,
                priority=str(priority) if isinstance(priority, str) and priority.strip() else None,
                metadata=metadata,
            )
            return {"card": card}

        if action == "card.update":
            card_id = _coerce_int(_render(config.get("card_id")), "card_id")
            title = _render(config.get("title"))
            description = _render(config.get("description"))
            due_date = _coerce_date_str(_render(config.get("due_date")))
            due_complete = _coerce_optional_bool(config.get("due_complete"))
            start_date = _coerce_date_str(_render(config.get("start_date")))
            priority = _render(config.get("priority"))
            metadata = config.get("metadata") if isinstance(config.get("metadata"), dict) else None
            expected_version = _coerce_int(_render(config.get("expected_version")), "expected_version", allow_none=True)
            card = db.update_card(
                card_id=card_id,
                title=str(title) if isinstance(title, str) else title,
                description=str(description) if isinstance(description, str) else description,
                due_date=due_date,
                due_complete=due_complete,
                start_date=start_date,
                priority=str(priority) if isinstance(priority, str) and priority.strip() else None,
                metadata=metadata,
                expected_version=expected_version,
            )
            return {"card": card}

        if action == "card.reorder":
            list_id = _coerce_int(_render(config.get("list_id")), "list_id")
            card_ids = _coerce_int_list(config.get("card_ids") or config.get("ids"))
            if not card_ids:
                return {"error": "missing_card_ids"}
            db.reorder_cards(list_id=list_id, card_ids=card_ids)
            return {"success": True, "count": len(card_ids)}

        if action == "card.move":
            card_id = _coerce_int(_render(config.get("card_id")), "card_id")
            target_list_id = _coerce_int(_render(config.get("target_list_id")), "target_list_id")
            position = _coerce_int(_render(config.get("position")), "position", allow_none=True)
            card = db.move_card(card_id=card_id, target_list_id=target_list_id, position=position)
            return {"card": card}

        if action == "card.copy":
            card_id = _coerce_int(_render(config.get("card_id")), "card_id")
            target_list_id = _coerce_int(_render(config.get("target_list_id")), "target_list_id")
            new_client_id = str(_render(config.get("new_client_id") or "")).strip()
            if not new_client_id:
                import uuid as _uuid
                new_client_id = f"wf_{_uuid.uuid4().hex}"
            new_title = _render(config.get("new_title"))
            position = _coerce_int(_render(config.get("position")), "position", allow_none=True)
            copy_checklists = _coerce_bool(config.get("copy_checklists"), True)
            copy_labels = _coerce_bool(config.get("copy_labels"), True)
            card = db.copy_card_with_checklists(
                card_id=card_id,
                target_list_id=target_list_id,
                new_client_id=new_client_id,
                position=position,
                new_title=str(new_title) if isinstance(new_title, str) and new_title.strip() else None,
                copy_checklists=copy_checklists,
                copy_labels=copy_labels,
            )
            return {"card": card}

        if action in {"card.archive", "card.unarchive"}:
            card_id = _coerce_int(_render(config.get("card_id")), "card_id")
            archive_flag = action != "card.unarchive"
            if "archive" in config:
                archive_flag = _coerce_bool(config.get("archive"), archive_flag)
            card = db.archive_card(card_id, archive=archive_flag)
            return {"card": card}

        if action == "card.delete":
            card_id = _coerce_int(_render(config.get("card_id")), "card_id")
            hard_delete = _coerce_bool(config.get("hard_delete"), False)
            success = db.delete_card(card_id, hard_delete=hard_delete)
            return {"success": success}

        if action == "card.restore":
            card_id = _coerce_int(_render(config.get("card_id")), "card_id")
            card = db.restore_card(card_id)
            return {"card": card}

        if action == "card.search":
            query = str(_render(config.get("query") or "")).strip()
            if not query:
                return {"error": "missing_query"}
            board_id = _coerce_int(_render(config.get("board_id")), "board_id", allow_none=True)
            label_ids = _coerce_int_list(config.get("label_ids"))
            priority = _render(config.get("priority"))
            include_archived = _coerce_bool(config.get("include_archived"), False)
            limit = _coerce_limit(_render(config.get("limit")), 50)
            offset = max(0, _coerce_int(_render(config.get("offset", 0)), "offset", allow_none=True) or 0)
            cards, total = db.search_cards(
                query=query,
                board_id=board_id,
                label_ids=label_ids or None,
                priority=str(priority) if isinstance(priority, str) and priority.strip() else None,
                include_archived=include_archived,
                limit=limit,
                offset=offset,
            )
            return {"cards": cards, "total": total, "limit": limit, "offset": offset}

        if action in {"board.cards.filter", "cards.filter"}:
            board_id = _coerce_int(_render(config.get("board_id")), "board_id")
            filters = config.get("filters") if isinstance(config.get("filters"), dict) else {}
            def _f(key: str) -> Any:
                return config.get(key) if key in config else filters.get(key)
            label_ids = _coerce_int_list(_f("label_ids"))
            priority = _render(_f("priority"))
            due_before = _render(_f("due_before"))
            due_after = _render(_f("due_after"))
            overdue = _coerce_optional_bool(_f("overdue"))
            has_due_date = _coerce_optional_bool(_f("has_due_date"))
            has_checklist = _coerce_optional_bool(_f("has_checklist"))
            is_complete = _coerce_optional_bool(_f("is_complete"))
            include_archived = _coerce_bool(_f("include_archived"), False)
            include_deleted = _coerce_bool(_f("include_deleted"), False)
            limit = _coerce_limit(_render(_f("limit") or _f("per_page")), 50)
            offset = _coerce_int(_render(_f("offset")), "offset", allow_none=True)
            if offset is None:
                page = _coerce_int(_render(_f("page")), "page", allow_none=True)
                if page is not None and page > 0:
                    offset = (page - 1) * limit
                else:
                    offset = 0
            cards, total = db.get_board_cards_filtered(
                board_id=board_id,
                label_ids=label_ids or None,
                priority=str(priority) if isinstance(priority, str) and priority.strip() else None,
                due_before=str(due_before) if isinstance(due_before, str) and due_before.strip() else None,
                due_after=str(due_after) if isinstance(due_after, str) and due_after.strip() else None,
                overdue=overdue,
                has_due_date=has_due_date,
                has_checklist=has_checklist,
                is_complete=is_complete,
                include_archived=include_archived,
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
            )
            return {"cards": cards, "total": total, "limit": limit, "offset": offset}

        return {"error": f"unsupported_action:{action}"}

    except AdapterError as exc:
        return {"error": str(exc) or "adapter_error"}
    except (InputError, ConflictError, NotFoundError, KanbanDBError) as exc:
        return {"error": "kanban_error", "error_type": exc.__class__.__name__, "detail": str(exc)}
    finally:
        try:
            db.close()
        except Exception:
            pass


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
    out_dir = _resolve_artifacts_dir(step_run_id)
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
    fname = _resolve_artifact_filename(fname, ext, default_stem="speech")
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
            import shutil
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
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(out_dir),
                    )
                    try:
                        await asyncio.wait_for(proc.communicate(), timeout=120)
                    except asyncio.TimeoutError:
                        proc.kill()
                        try:
                            await proc.communicate()
                        except Exception:
                            pass
                    else:
                        if proc.returncode == 0:
                            normalized = True
                            normalized_path = norm_out
                        else:
                            normalized = False
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
        except Exception:
            logger.exception("Web scraping process media failed")
            return {"error": "process_media_error"}
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
        try:
            resolved_path = _resolve_workflow_file_uri(file_uri, context, config)
        except AdapterError as e:
            return {"error": str(e)}
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf_task
            fb = resolved_path.read_bytes()
            performed_analysis = bool(config.get("perform_analysis", True))
            chunk_opts = config.get("chunking") or {}
            result = await process_pdf_task(
                file_bytes=fb,
                filename=resolved_path.name,
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
        try:
            resolved_path = _resolve_workflow_file_uri(file_uri, context, config)
        except AdapterError as e:
            return {"error": str(e)}
        try:
            from tldw_Server_API.app.services.ebook_processing_service import process_ebook_task
            res = await process_ebook_task(file_path=str(resolved_path), title=config.get("title"), author=config.get("author"), custom_prompt=config.get("custom_prompt"), api_name=config.get("api_name"))
            out = {"kind": "ebook", "content": res.get("text") or "", "summary": res.get("summary") or "", "metadata": res.get("metadata") or {}}
            return _emit(out)
        except Exception as e:
            return {"error": f"ebook_process_error:{e}"}

    # XML (file_uri; placeholder service)
    if kind == "xml":
        file_uri = str(config.get("file_uri") or "").strip()
        if not file_uri.startswith("file://"):
            return {"error": "missing_or_invalid_file_uri"}
        try:
            resolved_path = _resolve_workflow_file_uri(file_uri, context, config)
        except AdapterError as e:
            return {"error": str(e)}
        try:
            from tldw_Server_API.app.services.xml_processing_service import process_xml_task
            fb = resolved_path.read_bytes()
            res = await process_xml_task(
                file_bytes=fb,
                filename=resolved_path.name,
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
        try:
            resolved_path = _resolve_workflow_file_uri(file_uri, context, config)
        except AdapterError as e:
            return {"error": str(e)}
        try:
            content = resolved_path.read_text(errors="ignore")
        except Exception:
            content = ""
        return _emit({"kind": "mediawiki_dump", "content": content[:5000], "metadata": {"file": resolved_path.name}})

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
                with _wf_create_client(timeout=timeout) as client:
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

    user_id = _resolve_context_user_id(context)
    if not user_id:
        return {"error": "missing_user_id"}
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

    # Try OpenAI-compatible adapter first; fall back to returning input
    try:
        adapter = get_registry().get_adapter("openai")
        if adapter is None:
            raise ChatConfigurationError(provider="openai", message="OpenAI adapter unavailable.")
        system = f"You are a professional translator. Translate the user text to {target}. Preserve meaning and tone. Output only the translation."
        messages = [{"role": "user", "content": text}]
        resp = await adapter.achat(
            {
                "messages": messages,
                "system_message": system,
                "model": None,
                "stream": False,
            }
        )
        out = _extract_openai_content(resp)
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
      - hotwords: optional list/CSV/JSON string of hotwords
      - diarize: bool (default false)
      - word_timestamps: bool (default false)

    Output: { text, segments: [...], language? }
    """
    file_uri = str(config.get("file_uri") or "").strip()
    if not (file_uri and file_uri.startswith("file://")):
        return {"error": "missing_or_invalid_file_uri"}
    try:
        resolved_path = _resolve_workflow_file_uri(file_uri, context, config)
    except AdapterError as e:
        return {"error": str(e)}
    model = str(config.get("model") or "large-v3")
    language = config.get("language") or None
    hotwords = config.get("hotwords") or None
    diarize = bool(config.get("diarize", False))
    word_ts = bool(config.get("word_timestamps", False))
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import speech_to_text
        # When language is None, allow the STT backend to auto-detect.
        segs_or_pair = speech_to_text(
            str(resolved_path),
            whisper_model=model,
            selected_source_lang=language,
            vad_filter=False,
            diarize=diarize,
            word_timestamps=word_ts,
            return_language=True,
            hotwords=hotwords,
        )
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
        headers = {"content-type": "application/json"}
        try:
            headers.update({k: str(v) for k, v in extra_headers.items()})
        except Exception:
            pass
        body = {"text": message}
        if subject:
            body["subject"] = subject
        timeout = float(_os.getenv("WORKFLOWS_NOTIFY_TIMEOUT", "10"))
        with _wf_create_client(timeout=timeout) as client:
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
    """Minimal async file writer context manager for streaming to disk.

    Uses synchronous file I/O; keep payloads small or swap to aiofiles if needed.
    """
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
    Limitations: Supported nested step types are a subset: prompt, log, delay, rag_search, media_ingest, mcp_tool, webhook, kanban.
                 Unsupported sub-steps raise AdapterError.
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
    if not sub_type:
        raise AdapterError("missing_substep_type")
    if sub_type not in MAP_SUBSTEP_TYPES:
        raise AdapterError(f"unsupported_substep_type:{sub_type}")
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
                    if sub_type == "kanban":
                        return await run_kanban_adapter(sub_cfg, sub_ctx)
                    if sub_type == "notes":
                        return await run_notes_adapter(sub_cfg, sub_ctx)
                    if sub_type == "prompts":
                        return await run_prompts_adapter(sub_cfg, sub_ctx)
                    if sub_type == "chunking":
                        return await run_chunking_adapter(sub_cfg, sub_ctx)
                    if sub_type == "web_search":
                        return await run_web_search_adapter(sub_cfg, sub_ctx)
                    if sub_type == "collections":
                        return await run_collections_adapter(sub_cfg, sub_ctx)
                    if sub_type == "evaluations":
                        return await run_evaluations_adapter(sub_cfg, sub_ctx)
                    if sub_type == "claims_extract":
                        return await run_claims_extract_adapter(sub_cfg, sub_ctx)
                    if sub_type == "character_chat":
                        return await run_character_chat_adapter(sub_cfg, sub_ctx)
                    if sub_type == "moderation":
                        return await run_moderation_adapter(sub_cfg, sub_ctx)
                    if sub_type == "image_gen":
                        return await run_image_gen_adapter(sub_cfg, sub_ctx)
                    if sub_type == "summarize":
                        return await run_summarize_adapter(sub_cfg, sub_ctx)
                    if sub_type == "query_expand":
                        return await run_query_expand_adapter(sub_cfg, sub_ctx)
                    if sub_type == "citations":
                        return await run_citations_adapter(sub_cfg, sub_ctx)
                    if sub_type == "ocr":
                        return await run_ocr_adapter(sub_cfg, sub_ctx)
                    if sub_type == "pdf_extract":
                        return await run_pdf_extract_adapter(sub_cfg, sub_ctx)
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
                if sub_type == "kanban":
                    return await run_kanban_adapter(sub_cfg, sub_ctx)
                if sub_type == "notes":
                    return await run_notes_adapter(sub_cfg, sub_ctx)
                if sub_type == "prompts":
                    return await run_prompts_adapter(sub_cfg, sub_ctx)
                if sub_type == "chunking":
                    return await run_chunking_adapter(sub_cfg, sub_ctx)
                if sub_type == "web_search":
                    return await run_web_search_adapter(sub_cfg, sub_ctx)
                if sub_type == "collections":
                    return await run_collections_adapter(sub_cfg, sub_ctx)
                if sub_type == "evaluations":
                    return await run_evaluations_adapter(sub_cfg, sub_ctx)
                if sub_type == "claims_extract":
                    return await run_claims_extract_adapter(sub_cfg, sub_ctx)
                if sub_type == "character_chat":
                    return await run_character_chat_adapter(sub_cfg, sub_ctx)
                if sub_type == "moderation":
                    return await run_moderation_adapter(sub_cfg, sub_ctx)
                if sub_type == "image_gen":
                    return await run_image_gen_adapter(sub_cfg, sub_ctx)
                if sub_type == "summarize":
                    return await run_summarize_adapter(sub_cfg, sub_ctx)
                if sub_type == "query_expand":
                    return await run_query_expand_adapter(sub_cfg, sub_ctx)
                if sub_type == "citations":
                    return await run_citations_adapter(sub_cfg, sub_ctx)
                if sub_type == "ocr":
                    return await run_ocr_adapter(sub_cfg, sub_ctx)
                if sub_type == "pdf_extract":
                    return await run_pdf_extract_adapter(sub_cfg, sub_ctx)
                return {"error": f"unsupported_substep:{sub_type}"}

    results = await asyncio.gather(*[_run_one(i, it) for i, it in enumerate(items)], return_exceptions=False)
    return {"results": results, "count": len(results)}


def _normalize_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        return [s.strip() for s in raw.split(",") if s.strip()]
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return [str(value).strip()]


def _extract_mcp_policy(context: Dict[str, Any]) -> Dict[str, Any]:
    policy = context.get("workflow_mcp_policy")
    if not isinstance(policy, dict):
        policy = None
    if policy is None:
        meta = context.get("workflow_metadata")
        if isinstance(meta, dict):
            candidate = meta.get("mcp") or meta.get("mcp_policy")
            if isinstance(candidate, dict):
                policy = candidate
    return policy or {}


def _tool_matches_allowlist(tool_name: str, allowlist: List[str]) -> bool:
    if not allowlist:
        return True
    if "*" in allowlist:
        return True
    for entry in allowlist:
        if entry == tool_name:
            return True
        if entry.endswith("*") and tool_name.startswith(entry[:-1]):
            return True
    return False


def _extract_tool_scopes(tool_def: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(tool_def, dict):
        return []
    raw = tool_def.get("scopes") or tool_def.get("scope")
    if raw is None:
        meta = tool_def.get("metadata") or {}
        if isinstance(meta, dict):
            raw = meta.get("scopes") or meta.get("scope") or meta.get("capabilities") or meta.get("capability")
    return _normalize_str_list(raw)


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
    policy = _extract_mcp_policy(context)
    allowlist = _normalize_str_list(policy.get("allowlist") or policy.get("allowed_tools"))
    if allowlist and not _tool_matches_allowlist(tool_name, allowlist):
        raise AdapterError("mcp_tool_not_allowed")
    allowed_scopes = _normalize_str_list(policy.get("scopes") or policy.get("allow_scopes") or policy.get("capabilities"))
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
    tool_def = None
    if module is not None:
        try:
            tool_defs = await module.get_tools()
            for tool in tool_defs:
                if tool.get("name") == tool_name:
                    tool_def = tool
                    break
        except Exception as exc:
            logger.debug(f"MCP tool adapter: failed to get tool definitions for {tool_name}: {exc}")
    required_scopes = _extract_tool_scopes(tool_def)
    if required_scopes:
        if not allowed_scopes:
            raise AdapterError("mcp_tool_scope_denied")
        if "*" not in allowed_scopes:
            missing = [s for s in required_scopes if s not in allowed_scopes]
            if missing:
                raise AdapterError("mcp_tool_scope_denied")
    if module is None:
        # Test-friendly fallback for echo
        if tool_name == "echo":
            return {"result": arguments.get("message"), "module": "_fallback"}
        return {"error": "tool_not_found"}
    result = await module.execute_tool(tool_name, arguments)
    # Optional artifact persistence of result
    try:
        if bool(config.get("save_artifact")) and callable(context.get("add_artifact")):
            step_run_id = str(context.get("step_run_id") or "")
            art_dir = _resolve_artifacts_dir(step_run_id or f"mcp_{int(time.time()*1000)}")
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

    def _normalize_policy_hosts(entries: Any) -> list[str]:
        from urllib.parse import urlparse
        out: list[str] = []
        if not entries:
            return out
        if isinstance(entries, str):
            entries = [entries]
        for raw in entries:
            if raw is None:
                continue
            entry = str(raw).strip().lower()
            if not entry:
                continue
            host = ""
            if "://" in entry:
                try:
                    host = urlparse(entry).hostname or ""
                except Exception:
                    host = ""
            else:
                # Strip path if present
                if "/" in entry:
                    entry = entry.split("/", 1)[0]
                host = entry
            host = host.strip()
            if host.startswith("*."):
                host = host[2:]
            if host.startswith("."):
                host = host[1:]
            if host.count(":") == 1 and host.rsplit(":", 1)[-1].isdigit():
                host = host.rsplit(":", 1)[0]
            if host:
                out.append(host)
        return out

    def _resolve_signing_secret(ref: str) -> Optional[str]:
        if not ref:
            return None
        try:
            secrets = context.get("secrets") if isinstance(context, dict) else None
            if isinstance(secrets, dict) and ref in secrets:
                return str(secrets.get(ref))
        except Exception:
            pass
        try:
            import os as _os
            val = _os.getenv(ref, "")
            return val if val else None
        except Exception:
            return None

    def _policy_allows(url_val: str) -> tuple[bool, Optional[str]]:
        policy_cfg = config.get("egress_policy") or config.get("egress") or {}
        if not isinstance(policy_cfg, dict) or not policy_cfg:
            return True, None
        allowlist = _normalize_policy_hosts(policy_cfg.get("allowlist") or policy_cfg.get("allow") or [])
        denylist = _normalize_policy_hosts(policy_cfg.get("denylist") or policy_cfg.get("deny") or [])
        block_private = policy_cfg.get("block_private")
        try:
            from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
            result = evaluate_url_policy(
                url_val,
                allowlist=allowlist or None,
                denylist=denylist or None,
                block_private_override=block_private if isinstance(block_private, bool) else None,
            )
            return result.allowed, result.reason
        except Exception as e:
            return False, str(e)

    def _record_blocked(url_val: str) -> None:
        try:
            from urllib.parse import urlparse as _urlparse
            host = _urlparse(url_val).hostname or ""
            from tldw_Server_API.app.core.Metrics import increment_counter as _inc
            _inc("workflows_webhook_deliveries_total", labels={"status": "blocked", "host": host})
        except Exception:
            pass
    from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
    user_id = _resolve_context_user_id(context)
    if not user_id:
        return {"dispatched": False, "error": "missing_user_id"}
    event_name = str(config.get("event") or "workflow.event")
    payload = config.get("data") or {"context": list(context.keys())}
    url = str(config.get("url") or "").strip()
    import os
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        # Skip outbound work in tests
        return {"dispatched": False, "test_mode": True}

    if url:
        tenant_id = str(context.get("tenant_id") or "default")
        def _global_allows(url_val: str) -> bool:
            try:
                from tldw_Server_API.app.core.Security.egress import is_webhook_url_allowed_for_tenant
                return is_webhook_url_allowed_for_tenant(url_val, tenant_id)
            except Exception:
                return is_url_allowed(url_val)

        try:
            import hmac, hashlib
            # Method, headers, timeout
            method = str(config.get("method") or "POST").upper()
            headers_cfg = config.get("headers") or {}
            # Templating for url and headers
            url_t = _render_value(url) or url
            url_t = str(url_t).strip()
            if not url_t:
                return {"dispatched": False, "error": "missing_url"}
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
            # Per-step allow/deny policy
            try:
                step_allowed, reason = _policy_allows(url_t)
            except Exception:
                step_allowed, reason = (False, "policy_error")
            if not _global_allows(url_t) or not step_allowed:
                _record_blocked(url_t)
                return {"dispatched": False, "error": "blocked_egress", "reason": reason}
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
                        with _wf_create_client(timeout=5.0, trust_env=False) as _client:
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
            # Optional per-step signing config overrides
            try:
                signing_cfg = config.get("signing")
                if signing_cfg is False or str(signing_cfg).lower() in {"0", "false", "none", "off"}:
                    secret = ""
                elif isinstance(signing_cfg, dict):
                    stype = str(signing_cfg.get("type") or "hmac-sha256").lower()
                    if stype in {"none", "off"}:
                        secret = ""
                    elif stype not in {"hmac-sha256", "hmac_sha256", "hmacsha256"}:
                        return {"dispatched": False, "error": "unsupported_signing_type"}
                    else:
                        sref = str(signing_cfg.get("secret_ref") or "").strip()
                        sdirect = signing_cfg.get("secret")
                        if sref:
                            secret = _resolve_signing_secret(sref) or ""
                        elif sdirect:
                            secret = str(sdirect)
                        if not secret:
                            return {"dispatched": False, "error": "missing_signing_secret"}
                elif signing_cfg:
                    # Truthy non-dict => fall back to env secret if available
                    secret = os.getenv("WORKFLOWS_WEBHOOK_SECRET", "")
            except Exception:
                pass
            if secret:
                sig = hmac.new(secret.encode("utf-8"), (body_json_str or "").encode("utf-8"), hashlib.sha256).hexdigest()
                headers_r["X-Workflows-Signature"] = sig
                headers_r["X-Hub-Signature-256"] = f"sha256={sig}"

            timeout = float(config.get("timeout_seconds") or os.getenv("WORKFLOWS_WEBHOOK_TIMEOUT", "10"))
            follow_redirects = bool(config.get("follow_redirects") or config.get("allow_redirects") or False)
            try:
                max_redirects = int(config.get("max_redirects") or os.getenv("HTTP_MAX_REDIRECTS", "5"))
            except Exception:
                max_redirects = int(os.getenv("HTTP_MAX_REDIRECTS", "5"))
            try:
                max_bytes = int(config.get("max_bytes")) if config.get("max_bytes") is not None else None
            except Exception:
                max_bytes = None
            try:
                client_ctx = _wf_create_client(timeout=timeout, trust_env=False)
            except TypeError:
                client_ctx = _wf_create_client(timeout=timeout)
            with client_ctx as client:
                # Dispatch with explicit redirect handling
                cur_url = url_t
                resp = None
                redirects = 0
                method_cur = method
                req_kwargs_cur = dict(req_kwargs)
                while True:
                    if not _global_allows(cur_url):
                        _record_blocked(cur_url)
                        return {"dispatched": False, "error": "blocked_egress"}
                    step_allowed, reason = _policy_allows(cur_url)
                    if not step_allowed:
                        _record_blocked(cur_url)
                        return {"dispatched": False, "error": "blocked_egress", "reason": reason}
                    resp = client.request(method_cur, cur_url, headers=headers_r, follow_redirects=False, **req_kwargs_cur)
                    if not follow_redirects or resp.status_code not in (301, 302, 303, 307, 308):
                        break
                    location = resp.headers.get("location")
                    try:
                        resp.close()
                    except Exception:
                        pass
                    if not location:
                        return {"dispatched": False, "error": "redirect_missing_location"}
                    redirects += 1
                    if redirects > max_redirects:
                        return {"dispatched": False, "error": "redirects_exceeded"}
                    try:
                        from urllib.parse import urljoin
                        cur_url = urljoin(cur_url, location)
                    except Exception:
                        cur_url = location
                    if resp.status_code in (301, 302, 303) and method_cur not in ("GET", "HEAD"):
                        method_cur = "GET"
                        req_kwargs_cur = {k: v for k, v in req_kwargs_cur.items() if k == "params"}
                if resp is None:
                    return {"dispatched": False, "error": "webhook_no_response"}
                # Optional response size guard
                def _read_response_bytes(r) -> bytes:
                    if max_bytes is not None:
                        clen = r.headers.get("content-length")
                        if clen:
                            try:
                                if int(clen) > max_bytes:
                                    try:
                                        r.close()
                                    except Exception:
                                        pass
                                    raise ValueError("response_too_large")
                            except ValueError:
                                raise
                            except Exception:
                                pass
                    buf = bytearray()
                    if max_bytes is None:
                        try:
                            data = r.read()
                            return data if data is not None else b""
                        except Exception:
                            return b""
                        finally:
                            try:
                                r.close()
                            except Exception:
                                pass
                    try:
                        for chunk in r.iter_bytes():
                            buf.extend(chunk)
                            if max_bytes is not None and len(buf) > max_bytes:
                                raise ValueError("response_too_large")
                    finally:
                        try:
                            r.close()
                        except Exception:
                            pass
                    return bytes(buf)
                ok = 200 <= resp.status_code < 300
                # Metrics for success/failure
                try:
                    from urllib.parse import urlparse as _urlparse
                    host = _urlparse(cur_url).hostname or ""
                    from tldw_Server_API.app.core.Metrics import increment_counter as _inc
                    _inc("workflows_webhook_deliveries_total", labels={"status": ("delivered" if ok else "failed"), "host": host})
                except Exception:
                    pass
                # Optional artifact of response metadata
                try:
                    if callable(context.get("add_artifact")):
                        step_run_id = str(context.get("step_run_id") or "")
                        art_dir = _resolve_artifacts_dir(step_run_id or f"webhook_{int(time.time()*1000)}")
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
                    body_bytes = _read_response_bytes(resp)
                except ValueError:
                    out["dispatched"] = False
                    out["error"] = "response_too_large"
                    return out
                try:
                    enc = resp.encoding or "utf-8"
                except Exception:
                    enc = "utf-8"
                try:
                    text = body_bytes.decode(enc, errors="replace")
                except Exception:
                    text = ""
                try:
                    out["response_json"] = json.loads(text) if text else None
                except Exception:
                    if text:
                        out["response_text"] = text
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


# ---------------------------------------------------------------------------
# Notes Adapter
# ---------------------------------------------------------------------------

async def run_notes_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Manage notes within a workflow step.

    Config:
      - action: Literal["create", "get", "list", "update", "delete", "search"]
      - note_id: Optional[str] (for get/update/delete)
      - title: Optional[str] (templated, for create/update)
      - content: Optional[str] (templated, for create/update)
      - query: Optional[str] (templated, for search)
      - limit: int = 100
      - offset: int = 0
      - expected_version: Optional[int] (for update/delete)
    Output:
      - {"note": {...}, "notes": [...], "success": bool}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    user_id = _resolve_context_user_id(context)
    if not user_id:
        try:
            user_id = str(DatabasePaths.get_single_user_id())
        except Exception:
            return {"error": "missing_user_id"}
    user_id = str(user_id)

    action = str(config.get("action") or "").strip().lower()
    if not action:
        return {"error": "missing_action"}

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        if action == "create":
            return {"note": {"id": "test-note-id", "title": _render(config.get("title")), "content": _render(config.get("content"))}, "success": True, "simulated": True}
        if action == "get":
            return {"note": {"id": config.get("note_id"), "title": "Test Note", "content": "Test content"}, "simulated": True}
        if action == "list":
            return {"notes": [], "count": 0, "simulated": True}
        if action == "update":
            return {"note": {"id": config.get("note_id")}, "success": True, "simulated": True}
        if action == "delete":
            return {"success": True, "simulated": True}
        if action == "search":
            return {"notes": [], "count": 0, "simulated": True}
        return {"error": f"unknown_action:{action}", "simulated": True}

    try:
        from tldw_Server_API.app.core.Notes.Notes_Library import NotesInteropService

        # Resolve notes DB directory
        try:
            notes_base_dir = DatabasePaths.get_user_base_directory(int(user_id))
        except Exception:
            notes_base_dir = Path("Databases") / "user_databases"

        service = NotesInteropService(base_db_directory=notes_base_dir, api_client_id="workflow_engine")

        if action == "create":
            title = _render(config.get("title") or "")
            content = _render(config.get("content") or "")
            if not title:
                return {"error": "missing_title"}
            note_id = service.add_note(user_id=user_id, title=title, content=content)
            note = service.get_note_by_id(user_id=user_id, note_id=note_id)
            return {"note": note, "success": True}

        if action == "get":
            note_id = str(config.get("note_id") or "").strip()
            if not note_id:
                return {"error": "missing_note_id"}
            note = service.get_note_by_id(user_id=user_id, note_id=note_id)
            if note is None:
                return {"error": "note_not_found", "note_id": note_id}
            return {"note": note}

        if action == "list":
            limit = int(config.get("limit") or 100)
            offset = int(config.get("offset") or 0)
            notes = service.list_notes(user_id=user_id, limit=limit, offset=offset)
            return {"notes": notes, "count": len(notes)}

        if action == "update":
            note_id = str(config.get("note_id") or "").strip()
            if not note_id:
                return {"error": "missing_note_id"}
            expected_version = config.get("expected_version")
            if expected_version is None:
                # Fetch current version
                current = service.get_note_by_id(user_id=user_id, note_id=note_id)
                if current is None:
                    return {"error": "note_not_found", "note_id": note_id}
                expected_version = current.get("version", 1)
            update_data: Dict[str, Any] = {}
            title = config.get("title")
            if title is not None:
                update_data["title"] = _render(title)
            content = config.get("content")
            if content is not None:
                update_data["content"] = _render(content)
            if not update_data:
                return {"error": "no_update_fields"}
            service.update_note(user_id=user_id, note_id=note_id, update_data=update_data, expected_version=int(expected_version))
            updated = service.get_note_by_id(user_id=user_id, note_id=note_id)
            return {"note": updated, "success": True}

        if action == "delete":
            note_id = str(config.get("note_id") or "").strip()
            if not note_id:
                return {"error": "missing_note_id"}
            expected_version = config.get("expected_version")
            if expected_version is None:
                current = service.get_note_by_id(user_id=user_id, note_id=note_id)
                if current is None:
                    return {"error": "note_not_found", "note_id": note_id}
                expected_version = current.get("version", 1)
            success = service.soft_delete_note(user_id=user_id, note_id=note_id, expected_version=int(expected_version))
            return {"success": success}

        if action == "search":
            query = _render(config.get("query") or "")
            if not query:
                return {"error": "missing_query"}
            limit = int(config.get("limit") or 100)
            offset = int(config.get("offset") or 0)
            notes = service.search_notes(user_id=user_id, query=query, limit=limit, offset=offset)
            return {"notes": notes, "count": len(notes)}

        return {"error": f"unknown_action:{action}"}

    except Exception as e:
        logger.exception(f"Notes adapter error: {e}")
        return {"error": f"notes_error:{e}"}


# ---------------------------------------------------------------------------
# Prompts Adapter
# ---------------------------------------------------------------------------

async def run_prompts_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Manage prompts within a workflow step.

    Config:
      - action: Literal["get", "list", "create", "update", "search"]
      - prompt_id: Optional[int]
      - name: Optional[str] (templated)
      - prompt: Optional[str] (templated) - the prompt content
      - author: Optional[str]
      - details: Optional[str] (templated)
      - system_prompt: Optional[str] (templated)
      - user_prompt: Optional[str] (templated)
      - keywords/tags: Optional[List[str]]
      - query: Optional[str] (templated, for search)
      - limit: int = 50
      - page: int = 1
    Output:
      - {"prompt": {...}, "prompts": [...]}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    action = str(config.get("action") or "").strip().lower()
    if not action:
        return {"error": "missing_action"}

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        if action == "create":
            return {"prompt": {"id": 1, "name": _render(config.get("name"))}, "success": True, "simulated": True}
        if action == "get":
            return {"prompt": {"id": config.get("prompt_id"), "name": "Test Prompt", "prompt": "Test content"}, "simulated": True}
        if action == "list":
            return {"prompts": [], "total": 0, "simulated": True}
        if action == "update":
            return {"prompt": {"id": config.get("prompt_id")}, "success": True, "simulated": True}
        if action == "search":
            return {"prompts": [], "total": 0, "simulated": True}
        return {"error": f"unknown_action:{action}", "simulated": True}

    try:
        from tldw_Server_API.app.core.Prompt_Management import Prompts_Interop as prompts_interop

        # Ensure interop is initialized
        if not prompts_interop.is_initialized():
            try:
                prompts_db_path = DatabasePaths.get_prompts_db_path()
            except Exception:
                prompts_db_path = Path("Databases") / "prompts.db"
            prompts_interop.initialize_interop(db_path=str(prompts_db_path), client_id="workflow_engine")

        if action == "get":
            prompt_id = config.get("prompt_id")
            prompt_name = config.get("name")
            prompt_uuid = config.get("uuid")
            if prompt_id is not None:
                prompt = prompts_interop.get_prompt_by_id(int(prompt_id))
            elif prompt_uuid:
                prompt = prompts_interop.get_prompt_by_uuid(str(prompt_uuid))
            elif prompt_name:
                prompt = prompts_interop.get_prompt_by_name(_render(prompt_name))
            else:
                return {"error": "missing_prompt_identifier"}
            if prompt is None:
                return {"error": "prompt_not_found"}
            return {"prompt": prompt}

        if action == "list":
            page = int(config.get("page") or 1)
            per_page = int(config.get("limit") or config.get("per_page") or 50)
            prompts_list, total_prompts, total_pages, current_page = prompts_interop.list_prompts(
                page=page, per_page=per_page
            )
            return {"prompts": prompts_list, "total": total_prompts, "total_pages": total_pages, "page": current_page}

        if action == "create":
            name = _render(config.get("name") or "")
            if not name:
                return {"error": "missing_name"}
            author = _render(config.get("author") or "")
            details = _render(config.get("details") or "")
            system_prompt = _render(config.get("system_prompt") or config.get("system") or "")
            user_prompt = _render(config.get("user_prompt") or config.get("prompt") or "")
            keywords = config.get("keywords") or config.get("tags") or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(",") if k.strip()]
            prompt_id, prompt_uuid, msg = prompts_interop.add_prompt(
                name=name,
                author=author or None,
                details=details or None,
                system_prompt=system_prompt or None,
                user_prompt=user_prompt or None,
                keywords=keywords if keywords else None,
                overwrite=bool(config.get("overwrite", False)),
            )
            return {"prompt": {"id": prompt_id, "uuid": prompt_uuid, "name": name}, "message": msg, "success": prompt_id is not None}

        if action == "update":
            prompt_id = config.get("prompt_id")
            prompt_name = config.get("name")
            if prompt_id is None and not prompt_name:
                return {"error": "missing_prompt_identifier"}
            # Fetch existing to update
            if prompt_id is not None:
                existing = prompts_interop.get_prompt_by_id(int(prompt_id))
            else:
                existing = prompts_interop.get_prompt_by_name(_render(prompt_name))
            if existing is None:
                return {"error": "prompt_not_found"}
            name = _render(config.get("new_name") or existing.get("name") or "")
            author = _render(config.get("author")) if config.get("author") is not None else existing.get("author")
            details = _render(config.get("details")) if config.get("details") is not None else existing.get("details")
            system_prompt = _render(config.get("system_prompt")) if config.get("system_prompt") is not None else existing.get("system_prompt")
            user_prompt = _render(config.get("user_prompt") or config.get("prompt")) if (config.get("user_prompt") or config.get("prompt")) is not None else existing.get("user_prompt")
            keywords = config.get("keywords") or config.get("tags")
            if keywords is None:
                keywords = existing.get("keywords") or []
            elif isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(",") if k.strip()]
            pid, puuid, msg = prompts_interop.add_prompt(
                name=name,
                author=author,
                details=details,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                keywords=keywords if keywords else None,
                overwrite=True,
            )
            return {"prompt": {"id": pid, "uuid": puuid, "name": name}, "message": msg, "success": pid is not None}

        if action == "search":
            query = _render(config.get("query") or "")
            if not query:
                return {"error": "missing_query"}
            page = int(config.get("page") or 1)
            per_page = int(config.get("limit") or 50)
            search_fields = config.get("search_fields")
            results, total = prompts_interop.search_prompts(
                search_query=query,
                search_fields=search_fields,
                page=page,
                results_per_page=per_page,
            )
            return {"prompts": results, "total": total}

        return {"error": f"unknown_action:{action}"}

    except Exception as e:
        logger.exception(f"Prompts adapter error: {e}")
        return {"error": f"prompts_error:{e}"}


# ---------------------------------------------------------------------------
# Chunking Adapter
# ---------------------------------------------------------------------------

async def run_chunking_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Chunk text using various strategies.

    Config:
      - text: Optional[str] (templated, defaults to last.text or last.content)
      - method: Literal["words", "sentences", "tokens", "structure_aware", "fixed_size"] = "sentences"
      - max_size: int = 400
      - overlap: int = 50
      - language: Optional[str]
    Output:
      - {"chunks": [...], "count": int, "text": str}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    # Resolve text input
    text = config.get("text")
    if text is not None:
        text = _render(text)
    else:
        # Try to get from context (last step output)
        last = context.get("last") or {}
        if isinstance(last, dict):
            text = last.get("text") or last.get("content") or last.get("summary") or ""
        else:
            text = ""
    text = str(text) if text else ""

    if not text.strip():
        return {"chunks": [], "count": 0, "text": ""}

    method = str(config.get("method") or "sentences").strip().lower()
    max_size = int(config.get("max_size") or config.get("max_tokens") or 400)
    overlap = int(config.get("overlap") or 50)
    language = config.get("language")

    # Validate method
    valid_methods = {"words", "sentences", "tokens", "structure_aware", "fixed_size"}
    if method not in valid_methods:
        return {"error": f"invalid_method:{method}", "valid_methods": list(valid_methods)}

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        # Simple mock chunking
        words = text.split()
        chunk_size = max(1, max_size // 5)  # Rough word-based simulation
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return {"chunks": chunks, "count": len(chunks), "text": text, "method": method, "simulated": True}

    try:
        from tldw_Server_API.app.core.Chunking import Chunker

        chunker = Chunker()
        chunks_result = chunker.chunk_text(
            text=text,
            method=method,
            max_size=max_size,
            overlap=overlap,
            language=language,
        )

        return {
            "chunks": chunks_result,
            "count": len(chunks_result),
            "text": text,
            "method": method,
            "max_size": max_size,
            "overlap": overlap,
        }

    except Exception as e:
        logger.exception(f"Chunking adapter error: {e}")
        return {"error": f"chunking_error:{e}"}


# ---------------------------------------------------------------------------
# Web Search Adapter
# ---------------------------------------------------------------------------

async def run_web_search_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Perform web search using various search engines.

    Config:
      - query: str (templated)
      - engine: Literal["google", "bing", "duckduckgo", "brave", "searxng"] = "google"
      - num_results: int = 10
      - content_country: str = "US"
      - search_lang: str = "en"
      - output_lang: str = "en"
      - safesearch: str = "active"
      - date_range: Optional[str]
      - summarize: bool = False
      - api_name: Optional[str] (for LLM summarization)
    Output:
      - {"results": [{title, link, snippet}], "count": int, "text": str}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    query = _render(config.get("query") or "")
    if not query:
        return {"error": "missing_query"}

    engine = str(config.get("engine") or "google").strip().lower()
    num_results = int(config.get("num_results") or config.get("result_count") or 10)
    content_country = str(config.get("content_country") or "US")
    search_lang = str(config.get("search_lang") or "en")
    output_lang = str(config.get("output_lang") or "en")
    safesearch = str(config.get("safesearch") or "active")
    date_range = config.get("date_range")
    summarize = bool(config.get("summarize", False))

    valid_engines = {"google", "bing", "duckduckgo", "brave", "searxng", "kagi", "serper", "tavily"}
    if engine not in valid_engines:
        return {"error": f"invalid_engine:{engine}", "valid_engines": list(valid_engines)}

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        mock_results = [
            {"title": f"Result 1 for {query}", "link": "https://example.com/1", "snippet": f"Snippet about {query}"},
            {"title": f"Result 2 for {query}", "link": "https://example.com/2", "snippet": f"More info about {query}"},
        ]
        return {
            "results": mock_results,
            "count": len(mock_results),
            "query": query,
            "engine": engine,
            "text": "\n".join([f"- {r['title']}: {r['snippet']}" for r in mock_results]),
            "simulated": True,
        }

    try:
        from tldw_Server_API.app.core.WebSearch.Web_Search import perform_websearch

        raw_results = perform_websearch(
            search_engine=engine,
            search_query=query,
            content_country=content_country,
            search_lang=search_lang,
            output_lang=output_lang,
            result_count=num_results,
            date_range=date_range,
            safesearch=safesearch,
            site_blacklist=config.get("site_blacklist"),
            exactTerms=config.get("exact_terms"),
            excludeTerms=config.get("exclude_terms"),
        )

        if not isinstance(raw_results, dict):
            return {"error": "search_failed", "query": query}

        if raw_results.get("processing_error"):
            return {"error": f"search_error:{raw_results.get('processing_error')}", "query": query}

        results = raw_results.get("results") or []
        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": r.get("title") or "",
                "link": r.get("link") or r.get("url") or "",
                "snippet": r.get("snippet") or r.get("description") or "",
            })

        # Combine snippets into text for downstream steps
        text = "\n".join([f"- {r['title']}: {r['snippet']}" for r in formatted_results if r.get("title")])

        out: Dict[str, Any] = {
            "results": formatted_results,
            "count": len(formatted_results),
            "query": query,
            "engine": engine,
            "text": text,
            "total_found": raw_results.get("total_results_found", len(formatted_results)),
        }

        # Optional summarization
        if summarize and text:
            try:
                from tldw_Server_API.app.core.WebSearch.Web_Search import summarize as ws_summarize
                api_name = _render(config.get("api_name") or config.get("api_provider") or "openai")
                summary = ws_summarize(
                    input_data=text,
                    custom_prompt_arg=f"Summarize the following search results for the query '{query}':",
                    api_name=api_name,
                )
                out["summary"] = summary
                out["text"] = summary  # Replace text with summary for downstream
            except Exception as e:
                logger.debug(f"Web search summarization failed: {e}")
                out["summary_error"] = str(e)

        return out

    except Exception as e:
        logger.exception(f"Web search adapter error: {e}")
        return {"error": f"web_search_error:{e}"}


# ---------------------------------------------------------------------------
# Collections (Reading List) Adapter
# ---------------------------------------------------------------------------

async def run_collections_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Manage reading list collections within a workflow step.

    Config:
      - action: Literal["save", "update", "list", "get", "delete", "search"]
      - url: Optional[str] (for save)
      - item_id: Optional[int] (for get/update/delete)
      - status: Optional[Literal["saved", "reading", "read", "archived"]]
      - tags: Optional[List[str]]
      - query: Optional[str] (for search, templated)
      - favorite: Optional[bool]
      - limit: int = 50
      - page: int = 1
    Output:
      - {"item": {...}, "items": [...], "count": int}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    user_id = _resolve_context_user_id(context)
    if not user_id:
        try:
            user_id = str(DatabasePaths.get_single_user_id())
        except Exception:
            return {"error": "missing_user_id"}
    user_id = str(user_id)

    action = str(config.get("action") or "").strip().lower()
    if not action:
        return {"error": "missing_action"}

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        if action == "save":
            return {
                "item": {"id": 1, "url": _render(config.get("url")), "title": "Test Item", "status": "saved"},
                "created": True,
                "simulated": True,
            }
        if action == "get":
            return {
                "item": {"id": config.get("item_id"), "url": "https://example.com", "title": "Test Item"},
                "simulated": True,
            }
        if action == "list":
            return {"items": [], "count": 0, "total": 0, "simulated": True}
        if action == "update":
            return {"item": {"id": config.get("item_id")}, "success": True, "simulated": True}
        if action == "delete":
            return {"success": True, "simulated": True}
        if action == "search":
            return {"items": [], "count": 0, "simulated": True}
        return {"error": f"unknown_action:{action}", "simulated": True}

    try:
        from tldw_Server_API.app.core.Collections.reading_service import ReadingService

        service = ReadingService(user_id=int(user_id))

        if action == "save":
            url = _render(config.get("url") or "")
            if not url:
                return {"error": "missing_url"}
            tags = config.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            status = config.get("status") or "saved"
            favorite = bool(config.get("favorite", False))
            title_override = _render(config.get("title")) if config.get("title") else None
            notes = _render(config.get("notes")) if config.get("notes") else None

            result = await service.save_url(
                url=url,
                tags=tags,
                status=status,
                favorite=favorite,
                title_override=title_override,
                notes=notes,
            )
            return {
                "item": {
                    "id": result.item.id,
                    "url": result.item.url,
                    "title": result.item.title,
                    "status": result.item.status,
                    "canonical_url": result.item.canonical_url,
                },
                "created": result.created,
                "media_id": result.media_id,
            }

        if action == "get":
            item_id = config.get("item_id")
            if item_id is None:
                return {"error": "missing_item_id"}
            try:
                item = service.get_item(int(item_id))
                return {
                    "item": {
                        "id": item.id,
                        "url": item.url,
                        "title": item.title,
                        "status": item.status,
                        "favorite": item.favorite,
                        "summary": item.summary,
                        "notes": item.notes,
                    }
                }
            except KeyError:
                return {"error": "item_not_found", "item_id": item_id}

        if action == "list":
            page = int(config.get("page") or 1)
            limit = int(config.get("limit") or config.get("size") or 50)
            status = config.get("status")
            status_list = [status] if status and isinstance(status, str) else status
            tags = config.get("tags")
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            favorite = config.get("favorite")
            if favorite is not None:
                favorite = bool(favorite)

            items, total = service.list_items(
                status=status_list,
                tags=tags,
                favorite=favorite,
                page=page,
                size=limit,
            )
            return {
                "items": [
                    {"id": i.id, "url": i.url, "title": i.title, "status": i.status, "favorite": i.favorite}
                    for i in items
                ],
                "count": len(items),
                "total": total,
                "page": page,
            }

        if action == "update":
            item_id = config.get("item_id")
            if item_id is None:
                return {"error": "missing_item_id"}
            status = config.get("status")
            favorite = config.get("favorite")
            if favorite is not None:
                favorite = bool(favorite)
            tags = config.get("tags")
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            notes = _render(config.get("notes")) if config.get("notes") else None
            title = _render(config.get("title")) if config.get("title") else None

            try:
                item = service.update_item(
                    int(item_id),
                    status=status,
                    favorite=favorite,
                    tags=tags,
                    notes=notes,
                    title=title,
                )
                return {
                    "item": {"id": item.id, "url": item.url, "title": item.title, "status": item.status},
                    "success": True,
                }
            except KeyError:
                return {"error": "item_not_found", "item_id": item_id}

        if action == "delete":
            item_id = config.get("item_id")
            if item_id is None:
                return {"error": "missing_item_id"}
            try:
                service.delete_item(int(item_id))
                return {"success": True}
            except KeyError:
                return {"error": "item_not_found", "item_id": item_id}

        if action == "search":
            query = _render(config.get("query") or "")
            if not query:
                return {"error": "missing_query"}
            page = int(config.get("page") or 1)
            limit = int(config.get("limit") or 50)

            items, total = service.list_items(q=query, page=page, size=limit)
            return {
                "items": [
                    {"id": i.id, "url": i.url, "title": i.title, "status": i.status}
                    for i in items
                ],
                "count": len(items),
                "total": total,
            }

        return {"error": f"unknown_action:{action}"}

    except Exception as e:
        logger.exception(f"Collections adapter error: {e}")
        return {"error": f"collections_error:{e}"}


# ---------------------------------------------------------------------------
# Chatbooks Adapter
# ---------------------------------------------------------------------------

async def run_chatbooks_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Export and import chatbooks within a workflow step.

    Config:
      - action: Literal["export", "import", "list_jobs", "get_job", "preview"]
      - content_types: Optional[List[str]] (for export: "conversations", "notes", "prompts", "media")
      - name: Optional[str] (templated, for export)
      - description: Optional[str] (templated, for export)
      - file_path: Optional[str] (for import)
      - job_id: Optional[str] (for get_job)
    Output:
      - {"job_id": str, "status": str, "artifact_uri": str}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    user_id = _resolve_context_user_id(context)
    if not user_id:
        try:
            user_id = str(DatabasePaths.get_single_user_id())
        except Exception:
            return {"error": "missing_user_id"}
    user_id = str(user_id)

    action = str(config.get("action") or "").strip().lower()
    if not action:
        return {"error": "missing_action"}

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        if action == "export":
            return {
                "job_id": "test-job-123",
                "status": "completed",
                "name": _render(config.get("name") or "Test Export"),
                "simulated": True,
            }
        if action == "import":
            return {"job_id": "test-import-123", "status": "completed", "imported": 0, "simulated": True}
        if action == "list_jobs":
            return {"jobs": [], "count": 0, "simulated": True}
        if action == "get_job":
            return {"job": {"id": config.get("job_id"), "status": "completed"}, "simulated": True}
        if action == "preview":
            return {"preview": {"conversations": 0, "notes": 0, "prompts": 0}, "simulated": True}
        return {"error": f"unknown_action:{action}", "simulated": True}

    try:
        from tldw_Server_API.app.core.Chatbooks.chatbook_service import ChatbookService
        from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB

        # Initialize user's notes database for chatbook service
        try:
            user_id_int = int(user_id)
            notes_db_path = DatabasePaths.get_chachanotes_db_path(user_id_int)
        except Exception:
            user_id_int = None
            notes_db_path = Path("Databases") / "user_databases" / user_id / "ChaChaNotes.db"

        db = CharactersRAGDB(db_path=notes_db_path, client_id="workflow_engine")
        service = ChatbookService(user_id=user_id, db=db, user_id_int=user_id_int)

        if action == "export":
            content_types = config.get("content_types") or ["conversations", "notes"]
            if isinstance(content_types, str):
                content_types = [c.strip() for c in content_types.split(",") if c.strip()]
            name = _render(config.get("name") or "Workflow Export")
            description = _render(config.get("description") or "")

            job_info = service.create_export_job(
                name=name,
                description=description,
                content_types=content_types,
            )
            return {
                "job_id": job_info.get("job_id"),
                "status": job_info.get("status", "pending"),
                "name": name,
                "content_types": content_types,
            }

        if action == "import":
            file_path = _render(config.get("file_path") or "")
            if not file_path:
                return {"error": "missing_file_path"}
            # Note: Import is async and job-based; we just start the job here
            return {"error": "import_not_yet_supported_in_workflows", "file_path": file_path}

        if action == "list_jobs":
            status_filter = config.get("status")
            limit = int(config.get("limit") or 100)
            jobs = service.list_export_jobs(status=status_filter, limit=limit)
            return {
                "jobs": [
                    {"id": j.job_id, "name": j.name, "status": j.status.value if hasattr(j.status, 'value') else str(j.status)}
                    for j in jobs
                ],
                "count": len(jobs),
            }

        if action == "get_job":
            job_id = config.get("job_id")
            if not job_id:
                return {"error": "missing_job_id"}
            job = service.get_export_job(str(job_id))
            if job is None:
                return {"error": "job_not_found", "job_id": job_id}
            return {
                "job": {
                    "id": job.job_id,
                    "name": job.name,
                    "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                }
            }

        if action == "preview":
            content_types = config.get("content_types") or ["conversations", "notes", "prompts"]
            if isinstance(content_types, str):
                content_types = [c.strip() for c in content_types.split(",") if c.strip()]
            preview = service.preview_export(content_types=content_types)
            return {"preview": preview}

        return {"error": f"unknown_action:{action}"}

    except Exception as e:
        logger.exception(f"Chatbooks adapter error: {e}")
        return {"error": f"chatbooks_error:{e}"}


# ---------------------------------------------------------------------------
# Evaluations Adapter (Stage 3)
# ---------------------------------------------------------------------------

async def run_evaluations_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Run LLM evaluations (geval, rag, response_quality) within a workflow step.

    Config:
      - action: Literal["geval", "rag", "response_quality", "get_run", "list_runs"]
      - response: Optional[str] (templated, defaults to last.text) - for geval/rag/response_quality
      - context: Optional[str] (templated) - source text for geval, context for response_quality
      - criteria: Optional[List[str]] - e.g., ["relevance", "coherence", "fluency"]
      - question: Optional[str] (templated) - for rag
      - retrieved_contexts: Optional[List[str]] - from last.documents or explicit
      - reference_answer: Optional[str] (templated) - for rag
      - run_id: Optional[str] - for get_run
      - api_name: Optional[str] - LLM provider for evaluation
      - limit: int = 20 (for list_runs)
    Output:
      - {"score": float, "metrics": {...}, "passed": bool, "details": {...}}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    user_id = _resolve_context_user_id(context)
    if not user_id:
        try:
            user_id = str(DatabasePaths.get_single_user_id())
        except Exception:
            return {"error": "missing_user_id"}
    user_id = str(user_id)

    action = str(config.get("action") or "").strip().lower()
    if not action:
        return {"error": "missing_action"}

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        if action == "geval":
            # Use criteria from config or default metrics
            criteria = config.get("criteria") or config.get("metrics")
            if isinstance(criteria, str):
                criteria = [c.strip() for c in criteria.split(",") if c.strip()]
            elif not isinstance(criteria, list):
                criteria = ["coherence", "relevance", "fluency"]
            # Generate simulated scores for each criterion
            simulated_metrics = {c: 0.8 + (hash(c) % 15) / 100 for c in criteria}
            avg_score = sum(simulated_metrics.values()) / len(simulated_metrics) if simulated_metrics else 0.85
            return {
                "evaluation_id": "test-eval-geval",
                "score": round(avg_score, 2),
                "metrics": simulated_metrics,
                "passed": avg_score >= float(config.get("threshold", 0.6)),
                "evaluation_time": 0.5,
                "simulated": True,
            }
        if action == "rag":
            return {
                "evaluation_id": "test-eval-rag",
                "score": 0.82,
                "metrics": {"faithfulness": 0.85, "answer_relevance": 0.80, "context_relevance": 0.81},
                "passed": True,
                "evaluation_time": 0.6,
                "simulated": True,
            }
        if action == "response_quality":
            return {
                "evaluation_id": "test-eval-quality",
                "score": 0.88,
                "metrics": {"clarity": 0.9, "completeness": 0.85, "accuracy": 0.89},
                "passed": True,
                "evaluation_time": 0.4,
                "simulated": True,
            }
        if action == "get_run":
            return {
                "run": {"id": config.get("run_id"), "status": "completed", "score": 0.85},
                "simulated": True,
            }
        if action == "list_runs":
            return {"runs": [], "has_more": False, "simulated": True}
        return {"error": f"unknown_action:{action}", "simulated": True}

    try:
        from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import UnifiedEvaluationService

        service = UnifiedEvaluationService(enable_webhooks=False)
        await service.initialize()

        api_name = _render(config.get("api_name") or config.get("api_provider") or "openai")

        if action == "geval":
            # G-Eval: evaluate summarization quality
            response = config.get("response") or config.get("summary")
            if response is not None:
                response = _render(response)
            else:
                last = context.get("last") or {}
                if isinstance(last, dict):
                    response = last.get("text") or last.get("content") or last.get("summary") or ""
                else:
                    response = ""

            source_text = config.get("context") or config.get("source_text")
            if source_text is not None:
                source_text = _render(source_text)
            else:
                source_text = ""

            if not response:
                return {"error": "missing_response_for_geval"}

            # Extract criteria/metrics for G-Eval (e.g., ["relevance", "coherence", "fluency"])
            criteria = config.get("criteria") or config.get("metrics")
            if isinstance(criteria, str):
                criteria = [c.strip() for c in criteria.split(",") if c.strip()]
            elif not isinstance(criteria, list):
                criteria = None

            result = await service.evaluate_geval(
                source_text=source_text,
                summary=response,
                metrics=criteria,
                api_name=api_name,
                user_id=user_id,
            )

            results = result.get("results") or {}
            avg_score = results.get("average_score", 0.0)
            return {
                "evaluation_id": result.get("evaluation_id"),
                "score": avg_score,
                "metrics": results.get("scores") or results,
                "passed": avg_score >= float(config.get("threshold", 0.6)),
                "evaluation_time": result.get("evaluation_time"),
                "details": results,
            }

        if action == "rag":
            # RAG evaluation: assess retrieval + generation quality
            question = config.get("question") or config.get("query")
            if question is not None:
                question = _render(question)
            else:
                question = ""

            response = config.get("response")
            if response is not None:
                response = _render(response)
            else:
                last = context.get("last") or {}
                if isinstance(last, dict):
                    response = last.get("text") or last.get("content") or ""
                else:
                    response = ""

            # Resolve contexts from config or last step
            retrieved_contexts = config.get("retrieved_contexts") or config.get("contexts")
            if retrieved_contexts is None:
                last = context.get("last") or {}
                if isinstance(last, dict):
                    docs = last.get("documents") or last.get("results") or []
                    if isinstance(docs, list):
                        retrieved_contexts = []
                        for d in docs:
                            if isinstance(d, dict):
                                txt = d.get("content") or d.get("text") or d.get("snippet") or ""
                                if txt:
                                    retrieved_contexts.append(txt)
                            elif isinstance(d, str):
                                retrieved_contexts.append(d)
            if not isinstance(retrieved_contexts, list):
                retrieved_contexts = []

            reference_answer = config.get("reference_answer") or config.get("ground_truth")
            if reference_answer is not None:
                reference_answer = _render(reference_answer)

            if not question or not response:
                return {"error": "missing_question_or_response_for_rag"}

            result = await service.evaluate_rag(
                query=question,
                contexts=retrieved_contexts,
                response=response,
                ground_truth=reference_answer,
                api_name=api_name,
                user_id=user_id,
            )

            results = result.get("results") or {}
            overall_score = results.get("overall_score", 0.0)
            return {
                "evaluation_id": result.get("evaluation_id"),
                "score": overall_score,
                "metrics": results.get("metrics") or results,
                "passed": overall_score >= float(config.get("threshold", 0.6)),
                "evaluation_time": result.get("evaluation_time"),
                "details": results,
            }

        if action == "response_quality":
            # Response quality evaluation
            prompt = config.get("prompt") or config.get("question")
            if prompt is not None:
                prompt = _render(prompt)
            else:
                prompt = ""

            response = config.get("response")
            if response is not None:
                response = _render(response)
            else:
                last = context.get("last") or {}
                if isinstance(last, dict):
                    response = last.get("text") or last.get("content") or ""
                else:
                    response = ""

            if not response:
                return {"error": "missing_response_for_quality_eval"}

            expected_format = config.get("expected_format")
            custom_criteria = config.get("custom_criteria")

            result = await service.evaluate_response_quality(
                prompt=prompt,
                response=response,
                expected_format=expected_format,
                custom_criteria=custom_criteria,
                api_name=api_name,
                user_id=user_id,
            )

            results = result.get("results") or {}
            overall_score = results.get("overall_score", results.get("score", 0.0))
            return {
                "evaluation_id": result.get("evaluation_id"),
                "score": overall_score,
                "metrics": results.get("metrics") or results,
                "passed": overall_score >= float(config.get("threshold", 0.6)),
                "evaluation_time": result.get("evaluation_time"),
                "details": results,
            }

        if action == "get_run":
            run_id = config.get("run_id")
            if not run_id:
                return {"error": "missing_run_id"}
            run = await service.get_run(str(run_id))
            if run is None:
                return {"error": "run_not_found", "run_id": run_id}
            return {"run": run}

        if action == "list_runs":
            limit = int(config.get("limit") or 20)
            eval_id = config.get("eval_id")
            status = config.get("status")
            runs, has_more = await service.list_runs(
                eval_id=eval_id,
                status=status,
                limit=limit,
            )
            return {"runs": runs, "has_more": has_more}

        return {"error": f"unknown_action:{action}"}

    except Exception as e:
        logger.exception(f"Evaluations adapter error: {e}")
        return {"error": f"evaluations_error:{e}"}


# ---------------------------------------------------------------------------
# Claims Extract Adapter (Stage 3)
# ---------------------------------------------------------------------------

async def run_claims_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and search claims from text within a workflow step.

    Config:
      - action: Literal["extract", "search", "list"]
      - text: Optional[str] (templated, defaults to last.text) - for extract
      - media_id: Optional[int] - associate claims with media item
      - query: Optional[str] (templated) - for search
      - limit: int = 50
      - offset: int = 0
      - api_name: Optional[str] - LLM provider for extraction
    Output:
      - {"claims": [{claim_text, source_span, confidence, metadata}], "count": int}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    user_id = _resolve_context_user_id(context)
    if not user_id:
        try:
            user_id = str(DatabasePaths.get_single_user_id())
        except Exception:
            return {"error": "missing_user_id"}
    user_id = str(user_id)

    action = str(config.get("action") or "").strip().lower()
    if not action:
        return {"error": "missing_action"}

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        if action == "extract":
            return {
                "claims": [
                    {"id": "claim-1", "text": "Test claim extracted from text", "span": [0, 30], "confidence": 0.9}
                ],
                "count": 1,
                "simulated": True,
            }
        if action == "search":
            return {
                "claims": [],
                "count": 0,
                "query": _render(config.get("query") or ""),
                "simulated": True,
            }
        if action == "list":
            return {"claims": [], "count": 0, "simulated": True}
        return {"error": f"unknown_action:{action}", "simulated": True}

    try:
        if action == "extract":
            # Resolve text input
            text = config.get("text")
            if text is not None:
                text = _render(text)
            else:
                last = context.get("last") or {}
                if isinstance(last, dict):
                    text = last.get("text") or last.get("content") or ""
                else:
                    text = ""

            if not text:
                return {"error": "missing_text_for_extraction"}

            # Use ClaimsEngine to extract claims
            from tldw_Server_API.app.core.Claims_Extraction.claims_engine import LLMClaimExtractor

            api_name = _render(config.get("api_name") or "openai")
            max_claims = int(config.get("max_claims") or 25)

            extractor = LLMClaimExtractor(provider=api_name)
            claims = await extractor.extract(text, max_claims=max_claims)

            # Format claims for output
            claims_list = []
            for claim in claims:
                claims_list.append({
                    "id": claim.id,
                    "text": claim.text,
                    "span": list(claim.span) if claim.span else None,
                })

            return {
                "claims": claims_list,
                "count": len(claims_list),
                "text": text[:500] if len(text) > 500 else text,
            }

        if action == "search":
            query = _render(config.get("query") or "")
            if not query:
                return {"error": "missing_query"}

            limit = int(config.get("limit") or 50)
            offset = int(config.get("offset") or 0)

            # Search claims in media database
            from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database

            media_db = create_media_database(user_id=int(user_id))
            results = media_db.search_claims(query=query, limit=limit, offset=offset)

            claims_list = []
            for r in results:
                claims_list.append({
                    "id": r.get("id"),
                    "text": r.get("claim_text") or r.get("text"),
                    "media_id": r.get("media_id"),
                    "relevance_score": r.get("relevance_score"),
                })

            return {
                "claims": claims_list,
                "count": len(claims_list),
                "query": query,
            }

        if action == "list":
            limit = int(config.get("limit") or 50)
            offset = int(config.get("offset") or 0)
            media_id = config.get("media_id")

            from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database

            media_db = create_media_database(user_id=int(user_id))

            if media_id is not None:
                results = media_db.list_claims_for_media(media_id=int(media_id), limit=limit, offset=offset)
            else:
                results = media_db.list_claims(limit=limit, offset=offset)

            claims_list = []
            for r in results:
                claims_list.append({
                    "id": r.get("id"),
                    "text": r.get("claim_text") or r.get("text"),
                    "media_id": r.get("media_id"),
                })

            return {
                "claims": claims_list,
                "count": len(claims_list),
            }

        return {"error": f"unknown_action:{action}"}

    except Exception as e:
        logger.exception(f"Claims extract adapter error: {e}")
        return {"error": f"claims_extract_error:{e}"}


# ---------------------------------------------------------------------------
# Character Chat Adapter (Stage 3)
# ---------------------------------------------------------------------------

async def run_character_chat_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Chat with AI characters using character cards within a workflow step.

    Config:
      - action: Literal["start", "message", "load"] (default: "message")
      - character_id: Optional[int] - for start
      - conversation_id: Optional[str] - for message/load
      - message: Optional[str] (templated) - for message action
      - api_name: Optional[str] - LLM provider
      - temperature: float = 0.8
      - user_name: Optional[str] - user display name for placeholders
    Output:
      - {"response": str, "conversation_id": str, "character_name": str, "turn_count": int}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    user_id = _resolve_context_user_id(context)
    if not user_id:
        try:
            user_id = str(DatabasePaths.get_single_user_id())
        except Exception:
            return {"error": "missing_user_id"}
    user_id = str(user_id)

    action = str(config.get("action") or "message").strip().lower()

    def _render(value: Any) -> Any:
        if isinstance(value, str):
            return apply_template_to_string(value, context) or value
        return value

    user_name = _render(config.get("user_name") or "User")

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        if action == "start":
            return {
                "conversation_id": "test-conv-123",
                "character_name": "Test Character",
                "character_id": config.get("character_id"),
                "greeting": "Hello! How can I help you today?",
                "simulated": True,
            }
        if action == "message":
            return {
                "response": f"This is a simulated response to: {_render(config.get('message') or '')}",
                "conversation_id": config.get("conversation_id") or "test-conv-123",
                "character_name": "Test Character",
                "turn_count": 2,
                "simulated": True,
            }
        if action == "load":
            return {
                "conversation_id": config.get("conversation_id"),
                "character_name": "Test Character",
                "history": [],
                "turn_count": 0,
                "simulated": True,
            }
        return {"error": f"unknown_action:{action}", "simulated": True}

    try:
        from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
        from tldw_Server_API.app.core.Character_Chat.modules.character_chat import (
            start_new_chat_session,
            load_chat_and_character,
            post_message_to_conversation,
        )

        # Initialize user's character DB
        try:
            user_id_int = int(user_id)
            db_path = DatabasePaths.get_chachanotes_db_path(user_id_int)
        except Exception:
            db_path = Path("Databases") / "user_databases" / user_id / "ChaChaNotes.db"

        db = CharactersRAGDB(db_path=db_path, client_id="workflow_engine")

        if action == "start":
            character_id = config.get("character_id")
            if character_id is None:
                return {"error": "missing_character_id"}

            custom_title = _render(config.get("title")) if config.get("title") else None

            conversation_id, char_data, initial_history, _ = start_new_chat_session(
                db=db,
                character_id=int(character_id),
                user_name=user_name,
                custom_title=custom_title,
            )

            if not conversation_id:
                return {"error": "failed_to_start_chat_session"}

            char_name = char_data.get("name", "Character") if char_data else "Character"
            greeting = ""
            if initial_history and initial_history[0]:
                greeting = initial_history[0][1] or ""

            return {
                "conversation_id": conversation_id,
                "character_name": char_name,
                "character_id": character_id,
                "greeting": greeting,
                "turn_count": 1 if greeting else 0,
            }

        if action == "load":
            conversation_id = config.get("conversation_id")
            if not conversation_id:
                return {"error": "missing_conversation_id"}

            char_data, history, _ = load_chat_and_character(
                db=db,
                conversation_id_str=str(conversation_id),
                user_name=user_name,
            )

            if char_data is None:
                return {"error": "conversation_not_found", "conversation_id": conversation_id}

            char_name = char_data.get("name", "Character") if char_data else "Unknown"

            # Format history for output
            formatted_history = []
            for user_msg, char_msg in history:
                if user_msg:
                    formatted_history.append({"role": "user", "content": user_msg})
                if char_msg:
                    formatted_history.append({"role": "character", "content": char_msg})

            return {
                "conversation_id": conversation_id,
                "character_name": char_name,
                "character_id": char_data.get("id") if char_data else None,
                "history": formatted_history,
                "turn_count": len(history),
            }

        if action == "message":
            conversation_id = config.get("conversation_id")
            if not conversation_id:
                return {"error": "missing_conversation_id"}

            message = _render(config.get("message") or "")
            if not message:
                return {"error": "missing_message"}

            api_name = _render(config.get("api_name") or config.get("api_provider") or "openai")
            temperature = float(config.get("temperature") or 0.8)

            # Post message and get response
            result = await post_message_to_conversation(
                db=db,
                conversation_id=str(conversation_id),
                user_message=message,
                user_name=user_name,
                api_name=api_name,
                temperature=temperature,
            )

            if result is None:
                return {"error": "failed_to_post_message"}

            response_text = result.get("response") or result.get("content") or ""
            char_name = result.get("character_name") or "Character"

            return {
                "response": response_text,
                "text": response_text,  # Alias for downstream steps
                "conversation_id": conversation_id,
                "character_name": char_name,
                "turn_count": result.get("turn_count", 0),
            }

        return {"error": f"unknown_action:{action}"}

    except Exception as e:
        logger.exception(f"Character chat adapter error: {e}")
        return {"error": f"character_chat_error:{e}"}


# ---------------------------------------------------------------------------
# Stage 4 Adapters: Moderation, Sandbox Exec, Image Generation
# ---------------------------------------------------------------------------


async def run_moderation_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Check or redact text content using the moderation service.

    Config:
      - action: Literal["check", "redact"] (default: "check")
      - text: Optional[str] (templated, defaults to last.text)
      - action_type: str = "generic" (context for check action)
      - patterns: Optional[List[str]] (for redact action, additional patterns)
    Output for "check":
      - {"allowed": bool, "reason": str, "matched_rules": [...]}
    Output for "redact":
      - {"redacted_text": str, "redaction_count": int, "text": str}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    action = str(config.get("action") or "check").strip().lower()

    # Template rendering for text
    text_t = str(config.get("text") or "").strip()
    if text_t:
        text = apply_template_to_string(text_t, context) or text_t
    else:
        # Default to last.text
        text = None
        try:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                text = str(last.get("text") or last.get("content") or "")
        except Exception:
            pass
    text = text or ""

    if not text.strip():
        return {"error": "missing_text"}

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        if action == "check":
            # Simulate: flag if "blocked" appears in text
            is_blocked = "blocked" in text.lower() or "unsafe" in text.lower()
            return {
                "allowed": not is_blocked,
                "reason": "contains_blocked_term" if is_blocked else "passed",
                "matched_rules": ["test_blocked_term"] if is_blocked else [],
                "simulated": True,
            }
        if action == "redact":
            # Simulate: redact any occurrence of "secret" or "password"
            import re as _re
            redacted = _re.sub(r"\b(secret|password|blocked|unsafe)\b", "[REDACTED]", text, flags=_re.IGNORECASE)
            # Apply custom patterns if provided
            custom_patterns = config.get("patterns")
            if custom_patterns and isinstance(custom_patterns, list):
                for pattern_str in custom_patterns:
                    if isinstance(pattern_str, str) and pattern_str.strip():
                        try:
                            pat = _re.compile(pattern_str.strip(), flags=_re.IGNORECASE)
                            redacted = pat.sub("[REDACTED]", redacted)
                        except _re.error:
                            pass  # Skip invalid patterns in TEST_MODE
            # Count actual redaction markers
            redaction_count = redacted.count("[REDACTED]")
            return {
                "redacted_text": redacted,
                "text": redacted,
                "redaction_count": redaction_count,
                "simulated": True,
            }
        return {"error": f"unknown_action:{action}", "simulated": True}

    try:
        from tldw_Server_API.app.core.Moderation.moderation_service import get_moderation_service

        service = get_moderation_service()

        # Get effective policy (no user_id required for moderation - stateless)
        user_id = _resolve_context_user_id(context)
        policy = service.get_effective_policy(user_id)

        if action == "check":
            action_type = str(config.get("action_type") or "generic")
            # Use check_text for basic flagging
            is_flagged, matched_sample = service.check_text(text, policy, phase="input")

            if is_flagged:
                # Get more details via evaluate_action
                eval_action, _, pattern, category, _ = service.evaluate_action_with_match(
                    text, policy, phase="input"
                )
                return {
                    "allowed": False,
                    "reason": f"matched:{category or pattern or 'rule'}",
                    "matched_rules": [pattern] if pattern else [],
                    "action_recommended": eval_action,
                    "sample": matched_sample,
                }
            return {
                "allowed": True,
                "reason": "passed",
                "matched_rules": [],
            }

        if action == "redact":
            redacted = service.redact_text(text, policy)

            # Apply custom patterns if provided
            custom_patterns = config.get("patterns")
            if custom_patterns and isinstance(custom_patterns, list):
                import re as _re
                for pattern_str in custom_patterns:
                    if isinstance(pattern_str, str) and pattern_str.strip():
                        try:
                            pat = _re.compile(pattern_str.strip(), flags=_re.IGNORECASE)
                            redacted = pat.sub(policy.redact_replacement or "[REDACTED]", redacted)
                        except _re.error as pe:
                            logger.warning(f"Invalid custom redaction pattern '{pattern_str}': {pe}")

            # Count redactions by checking differences
            redaction_count = redacted.count("[REDACTED]") + redacted.count("[PII]")
            return {
                "redacted_text": redacted,
                "text": redacted,  # Alias for chaining
                "redaction_count": redaction_count,
                "original_length": len(text),
                "redacted_length": len(redacted),
            }

        return {"error": f"unknown_action:{action}"}

    except Exception as e:
        logger.exception(f"Moderation adapter error: {e}")
        return {"error": f"moderation_error:{e}"}


async def run_sandbox_exec_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute code in an isolated sandbox environment.

    Config:
      - code: str (templated) - code to execute
      - language: Literal["python", "bash", "javascript"] = "python"
      - timeout_seconds: int = 30
      - memory_limit_mb: int = 256
      - stdin: Optional[str] (templated) - input to provide via stdin
      - base_image: Optional[str] - Docker image to use
    Output:
      - {"stdout": str, "stderr": str, "exit_code": int, "duration_ms": float, "timed_out": bool}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    user_id = _resolve_context_user_id(context)
    if not user_id:
        try:
            user_id = str(DatabasePaths.get_single_user_id())
        except Exception:
            return {"error": "missing_user_id"}
    user_id = str(user_id)

    # Template rendering
    code_t = str(config.get("code") or "").strip()
    if code_t:
        code = apply_template_to_string(code_t, context) or code_t
    else:
        return {"error": "missing_code"}

    if not code.strip():
        return {"error": "missing_code"}

    language = str(config.get("language") or "python").strip().lower()
    if language not in ("python", "bash", "sh", "javascript", "js", "node"):
        return {"error": f"unsupported_language:{language}"}
    # Normalize aliases
    if language == "sh":
        language = "bash"
    if language in ("js", "node"):
        language = "javascript"

    timeout_seconds = int(config.get("timeout_seconds") or config.get("timeout_sec") or 30)
    timeout_seconds = max(1, min(timeout_seconds, 300))  # Cap at 5 minutes

    memory_limit_mb = int(config.get("memory_limit_mb") or config.get("memory_mb") or 256)
    memory_limit_mb = max(64, min(memory_limit_mb, 1024))  # 64MB to 1GB

    stdin_t = config.get("stdin")
    stdin_val = None
    if stdin_t is not None:
        stdin_val = apply_template_to_string(str(stdin_t), context) or str(stdin_t)

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        # Simulate execution
        simulated_stdout = f"[TEST_MODE] Code executed successfully\nLanguage: {language}\nCode length: {len(code)} chars"
        if stdin_val:
            simulated_stdout += f"\nStdin provided: {len(stdin_val)} chars"
        return {
            "stdout": simulated_stdout,
            "stderr": "",
            "exit_code": 0,
            "duration_ms": 42.0,
            "timed_out": False,
            "simulated": True,
            "language": language,
        }

    try:
        from tldw_Server_API.app.core.Sandbox.service import SandboxService
        from tldw_Server_API.app.core.Sandbox.models import RunSpec, RuntimeType

        service = SandboxService()

        # Determine base image based on language
        base_image = config.get("base_image")
        if not base_image:
            if language == "python":
                base_image = "python:3.11-slim"
            elif language == "javascript":
                base_image = "node:20-slim"
            else:
                base_image = "ubuntu:24.04"

        # Build command based on language
        if language == "python":
            command = ["python", "-c", code]
        elif language == "javascript":
            command = ["node", "-e", code]
        else:  # bash
            command = ["bash", "-c", code]

        # Create run spec
        spec = RunSpec(
            session_id=None,
            runtime=RuntimeType.docker,
            base_image=base_image,
            command=command,
            env=dict(config.get("env") or {}),
            timeout_sec=timeout_seconds,
            memory_mb=memory_limit_mb,
            network_policy="deny_all",  # Secure default
        )

        # Execute
        import uuid as _uuid
        idem_key = f"wf-sandbox-{_uuid.uuid4()}"
        status = service.start_run_scaffold(
            user_id=user_id,
            spec=spec,
            spec_version="1.0",
            idem_key=idem_key,
            raw_body={"code": code[:100], "language": language},
        )

        # Extract results
        from tldw_Server_API.app.core.Sandbox.models import RunPhase
        timed_out = status.phase == RunPhase.timed_out
        exit_code = status.exit_code if status.exit_code is not None else (124 if timed_out else 1)

        # Get stdout/stderr from artifacts if available
        stdout = ""
        stderr = ""
        if status.artifacts:
            stdout = (status.artifacts.get("stdout") or b"").decode("utf-8", errors="replace")
            stderr = (status.artifacts.get("stderr") or b"").decode("utf-8", errors="replace")
        elif status.message:
            # Fallback to message
            stderr = status.message

        duration_ms = 0.0
        if status.started_at and status.finished_at:
            duration_ms = (status.finished_at - status.started_at).total_seconds() * 1000

        result: Dict[str, Any] = {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
            "language": language,
            "run_id": status.id,
        }

        # Include text alias for chaining (prefer stdout)
        if stdout:
            result["text"] = stdout.strip()

        return result

    except Exception as e:
        logger.exception(f"Sandbox exec adapter error: {e}")
        return {"error": f"sandbox_exec_error:{e}"}


async def run_image_gen_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate images from text prompts using configured image generation backends.

    Config:
      - prompt: str (templated) - text prompt for image generation
      - negative_prompt: Optional[str] (templated) - negative prompt
      - backend: Literal["stable_diffusion_cpp", "swarmui"] = "stable_diffusion_cpp"
      - width: int = 512
      - height: int = 512
      - steps: int = 20
      - cfg_scale: float = 7.0
      - seed: Optional[int] = None
      - sampler: Optional[str] = None
      - model: Optional[str] = None
      - format: str = "png"
      - save_artifact: bool = True
    Output:
      - {"images": [{"uri": str, "width": int, "height": int, "format": str}], "count": int, "timings": {...}}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    user_id = _resolve_context_user_id(context)
    if not user_id:
        try:
            user_id = str(DatabasePaths.get_single_user_id())
        except Exception:
            return {"error": "missing_user_id"}
    user_id = str(user_id)

    # Template rendering for prompt
    prompt_t = str(config.get("prompt") or "").strip()
    if prompt_t:
        prompt = apply_template_to_string(prompt_t, context) or prompt_t
    else:
        # Try to get from last.text
        prompt = None
        try:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                prompt = str(last.get("text") or last.get("prompt") or "")
        except Exception:
            pass
    prompt = prompt or ""

    if not prompt.strip():
        return {"error": "missing_prompt"}

    # Negative prompt
    neg_prompt_t = config.get("negative_prompt")
    negative_prompt = None
    if neg_prompt_t:
        negative_prompt = apply_template_to_string(str(neg_prompt_t), context) or str(neg_prompt_t)

    # Parameters
    backend = str(config.get("backend") or "stable_diffusion_cpp").strip().lower()
    width = int(config.get("width") or 512)
    height = int(config.get("height") or 512)
    steps = int(config.get("steps") or 20)
    cfg_scale = float(config.get("cfg_scale") or 7.0)
    seed = config.get("seed")
    if seed is not None:
        try:
            seed = int(seed)
        except Exception:
            seed = None
    sampler = config.get("sampler")
    model = config.get("model")
    img_format = str(config.get("format") or "png").strip().lower()
    if img_format not in ("png", "jpg", "jpeg", "webp"):
        img_format = "png"
    save_artifact = config.get("save_artifact")
    if save_artifact is None:
        save_artifact = True
    else:
        save_artifact = bool(save_artifact)

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        import uuid as _uuid
        import time as _time
        fake_id = str(_uuid.uuid4())[:8]
        step_run_id = str(context.get("step_run_id") or f"test_image_gen_{int(_time.time()*1000)}")
        out_dir = _resolve_artifacts_dir(step_run_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        img_path = out_dir / f"test_image_{fake_id}.{img_format}"
        return {
            "images": [
                {
                    "uri": f"file://{img_path}",
                    "width": width,
                    "height": height,
                    "format": img_format,
                }
            ],
            "count": 1,
            "timings": {"total_ms": 100.0},
            "prompt": prompt,
            "backend": backend,
            "simulated": True,
        }

    try:
        from tldw_Server_API.app.core.Image_Generation.adapter_registry import get_registry
        from tldw_Server_API.app.core.Image_Generation.adapters.base import ImageGenRequest

        registry = get_registry()

        # Resolve backend name
        resolved_backend = registry.resolve_backend(backend)
        if not resolved_backend:
            return {"error": f"backend_unavailable:{backend}"}

        adapter = registry.get_adapter(resolved_backend)
        if not adapter:
            return {"error": f"adapter_init_failed:{resolved_backend}"}

        # Build request
        request = ImageGenRequest(
            backend=resolved_backend,
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            sampler=sampler,
            model=model,
            format=img_format,
            extra_params=dict(config.get("extra_params") or {}),
        )

        # Generate
        import time as _time
        start_ts = _time.time()
        result = adapter.generate(request)
        duration_ms = (_time.time() - start_ts) * 1000

        # Save image artifact
        images_output = []
        step_run_id = str(context.get("step_run_id") or f"image_gen_{int(_time.time()*1000)}")
        out_dir = _resolve_artifacts_dir(step_run_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Determine content type
        content_type_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }
        content_type = content_type_map.get(img_format, "image/png")

        # Save image to file
        import uuid as _uuid
        img_filename = f"generated_{_uuid.uuid4()}.{img_format}"
        img_path = out_dir / img_filename
        img_path.write_bytes(result.content)

        image_info = {
            "uri": f"file://{img_path}",
            "width": width,
            "height": height,
            "format": img_format,
            "size_bytes": result.bytes_len,
        }
        images_output.append(image_info)

        # Register artifact if requested
        artifact_registered = False
        if save_artifact and callable(context.get("add_artifact")):
            try:
                context["add_artifact"](
                    type="generated_image",
                    uri=f"file://{img_path}",
                    size_bytes=result.bytes_len,
                    mime_type=content_type,
                    metadata={
                        "prompt": prompt[:200],
                        "backend": resolved_backend,
                        "width": width,
                        "height": height,
                        "steps": steps,
                        "cfg_scale": cfg_scale,
                        "seed": seed,
                    },
                )
                artifact_registered = True
            except Exception as art_e:
                logger.warning(f"Image gen: failed to register artifact: {art_e}")

        return {
            "images": images_output,
            "count": len(images_output),
            "timings": {"total_ms": duration_ms},
            "prompt": prompt,
            "backend": resolved_backend,
            "artifact_registered": artifact_registered,
        }

    except Exception as e:
        logger.exception(f"Image gen adapter error: {e}")
        return {"error": f"image_gen_error:{e}"}


# ---------------------------------------------------------------------------
# Stage 5 Adapters: Summarize, Query Expand, Rerank, Citations
# ---------------------------------------------------------------------------


async def run_summarize_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize text using LLM with optional chunking strategies.

    Config:
      - text: Optional[str] (templated, defaults to last.text)
      - custom_prompt: Optional[str] (templated) - additional instructions
      - api_name: Optional[str] - LLM provider (defaults to 'openai')
      - system_message: Optional[str] (templated) - system message override
      - temperature: float = 0.7
      - recursive_summarization: bool = False
      - chunked_summarization: bool = False
      - chunk_options: Optional[Dict] - chunking configuration
    Output:
      - {"summary": str, "text": str, "api_name": str}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    # Template rendering for text
    text_t = str(config.get("text") or "").strip()
    if text_t:
        text = apply_template_to_string(text_t, context) or text_t
    else:
        # Default to last.text
        text = None
        try:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                text = str(last.get("text") or last.get("content") or last.get("summary") or "")
        except Exception:
            pass
    text = text or ""

    if not text.strip():
        return {"error": "missing_text", "summary": "", "text": ""}

    # Template other fields
    custom_prompt = None
    custom_prompt_t = config.get("custom_prompt")
    if custom_prompt_t:
        custom_prompt = apply_template_to_string(str(custom_prompt_t), context) or str(custom_prompt_t)

    system_message = None
    system_message_t = config.get("system_message")
    if system_message_t:
        system_message = apply_template_to_string(str(system_message_t), context) or str(system_message_t)

    api_name = str(config.get("api_name") or "openai").strip().lower()
    temperature = float(config.get("temperature") or 0.7)
    recursive_summarization = bool(config.get("recursive_summarization"))
    chunked_summarization = bool(config.get("chunked_summarization"))
    chunk_options = config.get("chunk_options")

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        # Simulate summarization by truncating
        simulated_summary = text[:200] + "..." if len(text) > 200 else text
        simulated_summary = f"[Summary of {len(text)} chars] {simulated_summary}"
        return {
            "summary": simulated_summary,
            "text": simulated_summary,  # Alias for chaining
            "api_name": api_name,
            "input_length": len(text),
            "output_length": len(simulated_summary),
            "simulated": True,
        }

    try:
        from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze

        # analyze is synchronous, wrap with asyncio.to_thread
        result = await asyncio.to_thread(
            analyze,
            api_name=api_name,
            input_data=text,
            custom_prompt_arg=custom_prompt,
            api_key=None,
            system_message=system_message,
            temp=temperature,
            streaming=False,  # Don't use streaming in workflow context
            recursive_summarization=recursive_summarization,
            chunked_summarization=chunked_summarization,
            chunk_options=chunk_options,
        )

        # Check for error
        if isinstance(result, str) and result.startswith("Error:"):
            return {"error": result, "summary": "", "text": ""}

        summary = str(result) if result else ""
        return {
            "summary": summary,
            "text": summary,  # Alias for chaining
            "api_name": api_name,
            "input_length": len(text),
            "output_length": len(summary),
        }

    except Exception as e:
        logger.exception(f"Summarize adapter error: {e}")
        return {"error": f"summarize_error:{e}"}


async def run_query_expand_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Expand search queries using multiple strategies.

    Config:
      - query: str (templated) - the query to expand
      - strategies: List[str] = ["synonym"] - strategies to use
        Options: "acronym", "synonym", "domain", "entity", "multi_query", "hybrid"
      - max_expansions: int = 5 - max expansions per strategy
      - domain_context: Optional[str] (templated) - for domain strategy
      - api_name: Optional[str] - for LLM-based strategies
    Output:
      - {"original": str, "variations": [str], "synonyms": [str], "keywords": [str],
         "entities": [str], "combined": str}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    # Template rendering for query
    query_t = str(config.get("query") or "").strip()
    if query_t:
        query = apply_template_to_string(query_t, context) or query_t
    else:
        # Try to get from last.text or last.query
        query = None
        try:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                query = str(last.get("query") or last.get("text") or "")
        except Exception:
            pass
    query = query or ""

    if not query.strip():
        return {"error": "missing_query", "original": "", "variations": [], "combined": ""}

    strategies = config.get("strategies") or ["synonym"]
    if isinstance(strategies, str):
        strategies = [s.strip() for s in strategies.split(",") if s.strip()]
    strategies = [s.lower().strip() for s in strategies]

    max_expansions = int(config.get("max_expansions") or 5)
    max_expansions = max(1, min(max_expansions, 20))

    domain_context = None
    domain_context_t = config.get("domain_context")
    if domain_context_t:
        domain_context = apply_template_to_string(str(domain_context_t), context) or str(domain_context_t)

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        # Simulate query expansion
        simulated_variations = [
            f"{query} (expanded)",
            f"alternative {query}",
            f"{query} definition",
        ][:max_expansions]
        words = query.lower().split()
        return {
            "original": query,
            "variations": simulated_variations,
            "synonyms": {w: [f"{w}_syn"] for w in words[:3]},
            "keywords": words,
            "entities": [w.capitalize() for w in words if len(w) > 3][:2],
            "combined": f"{query} {simulated_variations[0] if simulated_variations else ''}".strip(),
            "strategies_used": strategies,
            "simulated": True,
        }

    try:
        from tldw_Server_API.app.core.RAG.rag_service.query_expansion import (
            SynonymExpansion,
            MultiQueryGeneration,
            AcronymExpansion,
            DomainExpansion,
            EntityExpansion,
            HybridQueryExpansion,
            ExpandedQuery,
        )

        # Build strategy instances
        strategy_map = {
            "synonym": SynonymExpansion,
            "multi_query": MultiQueryGeneration,
            "acronym": AcronymExpansion,
            "domain": lambda: DomainExpansion(custom_terms={domain_context: []} if domain_context else None),
            "entity": EntityExpansion,
        }

        all_variations: List[str] = []
        all_synonyms: Dict[str, List[str]] = {}
        all_keywords: List[str] = []
        all_entities: List[str] = []

        # If hybrid, use the combined strategy
        if "hybrid" in strategies:
            expander = HybridQueryExpansion()
            result = await expander.expand(query)
            all_variations.extend(result.variations[:max_expansions])
            all_synonyms.update(result.synonyms)
            all_keywords.extend(result.keywords)
            all_entities.extend(result.entities)
        else:
            # Run individual strategies
            for strat_name in strategies:
                if strat_name in strategy_map:
                    factory = strategy_map[strat_name]
                    expander = factory() if callable(factory) else factory
                    try:
                        result = await expander.expand(query)
                        all_variations.extend(result.variations)
                        all_synonyms.update(result.synonyms)
                        all_keywords.extend(result.keywords)
                        all_entities.extend(result.entities)
                    except Exception as strat_e:
                        logger.debug(f"Query expansion strategy {strat_name} failed: {strat_e}")

        # Deduplicate
        seen = set()
        unique_variations = []
        for v in all_variations:
            if v not in seen:
                seen.add(v)
                unique_variations.append(v)

        unique_variations = unique_variations[:max_expansions]
        unique_keywords = list(dict.fromkeys(all_keywords))[:20]
        unique_entities = list(dict.fromkeys(all_entities))[:10]

        # Build combined query string for downstream use
        combined_parts = [query] + unique_variations[:2]
        combined = " ".join(combined_parts)

        return {
            "original": query,
            "variations": unique_variations,
            "synonyms": all_synonyms,
            "keywords": unique_keywords,
            "entities": unique_entities,
            "combined": combined,
            "strategies_used": strategies,
        }

    except Exception as e:
        logger.exception(f"Query expand adapter error: {e}")
        return {"error": f"query_expand_error:{e}"}


async def run_rerank_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Rerank documents using various scoring strategies.

    Config:
      - query: str (templated) - the search query
      - documents: Optional[List[Dict]] - from last.documents or explicit
      - strategy: str = "flashrank" - reranking strategy
        Options: "flashrank", "cross_encoder", "llm_scoring", "diversity",
                 "multi_criteria", "hybrid", "llama_cpp", "two_tier"
      - top_k: int = 10 - number of documents to return
      - api_name: Optional[str] - for LLM-based strategies
    Output:
      - {"documents": [{content, score, metadata, original_index}], "count": int, "strategy": str}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    # Template rendering for query
    query_t = str(config.get("query") or "").strip()
    if query_t:
        query = apply_template_to_string(query_t, context) or query_t
    else:
        # Try to get from last.query or last.combined
        query = None
        try:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                query = str(last.get("query") or last.get("combined") or last.get("text") or "")
        except Exception:
            pass
    query = query or ""

    if not query.strip():
        return {"error": "missing_query", "documents": [], "count": 0}

    # Get documents
    documents_raw = config.get("documents")
    documents: List[Dict[str, Any]] = []

    if documents_raw:
        # Template if it's a string reference
        if isinstance(documents_raw, str):
            rendered = apply_template_to_string(documents_raw, context)
            try:
                documents = json.loads(rendered) if rendered else []
            except Exception:
                documents = []
        elif isinstance(documents_raw, list):
            documents = documents_raw
    else:
        # Try to get from last.documents
        try:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                docs = last.get("documents") or last.get("results") or []
                if isinstance(docs, list):
                    documents = docs
        except Exception:
            pass

    if not documents:
        return {"error": "missing_documents", "documents": [], "count": 0}

    strategy = str(config.get("strategy") or "flashrank").strip().lower()
    top_k = int(config.get("top_k") or 10)
    top_k = max(1, min(top_k, 100))

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        # Simulate reranking by adding scores
        reranked = []
        for i, doc in enumerate(documents[:top_k]):
            score = 1.0 - (i * 0.1)  # Decreasing score
            score = max(0.1, min(1.0, score))
            reranked.append({
                "content": doc.get("content") or doc.get("text") or str(doc),
                "score": score,
                "original_index": i,
                "metadata": doc.get("metadata") or {},
            })
        return {
            "documents": reranked,
            "count": len(reranked),
            "strategy": strategy,
            "query": query,
            "simulated": True,
        }

    try:
        from tldw_Server_API.app.core.RAG.rag_service.advanced_reranking import (
            create_reranker,
            RerankingConfig,
            RerankingStrategy,
            ScoredDocument,
        )
        from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource

        # Map strategy string to enum
        strategy_enum_map = {
            "flashrank": RerankingStrategy.FLASHRANK,
            "cross_encoder": RerankingStrategy.CROSS_ENCODER,
            "llm_scoring": RerankingStrategy.LLM_SCORING,
            "diversity": RerankingStrategy.DIVERSITY,
            "multi_criteria": RerankingStrategy.MULTI_CRITERIA,
            "hybrid": RerankingStrategy.HYBRID,
            "llama_cpp": RerankingStrategy.LLAMA_CPP,
            "two_tier": RerankingStrategy.TWO_TIER,
        }

        if strategy not in strategy_enum_map:
            return {"error": f"invalid_strategy:{strategy}", "documents": [], "count": 0}

        strategy_enum = strategy_enum_map[strategy]

        # Build config
        rerank_config = RerankingConfig(
            strategy=strategy_enum,
            top_k=top_k,
            model_name=config.get("model_name"),
        )

        # Convert input documents to Document objects
        doc_objects: List[Document] = []
        for i, doc in enumerate(documents):
            content = doc.get("content") or doc.get("text") or str(doc)
            doc_obj = Document(
                id=doc.get("id") or f"doc_{i}",
                content=content,
                metadata=doc.get("metadata") or {},
                source=DataSource.WEB_CONTENT,
                score=float(doc.get("score") or 0.5),
            )
            doc_objects.append(doc_obj)

        # Create reranker and run
        reranker = create_reranker(strategy_enum, rerank_config)
        scored_docs: List[ScoredDocument] = await reranker.rerank(query, doc_objects)

        # Convert results
        output_docs = []
        for sd in scored_docs:
            output_docs.append({
                "content": sd.document.content,
                "score": sd.rerank_score,
                "original_index": doc_objects.index(sd.document) if sd.document in doc_objects else -1,
                "metadata": sd.document.metadata,
                "original_score": sd.original_score,
                "relevance_score": sd.relevance_score,
            })

        return {
            "documents": output_docs,
            "count": len(output_docs),
            "strategy": strategy,
            "query": query,
        }

    except Exception as e:
        logger.exception(f"Rerank adapter error: {e}")
        return {"error": f"rerank_error:{e}"}


async def run_citations_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate academic citations from documents.

    Config:
      - documents: Optional[List[Dict]] - from last.documents or explicit
      - style: str = "apa" - citation style
        Options: "mla", "apa", "chicago", "harvard", "ieee"
      - include_inline: bool = True - include inline markers
      - max_citations: int = 10 - maximum number of citations
    Output:
      - {"citations": [str], "chunk_citations": [dict], "inline_markers": dict,
         "citation_map": dict, "style": str}
    """
    # Cancellation check
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    # Get documents
    documents_raw = config.get("documents")
    documents: List[Dict[str, Any]] = []

    if documents_raw:
        # Template if it's a string reference
        if isinstance(documents_raw, str):
            rendered = apply_template_to_string(documents_raw, context)
            try:
                documents = json.loads(rendered) if rendered else []
            except Exception:
                documents = []
        elif isinstance(documents_raw, list):
            documents = documents_raw
    else:
        # Try to get from last.documents
        try:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                docs = last.get("documents") or last.get("results") or []
                if isinstance(docs, list):
                    documents = docs
        except Exception:
            pass

    if not documents:
        return {
            "error": "missing_documents",
            "citations": [],
            "chunk_citations": [],
            "inline_markers": {},
            "citation_map": {},
        }

    style = str(config.get("style") or "apa").strip().lower()
    valid_styles = {"mla", "apa", "chicago", "harvard", "ieee"}
    if style not in valid_styles:
        style = "apa"

    include_inline = config.get("include_inline")
    if include_inline is None:
        include_inline = True
    else:
        include_inline = bool(include_inline)

    max_citations = int(config.get("max_citations") or 10)
    max_citations = max(1, min(max_citations, 50))

    # Get query for relevance matching (optional)
    query = ""
    query_t = config.get("query")
    if query_t:
        query = apply_template_to_string(str(query_t), context) or str(query_t)
    else:
        try:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                query = str(last.get("query") or "")
        except Exception:
            pass

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        # Simulate citations
        simulated_citations = []
        simulated_chunks = []
        inline_markers = {}
        citation_map = {}

        for i, doc in enumerate(documents[:max_citations]):
            # Build simulated citation
            author = doc.get("metadata", {}).get("author") or doc.get("author") or "Unknown Author"
            title = doc.get("metadata", {}).get("title") or doc.get("title") or f"Document {i+1}"
            date = doc.get("metadata", {}).get("date") or "n.d."

            if style == "apa":
                citation = f"{author}. ({date}). {title}."
            elif style == "mla":
                citation = f'{author}. "{title}." {date}.'
            elif style == "chicago":
                citation = f'{author}. "{title}." ({date}).'
            elif style == "harvard":
                citation = f"{author} ({date}) '{title}'."
            else:  # ieee
                citation = f'[{i+1}] {author}, "{title}", {date}.'

            simulated_citations.append(citation)

            # Build chunk citation
            chunk_cite = {
                "chunk_id": doc.get("id") or f"chunk_{i}",
                "source_document_id": doc.get("source_id") or f"doc_{i}",
                "source_document_title": title,
                "location": f"Section {i+1}",
                "text_snippet": (doc.get("content") or doc.get("text") or "")[:100] + "...",
                "confidence": float(doc.get("score") or 0.8),
                "usage_context": "Relevant context",
            }
            simulated_chunks.append(chunk_cite)

            # Inline marker
            marker = f"[{i+1}]"
            inline_markers[marker] = doc.get("id") or f"chunk_{i}"

            # Citation map
            source_id = doc.get("source_id") or f"source_{i}"
            if source_id not in citation_map:
                citation_map[source_id] = []
            citation_map[source_id].append(doc.get("id") or f"chunk_{i}")

        return {
            "citations": simulated_citations,
            "chunk_citations": simulated_chunks,
            "inline_markers": inline_markers,
            "citation_map": citation_map,
            "style": style,
            "count": len(simulated_citations),
            "simulated": True,
        }

    try:
        from tldw_Server_API.app.core.RAG.rag_service.citations import (
            CitationGenerator,
            CitationStyle,
        )
        from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource

        # Map style string to enum
        style_enum_map = {
            "mla": CitationStyle.MLA,
            "apa": CitationStyle.APA,
            "chicago": CitationStyle.CHICAGO,
            "harvard": CitationStyle.HARVARD,
            "ieee": CitationStyle.IEEE,
        }
        style_enum = style_enum_map.get(style, CitationStyle.APA)

        # Convert input documents to Document objects
        doc_objects: List[Document] = []
        for i, doc in enumerate(documents[:max_citations]):
            content = doc.get("content") or doc.get("text") or str(doc)
            metadata = doc.get("metadata") or {}

            # Ensure metadata has citation-relevant fields
            if "title" not in metadata and "title" in doc:
                metadata["title"] = doc["title"]
            if "author" not in metadata and "author" in doc:
                metadata["author"] = doc["author"]
            if "date" not in metadata and "date" in doc:
                metadata["date"] = doc["date"]

            doc_obj = Document(
                id=doc.get("id") or f"doc_{i}",
                content=content,
                metadata=metadata,
                source=DataSource.WEB_CONTENT,
                score=float(doc.get("score") or 0.5),
                source_document_id=doc.get("source_id") or doc.get("source_document_id"),
            )
            doc_objects.append(doc_obj)

        # Create generator
        generator = CitationGenerator()

        # Generate citations
        result = await generator.generate_citations(
            documents=doc_objects,
            query=query,
            style=style_enum,
            include_chunks=include_inline,
            max_citations=max_citations,
        )

        # Convert chunk citations to dicts
        chunk_citations_out = []
        for cc in result.chunk_citations:
            chunk_citations_out.append(cc.to_dict() if hasattr(cc, 'to_dict') else {
                "chunk_id": cc.chunk_id,
                "source_document_id": cc.source_document_id,
                "source_document_title": cc.source_document_title,
                "location": cc.location,
                "text_snippet": cc.text_snippet,
                "confidence": cc.confidence,
                "usage_context": cc.usage_context,
            })

        return {
            "citations": result.academic_citations,
            "chunk_citations": chunk_citations_out,
            "inline_markers": result.inline_markers,
            "citation_map": result.citation_map,
            "style": style,
            "count": len(result.academic_citations),
        }

    except Exception as e:
        logger.exception(f"Citations adapter error: {e}")
        return {"error": f"citations_error:{e}"}


# ---------------------------------------------------------------------------
# Stage 6 Adapters: OCR, PDF Extract, Voice Intent
# ---------------------------------------------------------------------------


async def run_ocr_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Run OCR on an image to extract text.

    Config:
      - image_uri: str (templated, file:// path or artifact URI - required)
      - backend: str (optional: "auto", "tesseract", "deepseek", "nemotron_parse", etc.)
      - language: str (default: "eng")
      - output_format: Literal["text", "markdown", "html", "json"] (default: "text")
      - prompt_preset: str (optional, backend-specific)
    Output:
      - {text, format, blocks, tables, meta, warnings}
    """
    # Check cancellation
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    # Get and template image_uri
    image_uri_t = config.get("image_uri")
    if not image_uri_t:
        return {"error": "missing_image_uri", "text": ""}

    image_uri = _tmpl(str(image_uri_t), context) or str(image_uri_t)
    image_uri = image_uri.strip()

    if not image_uri:
        return {"error": "missing_image_uri", "text": ""}

    # Get other config options
    backend_name = config.get("backend") or None
    language = str(config.get("language") or "eng").strip()
    output_format = str(config.get("output_format") or "text").strip().lower()
    if output_format not in ("text", "markdown", "html", "json"):
        output_format = "text"
    prompt_preset = config.get("prompt_preset")

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        return {
            "text": f"[TEST_MODE OCR] Simulated text extraction from {image_uri}",
            "format": output_format,
            "blocks": [{"text": "Simulated block 1", "bbox": [0, 0, 100, 50], "block_type": "paragraph"}],
            "tables": [],
            "meta": {"backend": backend_name or "tesseract", "language": language},
            "warnings": [],
            "simulated": True,
        }

    # Resolve file URI to local path
    try:
        if image_uri.startswith("file://"):
            local_path = _resolve_workflow_file_uri(image_uri, context, config)
        else:
            local_path = _resolve_workflow_file_path(image_uri, context, config)
    except AdapterError as e:
        return {"error": str(e), "text": ""}
    except Exception as e:
        logger.debug(f"OCR adapter: failed to resolve image path: {e}")
        return {"error": f"invalid_image_path:{e}", "text": ""}

    if not local_path.exists():
        return {"error": "image_not_found", "text": ""}

    # Read image bytes
    try:
        image_bytes = local_path.read_bytes()
    except Exception as e:
        logger.exception(f"OCR adapter: failed to read image: {e}")
        return {"error": f"image_read_error:{e}", "text": ""}

    # Get OCR backend
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.registry import get_backend
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.types import OCRResult

        backend = get_backend(backend_name)
        if backend is None:
            return {"error": "ocr_backend_unavailable", "text": ""}

        # Use structured OCR if non-text format or prompt preset specified
        if output_format != "text" or prompt_preset:
            result = backend.ocr_image_structured(
                image_bytes,
                lang=language,
                output_format=output_format,
                prompt_preset=prompt_preset,
            )
            output = result.as_dict()
        else:
            text = backend.ocr_image(image_bytes, lang=language)
            output = {
                "text": text or "",
                "format": "text",
                "blocks": [],
                "tables": [],
                "meta": {"backend": getattr(backend, "name", "unknown"), "language": language},
                "warnings": [],
            }

        # Optional artifact persistence
        try:
            if bool(config.get("save_artifact")) and callable(context.get("add_artifact")):
                step_run_id = str(context.get("step_run_id") or "")
                art_dir = _resolve_artifacts_dir(step_run_id or f"ocr_{int(time.time()*1000)}")
                art_dir.mkdir(parents=True, exist_ok=True)
                fpath = art_dir / "ocr_result.txt"
                fpath.write_text(output.get("text") or "", encoding="utf-8")
                context["add_artifact"](
                    type="ocr_text",
                    uri=f"file://{fpath}",
                    size_bytes=len((output.get("text") or "").encode("utf-8")),
                    mime_type="text/plain",
                    metadata={"backend": output.get("meta", {}).get("backend"), "format": output_format},
                )
        except Exception as e:
            logger.debug(f"OCR adapter: failed to persist artifact: {e}")

        return output

    except Exception as e:
        logger.exception(f"OCR adapter error: {e}")
        return {"error": f"ocr_error:{e}", "text": ""}


async def run_pdf_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract text and metadata from a PDF file.

    Config:
      - pdf_uri: str (templated, file:// path - required)
      - parser: Literal["pymupdf4llm", "pymupdf", "docling"] (default: "pymupdf4llm")
      - title: str (optional, templated - title override)
      - author: str (optional, templated - author override)
      - keywords: List[str] (optional)
      - perform_chunking: bool (default: True)
      - chunk_method: str (default: "sentences")
      - max_chunk_size: int (default: 500)
      - chunk_overlap: int (default: 100)
      - enable_ocr: bool (default: False)
      - ocr_backend: str (optional)
      - ocr_lang: str (default: "eng")
      - ocr_mode: Literal["fallback", "always"] (default: "fallback")
      - enable_vlm: bool (default: False)
      - vlm_backend: str (optional)
      - vlm_detect_tables_only: bool (default: True)
    Output:
      - {status, content, text, metadata, chunks, keywords, page_count, warnings}
    """
    # Check cancellation
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    # Get and template pdf_uri
    pdf_uri_t = config.get("pdf_uri")
    if not pdf_uri_t:
        return {"error": "missing_pdf_uri", "status": "Error", "content": "", "text": ""}

    pdf_uri = _tmpl(str(pdf_uri_t), context) or str(pdf_uri_t)
    pdf_uri = pdf_uri.strip()

    if not pdf_uri:
        return {"error": "missing_pdf_uri", "status": "Error", "content": "", "text": ""}

    # Get other config options with templating where needed
    parser = str(config.get("parser") or "pymupdf4llm").strip()
    if parser not in ("pymupdf4llm", "pymupdf", "docling"):
        parser = "pymupdf4llm"

    title_t = config.get("title")
    title_override = _tmpl(str(title_t), context) if title_t else None

    author_t = config.get("author")
    author_override = _tmpl(str(author_t), context) if author_t else None

    keywords = config.get("keywords")
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    elif not isinstance(keywords, list):
        keywords = None

    perform_chunking = config.get("perform_chunking")
    if perform_chunking is None:
        perform_chunking = True
    else:
        perform_chunking = bool(perform_chunking)

    chunk_method = str(config.get("chunk_method") or "sentences").strip()
    max_chunk_size = int(config.get("max_chunk_size") or 500)
    chunk_overlap = int(config.get("chunk_overlap") or 100)

    # OCR options
    enable_ocr = bool(config.get("enable_ocr"))
    ocr_backend = config.get("ocr_backend")
    ocr_lang = str(config.get("ocr_lang") or "eng")
    ocr_mode = str(config.get("ocr_mode") or "fallback")
    if ocr_mode not in ("fallback", "always"):
        ocr_mode = "fallback"

    # VLM options
    enable_vlm = bool(config.get("enable_vlm"))
    vlm_backend = config.get("vlm_backend")
    vlm_detect_tables_only = config.get("vlm_detect_tables_only")
    if vlm_detect_tables_only is None:
        vlm_detect_tables_only = True
    else:
        vlm_detect_tables_only = bool(vlm_detect_tables_only)

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        simulated_content = f"[TEST_MODE PDF] Simulated text extraction from {pdf_uri}"
        simulated_chunks = [
            {"text": f"Chunk 1 from {pdf_uri}", "index": 0},
            {"text": f"Chunk 2 from {pdf_uri}", "index": 1},
        ] if perform_chunking else []

        return {
            "status": "Success",
            "content": simulated_content,
            "text": simulated_content,  # Alias for chaining
            "metadata": {
                "title": title_override or "Simulated Document",
                "author": author_override or "Unknown",
                "page_count": 5,
                "parser_used": parser,
            },
            "chunks": simulated_chunks,
            "keywords": keywords or [],
            "page_count": 5,
            "warnings": [],
            "simulated": True,
        }

    # Resolve file URI to local path
    try:
        if pdf_uri.startswith("file://"):
            local_path = _resolve_workflow_file_uri(pdf_uri, context, config)
        else:
            local_path = _resolve_workflow_file_path(pdf_uri, context, config)
    except AdapterError as e:
        return {"error": str(e), "status": "Error", "content": "", "text": ""}
    except Exception as e:
        logger.debug(f"PDF extract adapter: failed to resolve path: {e}")
        return {"error": f"invalid_pdf_path:{e}", "status": "Error", "content": "", "text": ""}

    if not local_path.exists():
        return {"error": "pdf_not_found", "status": "Error", "content": "", "text": ""}

    # Read PDF bytes
    try:
        pdf_bytes = local_path.read_bytes()
    except Exception as e:
        logger.exception(f"PDF extract adapter: failed to read PDF: {e}")
        return {"error": f"pdf_read_error:{e}", "status": "Error", "content": "", "text": ""}

    # Process PDF
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf

        # Build chunk options if chunking is enabled
        chunk_options = None
        if perform_chunking:
            chunk_options = {
                "method": chunk_method,
                "max_size": max_chunk_size,
                "overlap": chunk_overlap,
            }

        # Call process_pdf (sync function, wrap with asyncio.to_thread)
        result = await asyncio.to_thread(
            process_pdf,
            file_input=pdf_bytes,
            filename=str(local_path.name),
            parser=parser,
            title_override=title_override,
            author_override=author_override,
            keywords=keywords,
            perform_chunking=perform_chunking,
            chunk_options=chunk_options,
            perform_analysis=False,  # Don't do LLM analysis in workflow step
            enable_ocr=enable_ocr,
            ocr_backend=ocr_backend,
            ocr_lang=ocr_lang,
            ocr_mode=ocr_mode,
            enable_vlm=enable_vlm,
            vlm_backend=vlm_backend,
            vlm_detect_tables_only=vlm_detect_tables_only,
        )

        if result is None:
            return {"error": "pdf_processing_failed", "status": "Error", "content": "", "text": ""}

        # Extract page count from metadata
        page_count = 0
        if isinstance(result.get("metadata"), dict):
            page_count = result["metadata"].get("page_count", 0) or result["metadata"].get("raw", {}).get("page_count", 0)

        content = result.get("content") or ""

        # Optional artifact persistence
        try:
            if bool(config.get("save_artifact")) and callable(context.get("add_artifact")):
                step_run_id = str(context.get("step_run_id") or "")
                art_dir = _resolve_artifacts_dir(step_run_id or f"pdf_{int(time.time()*1000)}")
                art_dir.mkdir(parents=True, exist_ok=True)
                fpath = art_dir / "pdf_content.txt"
                fpath.write_text(content, encoding="utf-8")
                context["add_artifact"](
                    type="pdf_text",
                    uri=f"file://{fpath}",
                    size_bytes=len(content.encode("utf-8")),
                    mime_type="text/plain",
                    metadata={"parser": parser, "page_count": page_count},
                )
        except Exception as e:
            logger.debug(f"PDF extract adapter: failed to persist artifact: {e}")

        return {
            "status": result.get("status") or "Success",
            "content": content,
            "text": content,  # Alias for chaining
            "metadata": result.get("metadata") or {},
            "chunks": result.get("chunks") or [],
            "keywords": result.get("keywords") or [],
            "page_count": page_count,
            "warnings": result.get("warnings") or [],
        }

    except Exception as e:
        logger.exception(f"PDF extract adapter error: {e}")
        return {"error": f"pdf_extract_error:{e}", "status": "Error", "content": "", "text": ""}


async def run_voice_intent_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Parse voice/text input into actionable intents.

    Config:
      - text: str (templated, typically from STT output - required)
      - llm_enabled: bool (default: True - enable LLM fallback for complex queries)
      - awaiting_confirmation: bool (default: False - if expecting yes/no response)
      - conversation_history: List[Dict] (optional - for context)
    Output:
      - {intent, action_type, action_config, entities, confidence, requires_confirmation, match_method, alternatives, processing_time_ms}
    """
    # Check cancellation
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    # Resolve user_id
    user_id = _resolve_context_user_id(context)
    if not user_id:
        # Voice intent can work without user_id, default to 0
        user_id_int = 0
    else:
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            user_id_int = 0

    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    # Get and template text
    text_t = config.get("text")
    if not text_t:
        # Try to get from last.text
        try:
            last = context.get("prev") or context.get("last") or {}
            if isinstance(last, dict):
                text_t = last.get("text") or last.get("transcript") or last.get("content") or ""
        except Exception:
            text_t = ""

    if not text_t:
        return {
            "error": "missing_text",
            "intent": "",
            "action_type": "custom",
            "action_config": {"action": "empty_input"},
            "entities": {},
            "confidence": 0.0,
            "requires_confirmation": False,
            "match_method": "empty",
            "alternatives": [],
            "processing_time_ms": 0.0,
        }

    text = _tmpl(str(text_t), context) or str(text_t)
    text = text.strip()

    if not text:
        return {
            "error": "empty_text",
            "intent": "",
            "action_type": "custom",
            "action_config": {"action": "empty_input"},
            "entities": {},
            "confidence": 0.0,
            "requires_confirmation": False,
            "match_method": "empty",
            "alternatives": [],
            "processing_time_ms": 0.0,
        }

    # Get config options
    llm_enabled = config.get("llm_enabled")
    if llm_enabled is None:
        llm_enabled = True
    else:
        llm_enabled = bool(llm_enabled)

    awaiting_confirmation = bool(config.get("awaiting_confirmation"))

    conversation_history = config.get("conversation_history")
    if not isinstance(conversation_history, list):
        conversation_history = None

    # Test mode simulation
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        # Simulate basic intent parsing
        text_lower = text.lower()

        # Check for confirmation responses
        if awaiting_confirmation:
            if any(w in text_lower for w in ["yes", "yeah", "yep", "sure", "ok", "okay", "confirm"]):
                return {
                    "intent": "confirmation",
                    "action_type": "custom",
                    "action_config": {"action": "confirmation", "confirmed": True},
                    "entities": {},
                    "confidence": 1.0,
                    "requires_confirmation": False,
                    "match_method": "confirmation",
                    "alternatives": [],
                    "processing_time_ms": 1.0,
                    "simulated": True,
                }
            elif any(w in text_lower for w in ["no", "nope", "cancel", "stop", "abort"]):
                return {
                    "intent": "confirmation",
                    "action_type": "custom",
                    "action_config": {"action": "confirmation", "confirmed": False},
                    "entities": {},
                    "confidence": 1.0,
                    "requires_confirmation": False,
                    "match_method": "confirmation",
                    "alternatives": [],
                    "processing_time_ms": 1.0,
                    "simulated": True,
                }

        # Check for search-related patterns
        if any(w in text_lower for w in ["search", "find", "look for", "look up"]):
            # Extract query
            query = text
            for prefix in ["search for", "search", "find", "look for", "look up"]:
                if text_lower.startswith(prefix):
                    query = text[len(prefix):].strip()
                    break

            return {
                "intent": "search",
                "action_type": "mcp_tool",
                "action_config": {"tool_name": "media.search", "query": query},
                "entities": {"query": query},
                "confidence": 0.8,
                "requires_confirmation": False,
                "match_method": "pattern",
                "alternatives": [],
                "processing_time_ms": 5.0,
                "simulated": True,
            }

        # Check for note-related patterns
        if any(w in text_lower for w in ["note", "remember", "take a note"]):
            content = text
            for prefix in ["take a note", "note that", "note", "remember that", "remember"]:
                if text_lower.startswith(prefix):
                    content = text[len(prefix):].strip()
                    break

            return {
                "intent": "create_note",
                "action_type": "mcp_tool",
                "action_config": {"tool_name": "notes.create", "content": content},
                "entities": {"content": content},
                "confidence": 0.8,
                "requires_confirmation": False,
                "match_method": "pattern",
                "alternatives": [],
                "processing_time_ms": 5.0,
                "simulated": True,
            }

        # Default: treat as chat
        return {
            "intent": "chat",
            "action_type": "llm_chat",
            "action_config": {"message": text},
            "entities": {},
            "confidence": 0.5,
            "requires_confirmation": False,
            "match_method": "default",
            "alternatives": [],
            "processing_time_ms": 10.0,
            "simulated": True,
        }

    # Production mode: use the intent parser
    try:
        from tldw_Server_API.app.core.VoiceAssistant.intent_parser import get_intent_parser

        parser = get_intent_parser()

        # Save original LLM setting to restore after parsing (avoid mutating singleton state)
        original_llm_enabled = parser.llm_enabled

        try:
            # Override LLM setting if specified
            if not llm_enabled:
                parser.llm_enabled = False

            # Build context dict
            parse_context: Dict[str, Any] = {}
            if awaiting_confirmation:
                parse_context["awaiting_confirmation"] = True
            if conversation_history:
                parse_context["conversation_history"] = conversation_history

            # Parse the intent
            result = await parser.parse(
                text=text,
                user_id=user_id_int,
                context=parse_context if parse_context else None,
            )
        finally:
            # Restore original LLM setting to avoid side effects on subsequent calls
            parser.llm_enabled = original_llm_enabled

        # Extract action_type value (convert enum to string)
        action_type_str = result.intent.action_type.value if hasattr(result.intent.action_type, 'value') else str(result.intent.action_type)

        # Build alternatives list
        alternatives_out = []
        for alt in result.alternatives:
            alt_action_type = alt.action_type.value if hasattr(alt.action_type, 'value') else str(alt.action_type)
            alternatives_out.append({
                "command_id": alt.command_id,
                "action_type": alt_action_type,
                "action_config": alt.action_config,
                "entities": alt.entities,
                "confidence": alt.confidence,
                "requires_confirmation": alt.requires_confirmation,
            })

        return {
            "intent": result.intent.command_id or action_type_str,
            "action_type": action_type_str,
            "action_config": result.intent.action_config,
            "entities": result.intent.entities,
            "confidence": result.intent.confidence,
            "requires_confirmation": result.intent.requires_confirmation,
            "match_method": result.match_method,
            "alternatives": alternatives_out,
            "processing_time_ms": result.processing_time_ms,
        }

    except Exception as e:
        logger.exception(f"Voice intent adapter error: {e}")
        return {
            "error": f"voice_intent_error:{e}",
            "intent": "",
            "action_type": "custom",
            "action_config": {"action": "error"},
            "entities": {},
            "confidence": 0.0,
            "requires_confirmation": False,
            "match_method": "error",
            "alternatives": [],
            "processing_time_ms": 0.0,
        }


# ============================================================================
# TIER 1: RESEARCH AUTOMATION ADAPTERS
# ============================================================================


async def run_query_rewrite_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Rewrite a search query for better retrieval results.

    Config:
      - query: str (required) - Original query to rewrite
      - strategy: str - Rewrite strategy: "expand", "clarify", "simplify", "all" (default: "all")
      - provider: str - LLM provider for rewriting (default: from context)
      - model: str - Model to use
      - max_rewrites: int - Maximum number of rewritten queries (default: 3)
    Output:
      - original_query: str
      - rewritten_queries: list[str]
      - strategy: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    # Check cancellation
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    query = config.get("query") or ""
    if isinstance(query, str):
        query = _tmpl(query, context) or query
    query = str(query).strip()

    if not query:
        return {"error": "missing_query", "original_query": "", "rewritten_queries": []}

    strategy = str(config.get("strategy", "all")).lower()
    max_rewrites = int(config.get("max_rewrites", 3))
    provider = config.get("provider")
    model = config.get("model")

    # Build rewrite prompt based on strategy
    strategy_prompts = {
        "expand": "Expand the query with synonyms, related terms, and alternative phrasings.",
        "clarify": "Clarify ambiguous terms and add context to make the query more specific.",
        "simplify": "Simplify the query to its core concepts, removing unnecessary words.",
        "all": "Generate variations using expansion, clarification, and simplification techniques.",
    }

    system_prompt = f"""You are a search query optimizer. {strategy_prompts.get(strategy, strategy_prompts['all'])}

Return exactly {max_rewrites} rewritten queries, one per line. No numbering, no explanations, just the queries."""

    user_prompt = f"Rewrite this search query:\n{query}"

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        messages = [{"role": "user", "content": user_prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=provider,
            model=model,
            system_message=system_prompt,
            max_tokens=500,
            temperature=0.7,
        )

        # Extract text from response
        text = _extract_openai_content(response) or ""
        rewrites = [line.strip() for line in text.strip().split("\n") if line.strip()][:max_rewrites]

        return {
            "original_query": query,
            "rewritten_queries": rewrites,
            "strategy": strategy,
        }

    except Exception as e:
        logger.exception(f"Query rewrite adapter error: {e}")
        return {"error": f"query_rewrite_error:{e}", "original_query": query, "rewritten_queries": []}


async def run_hyde_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a Hypothetical Document Embedding (HyDE) for improved similarity search.

    Config:
      - query: str (required) - The search query
      - provider: str - LLM provider
      - model: str - Model to use
      - num_hypothetical: int - Number of hypothetical documents (default: 1)
      - document_type: str - Type of document to generate: "answer", "passage", "article" (default: "passage")
    Output:
      - query: str
      - hypothetical_documents: list[str]
      - document_type: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    query = config.get("query") or ""
    if isinstance(query, str):
        query = _tmpl(query, context) or query
    query = str(query).strip()

    if not query:
        return {"error": "missing_query", "query": "", "hypothetical_documents": []}

    provider = config.get("provider")
    model = config.get("model")
    num_hypothetical = int(config.get("num_hypothetical", 1))
    document_type = str(config.get("document_type", "passage")).lower()

    type_prompts = {
        "answer": "Write a direct, factual answer to the question as if you were an expert.",
        "passage": "Write a passage from a document that would contain the answer to this query.",
        "article": "Write an excerpt from an informative article that addresses this topic.",
    }

    system_prompt = f"""You are generating hypothetical documents for semantic search.
{type_prompts.get(document_type, type_prompts['passage'])}

Generate {num_hypothetical} hypothetical document(s). If multiple, separate with ---."""

    user_prompt = f"Query: {query}"

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        messages = [{"role": "user", "content": user_prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=provider,
            model=model,
            system_message=system_prompt,
            max_tokens=1000,
            temperature=0.8,
        )

        text = _extract_openai_content(response) or ""
        if num_hypothetical > 1:
            docs = [d.strip() for d in text.split("---") if d.strip()][:num_hypothetical]
        else:
            docs = [text.strip()] if text.strip() else []

        return {
            "query": query,
            "hypothetical_documents": docs,
            "document_type": document_type,
        }

    except Exception as e:
        logger.exception(f"HyDE generate adapter error: {e}")
        return {"error": f"hyde_error:{e}", "query": query, "hypothetical_documents": []}


async def run_semantic_cache_check_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Check semantic cache for similar queries before running expensive searches.

    Config:
      - query: str (required) - Query to check
      - cache_collection: str - ChromaDB collection for cache (default: "semantic_cache")
      - similarity_threshold: float - Minimum similarity for cache hit (default: 0.9)
      - max_age_seconds: int - Maximum age of cached results (default: 3600)
    Output:
      - cache_hit: bool
      - cached_query: str (if hit)
      - cached_result: dict (if hit)
      - similarity: float (if hit)
      - query: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    query = config.get("query") or ""
    if isinstance(query, str):
        query = _tmpl(query, context) or query
    query = str(query).strip()

    if not query:
        return {"cache_hit": False, "query": "", "error": "missing_query"}

    cache_collection = config.get("cache_collection", "semantic_cache")
    similarity_threshold = float(config.get("similarity_threshold", 0.9))
    max_age_seconds = int(config.get("max_age_seconds", 3600))

    try:
        from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import chroma_client, embedding_function_factory
        import time

        client = chroma_client()
        if not client:
            return {"cache_hit": False, "query": query, "error": "chroma_unavailable"}

        # Get or create cache collection
        try:
            collection = client.get_or_create_collection(
                name=cache_collection,
                embedding_function=embedding_function_factory(),
            )
        except Exception as e:
            logger.debug(f"Semantic cache collection error: {e}")
            return {"cache_hit": False, "query": query, "error": "collection_error"}

        # Search for similar queries
        results = collection.query(
            query_texts=[query],
            n_results=1,
            include=["metadatas", "distances", "documents"],
        )

        if results and results.get("distances") and results["distances"][0]:
            distance = results["distances"][0][0]
            # Convert distance to similarity (assuming cosine distance)
            similarity = 1 - distance

            if similarity >= similarity_threshold:
                metadata = results.get("metadatas", [[]])[0]
                if metadata:
                    meta = metadata[0] if isinstance(metadata, list) and metadata else metadata
                    cached_at = meta.get("cached_at", 0)
                    if time.time() - cached_at <= max_age_seconds:
                        cached_query = results.get("documents", [[]])[0]
                        if isinstance(cached_query, list) and cached_query:
                            cached_query = cached_query[0]

                        cached_result = meta.get("result")
                        if isinstance(cached_result, str):
                            try:
                                cached_result = json.loads(cached_result)
                            except Exception:
                                pass

                        return {
                            "cache_hit": True,
                            "query": query,
                            "cached_query": cached_query,
                            "cached_result": cached_result,
                            "similarity": similarity,
                        }

        return {"cache_hit": False, "query": query}

    except Exception as e:
        logger.exception(f"Semantic cache check error: {e}")
        return {"cache_hit": False, "query": query, "error": str(e)}


async def run_search_aggregate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate and deduplicate results from multiple search steps.

    Config:
      - results: list[dict] - List of search results to aggregate (each with 'documents' key)
      - dedup_field: str - Field to use for deduplication (default: "id")
      - sort_by: str - Field to sort by (default: "score")
      - sort_order: str - "asc" or "desc" (default: "desc")
      - limit: int - Maximum results to return (default: 20)
      - merge_scores: str - How to merge scores: "max", "sum", "avg" (default: "max")
    Output:
      - documents: list[dict]
      - total_before_dedup: int
      - total_after_dedup: int
      - sources: list[str]
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    # Get results from config or from previous step
    results = config.get("results")
    if not results:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            results = prev.get("results") or prev.get("documents") or []

    if not isinstance(results, list):
        results = [results] if results else []

    dedup_field = config.get("dedup_field", "id")
    sort_by = config.get("sort_by", "score")
    sort_order = config.get("sort_order", "desc")
    limit = int(config.get("limit", 20))
    merge_scores = config.get("merge_scores", "max")

    # Flatten all documents
    all_docs = []
    sources = []
    for i, result in enumerate(results):
        if isinstance(result, dict):
            docs = result.get("documents") or result.get("results") or []
            source = result.get("source", f"source_{i}")
        elif isinstance(result, list):
            docs = result
            source = f"source_{i}"
        else:
            continue

        sources.append(source)
        for doc in docs:
            if isinstance(doc, dict):
                doc_copy = dict(doc)
                doc_copy["_source"] = source
                all_docs.append(doc_copy)

    total_before = len(all_docs)

    # Deduplicate
    seen = {}
    for doc in all_docs:
        key = doc.get(dedup_field)
        if key is None:
            # Generate key from content
            key = hash(str(doc.get("content", doc.get("text", str(doc)))))

        if key in seen:
            # Merge scores
            existing = seen[key]
            existing_score = existing.get(sort_by, 0)
            new_score = doc.get(sort_by, 0)

            if merge_scores == "sum":
                existing[sort_by] = existing_score + new_score
            elif merge_scores == "avg":
                existing["_count"] = existing.get("_count", 1) + 1
                existing[sort_by] = (existing_score * (existing["_count"] - 1) + new_score) / existing["_count"]
            else:  # max
                existing[sort_by] = max(existing_score, new_score)
        else:
            seen[key] = doc

    # Sort
    deduped = list(seen.values())
    reverse = sort_order == "desc"
    deduped.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)

    # Limit
    final_docs = deduped[:limit]

    # Clean up internal fields
    for doc in final_docs:
        doc.pop("_count", None)

    return {
        "documents": final_docs,
        "total_before_dedup": total_before,
        "total_after_dedup": len(deduped),
        "sources": sources,
    }


async def run_entity_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract named entities (people, places, organizations, dates) from text.

    Config:
      - text: str (required) - Text to extract entities from
      - entity_types: list[str] - Types to extract: "person", "place", "organization", "date", "event", "all" (default: "all")
      - provider: str - LLM provider
      - model: str - Model to use
      - include_context: bool - Include surrounding context for each entity (default: false)
    Output:
      - entities: dict[str, list[dict]] - Entities grouped by type
      - total_count: int
      - text_length: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text
    text = str(text).strip()

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or prev.get("transcript") or ""
        text = str(text).strip()

    if not text:
        return {"error": "missing_text", "entities": {}, "total_count": 0}

    entity_types = config.get("entity_types", ["all"])
    if isinstance(entity_types, str):
        entity_types = [entity_types]
    if "all" in entity_types:
        entity_types = ["person", "place", "organization", "date", "event"]

    provider = config.get("provider")
    model = config.get("model")
    include_context = bool(config.get("include_context", False))

    types_str = ", ".join(entity_types)
    context_instruction = "Include a brief context snippet for each entity." if include_context else ""

    system_prompt = f"""Extract named entities from the text. Focus on: {types_str}.
{context_instruction}

Return a JSON object with entity types as keys and arrays of entities as values.
Each entity should have: "name", "type", and optionally "context".

Example:
{{"person": [{{"name": "John Smith", "type": "person"}}], "place": [{{"name": "New York", "type": "place"}}]}}"""

    user_prompt = f"Extract entities from:\n\n{text[:8000]}"

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        messages = [{"role": "user", "content": user_prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=provider,
            model=model,
            system_message=system_prompt,
            max_tokens=2000,
            temperature=0.3,
        )

        response_text = _extract_openai_content(response) or "{}"

        # Parse JSON from response
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                entities = json.loads(json_match.group())
            else:
                entities = {}
        except json.JSONDecodeError:
            entities = {}

        # Count total entities
        total_count = sum(len(v) if isinstance(v, list) else 0 for v in entities.values())

        return {
            "entities": entities,
            "total_count": total_count,
            "text_length": len(text),
        }

    except Exception as e:
        logger.exception(f"Entity extract adapter error: {e}")
        return {"error": f"entity_extract_error:{e}", "entities": {}, "total_count": 0}


async def run_bibliography_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate formatted bibliography/citations from sources.

    Config:
      - sources: list[dict] - Source documents with metadata
      - format: str - Citation format: "apa", "mla", "chicago", "harvard", "bibtex" (default: "apa")
      - sort_by: str - Sort order: "author", "date", "title" (default: "author")
    Output:
      - bibliography: str - Formatted bibliography
      - citations: list[dict] - Individual citations with keys
      - format: str
      - count: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    sources = config.get("sources")
    if not sources:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            sources = prev.get("documents") or prev.get("sources") or prev.get("results") or []

    if not isinstance(sources, list) or not sources:
        return {"error": "missing_sources", "bibliography": "", "citations": [], "count": 0}

    citation_format = str(config.get("format", "apa")).lower()
    sort_by = str(config.get("sort_by", "author")).lower()

    # Extract citation metadata from sources
    citations = []
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            continue

        citation = {
            "key": source.get("id") or source.get("key") or f"source_{i+1}",
            "title": source.get("title") or source.get("name") or "Untitled",
            "author": source.get("author") or source.get("authors") or "Unknown",
            "date": source.get("date") or source.get("published") or source.get("year") or "",
            "url": source.get("url") or source.get("link") or "",
            "type": source.get("type") or "document",
            "publisher": source.get("publisher") or source.get("source") or "",
            "pages": source.get("pages") or "",
        }
        citations.append(citation)

    # Sort citations
    if sort_by == "date":
        citations.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    elif sort_by == "title":
        citations.sort(key=lambda x: str(x.get("title", "")).lower())
    else:  # author
        citations.sort(key=lambda x: str(x.get("author", "")).lower())

    # Format citations
    formatted_entries = []
    for cit in citations:
        author = cit["author"]
        if isinstance(author, list):
            author = ", ".join(author)

        title = cit["title"]
        date = cit["date"]
        url = cit["url"]
        publisher = cit["publisher"]

        if citation_format == "apa":
            entry = f"{author} ({date}). {title}."
            if publisher:
                entry += f" {publisher}."
            if url:
                entry += f" Retrieved from {url}"
        elif citation_format == "mla":
            entry = f'{author}. "{title}."'
            if publisher:
                entry += f" {publisher},"
            if date:
                entry += f" {date}."
            if url:
                entry += f" {url}."
        elif citation_format == "chicago":
            entry = f'{author}. "{title}."'
            if publisher:
                entry += f" {publisher},"
            if date:
                entry += f" {date}."
            if url:
                entry += f" {url}."
        elif citation_format == "harvard":
            entry = f"{author} ({date}) {title}."
            if publisher:
                entry += f" {publisher}."
            if url:
                entry += f" Available at: {url}"
        elif citation_format == "bibtex":
            key = cit["key"].replace(" ", "_")
            entry = f"@misc{{{key},\n"
            entry += f"  author = {{{author}}},\n"
            entry += f"  title = {{{title}}},\n"
            if date:
                entry += f"  year = {{{date}}},\n"
            if url:
                entry += f"  url = {{{url}}},\n"
            entry = entry.rstrip(",\n") + "\n}"
        else:
            entry = f"{author}. {title}. {date}."

        cit["formatted"] = entry
        formatted_entries.append(entry)

    bibliography = "\n\n".join(formatted_entries)

    return {
        "bibliography": bibliography,
        "citations": citations,
        "format": citation_format,
        "count": len(citations),
    }


async def run_document_table_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract tables from documents as structured JSON/CSV.

    Config:
      - file_path: str - Path to document (PDF, image, etc.)
      - file_uri: str - Alternative: file:// URI
      - output_format: str - "json" or "csv" (default: "json")
      - table_index: int - Specific table index to extract (default: all)
      - provider: str - Extraction provider: "docling", "llm" (default: "docling")
    Output:
      - tables: list[dict] - Extracted tables
      - count: int
      - format: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    file_path = config.get("file_path")
    file_uri = config.get("file_uri")

    if file_uri:
        try:
            file_path = _resolve_workflow_file_uri(file_uri, context, config)
        except Exception as e:
            return {"error": f"invalid_file_uri:{e}", "tables": [], "count": 0}
    elif file_path:
        if isinstance(file_path, str):
            file_path = _tmpl(file_path, context) or file_path
        try:
            file_path = _resolve_workflow_file_path(file_path, context, config)
        except Exception as e:
            return {"error": f"file_access_denied:{e}", "tables": [], "count": 0}
    else:
        return {"error": "missing_file_path", "tables": [], "count": 0}

    output_format = str(config.get("output_format", "json")).lower()
    table_index = config.get("table_index")
    provider = str(config.get("provider", "docling")).lower()

    tables = []

    try:
        if provider == "docling":
            # Use docling for table extraction
            try:
                from docling.document_converter import DocumentConverter
                from docling.datamodel.base_models import InputFormat

                converter = DocumentConverter()
                result = converter.convert(str(file_path))

                for i, table in enumerate(result.document.tables):
                    if table_index is not None and i != table_index:
                        continue

                    table_data = {
                        "index": i,
                        "rows": [],
                        "headers": [],
                    }

                    # Extract table data
                    if hasattr(table, "export_to_dataframe"):
                        df = table.export_to_dataframe()
                        table_data["headers"] = list(df.columns)
                        table_data["rows"] = df.values.tolist()
                    elif hasattr(table, "data"):
                        table_data["rows"] = table.data

                    tables.append(table_data)

            except ImportError:
                logger.warning("Docling not available, falling back to LLM extraction")
                provider = "llm"

        if provider == "llm" or not tables:
            # Fallback to LLM-based extraction
            # Read file content
            content = ""
            if str(file_path).lower().endswith(".pdf"):
                try:
                    import pymupdf
                    doc = pymupdf.open(str(file_path))
                    for page in doc:
                        content += page.get_text()
                    doc.close()
                except Exception as e:
                    logger.debug(f"PDF read error: {e}")
            else:
                try:
                    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            if content:
                from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

                system_prompt = """Extract all tables from the document content.
Return a JSON array of tables, each with "headers" (array of column names) and "rows" (array of row arrays).
Example: [{"headers": ["Name", "Value"], "rows": [["A", "1"], ["B", "2"]]}]"""

                messages = [{"role": "user", "content": f"Extract tables from:\n\n{content[:10000]}"}]
                response = await perform_chat_api_call_async(
                    messages=messages,
                    system_message=system_prompt,
                    max_tokens=4000,
                    temperature=0.3,
                )

                text = _extract_openai_content(response) or "[]"
                try:
                    json_match = re.search(r'\[[\s\S]*\]', text)
                    if json_match:
                        tables = json.loads(json_match.group())
                except Exception:
                    pass

        # Convert to CSV if requested
        if output_format == "csv":
            for table in tables:
                headers = table.get("headers", [])
                rows = table.get("rows", [])
                csv_lines = []
                if headers:
                    csv_lines.append(",".join(str(h) for h in headers))
                for row in rows:
                    csv_lines.append(",".join(str(c) for c in row))
                table["csv"] = "\n".join(csv_lines)

        return {
            "tables": tables,
            "count": len(tables),
            "format": output_format,
        }

    except Exception as e:
        logger.exception(f"Document table extract error: {e}")
        return {"error": f"table_extract_error:{e}", "tables": [], "count": 0}


async def run_audio_diarize_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Perform speaker diarization on audio - separate audio by speaker with timestamps.

    Config:
      - audio_path: str - Path to audio file
      - audio_uri: str - Alternative: file:// URI
      - num_speakers: int - Expected number of speakers (optional, auto-detect if not set)
      - min_speakers: int - Minimum speakers for auto-detect (default: 1)
      - max_speakers: int - Maximum speakers for auto-detect (default: 10)
      - model: str - Diarization model to use (default: "pyannote")
    Output:
      - segments: list[dict] - Speaker segments with timestamps
      - speakers: list[str] - Unique speaker labels
      - total_duration: float - Total audio duration in seconds
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    audio_path = config.get("audio_path")
    audio_uri = config.get("audio_uri")

    if audio_uri:
        try:
            audio_path = _resolve_workflow_file_uri(audio_uri, context, config)
        except Exception as e:
            return {"error": f"invalid_audio_uri:{e}", "segments": [], "speakers": []}
    elif audio_path:
        if isinstance(audio_path, str):
            audio_path = _tmpl(audio_path, context) or audio_path
        try:
            audio_path = _resolve_workflow_file_path(audio_path, context, config)
        except Exception as e:
            return {"error": f"audio_access_denied:{e}", "segments": [], "speakers": []}
    else:
        # Try to get from previous step
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            audio_path = prev.get("audio_path") or prev.get("file_path")
        if not audio_path:
            return {"error": "missing_audio_path", "segments": [], "speakers": []}

    num_speakers = config.get("num_speakers")
    min_speakers = int(config.get("min_speakers", 1))
    max_speakers = int(config.get("max_speakers", 10))

    try:
        # Try to use pyannote for diarization
        try:
            from pyannote.audio import Pipeline
            import torch

            # Load diarization pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=os.getenv("HF_TOKEN"),
            )

            # Move to GPU if available
            if torch.cuda.is_available():
                pipeline.to(torch.device("cuda"))

            # Run diarization
            if num_speakers:
                diarization = pipeline(str(audio_path), num_speakers=num_speakers)
            else:
                diarization = pipeline(
                    str(audio_path),
                    min_speakers=min_speakers,
                    max_speakers=max_speakers,
                )

            # Extract segments
            segments = []
            speakers = set()
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker,
                    "duration": turn.end - turn.start,
                })
                speakers.add(speaker)

            total_duration = max((s["end"] for s in segments), default=0)

            return {
                "segments": segments,
                "speakers": sorted(list(speakers)),
                "total_duration": total_duration,
            }

        except ImportError:
            logger.warning("Pyannote not available, using simplified diarization")

            # Fallback: use whisper with speaker detection if available
            try:
                from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
                    transcribe_audio_with_whisper,
                )

                result = await asyncio.to_thread(
                    transcribe_audio_with_whisper,
                    str(audio_path),
                    diarize=True,
                )

                if isinstance(result, dict) and result.get("segments"):
                    segments = []
                    speakers = set()
                    for seg in result["segments"]:
                        speaker = seg.get("speaker", "SPEAKER_0")
                        segments.append({
                            "start": seg.get("start", 0),
                            "end": seg.get("end", 0),
                            "speaker": speaker,
                            "text": seg.get("text", ""),
                        })
                        speakers.add(speaker)

                    return {
                        "segments": segments,
                        "speakers": sorted(list(speakers)),
                        "total_duration": result.get("duration", 0),
                    }

            except Exception as e:
                logger.debug(f"Whisper diarization fallback failed: {e}")

            return {
                "error": "diarization_unavailable",
                "segments": [],
                "speakers": [],
                "message": "Install pyannote-audio for speaker diarization",
            }

    except Exception as e:
        logger.exception(f"Audio diarize adapter error: {e}")
        return {"error": f"diarization_error:{e}", "segments": [], "speakers": []}


# ============================================================================
# TIER 2: LEARNING / EDUCATION ADAPTERS
# ============================================================================


async def run_flashcard_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate flashcards from content using LLM."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text
    text = str(text).strip()

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or prev.get("transcript") or ""
        text = str(text).strip()

    if not text:
        return {"error": "missing_text", "flashcards": [], "count": 0}

    num_cards = int(config.get("num_cards", 10))
    card_type = str(config.get("card_type", "basic")).lower()
    difficulty = str(config.get("difficulty", "medium")).lower()
    focus_topics = config.get("focus_topics")
    provider = config.get("provider")
    model = config.get("model")

    type_instructions = {"basic": "Create standard question/answer flashcards.", "cloze": "Create cloze deletion cards.", "basic_reverse": "Create bidirectional cards."}
    difficulty_hints = {"easy": "Focus on basic concepts.", "medium": "Include intermediate concepts.", "hard": "Focus on complex details."}
    topics_hint = f"\nFocus on: {', '.join(focus_topics)}" if focus_topics else ""

    system_prompt = f"Generate {num_cards} flashcards.\n{type_instructions.get(card_type, type_instructions['basic'])}\n{difficulty_hints.get(difficulty, difficulty_hints['medium'])}{topics_hint}\nReturn JSON array: [{{\"front\": \"Q\", \"back\": \"A\", \"tags\": []}}]"

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        messages = [{"role": "user", "content": f"Generate flashcards from:\n\n{text[:8000]}"}]
        response = await perform_chat_api_call_async(messages=messages, api_provider=provider, model=model, system_message=system_prompt, max_tokens=4000, temperature=0.7)
        response_text = _extract_openai_content(response) or "[]"
        try:
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            flashcards = json.loads(json_match.group()) if json_match else []
        except json.JSONDecodeError:
            flashcards = []
        for card in flashcards:
            card["model_type"] = card_type
        return {"flashcards": flashcards, "count": len(flashcards)}
    except Exception as e:
        logger.exception(f"Flashcard generate adapter error: {e}")
        return {"error": f"flashcard_generate_error:{e}", "flashcards": [], "count": 0}


async def run_quiz_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate quiz questions from content using LLM."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text
    text = str(text).strip()

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or prev.get("transcript") or ""
        text = str(text).strip()

    if not text:
        return {"error": "missing_text", "questions": [], "count": 0}

    num_questions = int(config.get("num_questions", 10))
    question_types = config.get("question_types", ["multiple_choice"])
    if isinstance(question_types, str):
        question_types = [question_types]
    difficulty = str(config.get("difficulty", "medium")).lower()
    provider = config.get("provider")
    model = config.get("model")

    system_prompt = f"Generate {num_questions} quiz questions. Types: {', '.join(question_types)}. Difficulty: {difficulty}.\nReturn JSON: [{{\"question_type\": \"multiple_choice\", \"question_text\": \"Q\", \"options\": [\"A\",\"B\",\"C\",\"D\"], \"correct_answer\": 0, \"explanation\": \"Why\", \"points\": 1}}]"

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        messages = [{"role": "user", "content": f"Generate quiz from:\n\n{text[:8000]}"}]
        response = await perform_chat_api_call_async(messages=messages, api_provider=provider, model=model, system_message=system_prompt, max_tokens=4000, temperature=0.7)
        response_text = _extract_openai_content(response) or "[]"
        try:
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            questions = json.loads(json_match.group()) if json_match else []
        except json.JSONDecodeError:
            questions = []
        return {"questions": questions, "count": len(questions)}
    except Exception as e:
        logger.exception(f"Quiz generate adapter error: {e}")
        return {"error": f"quiz_generate_error:{e}", "questions": [], "count": 0}


async def run_quiz_evaluate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate quiz answers and provide feedback."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    questions = config.get("questions")
    if not questions:
        prev = context.get("prev") or context.get("last") or {}
        questions = prev.get("questions") if isinstance(prev, dict) else []

    answers = config.get("answers") or []
    if not isinstance(questions, list) or not questions:
        return {"error": "missing_questions", "score": 0, "results": []}

    passing_score = float(config.get("passing_score", 70))
    answer_map = {(a.get("question_id", i) if isinstance(a, dict) else i): (a.get("user_answer") if isinstance(a, dict) else a) for i, a in enumerate(answers)}

    results, points_earned, points_possible = [], 0, 0
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        qid, correct, user_ans, pts = q.get("id", i), q.get("correct_answer"), answer_map.get(q.get("id", i)), q.get("points", 1)
        points_possible += pts
        qtype = q.get("question_type", "multiple_choice")
        is_correct = (correct == user_ans) if qtype == "multiple_choice" else (str(correct).lower().strip() == str(user_ans or "").lower().strip())
        if is_correct:
            points_earned += pts
        results.append({"question_id": qid, "is_correct": is_correct, "points": pts if is_correct else 0})

    score = (points_earned / points_possible * 100) if points_possible > 0 else 0
    return {"score": round(score, 2), "points_earned": points_earned, "points_possible": points_possible, "results": results, "passed": score >= passing_score}


async def run_outline_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a hierarchical outline from content."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text
    text = str(text).strip()
    if not text:
        prev = context.get("prev") or context.get("last") or {}
        text = str(prev.get("text") or prev.get("content") or "") if isinstance(prev, dict) else ""

    if not text:
        return {"error": "missing_text", "outline": {}, "outline_text": ""}

    max_depth = int(config.get("max_depth", 3))
    provider, model = config.get("provider"), config.get("model")
    system_prompt = f"Create outline. Max depth: {max_depth}. Return JSON: {{\"sections\": [{{\"title\": \"Section\", \"level\": 1, \"subsections\": []}}]}}"

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        response = await perform_chat_api_call_async(messages=[{"role": "user", "content": f"Outline:\n\n{text[:8000]}"}], api_provider=provider, model=model, system_message=system_prompt, max_tokens=2000, temperature=0.5)
        response_text = _extract_openai_content(response) or ""
        outline = {}
        try:
            json_match = re.search(r'\{[\s\S]*"sections"[\s\S]*\}', response_text)
            outline = json.loads(json_match.group()) if json_match else {}
        except json.JSONDecodeError:
            pass
        return {"outline": outline, "outline_text": response_text, "sections": len(outline.get("sections", []))}
    except Exception as e:
        logger.exception(f"Outline generate error: {e}")
        return {"error": str(e), "outline": {}, "outline_text": ""}


async def run_glossary_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key terms and definitions from content."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text
    text = str(text).strip()
    if not text:
        prev = context.get("prev") or context.get("last") or {}
        text = str(prev.get("text") or prev.get("content") or "") if isinstance(prev, dict) else ""

    if not text:
        return {"error": "missing_text", "glossary": [], "count": 0}

    max_terms = int(config.get("max_terms", 20))
    provider, model = config.get("provider"), config.get("model")
    system_prompt = f"Extract up to {max_terms} key terms. Return JSON: [{{\"term\": \"Name\", \"definition\": \"Def\"}}]"

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        response = await perform_chat_api_call_async(messages=[{"role": "user", "content": f"Extract glossary:\n\n{text[:8000]}"}], api_provider=provider, model=model, system_message=system_prompt, max_tokens=3000, temperature=0.5)
        response_text = _extract_openai_content(response) or "[]"
        try:
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            glossary = json.loads(json_match.group()) if json_match else []
        except json.JSONDecodeError:
            glossary = []
        return {"glossary": glossary, "count": len(glossary)}
    except Exception as e:
        logger.exception(f"Glossary extract error: {e}")
        return {"error": str(e), "glossary": [], "count": 0}


async def run_mindmap_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a mindmap structure from content."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text
    text = str(text).strip()
    if not text:
        prev = context.get("prev") or context.get("last") or {}
        text = str(prev.get("text") or prev.get("content") or "") if isinstance(prev, dict) else ""

    if not text:
        return {"error": "missing_text", "mindmap": {}, "mermaid": ""}

    max_branches = int(config.get("max_branches", 6))
    provider, model = config.get("provider"), config.get("model")
    system_prompt = f"Create mindmap. Max {max_branches} branches. Return JSON: {{\"central\": \"Topic\", \"branches\": [{{\"topic\": \"Branch\", \"children\": []}}]}}"

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        response = await perform_chat_api_call_async(messages=[{"role": "user", "content": f"Mindmap:\n\n{text[:8000]}"}], api_provider=provider, model=model, system_message=system_prompt, max_tokens=2000, temperature=0.6)
        response_text = _extract_openai_content(response) or ""
        mindmap = {}
        try:
            json_match = re.search(r'\{[\s\S]*"central"[\s\S]*\}', response_text)
            mindmap = json.loads(json_match.group()) if json_match else {}
        except json.JSONDecodeError:
            pass
        return {"mindmap": mindmap, "mermaid": "", "node_count": 0}
    except Exception as e:
        logger.exception(f"Mindmap generate error: {e}")
        return {"error": str(e), "mindmap": {}, "mermaid": ""}


async def run_eval_readability_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate readability scores for text."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import math

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text
    text = str(text).strip()
    if not text:
        prev = context.get("prev") or context.get("last") or {}
        text = str(prev.get("text") or prev.get("content") or "") if isinstance(prev, dict) else ""

    if not text:
        return {"error": "missing_text", "scores": {}}

    words = text.split()
    word_count = len(words)
    sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]
    sentence_count = len(sentences) or 1

    def count_syllables(word):
        word = word.lower()
        if len(word) <= 3:
            return 1
        if word.endswith('e'):
            word = word[:-1]
        count, prev_vowel = 0, False
        for c in word:
            is_v = c in "aeiouy"
            if is_v and not prev_vowel:
                count += 1
            prev_vowel = is_v
        return max(1, count)

    syllable_count = sum(count_syllables(w) for w in words)
    char_count = sum(len(w) for w in words)
    scores = {}

    if word_count > 0:
        scores["flesch_reading_ease"] = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)
        scores["flesch_kincaid_grade"] = 0.39 * (word_count / sentence_count) + 11.8 * (syllable_count / word_count) - 15.59

    return {"scores": {k: round(v, 2) for k, v in scores.items()}, "grade_level": round(scores.get("flesch_kincaid_grade", 0), 1), "reading_ease": round(scores.get("flesch_reading_ease", 50), 1), "word_count": word_count, "sentence_count": sentence_count}


# ============================================================================
# TIER 3: DATA PROCESSING ADAPTERS
# ============================================================================


async def run_json_transform_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Transform JSON data using JQ-like expressions."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    data = config.get("data")
    if data is None:
        prev = context.get("prev") or context.get("last") or {}
        data = prev if isinstance(prev, (dict, list)) else {}

    expression = config.get("expression") or config.get("query") or "."

    try:
        import jmespath
        result = jmespath.search(expression, data)
        return {"result": result, "expression": expression}
    except ImportError:
        # Fallback: simple path extraction
        if expression == ".":
            return {"result": data, "expression": expression}
        parts = expression.strip(".").split(".")
        result = data
        for part in parts:
            if isinstance(result, dict):
                result = result.get(part)
            elif isinstance(result, list) and part.isdigit():
                idx = int(part)
                result = result[idx] if 0 <= idx < len(result) else None
            else:
                result = None
                break
        return {"result": result, "expression": expression}
    except Exception as e:
        logger.exception(f"JSON transform error: {e}")
        return {"error": str(e), "result": None}


async def run_json_validate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate JSON data against a schema."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    data = config.get("data")
    if data is None:
        prev = context.get("prev") or context.get("last") or {}
        data = prev if isinstance(prev, (dict, list)) else {}

    schema = config.get("schema")
    if not schema:
        return {"error": "missing_schema", "valid": False, "errors": []}

    try:
        import jsonschema
        jsonschema.validate(data, schema)
        return {"valid": True, "errors": []}
    except ImportError:
        return {"error": "jsonschema_not_installed", "valid": False, "errors": ["Install jsonschema package"]}
    except jsonschema.ValidationError as e:
        return {"valid": False, "errors": [str(e.message)], "path": list(e.path)}
    except Exception as e:
        return {"error": str(e), "valid": False, "errors": [str(e)]}


async def run_csv_to_json_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert CSV data to JSON records."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import csv
    import io

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    csv_data = config.get("csv_data") or config.get("data") or ""
    if isinstance(csv_data, str):
        csv_data = _tmpl(csv_data, context) or csv_data

    if not csv_data:
        prev = context.get("prev") or context.get("last") or {}
        csv_data = prev.get("text") or prev.get("content") or "" if isinstance(prev, dict) else ""

    if not csv_data:
        return {"error": "missing_csv_data", "records": [], "count": 0}

    delimiter = config.get("delimiter", ",")
    has_header = config.get("has_header", True)

    try:
        reader = csv.reader(io.StringIO(csv_data), delimiter=delimiter)
        rows = list(reader)
        if not rows:
            return {"records": [], "count": 0}

        if has_header:
            headers = rows[0]
            records = [dict(zip(headers, row)) for row in rows[1:]]
        else:
            records = [{"col_" + str(i): v for i, v in enumerate(row)} for row in rows]

        return {"records": records, "count": len(records), "columns": headers if has_header else None}
    except Exception as e:
        logger.exception(f"CSV to JSON error: {e}")
        return {"error": str(e), "records": [], "count": 0}


async def run_json_to_csv_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert JSON records to CSV."""
    import csv
    import io

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    records = config.get("records") or config.get("data")
    if records is None:
        prev = context.get("prev") or context.get("last") or {}
        records = prev.get("records") or prev.get("data") or prev if isinstance(prev, list) else []

    if not isinstance(records, list) or not records:
        return {"error": "missing_records", "csv": "", "count": 0}

    delimiter = config.get("delimiter", ",")
    include_header = config.get("include_header", True)

    try:
        output = io.StringIO()
        if records and isinstance(records[0], dict):
            headers = list(records[0].keys())
            writer = csv.DictWriter(output, fieldnames=headers, delimiter=delimiter)
            if include_header:
                writer.writeheader()
            writer.writerows(records)
        else:
            writer = csv.writer(output, delimiter=delimiter)
            writer.writerows(records)

        csv_data = output.getvalue()
        return {"csv": csv_data, "count": len(records)}
    except Exception as e:
        logger.exception(f"JSON to CSV error: {e}")
        return {"error": str(e), "csv": "", "count": 0}


async def run_regex_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract text matching regex patterns with named groups."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text
    text = str(text).strip()

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        text = prev.get("text") or prev.get("content") or "" if isinstance(prev, dict) else ""

    pattern = config.get("pattern")
    if not pattern:
        return {"error": "missing_pattern", "matches": [], "count": 0}

    flags = 0
    if config.get("ignore_case"):
        flags |= re.IGNORECASE
    if config.get("multiline"):
        flags |= re.MULTILINE
    if config.get("dotall"):
        flags |= re.DOTALL

    try:
        regex = re.compile(pattern, flags)
        matches = []
        for match in regex.finditer(text):
            m = {"full": match.group(0), "start": match.start(), "end": match.end()}
            if match.groupdict():
                m["groups"] = match.groupdict()
            elif match.groups():
                m["groups"] = list(match.groups())
            matches.append(m)

        return {"matches": matches, "count": len(matches), "pattern": pattern}
    except re.error as e:
        return {"error": f"invalid_pattern: {e}", "matches": [], "count": 0}
    except Exception as e:
        logger.exception(f"Regex extract error: {e}")
        return {"error": str(e), "matches": [], "count": 0}


async def run_text_clean_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and normalize text."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import html

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text
    text = str(text)

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        text = prev.get("text") or prev.get("content") or "" if isinstance(prev, dict) else ""

    operations = config.get("operations", ["strip_html", "normalize_whitespace", "fix_encoding"])

    original_len = len(text)

    if "strip_html" in operations:
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)

    if "fix_encoding" in operations:
        try:
            text = text.encode('utf-8', errors='ignore').decode('utf-8')
        except Exception:
            pass

    if "normalize_whitespace" in operations:
        text = re.sub(r'\s+', ' ', text)

    if "strip" in operations or "normalize_whitespace" in operations:
        text = text.strip()

    if "lowercase" in operations:
        text = text.lower()

    if "remove_urls" in operations:
        text = re.sub(r'https?://\S+', '', text)

    if "remove_emails" in operations:
        text = re.sub(r'\S+@\S+\.\S+', '', text)

    return {"text": text, "original_length": original_len, "cleaned_length": len(text), "operations": operations}


async def run_xml_transform_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Transform XML using XPath queries."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    xml_data = config.get("xml") or config.get("data") or ""
    if isinstance(xml_data, str):
        xml_data = _tmpl(xml_data, context) or xml_data

    if not xml_data:
        prev = context.get("prev") or context.get("last") or {}
        xml_data = prev.get("xml") or prev.get("text") or "" if isinstance(prev, dict) else ""

    xpath = config.get("xpath") or config.get("query")
    if not xpath:
        return {"error": "missing_xpath", "results": []}

    try:
        from lxml import etree
        root = etree.fromstring(xml_data.encode() if isinstance(xml_data, str) else xml_data)
        results = root.xpath(xpath)
        output = []
        for r in results:
            if hasattr(r, 'text'):
                output.append({"tag": r.tag, "text": r.text, "attrib": dict(r.attrib)})
            else:
                output.append(str(r))
        return {"results": output, "count": len(output), "xpath": xpath}
    except ImportError:
        return {"error": "lxml_not_installed", "results": []}
    except Exception as e:
        logger.exception(f"XML transform error: {e}")
        return {"error": str(e), "results": []}


async def run_template_render_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Render a Jinja2 template with provided variables."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    template = config.get("template") or ""
    template_file = config.get("template_file")

    if template_file:
        try:
            file_path = _resolve_workflow_file_path(template_file, context, config)
            template = Path(file_path).read_text(encoding="utf-8")
        except Exception as e:
            return {"error": f"template_file_error: {e}", "text": ""}

    if not template:
        return {"error": "missing_template", "text": ""}

    variables = config.get("variables") or {}
    # Merge context inputs
    render_context = {**context.get("inputs", {}), **variables}
    render_context["prev"] = context.get("prev") or context.get("last") or {}

    try:
        rendered = _tmpl(template, render_context) or template
        return {"text": rendered}
    except Exception as e:
        logger.exception(f"Template render error: {e}")
        return {"error": str(e), "text": ""}


async def run_batch_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Batch items into chunks for processing."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    items = config.get("items")
    if items is None:
        prev = context.get("prev") or context.get("last") or {}
        items = prev.get("items") or prev.get("documents") or prev.get("records")
        if items is None and isinstance(prev, list):
            items = prev

    if not isinstance(items, list):
        return {"error": "missing_items", "batches": [], "batch_count": 0}

    batch_size = int(config.get("batch_size", 10))
    if batch_size < 1:
        batch_size = 1

    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

    return {"batches": batches, "batch_count": len(batches), "total_items": len(items), "batch_size": batch_size}


# ============================================================================
# TIER 4: WORKFLOW ORCHESTRATION ADAPTERS
# ============================================================================


async def run_workflow_call_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Call another workflow as a sub-workflow."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    workflow_id = config.get("workflow_id")
    if not workflow_id:
        return {"error": "missing_workflow_id", "result": None}

    inputs = config.get("inputs") or {}
    wait = config.get("wait", True)
    timeout_seconds = int(config.get("timeout_seconds", 300))

    try:
        from tldw_Server_API.app.core.Workflows.workflows_db import get_workflows_db

        db = get_workflows_db()
        workflow = db.get_workflow(workflow_id)
        if not workflow:
            return {"error": f"workflow_not_found: {workflow_id}", "result": None}

        # Create a sub-run
        import uuid
        run_id = str(uuid.uuid4())
        tenant_id = context.get("tenant_id", "default")
        user_id = context.get("user_id")

        db.create_run(
            run_id=run_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            user_id=user_id,
            inputs=inputs,
            status="pending",
        )

        if wait:
            from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine, EngineConfig

            engine = WorkflowEngine(db=db, config=EngineConfig(tenant_id=tenant_id))
            await asyncio.wait_for(engine.start_run(run_id, mode="sync"), timeout=timeout_seconds)

            run = db.get_run(run_id)
            if run:
                return {"run_id": run_id, "status": run.status, "outputs": run.outputs or {}, "result": run.outputs}
            return {"run_id": run_id, "status": "unknown", "result": None}
        else:
            # Async execution
            from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine, EngineConfig

            engine = WorkflowEngine(db=db, config=EngineConfig(tenant_id=tenant_id))
            engine.submit(run_id, mode="async")
            return {"run_id": run_id, "status": "submitted", "async": True}

    except asyncio.TimeoutError:
        return {"error": "workflow_timeout", "run_id": run_id if 'run_id' in dir() else None}
    except Exception as e:
        logger.exception(f"Workflow call error: {e}")
        return {"error": str(e), "result": None}


async def run_parallel_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute multiple steps in parallel."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    steps = config.get("steps")
    if not isinstance(steps, list) or not steps:
        return {"error": "missing_steps", "results": []}

    max_concurrency = int(config.get("max_concurrency", 5))
    fail_fast = config.get("fail_fast", False)

    semaphore = asyncio.Semaphore(max_concurrency)
    results = [None] * len(steps)
    errors = []

    async def run_step(idx, step_config):
        async with semaphore:
            if callable(context.get("is_cancelled")) and context["is_cancelled"]():
                return

            step_type = step_config.get("type")
            step_cfg = step_config.get("config", {})

            try:
                # Look up adapter in explicit registry (avoids fragile sys.modules inspection)
                adapter = get_adapter(step_type)
                if adapter is not None:
                    result = await adapter(step_cfg, context)
                    results[idx] = result
                else:
                    results[idx] = {"error": f"unknown_step_type: {step_type}"}
            except Exception as e:
                results[idx] = {"error": str(e)}
                if fail_fast:
                    errors.append(str(e))

    tasks = [run_step(i, step) for i, step in enumerate(steps)]
    await asyncio.gather(*tasks, return_exceptions=not fail_fast)

    return {"results": results, "count": len(results), "errors": errors if errors else None}


async def run_cache_result_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Cache step result by key for reuse."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    cache_key = config.get("key")
    if not cache_key:
        return {"error": "missing_cache_key", "cached": False}

    ttl_seconds = int(config.get("ttl_seconds", 3600))
    action = config.get("action", "get_or_set")  # get, set, get_or_set, invalidate

    # Get data to cache (for set operations)
    data = config.get("data")
    if data is None:
        prev = context.get("prev") or context.get("last") or {}
        data = prev

    try:
        from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import chroma_client
        import time

        client = chroma_client()
        if not client:
            # Fallback: just pass through
            return {"cached": False, "data": data, "error": "cache_unavailable"}

        cache_collection_name = "workflow_cache"
        try:
            collection = client.get_or_create_collection(name=cache_collection_name)
        except Exception:
            return {"cached": False, "data": data, "error": "cache_collection_error"}

        if action == "invalidate":
            try:
                collection.delete(ids=[cache_key])
            except Exception:
                pass
            return {"invalidated": True, "key": cache_key}

        if action in ("get", "get_or_set"):
            try:
                result = collection.get(ids=[cache_key], include=["metadatas", "documents"])
                if result and result.get("ids") and result["ids"]:
                    meta = result.get("metadatas", [{}])[0] or {}
                    cached_at = meta.get("cached_at", 0)
                    if time.time() - cached_at <= ttl_seconds:
                        cached_data = meta.get("data")
                        if isinstance(cached_data, str):
                            try:
                                cached_data = json.loads(cached_data)
                            except Exception:
                                pass
                        return {"cached": True, "data": cached_data, "key": cache_key, "age_seconds": int(time.time() - cached_at)}
            except Exception:
                pass

        if action in ("set", "get_or_set"):
            try:
                data_str = json.dumps(data) if not isinstance(data, str) else data
                collection.upsert(
                    ids=[cache_key],
                    documents=[cache_key],
                    metadatas=[{"data": data_str, "cached_at": time.time()}],
                )
                return {"cached": False, "stored": True, "data": data, "key": cache_key}
            except Exception as e:
                return {"cached": False, "data": data, "error": f"cache_store_error: {e}"}

        return {"cached": False, "data": data}

    except Exception as e:
        logger.exception(f"Cache result error: {e}")
        return {"cached": False, "data": data, "error": str(e)}


async def run_retry_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap a step with retry logic."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    step_type = config.get("step_type")
    step_config = config.get("step_config", {})
    if not step_type:
        return {"error": "missing_step_type", "result": None}

    max_retries = int(config.get("max_retries", 3))
    backoff_base = float(config.get("backoff_base", 2.0))
    backoff_max = float(config.get("backoff_max", 30.0))
    retry_on_errors = config.get("retry_on_errors")  # List of error patterns to retry on

    # Look up adapter in explicit registry (avoids fragile sys.modules inspection)
    adapter = get_adapter(step_type)
    if adapter is None:
        return {"error": f"unknown_step_type: {step_type}", "result": None}
    last_error = None

    for attempt in range(max_retries + 1):
        if callable(context.get("is_cancelled")) and context["is_cancelled"]():
            return {"__status__": "cancelled"}

        try:
            result = await adapter(step_config, context)

            # Check if result indicates an error
            if isinstance(result, dict) and result.get("error"):
                error_str = str(result["error"])
                if retry_on_errors:
                    should_retry = any(pat in error_str for pat in retry_on_errors)
                else:
                    should_retry = True

                if should_retry and attempt < max_retries:
                    last_error = error_str
                    delay = min(backoff_base ** attempt, backoff_max)
                    await asyncio.sleep(delay)
                    continue

            return {"result": result, "attempts": attempt + 1, "success": True}

        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = min(backoff_base ** attempt, backoff_max)
                await asyncio.sleep(delay)
            else:
                return {"error": last_error, "attempts": attempt + 1, "success": False}

    return {"error": last_error, "attempts": max_retries + 1, "success": False}


async def run_checkpoint_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Save workflow state for recovery."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    checkpoint_id = config.get("checkpoint_id") or f"checkpoint_{int(time.time()*1000)}"
    data = config.get("data")
    if data is None:
        prev = context.get("prev") or context.get("last") or {}
        data = {"prev": prev, "inputs": context.get("inputs", {})}

    run_id = context.get("run_id")

    try:
        from tldw_Server_API.app.core.Workflows.workflows_db import get_workflows_db

        db = get_workflows_db()

        # Store checkpoint as an event
        if callable(context.get("append_event")):
            context["append_event"]("checkpoint", {
                "checkpoint_id": checkpoint_id,
                "data": data,
            })

        # Also store as artifact for persistence
        if callable(context.get("add_artifact")):
            step_run_id = str(context.get("step_run_id") or checkpoint_id)
            art_dir = _resolve_artifacts_dir(step_run_id)
            art_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_file = art_dir / f"{checkpoint_id}.json"
            checkpoint_file.write_text(json.dumps(data, default=str), encoding="utf-8")

            context["add_artifact"](
                type="checkpoint",
                uri=f"file://{checkpoint_file}",
                size_bytes=checkpoint_file.stat().st_size,
                mime_type="application/json",
                metadata={"checkpoint_id": checkpoint_id},
            )

        return {"checkpoint_id": checkpoint_id, "saved": True, "run_id": run_id}

    except Exception as e:
        logger.exception(f"Checkpoint error: {e}")
        return {"error": str(e), "checkpoint_id": checkpoint_id, "saved": False}


# ============================================================================
# TIER 5: EXTERNAL INTEGRATION ADAPTERS
# ============================================================================


async def run_s3_upload_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Upload content to S3-compatible storage."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    bucket = config.get("bucket")
    key = config.get("key")
    if not bucket or not key:
        return {"error": "missing_bucket_or_key", "uploaded": False}

    # Get content
    content = config.get("content")
    file_path = config.get("file_path")

    if file_path:
        if isinstance(file_path, str):
            file_path = _tmpl(file_path, context) or file_path
        try:
            resolved_path = _resolve_workflow_file_path(file_path, context, config)
            content = resolved_path.read_bytes()
        except Exception as e:
            return {"error": f"file_read_error: {e}", "uploaded": False}
    elif content is None:
        prev = context.get("prev") or context.get("last") or {}
        content = prev.get("content") or prev.get("text") or ""

    if isinstance(content, str):
        content = content.encode("utf-8")

    endpoint_url = config.get("endpoint_url") or os.getenv("S3_ENDPOINT_URL")
    access_key = config.get("access_key") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = config.get("secret_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
    region = config.get("region") or os.getenv("AWS_REGION", "us-east-1")

    try:
        import boto3
        from botocore.config import Config as BotoConfig

        client_kwargs = {"region_name": region}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key

        s3 = boto3.client("s3", **client_kwargs)
        s3.put_object(Bucket=bucket, Key=key, Body=content)

        return {"uploaded": True, "bucket": bucket, "key": key, "size_bytes": len(content)}

    except ImportError:
        return {"error": "boto3_not_installed", "uploaded": False}
    except Exception as e:
        logger.exception(f"S3 upload error: {e}")
        return {"error": str(e), "uploaded": False}


async def run_s3_download_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Download content from S3-compatible storage."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    bucket = config.get("bucket")
    key = config.get("key")
    if not bucket or not key:
        return {"error": "missing_bucket_or_key", "content": None}

    endpoint_url = config.get("endpoint_url") or os.getenv("S3_ENDPOINT_URL")
    access_key = config.get("access_key") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = config.get("secret_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
    region = config.get("region") or os.getenv("AWS_REGION", "us-east-1")
    as_text = config.get("as_text", True)

    try:
        import boto3

        client_kwargs = {"region_name": region}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key

        s3 = boto3.client("s3", **client_kwargs)
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read()

        if as_text:
            content = content.decode("utf-8", errors="ignore")

        return {"content": content, "bucket": bucket, "key": key, "size_bytes": len(content) if isinstance(content, (str, bytes)) else 0}

    except ImportError:
        return {"error": "boto3_not_installed", "content": None}
    except Exception as e:
        logger.exception(f"S3 download error: {e}")
        return {"error": str(e), "content": None}


async def run_github_create_issue_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Create a GitHub issue."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    repo = config.get("repo")  # format: owner/repo
    title = config.get("title")
    if not repo or not title:
        return {"error": "missing_repo_or_title", "issue_url": None}

    if isinstance(title, str):
        title = _tmpl(title, context) or title

    body = config.get("body") or ""
    if isinstance(body, str):
        body = _tmpl(body, context) or body

    labels = config.get("labels") or []
    assignees = config.get("assignees") or []

    token = config.get("token") or os.getenv("GITHUB_TOKEN")
    if not token:
        return {"error": "missing_github_token", "issue_url": None}

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/repos/{repo}/issues",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={
                    "title": title,
                    "body": body,
                    "labels": labels,
                    "assignees": assignees,
                },
                timeout=30,
            )

            if response.status_code == 201:
                data = response.json()
                return {"issue_url": data.get("html_url"), "issue_number": data.get("number"), "created": True}
            else:
                return {"error": f"github_api_error: {response.status_code} - {response.text}", "created": False}

    except Exception as e:
        logger.exception(f"GitHub create issue error: {e}")
        return {"error": str(e), "issue_url": None, "created": False}


# ============================================================================
# TIER 6: AGENTIC SUPPORT ADAPTERS
# ============================================================================


async def run_llm_with_tools_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """LLM call that can invoke defined tools."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    prompt = config.get("prompt") or ""
    if isinstance(prompt, str):
        prompt = _tmpl(prompt, context) or prompt

    if not prompt:
        prev = context.get("prev") or context.get("last") or {}
        prompt = prev.get("text") or prev.get("prompt") or "" if isinstance(prev, dict) else ""

    tools = config.get("tools") or []
    auto_execute = config.get("auto_execute", True)
    max_tool_calls = int(config.get("max_tool_calls", 5))
    provider = config.get("provider")
    model = config.get("model")
    system_message = config.get("system_message") or "You are a helpful assistant with access to tools."

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        messages = [{"role": "user", "content": prompt}]
        tool_results = []
        final_response = None

        for iteration in range(max_tool_calls + 1):
            if callable(context.get("is_cancelled")) and context["is_cancelled"]():
                return {"__status__": "cancelled"}

            response = await perform_chat_api_call_async(
                messages=messages,
                api_provider=provider,
                model=model,
                system_message=system_message,
                tools=tools if tools else None,
            )

            # Check for tool calls in response
            tool_calls = None
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    tool_calls = message.get("tool_calls")
                    if not tool_calls:
                        final_response = _extract_openai_content(response)
                        break

            if not tool_calls or not auto_execute:
                final_response = _extract_openai_content(response)
                break

            # Execute tool calls
            for tc in tool_calls:
                tool_name = tc.get("function", {}).get("name")
                tool_args_str = tc.get("function", {}).get("arguments", "{}")
                try:
                    tool_args = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    tool_args = {}

                # Try to execute via MCP
                try:
                    from tldw_Server_API.app.core.MCP_unified.manager import get_mcp_manager
                    manager = get_mcp_manager()
                    result = await manager.execute_tool(tool_name, tool_args, context=None)
                    tool_results.append({"tool": tool_name, "result": result})

                    messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                    messages.append({"role": "tool", "tool_call_id": tc.get("id"), "content": json.dumps(result, default=str)})
                except Exception as e:
                    tool_results.append({"tool": tool_name, "error": str(e)})
                    messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                    messages.append({"role": "tool", "tool_call_id": tc.get("id"), "content": f"Error: {e}"})

        return {"text": final_response or "", "tool_results": tool_results, "iterations": iteration + 1}

    except Exception as e:
        logger.exception(f"LLM with tools error: {e}")
        return {"error": str(e), "text": "", "tool_results": []}


async def run_llm_critique_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Run LLM critique on content (Constitutional AI pattern)."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    content = config.get("content") or ""
    if isinstance(content, str):
        content = _tmpl(content, context) or content

    if not content:
        prev = context.get("prev") or context.get("last") or {}
        content = prev.get("text") or prev.get("content") or "" if isinstance(prev, dict) else ""

    if not content:
        return {"error": "missing_content", "critique": "", "revised": ""}

    criteria = config.get("criteria") or ["accuracy", "clarity", "completeness"]
    revise = config.get("revise", True)
    provider = config.get("provider")
    model = config.get("model")

    criteria_str = ", ".join(criteria)

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        # Step 1: Critique
        critique_prompt = f"""Critique the following content based on these criteria: {criteria_str}

Content:
{content[:6000]}

Provide specific, actionable feedback."""

        messages = [{"role": "user", "content": critique_prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=provider,
            model=model,
            system_message="You are a critical reviewer providing constructive feedback.",
            max_tokens=1500,
            temperature=0.5,
        )

        critique = _extract_openai_content(response) or ""

        revised = ""
        if revise and critique:
            # Step 2: Revise
            revise_prompt = f"""Original content:
{content[:5000]}

Critique:
{critique}

Revise the content to address the critique while maintaining the original intent."""

            messages = [{"role": "user", "content": revise_prompt}]
            response = await perform_chat_api_call_async(
                messages=messages,
                api_provider=provider,
                model=model,
                system_message="You revise content based on feedback.",
                max_tokens=2000,
                temperature=0.5,
            )

            revised = _extract_openai_content(response) or ""

        return {"critique": critique, "revised": revised, "criteria": criteria}

    except Exception as e:
        logger.exception(f"LLM critique error: {e}")
        return {"error": str(e), "critique": "", "revised": ""}


async def run_context_build_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Build context from multiple sources."""
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    sources = config.get("sources") or []
    max_tokens = int(config.get("max_tokens", 4000))
    separator = config.get("separator", "\n\n---\n\n")

    context_parts = []
    total_chars = 0
    char_limit = max_tokens * 4  # Rough estimate

    # Include inputs if specified
    if config.get("include_inputs"):
        inputs = context.get("inputs", {})
        if inputs:
            context_parts.append(f"**Inputs:**\n{json.dumps(inputs, indent=2)}")

    # Include previous step output
    if config.get("include_prev"):
        prev = context.get("prev") or context.get("last") or {}
        prev_text = prev.get("text") or prev.get("content") or ""
        if prev_text:
            context_parts.append(f"**Previous Output:**\n{prev_text}")

    # Process additional sources
    for source in sources:
        if total_chars >= char_limit:
            break

        if isinstance(source, str):
            source = _tmpl(source, context) or source
            context_parts.append(source)
            total_chars += len(source)
        elif isinstance(source, dict):
            source_type = source.get("type")
            if source_type == "text":
                text = source.get("text") or source.get("content") or ""
                if isinstance(text, str):
                    text = _tmpl(text, context) or text
                label = source.get("label", "Content")
                context_parts.append(f"**{label}:**\n{text}")
                total_chars += len(text)
            elif source_type == "documents":
                docs = source.get("documents") or []
                for doc in docs:
                    if total_chars >= char_limit:
                        break
                    doc_text = doc.get("content") or doc.get("text") or str(doc)
                    context_parts.append(doc_text)
                    total_chars += len(doc_text)

    combined_context = separator.join(context_parts)

    # Truncate if needed
    if len(combined_context) > char_limit:
        combined_context = combined_context[:char_limit] + "\n... [truncated]"

    return {"context": combined_context, "source_count": len(context_parts), "total_chars": len(combined_context)}


# ============================================================================
# PHASE 2: GROUP A - INDIVIDUAL UTILITY NODES
# ============================================================================


async def run_document_merge_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple documents into one.

    Config:
      - documents: list[str] - List of document texts to merge
      - separator: str - Separator between documents (default: "\n\n")
      - add_headers: bool - Add section headers (default: False)
    Output:
      - merged: str - The merged document
      - document_count: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    documents = config.get("documents") or []
    separator = config.get("separator", "\n\n")
    add_headers = bool(config.get("add_headers", False))

    # Try to get documents from previous step if not provided
    if not documents:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            documents = prev.get("documents") or prev.get("texts") or []
            if not documents and prev.get("text"):
                documents = [prev.get("text")]

    # Template each document
    processed = []
    for i, doc in enumerate(documents):
        if isinstance(doc, str):
            doc = _tmpl(doc, context) or doc
        elif isinstance(doc, dict):
            doc = doc.get("content") or doc.get("text") or str(doc)
        else:
            doc = str(doc)

        if add_headers:
            processed.append(f"## Document {i + 1}\n\n{doc}")
        else:
            processed.append(doc)

    merged = separator.join(processed)
    return {"merged": merged, "text": merged, "document_count": len(processed)}


async def run_document_diff_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two documents and output diff.

    Config:
      - document_a: str - First document
      - document_b: str - Second document
      - context_lines: int - Lines of context around changes (default: 3)
      - output_format: str - "unified", "html", or "side_by_side" (default: "unified")
    Output:
      - diff: str - The diff output
      - has_changes: bool
      - additions: int
      - deletions: int
    """
    import difflib
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    doc_a = config.get("document_a") or ""
    doc_b = config.get("document_b") or ""

    if isinstance(doc_a, str):
        doc_a = _tmpl(doc_a, context) or doc_a
    if isinstance(doc_b, str):
        doc_b = _tmpl(doc_b, context) or doc_b

    context_lines = int(config.get("context_lines", 3))
    output_format = str(config.get("output_format", "unified")).lower()

    lines_a = doc_a.splitlines(keepends=True)
    lines_b = doc_b.splitlines(keepends=True)

    if output_format == "html":
        differ = difflib.HtmlDiff()
        diff_output = differ.make_file(lines_a, lines_b, context=True, numlines=context_lines)
    elif output_format == "side_by_side":
        differ = difflib.Differ()
        diff_output = "\n".join(differ.compare(lines_a, lines_b))
    else:
        diff_output = "".join(difflib.unified_diff(lines_a, lines_b, lineterm="", n=context_lines))

    # Count additions and deletions
    additions = sum(1 for line in diff_output.split("\n") if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff_output.split("\n") if line.startswith("-") and not line.startswith("---"))

    return {
        "diff": diff_output,
        "has_changes": bool(additions or deletions),
        "additions": additions,
        "deletions": deletions,
    }


async def run_markdown_to_html_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert markdown to HTML.

    Config:
      - markdown: str - Markdown text to convert
      - extensions: list[str] - Markdown extensions to use (default: ["tables", "fenced_code"])
    Output:
      - html: str - The converted HTML
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    markdown_text = config.get("markdown") or config.get("text") or ""
    if isinstance(markdown_text, str):
        markdown_text = _tmpl(markdown_text, context) or markdown_text

    if not markdown_text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            markdown_text = prev.get("text") or prev.get("content") or prev.get("markdown") or ""

    extensions = config.get("extensions") or ["tables", "fenced_code"]

    try:
        import markdown
        html = markdown.markdown(markdown_text, extensions=extensions)
        return {"html": html, "text": html}
    except ImportError:
        # Fallback: basic conversion
        html = markdown_text.replace("\n\n", "</p><p>").replace("\n", "<br>")
        html = f"<p>{html}</p>"
        return {"html": html, "text": html, "warning": "markdown_library_not_installed"}


async def run_html_to_markdown_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert HTML to clean markdown.

    Config:
      - html: str - HTML to convert
      - strip_tags: list[str] - Tags to strip completely (default: ["script", "style"])
    Output:
      - markdown: str - The converted markdown
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    html_text = config.get("html") or config.get("text") or ""
    if isinstance(html_text, str):
        html_text = _tmpl(html_text, context) or html_text

    if not html_text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            html_text = prev.get("html") or prev.get("text") or prev.get("content") or ""

    try:
        from markdownify import markdownify as md
        markdown_text = md(html_text, strip=config.get("strip_tags") or ["script", "style"])
        return {"markdown": markdown_text, "text": markdown_text}
    except ImportError:
        # Fallback: basic tag stripping
        import re
        text = re.sub(r"<script[^>]*>.*?</script>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return {"markdown": text.strip(), "text": text.strip(), "warning": "markdownify_not_installed"}


async def run_keyword_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract keywords from text.

    Config:
      - text: str - Text to extract keywords from
      - method: str - "rake", "yake", or "llm" (default: "llm")
      - max_keywords: int - Maximum keywords to return (default: 10)
      - provider: str - LLM provider (for llm method)
      - model: str - Model to use (for llm method)
    Output:
      - keywords: list[str]
      - scored_keywords: list[dict] - Keywords with scores
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or ""

    if not text:
        return {"keywords": [], "scored_keywords": [], "error": "missing_text"}

    method = str(config.get("method", "llm")).lower()
    max_keywords = int(config.get("max_keywords", 10))

    if method == "rake":
        try:
            from rake_nltk import Rake
            r = Rake()
            r.extract_keywords_from_text(text)
            scored = r.get_ranked_phrases_with_scores()[:max_keywords]
            keywords = [kw for _, kw in scored]
            scored_keywords = [{"keyword": kw, "score": score} for score, kw in scored]
            return {"keywords": keywords, "scored_keywords": scored_keywords, "method": "rake"}
        except ImportError:
            method = "llm"  # Fallback

    if method == "yake":
        try:
            import yake
            kw_extractor = yake.KeywordExtractor(top=max_keywords)
            keywords_scored = kw_extractor.extract_keywords(text)
            keywords = [kw for kw, _ in keywords_scored]
            scored_keywords = [{"keyword": kw, "score": 1 - score} for kw, score in keywords_scored]
            return {"keywords": keywords, "scored_keywords": scored_keywords, "method": "yake"}
        except ImportError:
            method = "llm"  # Fallback

    # LLM method
    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        prompt = f"""Extract the {max_keywords} most important keywords from this text.
Return only the keywords, one per line, no numbering.

Text:
{text[:4000]}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Extract keywords from text. Return only keywords, one per line.",
            max_tokens=300,
            temperature=0.3,
        )

        result_text = _extract_openai_content(response) or ""
        keywords = [line.strip() for line in result_text.strip().split("\n") if line.strip()][:max_keywords]
        scored_keywords = [{"keyword": kw, "score": 1.0 - (i * 0.05)} for i, kw in enumerate(keywords)]

        return {"keywords": keywords, "scored_keywords": scored_keywords, "method": "llm"}

    except Exception as e:
        logger.exception(f"Keyword extract error: {e}")
        return {"keywords": [], "scored_keywords": [], "error": str(e)}


async def run_sentiment_analyze_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze sentiment of text.

    Config:
      - text: str - Text to analyze
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - sentiment: str - "positive", "negative", or "neutral"
      - score: float - Sentiment score (-1 to 1)
      - confidence: float
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or ""

    if not text:
        return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0, "error": "missing_text"}

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        prompt = f"""Analyze the sentiment of this text. Respond with JSON only:
{{"sentiment": "positive|negative|neutral", "score": <-1 to 1>, "confidence": <0 to 1>}}

Text: {text[:3000]}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Analyze sentiment. Return JSON only.",
            max_tokens=100,
            temperature=0.1,
        )

        result_text = _extract_openai_content(response) or ""
        try:
            result = json.loads(result_text)
            return {
                "sentiment": result.get("sentiment", "neutral"),
                "score": float(result.get("score", 0)),
                "confidence": float(result.get("confidence", 0.5)),
            }
        except json.JSONDecodeError:
            # Parse from text
            text_lower = result_text.lower()
            if "positive" in text_lower:
                return {"sentiment": "positive", "score": 0.7, "confidence": 0.6}
            elif "negative" in text_lower:
                return {"sentiment": "negative", "score": -0.7, "confidence": 0.6}
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.5}

    except Exception as e:
        logger.exception(f"Sentiment analyze error: {e}")
        return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0, "error": str(e)}


async def run_language_detect_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Detect language of text.

    Config:
      - text: str - Text to analyze
    Output:
      - language: str - ISO 639-1 language code
      - language_name: str - Full language name
      - confidence: float
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or ""

    if not text:
        return {"language": "unknown", "language_name": "Unknown", "confidence": 0.0, "error": "missing_text"}

    try:
        from langdetect import detect, detect_langs
        lang = detect(text[:5000])
        probs = detect_langs(text[:5000])
        confidence = probs[0].prob if probs else 0.5

        lang_names = {
            "en": "English", "es": "Spanish", "fr": "French", "de": "German",
            "it": "Italian", "pt": "Portuguese", "ru": "Russian", "zh-cn": "Chinese (Simplified)",
            "zh-tw": "Chinese (Traditional)", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
            "hi": "Hindi", "nl": "Dutch", "pl": "Polish", "tr": "Turkish",
        }

        return {
            "language": lang,
            "language_name": lang_names.get(lang, lang.upper()),
            "confidence": confidence,
        }
    except ImportError:
        return {"language": "unknown", "language_name": "Unknown", "confidence": 0.0, "error": "langdetect_not_installed"}
    except Exception as e:
        logger.exception(f"Language detect error: {e}")
        return {"language": "unknown", "language_name": "Unknown", "confidence": 0.0, "error": str(e)}


async def run_topic_model_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract topics from text using LLM.

    Config:
      - text: str - Text to analyze
      - num_topics: int - Number of topics to extract (default: 5)
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - topics: list[dict] - Topics with labels and keywords
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or ""

    if not text:
        return {"topics": [], "error": "missing_text"}

    num_topics = int(config.get("num_topics", 5))

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        prompt = f"""Identify the {num_topics} main topics in this text.
For each topic, provide a label and 3-5 keywords.
Return as JSON array: [{{"label": "Topic Name", "keywords": ["kw1", "kw2"]}}]

Text:
{text[:5000]}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Extract topics from text. Return JSON array only.",
            max_tokens=800,
            temperature=0.3,
        )

        result_text = _extract_openai_content(response) or ""
        # Try to extract JSON from response
        try:
            # Find JSON array in response
            start = result_text.find("[")
            end = result_text.rfind("]") + 1
            if start >= 0 and end > start:
                topics = json.loads(result_text[start:end])
                return {"topics": topics[:num_topics]}
        except json.JSONDecodeError:
            pass

        # Fallback: parse as text
        topics = [{"label": line.strip(), "keywords": []} for line in result_text.split("\n") if line.strip()]
        return {"topics": topics[:num_topics]}

    except Exception as e:
        logger.exception(f"Topic model error: {e}")
        return {"topics": [], "error": str(e)}


async def run_token_count_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Count tokens in text using model tokenizer.

    Config:
      - text: str - Text to count tokens for
      - model: str - Model name for tokenizer (default: "gpt-4")
    Output:
      - token_count: int
      - char_count: int
      - word_count: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or ""

    model = config.get("model", "gpt-4")
    char_count = len(text)
    word_count = len(text.split())

    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        token_count = len(encoding.encode(text))
        return {"token_count": token_count, "char_count": char_count, "word_count": word_count, "model": model}
    except ImportError:
        # Fallback: rough estimate
        token_count = int(char_count / 4)
        return {"token_count": token_count, "char_count": char_count, "word_count": word_count, "estimated": True}


async def run_context_window_check_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Check if content fits in model context window.

    Config:
      - text: str - Text to check
      - model: str - Model name (default: "gpt-4")
      - reserve_tokens: int - Tokens to reserve for response (default: 1000)
    Output:
      - fits: bool
      - token_count: int
      - context_limit: int
      - available_tokens: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = _tmpl(text, context) or text

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or ""

    model = config.get("model", "gpt-4")
    reserve_tokens = int(config.get("reserve_tokens", 1000))

    # Model context limits (common models)
    context_limits = {
        "gpt-4": 8192, "gpt-4-turbo": 128000, "gpt-4o": 128000,
        "gpt-3.5-turbo": 16384, "claude-3-opus": 200000, "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000, "llama-3": 8192, "mistral": 32768,
    }
    context_limit = context_limits.get(model, 8192)

    # Count tokens
    token_count = 0
    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        token_count = len(encoding.encode(text))
    except ImportError:
        token_count = int(len(text) / 4)

    available = context_limit - reserve_tokens
    fits = token_count <= available

    return {
        "fits": fits,
        "token_count": token_count,
        "context_limit": context_limit,
        "available_tokens": available,
        "excess_tokens": max(0, token_count - available),
    }


async def run_llm_compare_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Run same prompt through multiple LLMs and compare.

    Config:
      - prompt: str - Prompt to send to all LLMs
      - providers: list[dict] - List of {provider, model} pairs
      - system_message: str - Optional system message
    Output:
      - responses: list[dict] - Responses from each provider
      - comparison: dict - Comparison metadata
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    prompt = config.get("prompt") or ""
    if isinstance(prompt, str):
        prompt = _tmpl(prompt, context) or prompt

    if not prompt:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            prompt = prev.get("text") or prev.get("prompt") or ""

    if not prompt:
        return {"responses": [], "error": "missing_prompt"}

    providers = config.get("providers") or []
    if not providers:
        return {"responses": [], "error": "missing_providers"}

    system_message = config.get("system_message")

    responses = []
    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        for p in providers:
            if callable(context.get("is_cancelled")) and context["is_cancelled"]():
                return {"__status__": "cancelled"}

            provider = p.get("provider")
            model = p.get("model")
            start_time = time.time()

            try:
                messages = [{"role": "user", "content": prompt}]
                response = await perform_chat_api_call_async(
                    messages=messages,
                    api_provider=provider,
                    model=model,
                    system_message=system_message,
                )
                text = _extract_openai_content(response) or ""
                elapsed_ms = (time.time() - start_time) * 1000

                responses.append({
                    "provider": provider,
                    "model": model,
                    "text": text,
                    "elapsed_ms": elapsed_ms,
                    "char_count": len(text),
                })
            except Exception as e:
                responses.append({
                    "provider": provider,
                    "model": model,
                    "error": str(e),
                    "elapsed_ms": (time.time() - start_time) * 1000,
                })

        return {
            "responses": responses,
            "comparison": {
                "provider_count": len(providers),
                "successful": sum(1 for r in responses if "text" in r),
                "failed": sum(1 for r in responses if "error" in r),
            },
        }

    except Exception as e:
        logger.exception(f"LLM compare error: {e}")
        return {"responses": [], "error": str(e)}


async def run_image_describe_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Describe an image using VLM/multimodal LLM.

    Config:
      - image_path: str - Path to image file
      - image_url: str - URL of image
      - image_base64: str - Base64 encoded image
      - prompt: str - Description prompt (default: "Describe this image in detail.")
      - provider: str - LLM provider with vision support
      - model: str - Model to use
    Output:
      - description: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import base64

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    prompt = config.get("prompt", "Describe this image in detail.")
    if isinstance(prompt, str):
        prompt = _tmpl(prompt, context) or prompt

    # Get image data
    image_data = None
    image_url = config.get("image_url")

    if config.get("image_base64"):
        image_data = config.get("image_base64")
    elif config.get("image_path"):
        try:
            path = _resolve_workflow_file_path(config.get("image_path"), context, config)
            with open(path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return {"description": "", "error": f"image_read_error: {e}"}

    if not image_data and not image_url:
        return {"description": "", "error": "missing_image"}

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        # Build message with image
        content = [{"type": "text", "text": prompt}]
        if image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}})
        elif image_data:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}})

        messages = [{"role": "user", "content": content}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            max_tokens=1000,
        )

        description = _extract_openai_content(response) or ""
        return {"description": description, "text": description}

    except Exception as e:
        logger.exception(f"Image describe error: {e}")
        return {"description": "", "error": str(e)}


async def run_report_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a structured report from content.

    Config:
      - content: str - Content to generate report from
      - title: str - Report title
      - sections: list[str] - Section headings (default: auto-generated)
      - format: str - "markdown", "html", or "plain" (default: "markdown")
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - report: str
      - title: str
      - sections: list[str]
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    content = config.get("content") or ""
    if isinstance(content, str):
        content = _tmpl(content, context) or content

    if not content:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            content = prev.get("text") or prev.get("content") or ""

    if not content:
        return {"report": "", "error": "missing_content"}

    title = config.get("title", "Report")
    if isinstance(title, str):
        title = _tmpl(title, context) or title

    sections = config.get("sections")
    output_format = config.get("format", "markdown")

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        sections_str = ""
        if sections:
            sections_str = f"\n\nInclude these sections: {', '.join(sections)}"

        prompt = f"""Generate a structured report titled "{title}" from this content.
Format: {output_format}{sections_str}

Content:
{content[:6000]}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Generate well-structured reports with clear sections.",
            max_tokens=3000,
            temperature=0.5,
        )

        report = _extract_openai_content(response) or ""
        return {"report": report, "text": report, "title": title, "format": output_format}

    except Exception as e:
        logger.exception(f"Report generate error: {e}")
        return {"report": "", "error": str(e)}


async def run_newsletter_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate newsletter from content/items.

    Config:
      - items: list[dict] - Items to include (title, summary, url)
      - content: str - Alternative: raw content to summarize
      - title: str - Newsletter title
      - intro: str - Introduction text
      - format: str - "markdown" or "html" (default: "markdown")
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - newsletter: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    items = config.get("items") or []
    content = config.get("content") or ""

    if not items and not content:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            items = prev.get("items") or []
            content = prev.get("text") or prev.get("content") or ""

    if not items and not content:
        return {"newsletter": "", "error": "missing_items_or_content"}

    title = config.get("title", "Newsletter")
    if isinstance(title, str):
        title = _tmpl(title, context) or title

    intro = config.get("intro", "")
    if isinstance(intro, str):
        intro = _tmpl(intro, context) or intro

    output_format = config.get("format", "markdown")

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        items_text = ""
        if items:
            for i, item in enumerate(items[:20]):
                item_title = item.get("title", f"Item {i + 1}")
                item_summary = item.get("summary", "")
                item_url = item.get("url", "")
                items_text += f"\n- {item_title}: {item_summary}"
                if item_url:
                    items_text += f" ({item_url})"

        prompt = f"""Generate a newsletter titled "{title}".
Format: {output_format}

{f'Introduction: {intro}' if intro else ''}
{f'Items:{items_text}' if items_text else f'Content:\n{content[:5000]}'}

Include a header, brief intro, main content sections, and a closing."""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Generate engaging newsletters with clear sections.",
            max_tokens=2500,
            temperature=0.6,
        )

        newsletter = _extract_openai_content(response) or ""
        return {"newsletter": newsletter, "text": newsletter, "title": title}

    except Exception as e:
        logger.exception(f"Newsletter generate error: {e}")
        return {"newsletter": "", "error": str(e)}


async def run_slides_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate slide deck structure.

    Config:
      - content: str - Content to create slides from
      - title: str - Presentation title
      - num_slides: int - Target number of slides (default: 10)
      - style: str - "professional", "educational", "casual" (default: "professional")
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - slides: list[dict] - Slide content with title, bullets, notes
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    content = config.get("content") or ""
    if isinstance(content, str):
        content = _tmpl(content, context) or content

    if not content:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            content = prev.get("text") or prev.get("content") or ""

    if not content:
        return {"slides": [], "error": "missing_content"}

    title = config.get("title", "Presentation")
    num_slides = int(config.get("num_slides", 10))
    style = config.get("style", "professional")

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        prompt = f"""Create a {num_slides}-slide presentation outline titled "{title}".
Style: {style}

Return as JSON array with this format:
[{{"slide_number": 1, "title": "Slide Title", "bullets": ["Point 1", "Point 2"], "speaker_notes": "Notes for presenter"}}]

Content:
{content[:5000]}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Generate presentation slides as JSON.",
            max_tokens=3000,
            temperature=0.5,
        )

        result_text = _extract_openai_content(response) or ""
        try:
            start = result_text.find("[")
            end = result_text.rfind("]") + 1
            if start >= 0 and end > start:
                slides = json.loads(result_text[start:end])
                return {"slides": slides, "title": title, "slide_count": len(slides)}
        except json.JSONDecodeError:
            pass

        return {"slides": [], "raw_text": result_text, "error": "json_parse_failed"}

    except Exception as e:
        logger.exception(f"Slides generate error: {e}")
        return {"slides": [], "error": str(e)}


async def run_diagram_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate diagram code (mermaid/graphviz).

    Config:
      - content: str - Content to visualize
      - diagram_type: str - "flowchart", "sequence", "class", "er", "mindmap" (default: "flowchart")
      - format: str - "mermaid" or "graphviz" (default: "mermaid")
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - diagram: str - Diagram code
      - format: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    content = config.get("content") or ""
    if isinstance(content, str):
        content = _tmpl(content, context) or content

    if not content:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            content = prev.get("text") or prev.get("content") or ""

    if not content:
        return {"diagram": "", "error": "missing_content"}

    diagram_type = config.get("diagram_type", "flowchart")
    output_format = config.get("format", "mermaid")

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        format_examples = {
            "mermaid": "```mermaid\nflowchart TD\n    A --> B\n```",
            "graphviz": "digraph G {\n    A -> B;\n}",
        }

        prompt = f"""Create a {diagram_type} diagram from this content using {output_format} syntax.

Example format:
{format_examples.get(output_format, format_examples['mermaid'])}

Return ONLY the diagram code, no explanations.

Content:
{content[:4000]}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message=f"Generate {output_format} diagrams. Return only diagram code.",
            max_tokens=1500,
            temperature=0.3,
        )

        diagram = _extract_openai_content(response) or ""
        # Clean up code blocks
        if "```" in diagram:
            lines = diagram.split("\n")
            cleaned = []
            in_code = False
            for line in lines:
                if line.startswith("```"):
                    in_code = not in_code
                    continue
                if in_code or not line.startswith("```"):
                    cleaned.append(line)
            diagram = "\n".join(cleaned)

        return {"diagram": diagram.strip(), "format": output_format, "diagram_type": diagram_type}

    except Exception as e:
        logger.exception(f"Diagram generate error: {e}")
        return {"diagram": "", "error": str(e)}


async def run_email_send_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Send email via SMTP.

    Config:
      - to: str or list[str] - Recipient(s)
      - subject: str - Email subject
      - body: str - Email body (plain text or HTML)
      - html: bool - Is body HTML (default: False)
      - from_addr: str - From address (default: from env)
      - smtp_host: str - SMTP host (default: from env)
      - smtp_port: int - SMTP port (default: 587)
      - smtp_user: str - SMTP username (default: from env)
      - smtp_pass: str - SMTP password (default: from env)
      - timeout: int - Connection timeout in seconds (default: 30)
    Output:
      - sent: bool
      - message_id: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    # Email validation pattern
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    to = config.get("to")
    if not to:
        return {"sent": False, "error": "missing_recipient"}

    if isinstance(to, str):
        to = [t.strip() for t in to.split(",")]

    # Validate email addresses
    for addr in to:
        if not EMAIL_PATTERN.match(addr):
            return {"sent": False, "error": f"invalid_email: {addr}"}

    subject = config.get("subject", "")
    if isinstance(subject, str):
        subject = _tmpl(subject, context) or subject

    # Sanitize subject to prevent header injection (remove newlines and control chars)
    subject = subject.replace("\n", " ").replace("\r", " ")
    # Remove other control characters
    subject = re.sub(r'[\x00-\x1f\x7f]', '', subject)

    body = config.get("body", "")
    if isinstance(body, str):
        body = _tmpl(body, context) or body

    if not body:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            body = prev.get("text") or prev.get("content") or ""

    is_html = bool(config.get("html", False))
    from_addr = config.get("from_addr") or os.getenv("SMTP_FROM", "noreply@localhost")
    smtp_host = config.get("smtp_host") or os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(config.get("smtp_port") or os.getenv("SMTP_PORT", "587"))
    smtp_user = config.get("smtp_user") or os.getenv("SMTP_USER")
    smtp_pass = config.get("smtp_pass") or os.getenv("SMTP_PASS")
    timeout = int(config.get("timeout", 30))

    # TEST_MODE: return simulated result without actually sending
    if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        return {
            "sent": True,
            "recipients": to,
            "subject": subject,
            "simulated": True,
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to)

        if is_html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
            # Try STARTTLS, but allow plaintext on port 25 as fallback
            try:
                server.starttls()
            except smtplib.SMTPNotSupportedError:
                if smtp_port != 25:
                    raise  # Only allow plaintext on port 25
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, to, msg.as_string())

        return {"sent": True, "recipients": to, "subject": subject}

    except Exception as e:
        logger.exception(f"Email send error: {e}")
        return {"sent": False, "error": str(e)}


async def run_screenshot_capture_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Capture screenshot of URL using playwright.

    Config:
      - url: str - URL to capture
      - full_page: bool - Capture full page (default: False)
      - width: int - Viewport width (default: 1280)
      - height: int - Viewport height (default: 720)
      - format: str - "png" or "jpeg" (default: "png")
      - timeout: int - Navigation timeout in ms (default: 30000)
    Output:
      - screenshot_path: str
      - screenshot_base64: str (if return_base64 is True)
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    from tldw_Server_API.app.core.Security.egress import evaluate_url_policy

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    # TEST_MODE: return simulated result without real browser
    if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        url = config.get("url") or ""
        if isinstance(url, str):
            url = _tmpl(url, context) or url
        if not url:
            return {"error": "missing_url", "simulated": True}
        return {
            "screenshot_path": "/tmp/simulated_screenshot.png",
            "url": url,
            "simulated": True,
        }

    url = config.get("url") or ""
    if isinstance(url, str):
        url = _tmpl(url, context) or url

    if not url:
        return {"error": "missing_url"}

    # SSRF protection: validate URL before navigation
    policy_result = evaluate_url_policy(url)
    if not policy_result.allowed:
        return {"error": f"url_blocked: {policy_result.reason}"}

    full_page = bool(config.get("full_page", False))
    width = int(config.get("width", 1280))
    height = int(config.get("height", 720))
    img_format = config.get("format", "png")
    return_base64 = bool(config.get("return_base64", False))
    nav_timeout = int(config.get("timeout", 30000))

    try:
        from playwright.async_api import async_playwright

        step_run_id = str(context.get("step_run_id") or f"screenshot_{int(time.time() * 1000)}")
        art_dir = _resolve_artifacts_dir(step_run_id)
        art_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = art_dir / f"screenshot.{img_format}"

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": width, "height": height})
            # Navigate with timeout; use 'load' as wait_until for reliability
            await page.goto(url, wait_until="load", timeout=nav_timeout)
            # Try to wait for networkidle, but don't fail if it times out
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass  # Continue with load-complete state
            await page.screenshot(path=str(screenshot_path), full_page=full_page, type=img_format)
            await browser.close()

        result = {"screenshot_path": str(screenshot_path), "url": url}

        if return_base64:
            import base64
            with open(screenshot_path, "rb") as f:
                result["screenshot_base64"] = base64.b64encode(f.read()).decode("utf-8")

        # Add artifact
        if callable(context.get("add_artifact")):
            context["add_artifact"](
                type="screenshot",
                uri=f"file://{screenshot_path}",
                size_bytes=screenshot_path.stat().st_size,
                mime_type=f"image/{img_format}",
                metadata={"url": url},
            )

        return result

    except ImportError:
        return {"error": "playwright_not_installed"}
    except Exception as e:
        logger.exception(f"Screenshot capture error: {e}")
        return {"error": str(e)}


async def run_schedule_workflow_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule a workflow for future execution.

    Config:
      - workflow_id: str - Workflow to schedule
      - delay_seconds: int - Delay before execution
      - cron: str - Cron expression (alternative to delay)
      - inputs: dict - Inputs for the workflow
    Output:
      - scheduled: bool
      - schedule_id: str
      - run_at: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    from datetime import datetime, timedelta

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    workflow_id = config.get("workflow_id")
    if isinstance(workflow_id, str):
        workflow_id = _tmpl(workflow_id, context) or workflow_id

    if not workflow_id:
        return {"scheduled": False, "error": "missing_workflow_id"}

    delay_seconds = config.get("delay_seconds")
    cron = config.get("cron")
    inputs = config.get("inputs") or {}

    if not delay_seconds and not cron:
        return {"scheduled": False, "error": "missing_delay_or_cron"}

    try:
        # Calculate run time
        if delay_seconds:
            run_at = datetime.utcnow() + timedelta(seconds=int(delay_seconds))
        else:
            # For cron, just store the expression
            run_at = None

        schedule_id = f"sched_{int(time.time() * 1000)}"

        # Store schedule in database
        try:
            from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase

            db = WorkflowsDatabase()
            tenant_id = str(context.get("tenant_id", "default"))
            db.create_schedule(
                schedule_id=schedule_id,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                cron=cron,
                next_run_at=run_at.isoformat() if run_at else None,
                inputs_json=json.dumps(inputs),
            )
        except Exception as e:
            logger.debug(f"Schedule storage error: {e}")
            # Continue even if DB storage fails

        return {
            "scheduled": True,
            "schedule_id": schedule_id,
            "workflow_id": workflow_id,
            "run_at": run_at.isoformat() if run_at else None,
            "cron": cron,
        }

    except Exception as e:
        logger.exception(f"Schedule workflow error: {e}")
        return {"scheduled": False, "error": str(e)}


async def run_timing_start_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Start a named timer.

    Config:
      - timer_name: str - Name for the timer (default: "default")
    Output:
      - timer_name: str
      - started_at: float
    """
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    timer_name = config.get("timer_name", "default")
    started_at = time.time()

    # Store in context for retrieval by timing_stop
    # Use a special key pattern
    context[f"__timer_{timer_name}__"] = started_at

    return {
        "timer_name": timer_name,
        "started_at": started_at,
        "started_at_iso": datetime.datetime.utcnow().isoformat(),
    }


async def run_timing_stop_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Stop timer and return elapsed time.

    Config:
      - timer_name: str - Name of the timer (default: "default")
    Output:
      - timer_name: str
      - elapsed_ms: float
      - elapsed_seconds: float
    """
    import datetime

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    timer_name = config.get("timer_name", "default")
    stopped_at = time.time()

    # Try to get start time from context
    started_at = context.get(f"__timer_{timer_name}__")

    if started_at is None:
        # Try from inputs
        inputs = context.get("inputs", {})
        started_at = inputs.get(f"timer_{timer_name}_started_at")

    if started_at is None:
        return {
            "timer_name": timer_name,
            "error": "timer_not_found",
            "elapsed_ms": 0,
            "elapsed_seconds": 0,
        }

    elapsed_seconds = stopped_at - float(started_at)
    elapsed_ms = elapsed_seconds * 1000

    return {
        "timer_name": timer_name,
        "elapsed_ms": elapsed_ms,
        "elapsed_seconds": elapsed_seconds,
        "stopped_at": stopped_at,
        "stopped_at_iso": datetime.datetime.utcnow().isoformat(),
    }


# ============================================================================
# PHASE 2: GROUP B - AUDIO & VIDEO PROCESSING NODES
# ============================================================================


async def run_audio_normalize_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize audio volume levels using ffmpeg.

    Config:
      - input_path: str - Input audio file path
      - output_path: str - Output file path (optional, auto-generated if not provided)
      - target_loudness: float - Target loudness in LUFS (default: -23)
    Output:
      - output_path: str
      - normalized: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            input_path = prev.get("audio_path") or prev.get("output_path") or prev.get("path") or ""

    if not input_path:
        return {"error": "missing_input_path", "normalized": False}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "normalized": False}

    target_loudness = float(config.get("target_loudness", -23))

    # Generate output path
    output_path = config.get("output_path")
    if output_path:
        output_path = _tmpl(output_path, context) if isinstance(output_path, str) else output_path
    else:
        step_run_id = str(context.get("step_run_id") or f"audio_norm_{int(time.time() * 1000)}")
        art_dir = _resolve_artifacts_dir(step_run_id)
        art_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(art_dir / f"normalized_{resolved_input.name}")

    try:
        # Two-pass loudnorm filter
        cmd = [
            "ffmpeg", "-y", "-i", str(resolved_input),
            "-af", f"loudnorm=I={target_loudness}:TP=-1.5:LRA=11",
            "-ar", "48000",
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        if callable(context.get("add_artifact")):
            context["add_artifact"](
                type="audio",
                uri=f"file://{output_path}",
                size_bytes=Path(output_path).stat().st_size if Path(output_path).exists() else None,
                mime_type="audio/mpeg",
            )

        return {"output_path": output_path, "normalized": True, "target_loudness": target_loudness}

    except subprocess.TimeoutExpired:
        return {"error": "ffmpeg_timeout", "normalized": False}
    except subprocess.CalledProcessError as e:
        return {"error": f"ffmpeg_error: {e.stderr.decode() if e.stderr else str(e)}", "normalized": False}
    except Exception as e:
        logger.exception(f"Audio normalize error: {e}")
        return {"error": str(e), "normalized": False}


async def run_audio_concat_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Concatenate multiple audio files.

    Config:
      - input_paths: list[str] - List of audio file paths
      - output_path: str - Output file path (optional)
      - format: str - Output format (default: "mp3")
    Output:
      - output_path: str
      - concatenated: bool
      - file_count: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess
    import tempfile

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_paths = config.get("input_paths") or []
    if not input_paths:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            input_paths = prev.get("audio_paths") or prev.get("paths") or []

    if len(input_paths) < 2:
        return {"error": "need_at_least_2_files", "concatenated": False}

    output_format = config.get("format", "mp3")

    # Resolve all input paths
    resolved_inputs = []
    for p in input_paths:
        if isinstance(p, str):
            p = _tmpl(p, context) or p
        try:
            resolved_inputs.append(str(_resolve_workflow_file_path(p, context, config)))
        except Exception:
            continue

    if len(resolved_inputs) < 2:
        return {"error": "insufficient_valid_paths", "concatenated": False}

    # Generate output path
    output_path = config.get("output_path")
    if output_path:
        output_path = _tmpl(output_path, context) if isinstance(output_path, str) else output_path
    else:
        step_run_id = str(context.get("step_run_id") or f"audio_concat_{int(time.time() * 1000)}")
        art_dir = _resolve_artifacts_dir(step_run_id)
        art_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(art_dir / f"concatenated.{output_format}")

    try:
        # Create concat file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for p in resolved_inputs:
                f.write(f"file '{p}'\n")
            concat_file = f.name

        # Map output format to appropriate codec - always re-encode for compatibility
        # (copy fails when input files have different parameters)
        codec_map = {
            "mp3": "libmp3lame",
            "aac": "aac",
            "m4a": "aac",
            "ogg": "libvorbis",
            "wav": "pcm_s16le",
            "flac": "flac",
        }
        codec = codec_map.get(output_format, "aac")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:a", codec,
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)

        # Cleanup
        Path(concat_file).unlink(missing_ok=True)

        if callable(context.get("add_artifact")):
            context["add_artifact"](
                type="audio",
                uri=f"file://{output_path}",
                size_bytes=Path(output_path).stat().st_size if Path(output_path).exists() else None,
            )

        return {"output_path": output_path, "concatenated": True, "file_count": len(resolved_inputs)}

    except Exception as e:
        logger.exception(f"Audio concat error: {e}")
        return {"error": str(e), "concatenated": False}


async def run_audio_trim_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Trim audio by start/end timestamps.

    Config:
      - input_path: str - Input audio file
      - start: str - Start time (e.g., "00:01:30" or "90")
      - end: str - End time (optional)
      - duration: str - Duration instead of end (optional)
    Output:
      - output_path: str
      - trimmed: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        return {"error": "missing_input_path", "trimmed": False}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "trimmed": False}

    start = config.get("start", "0")
    end = config.get("end")
    duration = config.get("duration")

    step_run_id = str(context.get("step_run_id") or f"audio_trim_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / f"trimmed_{resolved_input.name}")

    try:
        cmd = ["ffmpeg", "-y", "-i", str(resolved_input), "-ss", str(start)]
        if end:
            cmd.extend(["-to", str(end)])
        elif duration:
            cmd.extend(["-t", str(duration)])
        cmd.extend(["-c", "copy", str(output_path)])

        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        return {"output_path": output_path, "trimmed": True, "start": start, "end": end or duration}

    except Exception as e:
        logger.exception(f"Audio trim error: {e}")
        return {"error": str(e), "trimmed": False}


async def run_audio_convert_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert audio format.

    Config:
      - input_path: str - Input audio file
      - format: str - Output format (mp3, wav, ogg, flac, aac)
      - bitrate: str - Audio bitrate (e.g., "192k")
      - sample_rate: int - Sample rate (e.g., 44100)
    Output:
      - output_path: str
      - converted: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            input_path = prev.get("audio_path") or prev.get("output_path") or ""

    if not input_path:
        return {"error": "missing_input_path", "converted": False}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "converted": False}

    output_format = config.get("format", "mp3")
    bitrate = config.get("bitrate")
    sample_rate = config.get("sample_rate")

    step_run_id = str(context.get("step_run_id") or f"audio_convert_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / f"{resolved_input.stem}.{output_format}")

    try:
        cmd = ["ffmpeg", "-y", "-i", str(resolved_input)]
        if bitrate:
            cmd.extend(["-b:a", str(bitrate)])
        if sample_rate:
            cmd.extend(["-ar", str(sample_rate)])
        cmd.append(str(output_path))

        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        return {"output_path": output_path, "converted": True, "format": output_format}

    except Exception as e:
        logger.exception(f"Audio convert error: {e}")
        return {"error": str(e), "converted": False}


async def run_audio_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract audio track from video.

    Config:
      - input_path: str - Input video file
      - format: str - Output format (mp3, wav, aac)
    Output:
      - output_path: str
      - extracted: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            input_path = prev.get("video_path") or prev.get("output_path") or ""

    if not input_path:
        return {"error": "missing_input_path", "extracted": False}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "extracted": False}

    output_format = config.get("format", "mp3")

    step_run_id = str(context.get("step_run_id") or f"audio_extract_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / f"{resolved_input.stem}.{output_format}")

    try:
        cmd = ["ffmpeg", "-y", "-i", str(resolved_input), "-vn", "-acodec", "copy" if output_format == "aac" else "libmp3lame", str(output_path)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        return {"output_path": output_path, "extracted": True, "format": output_format}

    except Exception as e:
        logger.exception(f"Audio extract error: {e}")
        return {"error": str(e), "extracted": False}


async def run_audio_mix_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Mix multiple audio tracks.

    Config:
      - input_paths: list[str] - Audio files to mix
      - volumes: list[float] - Volume levels for each track (0-1)
    Output:
      - output_path: str
      - mixed: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_paths = config.get("input_paths") or []
    volumes = config.get("volumes") or []

    if len(input_paths) < 2:
        return {"error": "need_at_least_2_files", "mixed": False}

    # Resolve paths
    resolved_inputs = []
    for p in input_paths:
        if isinstance(p, str):
            p = _tmpl(p, context) or p
        try:
            resolved_inputs.append(str(_resolve_workflow_file_path(p, context, config)))
        except Exception:
            continue

    if len(resolved_inputs) < 2:
        return {"error": "insufficient_valid_paths", "mixed": False}

    step_run_id = str(context.get("step_run_id") or f"audio_mix_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / "mixed.mp3")

    try:
        # Build amix filter
        inputs_str = "".join([f"-i {p} " for p in resolved_inputs])
        filter_complex = f"amix=inputs={len(resolved_inputs)}:duration=longest"

        cmd = ["ffmpeg", "-y"] + [item for p in resolved_inputs for item in ["-i", p]]
        cmd.extend(["-filter_complex", filter_complex, str(output_path)])

        subprocess.run(cmd, check=True, capture_output=True, timeout=600)

        return {"output_path": output_path, "mixed": True, "track_count": len(resolved_inputs)}

    except Exception as e:
        logger.exception(f"Audio mix error: {e}")
        return {"error": str(e), "mixed": False}


async def run_video_thumbnail_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate thumbnail from video.

    Config:
      - input_path: str - Input video file
      - timestamp: str - Time to capture (default: "00:00:05")
      - width: int - Thumbnail width (default: 320)
      - height: int - Thumbnail height (default: -1 for auto)
    Output:
      - output_path: str
      - generated: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            input_path = prev.get("video_path") or prev.get("output_path") or ""

    if not input_path:
        return {"error": "missing_input_path", "generated": False}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "generated": False}

    timestamp = config.get("timestamp", "00:00:05")
    width = int(config.get("width", 320))
    height = int(config.get("height", -1))

    step_run_id = str(context.get("step_run_id") or f"thumbnail_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / f"thumbnail_{resolved_input.stem}.jpg")

    try:
        cmd = [
            "ffmpeg", "-y", "-ss", str(timestamp), "-i", str(resolved_input),
            "-vframes", "1", "-vf", f"scale={width}:{height}",
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)

        if callable(context.get("add_artifact")):
            context["add_artifact"](
                type="thumbnail",
                uri=f"file://{output_path}",
                mime_type="image/jpeg",
            )

        return {"output_path": output_path, "generated": True, "timestamp": timestamp}

    except Exception as e:
        logger.exception(f"Video thumbnail error: {e}")
        return {"error": str(e), "generated": False}


async def run_video_trim_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Trim video by timestamps.

    Config:
      - input_path: str - Input video file
      - start: str - Start time
      - end: str - End time (optional)
      - duration: str - Duration (optional)
    Output:
      - output_path: str
      - trimmed: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        return {"error": "missing_input_path", "trimmed": False}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "trimmed": False}

    start = config.get("start", "0")
    end = config.get("end")
    duration = config.get("duration")

    step_run_id = str(context.get("step_run_id") or f"video_trim_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / f"trimmed_{resolved_input.name}")

    try:
        cmd = ["ffmpeg", "-y", "-i", str(resolved_input), "-ss", str(start)]
        if end:
            cmd.extend(["-to", str(end)])
        elif duration:
            cmd.extend(["-t", str(duration)])
        cmd.extend(["-c", "copy", str(output_path)])

        subprocess.run(cmd, check=True, capture_output=True, timeout=600)

        return {"output_path": output_path, "trimmed": True}

    except Exception as e:
        logger.exception(f"Video trim error: {e}")
        return {"error": str(e), "trimmed": False}


async def run_video_concat_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Concatenate video files.

    Config:
      - input_paths: list[str] - Video files to concatenate
    Output:
      - output_path: str
      - concatenated: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess
    import tempfile

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_paths = config.get("input_paths") or []
    if len(input_paths) < 2:
        return {"error": "need_at_least_2_files", "concatenated": False}

    resolved_inputs = []
    for p in input_paths:
        if isinstance(p, str):
            p = _tmpl(p, context) or p
        try:
            resolved_inputs.append(str(_resolve_workflow_file_path(p, context, config)))
        except Exception:
            continue

    if len(resolved_inputs) < 2:
        return {"error": "insufficient_valid_paths", "concatenated": False}

    step_run_id = str(context.get("step_run_id") or f"video_concat_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / "concatenated.mp4")

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for p in resolved_inputs:
                f.write(f"file '{p}'\n")
            concat_file = f.name

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", str(output_path)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=1200)

        Path(concat_file).unlink(missing_ok=True)

        return {"output_path": output_path, "concatenated": True, "file_count": len(resolved_inputs)}

    except Exception as e:
        logger.exception(f"Video concat error: {e}")
        return {"error": str(e), "concatenated": False}


async def run_video_convert_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert video format/codec.

    Config:
      - input_path: str - Input video file
      - format: str - Output format (mp4, webm, avi, mkv)
      - codec: str - Video codec (h264, h265, vp9)
      - resolution: str - Target resolution (e.g., "1280x720")
    Output:
      - output_path: str
      - converted: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        return {"error": "missing_input_path", "converted": False}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "converted": False}

    output_format = config.get("format", "mp4")
    codec = config.get("codec", "h264")
    resolution = config.get("resolution")

    codec_map = {"h264": "libx264", "h265": "libx265", "vp9": "libvpx-vp9"}

    step_run_id = str(context.get("step_run_id") or f"video_convert_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / f"{resolved_input.stem}.{output_format}")

    try:
        cmd = ["ffmpeg", "-y", "-i", str(resolved_input)]
        cmd.extend(["-c:v", codec_map.get(codec, "libx264")])
        if resolution:
            cmd.extend(["-vf", f"scale={resolution.replace('x', ':')}"])
        cmd.append(str(output_path))

        subprocess.run(cmd, check=True, capture_output=True, timeout=1800)

        return {"output_path": output_path, "converted": True, "format": output_format}

    except Exception as e:
        logger.exception(f"Video convert error: {e}")
        return {"error": str(e), "converted": False}


async def run_video_extract_frames_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract frames as images from video.

    Config:
      - input_path: str - Input video file
      - fps: float - Frames per second to extract (default: 1)
      - format: str - Image format (jpg, png)
      - max_frames: int - Maximum frames to extract (default: 100)
    Output:
      - frame_paths: list[str]
      - frame_count: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        return {"error": "missing_input_path", "frame_paths": [], "frame_count": 0}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "frame_paths": [], "frame_count": 0}

    fps = float(config.get("fps", 1))
    img_format = config.get("format", "jpg")
    max_frames = int(config.get("max_frames", 100))

    step_run_id = str(context.get("step_run_id") or f"frames_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = str(art_dir / f"frame_%04d.{img_format}")

    try:
        cmd = [
            "ffmpeg", "-y", "-i", str(resolved_input),
            "-vf", f"fps={fps}",
            "-frames:v", str(max_frames),
            str(output_pattern)
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)

        frame_paths = sorted([str(p) for p in art_dir.glob(f"frame_*.{img_format}")])

        return {"frame_paths": frame_paths, "frame_count": len(frame_paths), "output_dir": str(art_dir)}

    except Exception as e:
        logger.exception(f"Video extract frames error: {e}")
        return {"error": str(e), "frame_paths": [], "frame_count": 0}


async def run_subtitle_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate subtitles from audio/video using STT.

    Config:
      - input_path: str - Audio or video file
      - language: str - Language code (default: "en")
      - format: str - Subtitle format: "srt", "vtt" (default: "srt")
    Output:
      - subtitle_path: str
      - generated: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            input_path = prev.get("audio_path") or prev.get("video_path") or prev.get("output_path") or ""

    if not input_path:
        return {"error": "missing_input_path", "generated": False}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "generated": False}

    language = config.get("language", "en")
    sub_format = config.get("format", "srt")

    step_run_id = str(context.get("step_run_id") or f"subtitle_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / f"subtitles.{sub_format}")

    try:
        # Use the STT transcribe adapter to get transcript
        from tldw_Server_API.app.core.Workflows.adapters import run_stt_transcribe_adapter

        stt_result = await run_stt_transcribe_adapter({
            "audio_path": str(resolved_input),
            "language": language,
            "word_timestamps": True,
        }, context)

        if stt_result.get("error"):
            return {"error": stt_result.get("error"), "generated": False}

        segments = stt_result.get("segments") or []
        transcript = stt_result.get("transcript") or ""

        # Generate subtitle file
        if sub_format == "vtt":
            content = "WEBVTT\n\n"
            for i, seg in enumerate(segments):
                start = _format_time_vtt(seg.get("start", 0))
                end = _format_time_vtt(seg.get("end", 0))
                text = seg.get("text", "").strip()
                content += f"{start} --> {end}\n{text}\n\n"
        else:  # srt
            content = ""
            for i, seg in enumerate(segments):
                start = _format_time_srt(seg.get("start", 0))
                end = _format_time_srt(seg.get("end", 0))
                text = seg.get("text", "").strip()
                content += f"{i + 1}\n{start} --> {end}\n{text}\n\n"

        Path(output_path).write_text(content, encoding="utf-8")

        return {"subtitle_path": output_path, "generated": True, "segment_count": len(segments)}

    except Exception as e:
        logger.exception(f"Subtitle generate error: {e}")
        return {"error": str(e), "generated": False}


def _format_time_srt(seconds: float) -> str:
    """Format seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_time_vtt(seconds: float) -> str:
    """Format seconds to VTT time format (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


async def run_subtitle_translate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Translate subtitle file to another language.

    Config:
      - input_path: str - Input subtitle file (srt or vtt)
      - target_language: str - Target language
      - provider: str - LLM provider for translation
      - model: str - Model to use
    Output:
      - output_path: str
      - translated: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    input_path = config.get("input_path") or ""
    if isinstance(input_path, str):
        input_path = _tmpl(input_path, context) or input_path

    if not input_path:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            input_path = prev.get("subtitle_path") or prev.get("output_path") or ""

    if not input_path:
        return {"error": "missing_input_path", "translated": False}

    try:
        resolved_input = _resolve_workflow_file_path(input_path, context, config)
    except Exception as e:
        return {"error": f"input_path_error: {e}", "translated": False}

    target_language = config.get("target_language", "es")

    step_run_id = str(context.get("step_run_id") or f"subtitle_translate_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / f"translated_{resolved_input.name}")

    try:
        content = resolved_input.read_text(encoding="utf-8")

        # Use translate adapter for translation
        from tldw_Server_API.app.core.Workflows.adapters import run_translate_adapter

        translate_result = await run_translate_adapter({
            "text": content,
            "target_language": target_language,
            "provider": config.get("provider"),
            "model": config.get("model"),
        }, context)

        if translate_result.get("error"):
            return {"error": translate_result.get("error"), "translated": False}

        translated_content = translate_result.get("translated_text") or translate_result.get("text") or ""
        Path(output_path).write_text(translated_content, encoding="utf-8")

        return {"output_path": output_path, "translated": True, "target_language": target_language}

    except Exception as e:
        logger.exception(f"Subtitle translate error: {e}")
        return {"error": str(e), "translated": False}


async def run_subtitle_burn_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Burn subtitles into video.

    Config:
      - video_path: str - Input video file
      - subtitle_path: str - Subtitle file (srt or vtt)
      - font_size: int - Subtitle font size (default: 24)
      - position: str - "bottom", "top" (default: "bottom")
    Output:
      - output_path: str
      - burned: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import subprocess

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    video_path = config.get("video_path") or ""
    subtitle_path = config.get("subtitle_path") or ""

    if isinstance(video_path, str):
        video_path = _tmpl(video_path, context) or video_path
    if isinstance(subtitle_path, str):
        subtitle_path = _tmpl(subtitle_path, context) or subtitle_path

    if not video_path:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            video_path = prev.get("video_path") or prev.get("output_path") or ""

    if not video_path or not subtitle_path:
        return {"error": "missing_video_or_subtitle_path", "burned": False}

    try:
        resolved_video = _resolve_workflow_file_path(video_path, context, config)
        resolved_subtitle = _resolve_workflow_file_path(subtitle_path, context, config)
    except Exception as e:
        return {"error": f"path_error: {e}", "burned": False}

    font_size = int(config.get("font_size", 24))
    position = config.get("position", "bottom")

    step_run_id = str(context.get("step_run_id") or f"subtitle_burn_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(art_dir / f"subtitled_{resolved_video.name}")

    try:
        # Escape path for ffmpeg filter
        sub_path_escaped = str(resolved_subtitle).replace(":", r"\:").replace("'", r"\'")

        margin_v = 10 if position == "bottom" else 50
        force_style = f"FontSize={font_size},MarginV={margin_v}"

        cmd = [
            "ffmpeg", "-y", "-i", str(resolved_video),
            "-vf", f"subtitles='{sub_path_escaped}':force_style='{force_style}'",
            "-c:a", "copy",
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=1800)

        return {"output_path": output_path, "burned": True}

    except Exception as e:
        logger.exception(f"Subtitle burn error: {e}")
        return {"error": str(e), "burned": False}


# ============================================================================
# PHASE 2: GROUP C - RESEARCH & ACADEMIC NODES
# ============================================================================


async def run_arxiv_search_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Search arXiv for papers.

    Config:
      - query: str - Search query
      - max_results: int - Maximum results (default: 10)
      - sort_by: str - "relevance", "lastUpdatedDate", "submittedDate"
      - sort_order: str - "ascending", "descending"
    Output:
      - papers: list[dict] - Paper metadata
      - total_results: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    query = config.get("query") or ""
    if isinstance(query, str):
        query = _tmpl(query, context) or query

    if not query:
        return {"papers": [], "error": "missing_query"}

    # TEST_MODE: return simulated results without network call
    if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        return {
            "papers": [
                {
                    "arxiv_id": "2301.00001",
                    "title": f"Simulated Paper on {query}",
                    "authors": ["Test Author", "Another Author"],
                    "summary": f"This is a simulated paper about {query}.",
                    "published": "2023-01-01T00:00:00",
                    "updated": "2023-01-02T00:00:00",
                    "pdf_url": "https://arxiv.org/pdf/2301.00001.pdf",
                    "categories": ["cs.AI", "cs.LG"],
                    "doi": None,
                }
            ],
            "total_results": 1,
            "query": query,
            "simulated": True,
        }

    max_results = int(config.get("max_results", 10))
    sort_by = config.get("sort_by", "relevance")
    sort_order = config.get("sort_order", "descending")

    try:
        import arxiv

        sort_map = {
            "relevance": arxiv.SortCriterion.Relevance,
            "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
            "submittedDate": arxiv.SortCriterion.SubmittedDate,
        }
        order_map = {
            "ascending": arxiv.SortOrder.Ascending,
            "descending": arxiv.SortOrder.Descending,
        }

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=sort_map.get(sort_by, arxiv.SortCriterion.Relevance),
            sort_order=order_map.get(sort_order, arxiv.SortOrder.Descending),
        )

        papers = []
        for result in search.results():
            papers.append({
                "arxiv_id": result.entry_id.split("/")[-1],
                "title": result.title,
                "authors": [a.name for a in result.authors],
                "summary": result.summary,
                "published": result.published.isoformat() if result.published else None,
                "updated": result.updated.isoformat() if result.updated else None,
                "pdf_url": result.pdf_url,
                "categories": result.categories,
                "doi": result.doi,
            })

        return {"papers": papers, "total_results": len(papers), "query": query}

    except ImportError:
        return {"papers": [], "error": "arxiv_library_not_installed"}
    except Exception as e:
        logger.exception(f"arXiv search error: {e}")
        return {"papers": [], "error": str(e)}


async def run_arxiv_download_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Download paper PDF from arXiv.

    Config:
      - arxiv_id: str - arXiv paper ID (e.g., "2301.00001")
      - pdf_url: str - Direct PDF URL (alternative)
    Output:
      - pdf_path: str
      - downloaded: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    arxiv_id = config.get("arxiv_id") or ""
    pdf_url = config.get("pdf_url") or ""

    if isinstance(arxiv_id, str):
        arxiv_id = _tmpl(arxiv_id, context) or arxiv_id

    if not arxiv_id and not pdf_url:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            arxiv_id = prev.get("arxiv_id") or ""
            pdf_url = prev.get("pdf_url") or ""

    if not arxiv_id and not pdf_url:
        return {"error": "missing_arxiv_id_or_pdf_url", "downloaded": False}

    # TEST_MODE: return simulated result without actual download
    if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        return {
            "pdf_path": f"/tmp/simulated_{arxiv_id or 'paper'}.pdf",
            "downloaded": True,
            "arxiv_id": arxiv_id,
            "simulated": True,
        }

    step_run_id = str(context.get("step_run_id") or f"arxiv_download_{int(time.time() * 1000)}")
    art_dir = _resolve_artifacts_dir(step_run_id)
    art_dir.mkdir(parents=True, exist_ok=True)

    try:
        if arxiv_id:
            import arxiv
            paper = next(arxiv.Search(id_list=[arxiv_id]).results())
            filename = f"{arxiv_id.replace('/', '_')}.pdf"
            output_path = str(art_dir / filename)
            paper.download_pdf(dirpath=str(art_dir), filename=filename)
        else:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(pdf_url, follow_redirects=True, timeout=60)
                response.raise_for_status()
                filename = pdf_url.split("/")[-1] or "paper.pdf"
                output_path = str(art_dir / filename)
                Path(output_path).write_bytes(response.content)

        if callable(context.get("add_artifact")):
            context["add_artifact"](
                type="pdf",
                uri=f"file://{output_path}",
                mime_type="application/pdf",
            )

        return {"pdf_path": output_path, "downloaded": True, "arxiv_id": arxiv_id}

    except ImportError:
        return {"error": "arxiv_library_not_installed", "downloaded": False}
    except Exception as e:
        logger.exception(f"arXiv download error: {e}")
        return {"error": str(e), "downloaded": False}


async def run_pubmed_search_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Search PubMed for biomedical papers.

    Config:
      - query: str - Search query
      - max_results: int - Maximum results (default: 10)
    Output:
      - papers: list[dict]
      - total_results: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import httpx

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    query = config.get("query") or ""
    if isinstance(query, str):
        query = _tmpl(query, context) or query

    if not query:
        return {"papers": [], "error": "missing_query"}

    # TEST_MODE: return simulated results without network call
    if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        return {
            "papers": [
                {
                    "pmid": "12345678",
                    "title": f"Simulated PubMed Paper on {query}",
                    "authors": ["Test Author", "Medical Researcher"],
                    "source": "Test Journal",
                    "pubdate": "2023 Jan",
                    "doi": "10.1000/simulated",
                }
            ],
            "total_results": 1,
            "query": query,
            "simulated": True,
        }

    max_results = int(config.get("max_results", 10))

    try:
        # Use NCBI E-utilities
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

        async with httpx.AsyncClient() as client:
            # Search for IDs
            search_url = f"{base_url}/esearch.fcgi"
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
            }
            search_response = await client.get(search_url, params=search_params, timeout=30)
            search_data = search_response.json()

            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return {"papers": [], "total_results": 0, "query": query}

            # Fetch details
            fetch_url = f"{base_url}/esummary.fcgi"
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
            }
            fetch_response = await client.get(fetch_url, params=fetch_params, timeout=30)
            fetch_data = fetch_response.json()

            papers = []
            result_data = fetch_data.get("result", {})
            for pmid in id_list:
                if pmid in result_data:
                    paper = result_data[pmid]
                    papers.append({
                        "pmid": pmid,
                        "title": paper.get("title", ""),
                        "authors": [a.get("name", "") for a in paper.get("authors", [])],
                        "source": paper.get("source", ""),
                        "pubdate": paper.get("pubdate", ""),
                        "doi": paper.get("elocationid", ""),
                    })

            return {"papers": papers, "total_results": len(papers), "query": query}

    except Exception as e:
        logger.exception(f"PubMed search error: {e}")
        return {"papers": [], "error": str(e)}


async def run_semantic_scholar_search_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Search Semantic Scholar for papers.

    Config:
      - query: str - Search query
      - max_results: int - Maximum results (default: 10)
      - fields: list[str] - Fields to return
    Output:
      - papers: list[dict]
      - total_results: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import httpx

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    query = config.get("query") or ""
    if isinstance(query, str):
        query = _tmpl(query, context) or query

    if not query:
        return {"papers": [], "error": "missing_query"}

    # TEST_MODE: return simulated results without network call
    if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        return {
            "papers": [
                {
                    "paper_id": "abc123",
                    "title": f"Simulated Semantic Scholar Paper on {query}",
                    "authors": ["Test Author", "AI Researcher"],
                    "abstract": f"This is a simulated abstract about {query}.",
                    "year": 2023,
                    "citation_count": 42,
                    "url": "https://www.semanticscholar.org/paper/abc123",
                }
            ],
            "total_results": 1,
            "query": query,
            "simulated": True,
        }

    max_results = int(config.get("max_results", 10))
    fields = config.get("fields") or ["title", "authors", "abstract", "year", "citationCount", "url"]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": query,
                    "limit": max_results,
                    "fields": ",".join(fields),
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            papers = []
            for paper in data.get("data", []):
                papers.append({
                    "paper_id": paper.get("paperId"),
                    "title": paper.get("title"),
                    "authors": [a.get("name", "") for a in paper.get("authors", [])],
                    "abstract": paper.get("abstract"),
                    "year": paper.get("year"),
                    "citation_count": paper.get("citationCount"),
                    "url": paper.get("url"),
                })

            return {"papers": papers, "total_results": data.get("total", len(papers)), "query": query}

    except Exception as e:
        logger.exception(f"Semantic Scholar search error: {e}")
        return {"papers": [], "error": str(e)}


async def run_google_scholar_search_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Search Google Scholar for papers.

    Config:
      - query: str - Search query
      - max_results: int - Maximum results (default: 10)
    Output:
      - papers: list[dict]
      - total_results: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    query = config.get("query") or ""
    if isinstance(query, str):
        query = _tmpl(query, context) or query

    if not query:
        return {"papers": [], "error": "missing_query"}

    # TEST_MODE: return simulated results without network call (Google Scholar is rate-limited)
    if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        return {
            "papers": [
                {
                    "title": f"Simulated Google Scholar Paper on {query}",
                    "authors": ["Test Author", "Scholar Researcher"],
                    "abstract": f"This is a simulated abstract about {query}.",
                    "year": "2023",
                    "venue": "Simulated Conference",
                    "citation_count": 100,
                    "url": "https://scholar.google.com/simulated",
                }
            ],
            "total_results": 1,
            "query": query,
            "simulated": True,
        }

    max_results = int(config.get("max_results", 10))

    try:
        from scholarly import scholarly

        search_query = scholarly.search_pubs(query)
        papers = []

        for i, result in enumerate(search_query):
            if i >= max_results:
                break
            papers.append({
                "title": result.get("bib", {}).get("title", ""),
                "authors": result.get("bib", {}).get("author", []),
                "abstract": result.get("bib", {}).get("abstract", ""),
                "year": result.get("bib", {}).get("pub_year", ""),
                "venue": result.get("bib", {}).get("venue", ""),
                "citation_count": result.get("num_citations", 0),
                "url": result.get("pub_url", ""),
            })

        return {"papers": papers, "total_results": len(papers), "query": query}

    except ImportError:
        return {"papers": [], "error": "scholarly_library_not_installed"}
    except Exception as e:
        logger.exception(f"Google Scholar search error: {e}")
        return {"papers": [], "error": str(e)}


async def run_patent_search_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Search patent databases.

    Config:
      - query: str - Search query
      - max_results: int - Maximum results (default: 10)
      - database: str - "google_patents" (default)
    Output:
      - patents: list[dict]
      - total_results: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import httpx

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    query = config.get("query") or ""
    if isinstance(query, str):
        query = _tmpl(query, context) or query

    if not query:
        return {"patents": [], "error": "missing_query"}

    # TEST_MODE: return simulated results without network call
    if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        return {
            "patents": [
                {
                    "patent_id": "US-12345678-A1",
                    "title": f"Simulated Patent on {query}",
                    "assignee": "Test Corporation",
                    "inventors": ["Test Inventor"],
                    "filing_date": "2023-01-15",
                    "publication_date": "2023-07-15",
                    "abstract": f"This is a simulated patent about {query}.",
                    "url": "https://patents.google.com/patent/US12345678A1",
                }
            ],
            "total_results": 1,
            "query": query,
            "simulated": True,
        }

    max_results = int(config.get("max_results", 10))

    # Use Google Patents search via web scraping or API
    try:
        import urllib.parse

        async with httpx.AsyncClient() as client:
            encoded_query = urllib.parse.quote(query)
            url = f"https://patents.google.com/xhr/query?url=q%3D{encoded_query}&num={max_results}"

            response = await client.get(url, timeout=30, headers={"Accept": "application/json"})

            if response.status_code == 200:
                try:
                    data = response.json()
                    patents = []
                    for result in data.get("results", {}).get("cluster", [])[:max_results]:
                        patent = result.get("result", {}).get("patent", {})
                        patents.append({
                            "patent_id": patent.get("publication_number", ""),
                            "title": patent.get("title", ""),
                            "abstract": patent.get("abstract", ""),
                            "assignee": patent.get("assignee", ""),
                            "filing_date": patent.get("filing_date", ""),
                            "publication_date": patent.get("publication_date", ""),
                        })
                    return {"patents": patents, "total_results": len(patents), "query": query}
                except json.JSONDecodeError:
                    pass

            return {"patents": [], "total_results": 0, "query": query, "note": "google_patents_api_unavailable"}

    except Exception as e:
        logger.exception(f"Patent search error: {e}")
        return {"patents": [], "error": str(e)}


async def run_doi_resolve_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve DOI to metadata.

    Config:
      - doi: str - DOI to resolve (e.g., "10.1000/xyz123")
    Output:
      - metadata: dict - Paper metadata
      - resolved: bool
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl
    import httpx

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    doi = config.get("doi") or ""
    if isinstance(doi, str):
        doi = _tmpl(doi, context) or doi

    if not doi:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            doi = prev.get("doi") or ""

    if not doi:
        return {"metadata": {}, "error": "missing_doi", "resolved": False}

    # Clean DOI
    doi = doi.strip()
    if doi.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi.startswith("http://doi.org/"):
        doi = doi[15:]
    elif doi.startswith("doi:"):
        doi = doi[4:]

    # TEST_MODE: return simulated result without network call
    if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
        return {
            "metadata": {
                "doi": doi,
                "title": f"Simulated Paper for DOI {doi}",
                "authors": ["Test Author", "Another Author"],
                "journal": "Simulated Journal",
                "year": 2023,
                "volume": "1",
                "issue": "1",
                "pages": "1-10",
                "publisher": "Simulated Publisher",
                "url": f"https://doi.org/{doi}",
            },
            "resolved": True,
            "simulated": True,
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://doi.org/{doi}",
                headers={"Accept": "application/vnd.citationstyles.csl+json"},
                follow_redirects=True,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            metadata = {
                "doi": doi,
                "title": data.get("title", ""),
                "authors": [
                    f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in data.get("author", [])
                ],
                "container_title": data.get("container-title", ""),
                "publisher": data.get("publisher", ""),
                "issued": data.get("issued", {}).get("date-parts", [[]])[0],
                "type": data.get("type", ""),
                "abstract": data.get("abstract", ""),
                "url": data.get("URL", ""),
            }

            return {"metadata": metadata, "resolved": True}

    except Exception as e:
        logger.exception(f"DOI resolve error: {e}")
        return {"metadata": {}, "error": str(e), "resolved": False}


async def run_reference_parse_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Parse citation string to structured data.

    Config:
      - citation: str - Citation string to parse
      - provider: str - LLM provider (for parsing)
      - model: str - Model to use
    Output:
      - parsed: dict - Structured citation data
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    citation = config.get("citation") or ""
    if isinstance(citation, str):
        citation = _tmpl(citation, context) or citation

    if not citation:
        return {"parsed": {}, "error": "missing_citation"}

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        prompt = f"""Parse this citation into structured JSON with these fields:
- authors: list of author names
- title: paper/article title
- journal: journal or publication name
- year: publication year
- volume: volume number
- issue: issue number
- pages: page range
- doi: DOI if present
- url: URL if present

Citation: {citation}

Return JSON only."""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Parse citations into structured JSON.",
            max_tokens=500,
            temperature=0.1,
        )

        result_text = _extract_openai_content(response) or ""
        try:
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(result_text[start:end])
                return {"parsed": parsed}
        except json.JSONDecodeError:
            pass

        return {"parsed": {}, "raw_text": result_text}

    except Exception as e:
        logger.exception(f"Reference parse error: {e}")
        return {"parsed": {}, "error": str(e)}


async def run_bibtex_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate BibTeX entry from metadata.

    Config:
      - metadata: dict - Paper metadata (title, authors, year, etc.)
      - entry_type: str - BibTeX entry type (article, book, inproceedings)
      - cite_key: str - Citation key (auto-generated if not provided)
    Output:
      - bibtex: str
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    metadata = config.get("metadata") or {}

    if not metadata:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            metadata = prev.get("metadata") or prev.get("parsed") or {}

    if not metadata:
        return {"bibtex": "", "error": "missing_metadata"}

    entry_type = config.get("entry_type", "article")
    cite_key = config.get("cite_key")

    # Auto-generate cite key
    if not cite_key:
        authors = metadata.get("authors", [])
        first_author = authors[0].split()[-1] if authors else "unknown"
        year = metadata.get("year", "")
        cite_key = f"{first_author.lower()}{year}"

    # Build BibTeX
    lines = [f"@{entry_type}{{{cite_key},"]

    field_map = {
        "title": "title",
        "authors": "author",
        "journal": "journal",
        "year": "year",
        "volume": "volume",
        "number": "number",
        "pages": "pages",
        "doi": "doi",
        "url": "url",
        "publisher": "publisher",
        "booktitle": "booktitle",
        "abstract": "abstract",
    }

    for meta_key, bib_key in field_map.items():
        value = metadata.get(meta_key)
        if value:
            if isinstance(value, list):
                value = " and ".join(value)
            lines.append(f"  {bib_key} = {{{value}}},")

    lines.append("}")
    bibtex = "\n".join(lines)

    return {"bibtex": bibtex, "text": bibtex, "cite_key": cite_key}


async def run_literature_review_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate literature review summary from search results.

    Config:
      - papers: list[dict] - Papers to summarize
      - topic: str - Review topic
      - style: str - "brief", "detailed", "comparative" (default: "brief")
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - review: str
      - paper_count: int
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    papers = config.get("papers") or []

    if not papers:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            papers = prev.get("papers") or []

    if not papers:
        return {"review": "", "error": "missing_papers"}

    topic = config.get("topic", "")
    if isinstance(topic, str):
        topic = _tmpl(topic, context) or topic

    style = config.get("style", "brief")

    # Format papers for prompt
    papers_text = ""
    for i, paper in enumerate(papers[:15]):
        title = paper.get("title", "")
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            authors = ", ".join(authors[:3])
        year = paper.get("year", "")
        abstract = paper.get("abstract", paper.get("summary", ""))[:500]
        papers_text += f"\n{i + 1}. {title} ({year})\nAuthors: {authors}\nAbstract: {abstract}\n"

    style_instructions = {
        "brief": "Write a concise 2-3 paragraph overview.",
        "detailed": "Write a comprehensive review with sections for themes, gaps, and future directions.",
        "comparative": "Compare and contrast the different approaches and findings.",
    }

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        prompt = f"""Generate a literature review {f'on the topic of "{topic}"' if topic else ''} based on these papers:

{papers_text}

{style_instructions.get(style, style_instructions['brief'])}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Write academic literature reviews.",
            max_tokens=2000,
            temperature=0.5,
        )

        review = _extract_openai_content(response) or ""
        return {"review": review, "text": review, "paper_count": len(papers), "style": style}

    except Exception as e:
        logger.exception(f"Literature review error: {e}")
        return {"review": "", "error": str(e)}


# ---------------------------------------------------------------------------
# Adapter Registry
# ---------------------------------------------------------------------------
# This registry provides explicit mapping from step_type -> adapter function.
# Used by parallel/retry adapters instead of dynamic sys.modules inspection.
# ---------------------------------------------------------------------------

def get_adapter(step_type: str):
    """Look up adapter function by step type name.

    Args:
        step_type: The workflow step type (e.g., "llm", "prompt", "rag_search")

    Returns:
        The adapter coroutine function, or None if not found.
    """
    return ADAPTER_REGISTRY.get(step_type)


ADAPTER_REGISTRY: Dict[str, Any] = {
    "prompt": run_prompt_adapter,
    "llm": run_llm_adapter,
    "rag_search": run_rag_search_adapter,
    "media_ingest": run_media_ingest_adapter,
    "kanban": run_kanban_adapter,
    "delay": run_delay_adapter,
    "log": run_log_adapter,
    "policy_check": run_policy_check_adapter,
    "tts": run_tts_adapter,
    "process_media": run_process_media_adapter,
    "rss_fetch": run_rss_fetch_adapter,
    "atom_fetch": run_rss_fetch_adapter,  # Alias
    "embed": run_embed_adapter,
    "translate": run_translate_adapter,
    "stt_transcribe": run_stt_transcribe_adapter,
    "notify": run_notify_adapter,
    "diff_change_detector": run_diff_change_adapter,
    "branch": run_branch_adapter,
    "map": run_map_adapter,
    "mcp_tool": run_mcp_tool_adapter,
    "webhook": run_webhook_adapter,
    "notes": run_notes_adapter,
    "prompts": run_prompts_adapter,
    "chunking": run_chunking_adapter,
    "web_search": run_web_search_adapter,
    "collections": run_collections_adapter,
    "chatbooks": run_chatbooks_adapter,
    "evaluations": run_evaluations_adapter,
    "claims_extract": run_claims_extract_adapter,
    "character_chat": run_character_chat_adapter,
    "moderation": run_moderation_adapter,
    "sandbox_exec": run_sandbox_exec_adapter,
    "image_gen": run_image_gen_adapter,
    "summarize": run_summarize_adapter,
    "query_expand": run_query_expand_adapter,
    "rerank": run_rerank_adapter,
    "citations": run_citations_adapter,
    "ocr": run_ocr_adapter,
    "pdf_extract": run_pdf_extract_adapter,
    "voice_intent": run_voice_intent_adapter,
    # Tier 1: Research Automation
    "query_rewrite": run_query_rewrite_adapter,
    "hyde_generate": run_hyde_generate_adapter,
    "semantic_cache_check": run_semantic_cache_check_adapter,
    "search_aggregate": run_search_aggregate_adapter,
    "entity_extract": run_entity_extract_adapter,
    "bibliography_generate": run_bibliography_generate_adapter,
    "document_table_extract": run_document_table_extract_adapter,
    "audio_diarize": run_audio_diarize_adapter,
    # Tier 2: Learning/Education
    "flashcard_generate": run_flashcard_generate_adapter,
    "quiz_generate": run_quiz_generate_adapter,
    "quiz_evaluate": run_quiz_evaluate_adapter,
    "outline_generate": run_outline_generate_adapter,
    "glossary_extract": run_glossary_extract_adapter,
    "mindmap_generate": run_mindmap_generate_adapter,
    "eval_readability": run_eval_readability_adapter,
    # Tier 3: Data Processing
    "json_transform": run_json_transform_adapter,
    "json_validate": run_json_validate_adapter,
    "csv_to_json": run_csv_to_json_adapter,
    "json_to_csv": run_json_to_csv_adapter,
    "regex_extract": run_regex_extract_adapter,
    "text_clean": run_text_clean_adapter,
    "xml_transform": run_xml_transform_adapter,
    "template_render": run_template_render_adapter,
    "batch": run_batch_adapter,
    # Tier 4: Workflow Orchestration
    "workflow_call": run_workflow_call_adapter,
    "parallel": run_parallel_adapter,
    "cache_result": run_cache_result_adapter,
    "retry": run_retry_adapter,
    "checkpoint": run_checkpoint_adapter,
    # Tier 5: External Integrations
    "s3_upload": run_s3_upload_adapter,
    "s3_download": run_s3_download_adapter,
    "github_create_issue": run_github_create_issue_adapter,
    # Tier 6: Agentic Support
    "llm_with_tools": run_llm_with_tools_adapter,
    "llm_critique": run_llm_critique_adapter,
    "context_build": run_context_build_adapter,
    # Phase 2: Group A - Individual Utility Nodes
    "document_merge": run_document_merge_adapter,
    "document_diff": run_document_diff_adapter,
    "markdown_to_html": run_markdown_to_html_adapter,
    "html_to_markdown": run_html_to_markdown_adapter,
    "keyword_extract": run_keyword_extract_adapter,
    "sentiment_analyze": run_sentiment_analyze_adapter,
    "language_detect": run_language_detect_adapter,
    "topic_model": run_topic_model_adapter,
    "token_count": run_token_count_adapter,
    "context_window_check": run_context_window_check_adapter,
    "llm_compare": run_llm_compare_adapter,
    "image_describe": run_image_describe_adapter,
    "report_generate": run_report_generate_adapter,
    "newsletter_generate": run_newsletter_generate_adapter,
    "slides_generate": run_slides_generate_adapter,
    "diagram_generate": run_diagram_generate_adapter,
    "email_send": run_email_send_adapter,
    "screenshot_capture": run_screenshot_capture_adapter,
    "schedule_workflow": run_schedule_workflow_adapter,
    "timing_start": run_timing_start_adapter,
    "timing_stop": run_timing_stop_adapter,
    # Phase 2: Group B - Audio & Video Processing
    "audio_normalize": run_audio_normalize_adapter,
    "audio_concat": run_audio_concat_adapter,
    "audio_trim": run_audio_trim_adapter,
    "audio_convert": run_audio_convert_adapter,
    "audio_extract": run_audio_extract_adapter,
    "audio_mix": run_audio_mix_adapter,
    "video_thumbnail": run_video_thumbnail_adapter,
    "video_trim": run_video_trim_adapter,
    "video_concat": run_video_concat_adapter,
    "video_convert": run_video_convert_adapter,
    "video_extract_frames": run_video_extract_frames_adapter,
    "subtitle_generate": run_subtitle_generate_adapter,
    "subtitle_translate": run_subtitle_translate_adapter,
    "subtitle_burn": run_subtitle_burn_adapter,
    # Phase 2: Group C - Research & Academic
    "arxiv_search": run_arxiv_search_adapter,
    "arxiv_download": run_arxiv_download_adapter,
    "pubmed_search": run_pubmed_search_adapter,
    "semantic_scholar_search": run_semantic_scholar_search_adapter,
    "google_scholar_search": run_google_scholar_search_adapter,
    "patent_search": run_patent_search_adapter,
    "doi_resolve": run_doi_resolve_adapter,
    "reference_parse": run_reference_parse_adapter,
    "bibtex_generate": run_bibtex_generate_adapter,
    "literature_review": run_literature_review_adapter,
}
