# main.py
# Description: This file contains the main FastAPI application, which serves as the primary API for the tldw application.
#
# Imports
import logging
import asyncio
import os
#
# 3rd-party Libraries
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from loguru import logger
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles
#
# Local Imports
#
# Early logging configuration to keep startup output consistent
import os as _early_os
_early_os.environ.setdefault("MCP_INHERIT_GLOBAL_LOGGER", "1")

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # Walk back through frames to skip logging/loguru internals
        frame, depth = logging.currentframe(), 2
        try:
            import os as _os
            _logging_file = _os.path.abspath(getattr(logging, "__file__", ""))
        except Exception:
            _logging_file = ""
        # Move at least one frame back (currentframe() points to this emit())
        if frame is not None:
            frame = frame.f_back
        while frame is not None:
            fname = getattr(frame.f_code, "co_filename", "")
            if _logging_file and _logging_file == fname:
                depth += 1
                frame = frame.f_back
                continue
            # Skip frames inside loguru internals as well
            if "loguru" in (fname or ""):
                depth += 1
                frame = frame.f_back
                continue
            break
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

class _SafeExtra(dict):
    """A dict that returns empty string for missing keys.

    Prevents KeyError when format strings reference {extra[missing_key]}."""
    def __getitem__(self, key):  # type: ignore[override]
        try:
            return super().__getitem__(key)
        except KeyError:
            return ""


def _trace_log_patcher(record):
    try:
        from tldw_Server_API.app.core.Metrics.traces import get_tracing_manager as _get_tm
        span = _get_tm().get_current_span()
        trace_id = span.get_span_context().trace_id if span else 0
        span_id = span.get_span_context().span_id if span else 0
        record.setdefault("extra", {})
        record["extra"].setdefault("trace_id", f"{trace_id:032x}" if trace_id else "")
        record["extra"].setdefault("span_id", f"{span_id:016x}" if span_id else "")
        if record["extra"].get("trace_id") and record["extra"].get("span_id"):
            record["extra"].setdefault("traceparent", f"00-{record['extra']['trace_id']}-{record['extra']['span_id']}-01")
        else:
            record["extra"].setdefault("traceparent", "")
        try:
            req = _get_tm().get_baggage("request_id")
            ses = _get_tm().get_baggage("session_id")
            if req:
                record["extra"].setdefault("request_id", req)
            if ses:
                record["extra"].setdefault("session_id", ses)
        except Exception:
            pass
    except Exception:
        record.setdefault("extra", {})
        record["extra"].setdefault("trace_id", "")
        record["extra"].setdefault("span_id", "")
        record["extra"].setdefault("traceparent", "")
        record["extra"].setdefault("request_id", "")
        record["extra"].setdefault("session_id", "")
    # Ensure commonly referenced extra keys exist to avoid formatter KeyErrors
    # and wrap with SafeExtra so any unknown keys resolve to an empty string.
    try:
        record["extra"].setdefault("event_id", "")
        record["extra"].setdefault("event_type", "")
        record["extra"].setdefault("category", "")
        record["extra"].setdefault("action", "")
        # Replace the mapping with a tolerant wrapper
        if not isinstance(record["extra"], _SafeExtra):
            record["extra"] = _SafeExtra(record["extra"])  # type: ignore[assignment]
    except Exception:
        # As a last resort, provide an empty tolerant mapping
        record["extra"] = _SafeExtra()
    try:
        import re as _re
        msg = record.get("message", "")
        msg = _re.sub(r"sk-[A-Za-z0-9-_]{8,}", "sk-***REDACTED***", msg)
        msg = _re.sub(r"(?i)(api[_-]?key|authorization|token|password)\s*[:=]\s*[^\s,;]+", r"\1=***REDACTED***", msg)
        record["message"] = msg
    except Exception:
        pass
    # Normalize extra values for JSON serialization and log safety
    try:
        from datetime import datetime as _dt
        extra = record.get("extra", {})
        if isinstance(extra, dict):
            for _k, _v in list(extra.items()):
                if isinstance(_v, _dt):
                    extra[_k] = _v.isoformat()
                elif isinstance(_v, (set, tuple)):
                    extra[_k] = list(_v)
    except Exception:
        pass

def _safe_log_format(record: dict) -> str:
    """
    Build a safe format template for Loguru which defers insertion of
    dynamic values (especially the message) to Loguru's own formatting.

    Returning a template with placeholders avoids embedding the raw message
    into the format string. This prevents Loguru's colorizer from parsing
    curly braces coming from messages (e.g., JSON dicts) which previously
    caused recursive parsing and "Max string recursion exceeded" errors.
    """
    # Note: Markup tags (<level>, <dim>, etc.) are parsed before placeholders
    # are formatted, so the inserted {message} content will not be re-parsed
    # for markup. This removes the need to strip '<' or '>' from messages.
    return (
        "<dim>{time:YYYY-MM-DD HH:mm:ss.SSS}</dim> | "
        "<level>{level: <8}</level> | "
        "<cyan>trace={extra[trace_id]}</cyan> <cyan>span={extra[span_id]}</cyan> "
        "<cyan>tp={extra[traceparent]}</cyan> "
        "<yellow>req={extra[request_id]}</yellow> <yellow>job={extra[job_id]}</yellow> "
        "<yellow>ps={extra[ps_component]}:{extra[ps_job_kind]}</yellow> | "
        "<blue>{name}</blue>:<magenta>{function}</magenta>:<cyan>{line}</cyan> - {message}"
    )

# Reset Loguru and configure a single, thread-safe sink
logger.remove()
_log_level = "DEBUG"
_force_color = (
    _early_os.getenv("FORCE_COLOR", "").lower() in {"1","true","yes","on"}
    or _early_os.getenv("PY_COLORS", "").lower() in {"1","true","yes","on"}
)
_sink_choice = _early_os.getenv("LOG_STREAM", "stderr").lower()
_sink = sys.stdout if _sink_choice in {"1","true","yes","on","stdout"} else sys.stderr
_use_color = _force_color or (_sink.isatty() and _early_os.getenv("LOG_COLOR", "1").lower() not in {"0","false","no","off"})
# Use synchronous logging during import-time initialization to avoid Loguru's background
# queue thread taking the import lock while startup modules are still being loaded.
class _SafeStreamWrapper:
    def __init__(self, stream):
        self._stream = stream
    def write(self, message: str):
        try:
            # Normalize line endings and ensure a newline terminator
            if message and not message.endswith("\n"):
                if message.endswith("\r"):
                    message = message[:-1] + "\n"
                else:
                    message = message + "\n"
            self._stream.write(message)
            # Flush to avoid line coalescing in buffered environments
            try:
                self._stream.flush()
            except Exception:
                pass
        except Exception:
            # Swallow closed-file or teardown-time errors
            pass
    def flush(self):
        try:
            self._stream.flush()
        except Exception:
            pass
    def isatty(self):
        try:
            return bool(getattr(self._stream, "isatty", lambda: False)())
        except Exception:
            return False


def _unwrap_logger_add(func):
    """Follow wrapper attributes to locate the underlying Loguru ``logger.add``."""
    seen = set()
    candidate = func
    while True:
        next_candidate = getattr(candidate, "_tldw_safe_original", None) or getattr(candidate, "__wrapped__", None)
        if not next_candidate or next_candidate is candidate or next_candidate in seen:
            return candidate
        seen.add(candidate)
        candidate = next_candidate

# Ensure any subsequent logger.add calls wrap raw streams with SafeStreamWrapper
_original_logger_add = logger.add
_original_unwrapped_logger_add = _unwrap_logger_add(_original_logger_add)
def _safe_logger_add(sink, *args, **kwargs):
    try:
        if hasattr(sink, "write") and not isinstance(sink, _SafeStreamWrapper):
            sink = _SafeStreamWrapper(sink)
    except Exception:
        # Fall back to original sink if inspection failed
        pass
    target = _unwrap_logger_add(_original_logger_add)
    return target(sink, *args, **kwargs)
logger.add = _safe_logger_add  # type: ignore[assignment]
setattr(logger.add, "_tldw_safe_original", _original_unwrapped_logger_add)
setattr(logger.add, "__wrapped__", _original_unwrapped_logger_add)

# Sink-level filter to guarantee presence of common extra fields
def _ensure_log_extra_fields(record: dict) -> bool:
    try:
        extra = record.setdefault("extra", {})
        # Provide defaults to avoid KeyError in format templates
        extra.setdefault("trace_id", "")
        extra.setdefault("span_id", "")
        extra.setdefault("request_id", "")
        extra.setdefault("session_id", "")
        # Ensure W3C trace context placeholder exists even before patcher runs
        extra.setdefault("traceparent", "")
        # Structured context defaults (Prompt Studio/jobs)
        extra.setdefault("job_id", "")
        extra.setdefault("ps_component", "")
        extra.setdefault("ps_job_kind", "")
        extra.setdefault("optimization_id", "")
        extra.setdefault("evaluation_id", "")
    except Exception:
        # Never block a log line due to filter errors
        pass
    return True

logger.add(
    _SafeStreamWrapper(_sink),
    level=_log_level,
    format=_safe_log_format,
    colorize=_use_color,
    filter=_ensure_log_extra_fields,
    enqueue=False,
)
logger = logger.patch(_trace_log_patcher)

# Intercept stdlib and uvicorn logs early
try:
    for _h in list(logging.root.handlers):
        logging.root.removeHandler(_h)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
except Exception:
    logging.getLogger().handlers = [InterceptHandler()]
    logging.getLogger().setLevel(0)

for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _lg = logging.getLogger(_name)
    _lg.handlers = [InterceptHandler()]
    _lg.propagate = False

# Guard against later reconfiguration by uvicorn or libraries
def _reinstall_intercept_handlers():
    try:
        logging.root.handlers = [InterceptHandler()]
        logging.root.setLevel(0)
    except Exception:
        pass
    # Replace handlers on all known loggers to avoid mixed formats
    try:
        for _lname, _logger in list(logging.root.manager.loggerDict.items()):
            if isinstance(_logger, logging.Logger):
                _logger.handlers = [InterceptHandler()]
                _logger.propagate = False
    except Exception:
        pass
    for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        try:
            _lg = logging.getLogger(_name)
            _lg.handlers = [InterceptHandler()]
            _lg.propagate = False
        except Exception:
            pass

try:
    import logging.config as _logcfg

    if not hasattr(logging, "_tldw_original_basicConfig"):
        logging._tldw_original_basicConfig = logging.basicConfig  # type: ignore[attr-defined]
    logging._tldw_reinstall = _reinstall_intercept_handlers  # type: ignore[attr-defined]

    if not getattr(logging, "_tldw_basic_config_wrapped", False):
        def _basic_config_wrapper(*args, **kwargs):
            try:
                logging._tldw_original_basicConfig(*args, **kwargs)  # type: ignore[attr-defined]
            finally:
                _maybe_reinstall = getattr(logging, "_tldw_reinstall", None)
                if callable(_maybe_reinstall):
                    _maybe_reinstall()
        logging.basicConfig = _basic_config_wrapper  # type: ignore[assignment]
        logging._tldw_basic_config_wrapped = True  # type: ignore[attr-defined]

    if hasattr(_logcfg, "dictConfig"):
        if not hasattr(_logcfg, "_tldw_original_dictConfig"):
            _logcfg._tldw_original_dictConfig = _logcfg.dictConfig  # type: ignore[attr-defined]
        _logcfg._tldw_reinstall = _reinstall_intercept_handlers  # type: ignore[attr-defined]

        if not getattr(_logcfg, "_tldw_dict_config_wrapped", False):
            def _dict_config_wrapper(config):
                try:
                    _logcfg._tldw_original_dictConfig(config)  # type: ignore[attr-defined]
                finally:
                    _maybe_reinstall = getattr(_logcfg, "_tldw_reinstall", None)
                    if callable(_maybe_reinstall):
                        _maybe_reinstall()
            _logcfg.dictConfig = _dict_config_wrapper  # type: ignore[assignment]
            _logcfg._tldw_dict_config_wrapped = True  # type: ignore[attr-defined]
except Exception as _log_wrap_err:
    logger.debug(f"Failed to wrap logging.config.dictConfig for interception: {_log_wrap_err}")

# Apply once now as well
_reinstall_intercept_handlers()

logger.info("Logging configured (Loguru + stdlib interception)")

#
# Auth Endpoint (NEW)
#
# Auth Endpoint (NEW)
from tldw_Server_API.app.api.v1.endpoints.auth import router as auth_router
try:
    from tldw_Server_API.app.api.v1.endpoints.auth_enhanced import router as auth_enhanced_router
    _HAS_AUTH_ENHANCED = True
except Exception as _auth_enh_import_err:  # noqa: BLE001
    logger.warning(f"Enhanced auth endpoints unavailable; skipping import: {_auth_enh_import_err}")
    _HAS_AUTH_ENHANCED = False

# Minimal test-app gating: when enabled, skip importing heavy routers
from os import getenv as _getenv_min
_MINIMAL_TEST_APP = _getenv_min("MINIMAL_TEST_APP", "").lower() in {"1", "true", "yes", "on"}
# Ultra-minimal diagnostic mode: only import health endpoints
_ULTRA_MINIMAL_APP = _getenv_min("ULTRA_MINIMAL_APP", "").lower() in {"1", "true", "yes", "on"}
# Opt-in startup tracing
_STARTUP_TRACE = _getenv_min("STARTUP_TRACE", "").lower() in {"1", "true", "yes", "on"}

def _startup_trace(msg: str) -> None:
    if _STARTUP_TRACE:
        try:
            logger.info(f"[startup-trace] {msg}")
        except Exception as _startup_log_err:
            logger.debug(f"Startup trace logging failed: {_startup_log_err}")

_startup_trace(f"Endpoint import gating: ULTRA_MINIMAL_APP={_ULTRA_MINIMAL_APP}, MINIMAL_TEST_APP={_MINIMAL_TEST_APP}")
#
if _ULTRA_MINIMAL_APP:
    try:
        from tldw_Server_API.app.api.v1.endpoints.health import router as health_router
        _HAS_HEALTH = True
    except Exception as _h_e:  # noqa: BLE001
        logger.warning(f"Health endpoints unavailable; skipping import: {_h_e}")
        _HAS_HEALTH = False
elif not _MINIMAL_TEST_APP:
    # Audio Endpoint (includes WebSocket streaming transcription)
    try:
        from tldw_Server_API.app.api.v1.endpoints.audio import router as audio_router, ws_router as audio_ws_router
        _HAS_AUDIO = True
    except Exception as _audio_err:  # noqa: BLE001 - guard non-critical endpoints in tests
        logger.warning(f"Audio endpoints unavailable; skipping import: {_audio_err}")
        _HAS_AUDIO = False
    # Guard audio_jobs import to avoid unrelated test breakages
    try:
        from tldw_Server_API.app.api.v1.endpoints.audio_jobs import router as audio_jobs_router
        _HAS_AUDIO_JOBS = True
    except Exception as _audio_jobs_err:  # noqa: BLE001
        logger.warning(f"Audio jobs endpoints unavailable; skipping import: {_audio_jobs_err}")
        _HAS_AUDIO_JOBS = False
    # Chat Endpoint
    from tldw_Server_API.app.api.v1.endpoints.chat import router as chat_router
    # Character Endpoints
    from tldw_Server_API.app.api.v1.endpoints.characters_endpoint import router as character_router
    from tldw_Server_API.app.api.v1.endpoints.character_chat_sessions import router as character_chat_sessions_router
    from tldw_Server_API.app.api.v1.endpoints.character_messages import router as character_messages_router
    # Metrics Endpoint
    from tldw_Server_API.app.api.v1.endpoints.metrics import router as metrics_router
    # Sandbox Endpoint (scaffold)
    try:
        from tldw_Server_API.app.api.v1.endpoints.sandbox import router as sandbox_router
        _HAS_SANDBOX = True
    except Exception as _sandbox_err:  # noqa: BLE001
        logger.warning(f"Sandbox endpoints unavailable; skipping import: {_sandbox_err}")
        _HAS_SANDBOX = False
    # Chunking Endpoints
    from tldw_Server_API.app.api.v1.endpoints.chunking import chunking_router as chunking_router
    from tldw_Server_API.app.api.v1.endpoints.chunking_templates import router as chunking_templates_router
    # Embeddings / Vector stores / Claims
    from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import router as embeddings_router
    from tldw_Server_API.app.api.v1.endpoints.vector_stores_openai import router as vector_stores_router
    from tldw_Server_API.app.api.v1.endpoints.claims import router as claims_router
    # Collections (stubs to anchor PRD)
    try:
        from tldw_Server_API.app.api.v1.endpoints.outputs_templates import router as outputs_templates_router
        _HAS_OUTPUT_TEMPLATES = True
    except Exception as _ot_err:
        logger.warning(f"Outputs templates endpoints unavailable; skipping import: {_ot_err}")
        _HAS_OUTPUT_TEMPLATES = False
    try:
        from tldw_Server_API.app.api.v1.endpoints.outputs import router as outputs_router
        _HAS_OUTPUTS = True
    except Exception as _o_err:
        logger.warning(f"Outputs endpoints unavailable; skipping import: {_o_err}")
        _HAS_OUTPUTS = False
    try:
        from tldw_Server_API.app.api.v1.endpoints.reading_highlights import router as reading_highlights_router
        _HAS_READING_HIGHLIGHTS = True
    except Exception as _rh_err:
        logger.warning(f"Reading highlights endpoints unavailable; skipping import: {_rh_err}")
        _HAS_READING_HIGHLIGHTS = False
    # Media Endpoints
    try:
        from tldw_Server_API.app.api.v1.endpoints.media import router as media_router
        _HAS_MEDIA = True
    except Exception as _media_import_err:  # noqa: BLE001
        logger.warning(f"Media endpoints unavailable; skipping import: {_media_import_err}")
        _HAS_MEDIA = False
    from tldw_Server_API.app.api.v1.endpoints.media_embeddings import router as media_embeddings_router
    # Unified items endpoint
    try:
        from tldw_Server_API.app.api.v1.endpoints.items import router as items_router
        _HAS_ITEMS = True
    except Exception as _items_err:
        logger.warning(f"Items endpoints unavailable; skipping import: {_items_err}")
        _HAS_ITEMS = False
    # Notes / Prompts
    from tldw_Server_API.app.api.v1.endpoints.notes import router as notes_router
    from tldw_Server_API.app.api.v1.endpoints.prompts import router as prompt_router
    # Prompt Studio (guarded)
    try:
        from tldw_Server_API.app.api.v1.endpoints.prompt_studio_projects import router as prompt_studio_projects_router
        from tldw_Server_API.app.api.v1.endpoints.prompt_studio_prompts import router as prompt_studio_prompts_router
        from tldw_Server_API.app.api.v1.endpoints.prompt_studio_test_cases import router as prompt_studio_test_cases_router
        from tldw_Server_API.app.api.v1.endpoints.prompt_studio_optimization import router as prompt_studio_optimization_router
        from tldw_Server_API.app.api.v1.endpoints.prompt_studio_status import router as prompt_studio_status_router
        from tldw_Server_API.app.api.v1.endpoints.prompt_studio_websocket import router as prompt_studio_websocket_router
        from tldw_Server_API.app.api.v1.endpoints.prompt_studio_evaluations import router as prompt_studio_evaluations_router
        _HAS_PROMPT_STUDIO = True
    except Exception as _ps_import_err:  # noqa: BLE001
        logger.warning(f"Prompt Studio endpoints unavailable; skipping import: {_ps_import_err}")
        _HAS_PROMPT_STUDIO = False
    # RAG & Workflows
    from tldw_Server_API.app.api.v1.endpoints.rag_health import router as rag_health_router
    from tldw_Server_API.app.api.v1.endpoints.rag_unified import router as rag_unified_router
    try:
        from tldw_Server_API.app.api.v1.endpoints.workflows import router as workflows_router
        _HAS_WORKFLOWS = True
    except Exception as _wf_import_err:  # noqa: BLE001
        logger.warning(f"Workflows endpoints unavailable; skipping import: {_wf_import_err}")
        _HAS_WORKFLOWS = False
# Legacy RAG Endpoint (Deprecated)
# from tldw_Server_API.app.api.v1.endpoints.rag import router as retrieval_agent_router
#
# Research/Paper Search and heavy routers/imports
# In minimal test-app mode, import only what is needed for lightweight tests.
if _MINIMAL_TEST_APP and not _ULTRA_MINIMAL_APP:
    # Research Endpoint (lightweight subset for tests)
    from tldw_Server_API.app.api.v1.endpoints.research import router as research_router
    # Paper Search Endpoint (provider-specific)
    from tldw_Server_API.app.api.v1.endpoints.paper_search import router as paper_search_router
    from tldw_Server_API.app.api.v1.endpoints.privileges import router as privileges_router
    _HAS_UNIFIED_EVALUATIONS = False
    # Minimal chat/character endpoints to support lightweight tests
    # These are relatively lightweight and safe to import under MINIMAL_TEST_APP
    from tldw_Server_API.app.api.v1.endpoints.chat import router as chat_router
    from tldw_Server_API.app.api.v1.endpoints.characters_endpoint import router as character_router
    from tldw_Server_API.app.api.v1.endpoints.character_chat_sessions import router as character_chat_sessions_router
    from tldw_Server_API.app.api.v1.endpoints.character_messages import router as character_messages_router
    # Sandbox endpoint is optional; guard import so minimal startup never fails
    try:
        from tldw_Server_API.app.api.v1.endpoints.sandbox import router as sandbox_router
        _HAS_SANDBOX = True
    except Exception as _sb_err:  # noqa: BLE001
        logger.warning(f"Sandbox endpoints unavailable; skipping import: {_sb_err}")
        _HAS_SANDBOX = False
else:
    # Research Endpoint
    from tldw_Server_API.app.api.v1.endpoints.research import router as research_router
    # Paper Search Endpoint (provider-specific)
    from tldw_Server_API.app.api.v1.endpoints.paper_search import router as paper_search_router
    # Unified Evaluation endpoint (guarded; can be heavy and optional in some test contexts)
    try:
        from tldw_Server_API.app.api.v1.endpoints.evaluations_unified import router as unified_evaluation_router
        _HAS_UNIFIED_EVALUATIONS = True
    except Exception as _evals_import_err:  # noqa: BLE001 - log and continue for deterministic startup
        logger.warning(f"Unified Evaluation endpoints unavailable; skipping import: {_evals_import_err}")
        _HAS_UNIFIED_EVALUATIONS = False
    from tldw_Server_API.app.api.v1.endpoints.ocr import router as ocr_router
    from tldw_Server_API.app.api.v1.endpoints.vlm import router as vlm_router
    # Benchmark Endpoint
    from tldw_Server_API.app.api.v1.endpoints.benchmark_api import router as benchmark_router
    # Sync Endpoint
    from tldw_Server_API.app.api.v1.endpoints.sync import router as sync_router
    # Tools Endpoint (optional; guard import to avoid startup failure on optional module issues)
    try:
        from tldw_Server_API.app.api.v1.endpoints.tools import router as tools_router
    except Exception as _tools_import_err:  # noqa: BLE001
        logger.warning(f"Tools endpoints unavailable at import time; deferring: {_tools_import_err}")
        tools_router = None  # type: ignore[assignment]
    # Users Endpoint (NEW)
    from tldw_Server_API.app.api.v1.endpoints.users import router as users_router
    # Privilege Maps Endpoint
    from tldw_Server_API.app.api.v1.endpoints.privileges import router as privileges_router
    ## Trash Endpoint
    #from tldw_Server_API.app.api.v1.endpoints.trash import router as trash_router
    # MCP Unified Endpoint (Production-ready, secure implementation)
    from tldw_Server_API.app.api.v1.endpoints.mcp_unified_endpoint import router as mcp_unified_router
    # Chatbooks Endpoint
    from tldw_Server_API.app.api.v1.endpoints.chatbooks import router as chatbooks_router
    # Flashcards Endpoint (V5 - ChaChaNotes)
    from tldw_Server_API.app.api.v1.endpoints.flashcards import router as flashcards_router
    # LLM Providers Endpoint
    from tldw_Server_API.app.api.v1.endpoints.llm_providers import router as llm_providers_router
    from tldw_Server_API.app.api.v1.endpoints.llamacpp import router as llamacpp_router, public_router as llamacpp_public_router
    from tldw_Server_API.app.api.v1.endpoints.setup import router as setup_router
    # Web Scraping Management Endpoints
    from tldw_Server_API.app.api.v1.endpoints.web_scraping import router as web_scraping_router
    # Sandbox Endpoint (scaffold)
    try:
        from tldw_Server_API.app.api.v1.endpoints.sandbox import router as sandbox_router
        _HAS_SANDBOX = True
    except Exception as _sb_err:  # noqa: BLE001
        logger.warning(f"Sandbox endpoints unavailable; skipping import: {_sb_err}")
        _HAS_SANDBOX = False

# Metrics and Telemetry - import directly and fail fast on errors
from tldw_Server_API.app.core.Metrics import (
    initialize_telemetry,
    shutdown_telemetry,
    get_metrics_registry,
    track_metrics,
    OTEL_AVAILABLE,
)

# Core helpers - import directly (fail fast if missing)
from tldw_Server_API.app.core.Evaluations.evaluation_manager import get_cached_evaluation_manager
from tldw_Server_API.app.core.Setup.setup_manager import needs_setup
from tldw_Server_API.app.core.AuthNZ.initialize import ensure_single_user_rbac_seed_if_needed
# MCP Unified config validation (fail-fast hardening)
try:
    from tldw_Server_API.app.core.MCP_unified.config import (
        validate_config as validate_mcp_config,
        get_config as get_mcp_config,
    )
except Exception:
    # MCP module may be optional in some minimal deployments; guard import
    validate_mcp_config = None  # type: ignore[assignment]
    get_mcp_config = None  # type: ignore[assignment]
#
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
#
########################################################################################################################
#
# Functions:


"""
Optional JSON-structured logs sink (enable with LOG_JSON=true)
- Adds an additional sink which serializes records as JSON to stdout.
"""
try:
    import os as _jsonlog_os
    if (
        _jsonlog_os.getenv("LOG_JSON", "").lower() in {"1", "true", "yes", "on"}
        or _jsonlog_os.getenv("ENABLE_JSON_LOGS", "").lower() in {"1", "true", "yes", "on"}
    ):
        logger.add(
            _SafeStreamWrapper(sys.stdout),
            level=_log_level,
            serialize=True,
            backtrace=False,
            diagnose=False,
            filter=_ensure_log_extra_fields,
            enqueue=True,
        )
        try:
            logger.info("JSON logging enabled (serialize=True, async enqueue)")
        except Exception:
            pass
except Exception as _e:
    try:
        logger.debug(f"Failed to enable JSON logs sink: {_e}")
    except Exception:
        pass


BASE_DIR     = Path(__file__).resolve().parent
FAVICON_PATH = BASE_DIR / "static" / "favicon.ico"

############################# TEST DB Handling #####################################
# --- TEST DB Instance ---
test_db_instance_ref = None # Global or context variable to hold the test DB instance

# Global readiness state (flips false during graceful shutdown)
READINESS_STATE = {"ready": True}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown for the given FastAPI app, performing validations, initializing services, scheduling deferred non-critical startup tasks, and running background workers.

    Parameters:
        app (FastAPI): The FastAPI application instance whose lifespan is managed.

    Returns:
        None: Yields once to allow the application to run; when resumed performs orderly shutdown and resource cleanup.
    """
    _startup_trace("lifespan: entered")
    # Determine if heavy (non-critical) startup should be deferred to background
    # Read environment knobs with precedence:
    # - DISABLE_HEAVY_STARTUP=true  => force synchronous (no deferral)
    # - else DEFER_HEAVY_STARTUP=true => defer heavy startup
    # - default => synchronous (no deferral)
    try:
        import os as _env_os

        def _env_to_bool(v):
            return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

        _disable = _env_to_bool(_env_os.getenv("DISABLE_HEAVY_STARTUP"))
        if _disable:
            _defer_heavy = False
        else:
            _defer_heavy = _env_to_bool(_env_os.getenv("DEFER_HEAVY_STARTUP"))
        # Default to synchronous (False) if neither flag is set
        _defer_heavy = bool(_defer_heavy)
    except Exception:
        # On any error determining flags, default to synchronous startup
        _defer_heavy = False

    # Container for background startup tasks (used during shutdown)
    try:
        app.state.bg_tasks = {}
    except Exception:
        pass
    chat_config: dict[str, object] = {}
    # Startup: Validate MCP configuration in production (fail fast)
    try:
        if get_mcp_config and validate_mcp_config:
            mcp_cfg = get_mcp_config()
            if not mcp_cfg.debug_mode:
                ok = validate_mcp_config()
                if not ok:
                    raise RuntimeError(
                        "MCP configuration validation failed; refusing to start in production"
                    )
    except Exception as _mcp_val_err:
        # Abort startup on validation errors
        logger.error(f"Startup aborted due to insecure MCP configuration: {_mcp_val_err}")
        raise

    # Startup: Validate Postgres content backend when enabled
    try:
        from tldw_Server_API.app.core.DB_Management.DB_Manager import (
            validate_postgres_content_backend as _validate_content_backend,
        )

        _validate_content_backend()
        logger.info("App Startup: PostgreSQL content backend validated")
    except RuntimeError as _content_err:
        logger.error(f"Startup aborted: {_content_err}")
        raise
    except ImportError as _content_import_err:
        logger.debug(f"Content backend validation skipped (import error): {_content_import_err}")

    # Startup: Initialize telemetry and metrics
    logger.info("App Startup: Initializing telemetry and metrics...")
    try:
        telemetry_manager = initialize_telemetry()
        if OTEL_AVAILABLE:
            logger.info(f"App Startup: OpenTelemetry initialized for service: {telemetry_manager.config.service_name}")
        else:
            logger.warning("App Startup: OpenTelemetry not available, using fallback metrics")
    except Exception as e:
        logger.error(f"App Startup: Failed to initialize telemetry: {e}")

    # Startup: Warn if first-time setup is enabled (local-only, no proxies)
    try:
        if needs_setup():
            logger.warning(
                "First-time setup is enabled. The setup API is local-only and blocks proxied requests. "
                "If running behind a reverse proxy, ensure /setup and /api/v1/setup are not publicly exposed, or "
                "set TLDW_SETUP_ALLOW_REMOTE=1 temporarily on trusted networks."
            )
    except Exception as e:
        logger.debug(f"Setup status check failed during startup: {e}")

    # Startup: Initialize auth services
    logger.info("App Startup: Initializing authentication services...")
    try:
        # Initialize database pool for auth
        from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
        db_pool = await get_db_pool()
        logger.info("App Startup: Database pool initialized")

        # Ensure AuthNZ schema/migrations
        try:
            if getattr(db_pool, 'pool', None) is None and getattr(db_pool, 'db_path', None):
                # SQLite path: run migration manager
                from pathlib import Path as _Path
                from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables as _ensure_authnz
                _ensure_authnz(_Path(db_pool.db_path))
                logger.info("App Startup: Ensured AuthNZ migrations (SQLite)")
            else:
                # Postgres path: ensure additive extras (tool catalogs) exist
                try:
                    from tldw_Server_API.app.core.AuthNZ.pg_migrations_extra import (
                        ensure_tool_catalogs_tables_pg,
                        ensure_privilege_snapshots_table_pg,
                    )
                    ok_catalogs = await ensure_tool_catalogs_tables_pg(db_pool)
                    if ok_catalogs:
                        logger.info("App Startup: Ensured PG tool catalogs tables")
                    ok_priv_snapshots = await ensure_privilege_snapshots_table_pg(db_pool)
                    if ok_priv_snapshots:
                        logger.info("App Startup: Ensured PG privilege_snapshots table")
                except Exception as _pg_e:
                    logger.debug(f"App Startup: PG extras ensure failed/skipped: {_pg_e}")
        except Exception as _e:
            logger.debug(f"App Startup: Skipped AuthNZ migration ensure: {_e}")
        # Ensure RBAC seed exists in single-user mode (idempotent; both backends)
        try:
            await ensure_single_user_rbac_seed_if_needed()
            logger.info("App Startup: Ensured single-user RBAC seed (baseline roles/permissions)")
        except Exception as _e:
            logger.debug(f"App Startup: RBAC single-user seed ensure skipped: {_e}")

        # Initialize session manager
        from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
        session_manager = await get_session_manager()
        logger.info("App Startup: Session manager initialized")

        try:
            from tldw_Server_API.app.core.AuthNZ.alerting import get_security_alert_dispatcher
            dispatcher = get_security_alert_dispatcher()
            dispatcher.validate_configuration()
            if dispatcher.enabled:
                logger.info("App Startup: Security alert configuration validated")
        except ValueError as config_error:
            logger.error(f"App Startup: Security alert configuration invalid: {config_error}")
            raise
        except Exception as exc:
            logger.error(f"App Startup: Security alert validation failed: {exc}")
    except Exception as e:
        logger.error(f"App Startup: Failed to initialize auth services: {e}")
        # Continue startup even if auth services fail (for backward compatibility)

    # Startup: Validate privilege catalog and route metadata (fail fast on mismatch)
    try:
        from tldw_Server_API.app.core.PrivilegeMaps.startup import validate_privilege_metadata_on_startup

        validate_privilege_metadata_on_startup(app)
    except Exception as exc:
        logger.error(f"App Startup: Privilege metadata validation failed: {exc}")
        raise

    # Heavy initializations: helpers and shared runner to avoid duplication
    # Ensure resources are bound in the enclosing scope so shutdown can detect them
    mcp_server = None
    provider_manager = None
    request_queue = None
    async def _init_mcp_server(*, deferred: bool) -> None:
        nonlocal mcp_server
        try:
            from tldw_Server_API.app.core.MCP_unified import get_mcp_server
            mcp_server = get_mcp_server()
            if not deferred:
                logger.info("App Startup: Initializing MCP Unified server...")
            await mcp_server.initialize()
            logger.info(("Deferred startup: " if deferred else "App Startup: ") + "MCP Unified server initialized successfully")
        except Exception as e:
            if deferred:
                logger.debug(f"Deferred startup: MCP Unified server skipped/failed: {e}")
            else:
                logger.exception(f"App Startup: Failed to initialize MCP Unified server: {e}")
                logger.warning("Ensure MCP_JWT_SECRET and MCP_API_KEY_SALT environment variables are set")

    async def _init_provider_manager(*, deferred: bool) -> None:
        nonlocal provider_manager
        try:
            from tldw_Server_API.app.core.Chat.provider_manager import initialize_provider_manager
            from tldw_Server_API.app.core.Chat.provider_config import API_CALL_HANDLERS as PROVIDER_API_CALL_HANDLERS
            providers = list(PROVIDER_API_CALL_HANDLERS.keys())
            provider_manager = initialize_provider_manager(providers, primary_provider=providers[0] if providers else None)
            await provider_manager.start_health_checks()
            if deferred:
                logger.info(f"Deferred startup: Provider manager ready ({len(providers)} providers)")
            else:
                logger.info(f"App Startup: Provider manager initialized with {len(providers)} providers")
        except Exception as e:
            if deferred:
                logger.debug(f"Deferred startup: provider manager skipped/failed: {e}")
            else:
                logger.exception(f"App Startup: Failed to initialize provider manager: {e}")

    async def _init_request_queue(*, deferred: bool) -> None:
        nonlocal request_queue
        try:
            from tldw_Server_API.app.core.config import load_comprehensive_config
            from tldw_Server_API.app.core.Chat.request_queue import initialize_request_queue
            cfg = load_comprehensive_config()
            chat_cfg = {}
            if cfg and cfg.has_section('Chat-Module'):
                chat_cfg = dict(cfg.items('Chat-Module'))
            queued_execution_enabled = False
            try:
                env_queued = os.getenv("CHAT_QUEUED_EXECUTION")
                if env_queued is not None:
                    queued_execution_enabled = env_queued.strip().lower() in {"1", "true", "yes", "on"}
                else:
                    queued_execution_enabled = str(chat_cfg.get('queued_execution', 'False')).strip().lower() in {"1", "true", "yes", "on"}
            except Exception:
                queued_execution_enabled = False
            if queued_execution_enabled:
                request_queue = initialize_request_queue(
                    max_queue_size=int(chat_cfg.get('max_queue_size', 100)),
                    max_concurrent=int(chat_cfg.get('max_concurrent_requests', 10)),
                    global_rate_limit=int(chat_cfg.get('rate_limit_per_minute', 60)),
                    per_client_rate_limit=int(chat_cfg.get('rate_limit_per_conversation_per_minute', 20))
                )
                await request_queue.start(num_workers=4)
                if deferred:
                    logger.info("Deferred startup: Request queue online")
                else:
                    logger.info("App Startup: Request queue initialized with 4 workers")
            else:
                if not deferred:
                    logger.info("App Startup: Request queue disabled (QUEUED_EXECUTION is off)")
        except Exception as e:
            if deferred:
                logger.debug(f"Deferred startup: request queue skipped/failed: {e}")
            else:
                logger.exception(f"App Startup: Failed to initialize request queue: {e}")

    async def _init_rate_limiter(*, deferred: bool) -> None:
        try:
            from tldw_Server_API.app.core.config import load_comprehensive_config
            from tldw_Server_API.app.core.Chat.rate_limiter import initialize_rate_limiter, RateLimitConfig
            cfg = load_comprehensive_config()
            chat_cfg = {}
            if cfg and cfg.has_section('Chat-Module'):
                chat_cfg = dict(cfg.items('Chat-Module'))
            rl_cfg = RateLimitConfig(
                global_rpm=int(chat_cfg.get('rate_limit_per_minute', 60)),
                per_user_rpm=int(chat_cfg.get('rate_limit_per_user_per_minute', 20)),
                per_conversation_rpm=int(chat_cfg.get('rate_limit_per_conversation_per_minute', 10)),
                per_user_tokens_per_minute=int(chat_cfg.get('rate_limit_tokens_per_minute', 10000))
            )
            initialize_rate_limiter(rl_cfg)
            logger.info(("Deferred startup: " if deferred else "App Startup: ") + "Rate limiter " + ("online" if deferred else "initialized"))
        except Exception as e:
            if deferred:
                logger.debug(f"Deferred startup: rate limiter skipped/failed: {e}")
            else:
                logger.exception(f"App Startup: Failed to initialize rate limiter: {e}")

    async def _init_tts_service(*, deferred: bool) -> None:
        try:
            from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
            from tldw_Server_API.app.core.config import load_comprehensive_config_with_tts
            cfg_obj = load_comprehensive_config_with_tts()
            tts_cfg_dict = cfg_obj.get_tts_config() if hasattr(cfg_obj, 'get_tts_config') else None
            await get_tts_service_v2(config=tts_cfg_dict)
            logger.info(("Deferred startup: " if deferred else "App Startup: ") + "TTS service " + ("ready" if deferred else "initialized successfully"))
        except Exception as e:
            if deferred:
                logger.debug(f"Deferred startup: TTS skipped/failed: {e}")
            else:
                logger.exception(f"App Startup: Failed to initialize TTS service: {e}")
                logger.warning("TTS functionality will be unavailable")

    async def _init_chunking_templates(*, deferred: bool) -> None:
        try:
            from tldw_Server_API.app.core.Chunking.template_initialization import ensure_templates_initialized
            ok = ensure_templates_initialized()
            if ok:
                logger.info(("Deferred startup: " if deferred else "App Startup: ") + "Chunking templates " + ("ready" if deferred else "initialized successfully"))
            else:
                if deferred:
                    logger.debug("Deferred startup: Chunking templates incomplete")
                else:
                    logger.warning("App Startup: Chunking templates initialization incomplete")
        except Exception as e:
            if deferred:
                logger.debug(f"Deferred startup: chunking templates skipped/failed: {e}")
            else:
                logger.exception(f"App Startup: Failed to initialize chunking templates: {e}")

    async def _init_embeddings_dim_check(*, deferred: bool) -> None:
        try:
            enabled = os.getenv("EMBEDDINGS_STARTUP_DIM_CHECK_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"}
            if not enabled:
                return
            strict_mode = os.getenv("EMBEDDINGS_DIM_CHECK_STRICT", "false").lower() in {"true", "1", "yes", "y", "on"}
            if not deferred:
                logger.info("App Startup: Running embeddings dimension sanity check (opt-in)")
            from pathlib import Path as _Path
            from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
            from tldw_Server_API.app.core.config import settings as _emb_settings

            def _check_user(user_id: str) -> list[tuple[str, int, int, str]]:
                mms: list[tuple[str, int, int, str]] = []
                mgr = ChromaDBManager(user_id=user_id, user_embedding_config=_emb_settings)
                client = getattr(mgr, 'client', None)
                list_fn = getattr(client, 'list_collections', None)
                collections = list_fn() if callable(list_fn) else []
                for col in collections:
                    try:
                        name = getattr(col, 'name', None) or (col.get('name') if isinstance(col, dict) else None)
                        if not name:
                            continue
                        get_fn = getattr(client, 'get_collection', None)
                        c = get_fn(name=name) if callable(get_fn) else col
                        meta = getattr(c, 'metadata', None) or {}
                        expected = None
                        if isinstance(meta, dict) and meta.get('embedding_dimension'):
                            try:
                                expected = int(meta.get('embedding_dimension'))
                            except Exception:
                                expected = None
                        actual = None
                        if hasattr(c, 'get') and callable(getattr(c, 'get')):
                            try:
                                res = c.get(limit=1, include=['embeddings'])
                                embs = res.get('embeddings') if isinstance(res, dict) else None
                                if embs and len(embs) > 0:
                                    first = embs[0]
                                    if first and hasattr(first, '__len__'):
                                        actual = len(first)
                            except Exception:
                                pass
                        if expected is not None and actual is not None and expected != actual:
                            mms.append((name, expected, actual, user_id))
                    except Exception:
                        pass
                try:
                    mgr.close()
                except Exception:
                    pass
                return mms

            auth_mode = str(_emb_settings.get("AUTH_MODE", os.getenv("AUTH_MODE", "single_user")))
            mismatches: list[tuple[str, int, int, str]] = []
            if auth_mode == "multi_user":
                base: _Path = _emb_settings.get("USER_DB_BASE_DIR")
                if base and _Path(base).exists():
                    for entry in _Path(base).iterdir():
                        if entry.is_dir():
                            user_id = entry.name
                            try:
                                mismatches.extend(_check_user(user_id))
                            except Exception:
                                pass
                else:
                    if not deferred:
                        logger.warning("Embeddings dimension check: USER_DB_BASE_DIR missing or does not exist in multi_user mode")
            else:
                user_id = str(_emb_settings.get("SINGLE_USER_FIXED_ID", "1"))
                mismatches.extend(_check_user(user_id))

            if mismatches:
                for (n, e, a, u) in mismatches:
                    logger.error(("Deferred startup: " if deferred else "") + f"Embeddings dimension mismatch{' (deferred)' if deferred else ' at startup'} (user={u}) in collection '{n}': expected={e}, actual={a}")
                if strict_mode:
                    raise RuntimeError("EMBEDDINGS_STARTUP_DIM_CHECK_FAILED")
            else:
                logger.info(("Deferred startup: " if deferred else "") + ("Embeddings dimension check OK" if deferred else "Embeddings dimension sanity check: OK (no mismatches)"))
        except Exception as e:
            if deferred:
                logger.debug(f"Deferred startup: embeddings dimension check skipped/failed: {e}")
            else:
                logger.exception(f"Embeddings dimension sanity check failed: {e}")
                # Do not raise except in strict mode (handled above)

    async def _run_heavy_initializations(*, deferred: bool) -> None:
        if deferred:
            logger.info("Deferred startup: beginning non-critical initializations in background")
        # MCP Unified server
        await _init_mcp_server(deferred=deferred)
        # Provider manager
        await _init_provider_manager(deferred=deferred)
        # Request queue
        await _init_request_queue(deferred=deferred)
        # Rate limiter
        await _init_rate_limiter(deferred=deferred)
        # TTS service
        await _init_tts_service(deferred=deferred)
        # Chunking templates
        await _init_chunking_templates(deferred=deferred)
        # Embeddings dimension check
        await _init_embeddings_dim_check(deferred=deferred)
        if deferred:
            logger.info("Deferred startup: completed non-critical initializations")

    # Initialize Chat Module Components (single log retained)
    logger.info("App Startup: Initializing Chat module components...")

    # Run heavy initializations synchronously or schedule in background
    if _defer_heavy:
        import asyncio as _asyncio
        try:
            app.state.bg_tasks['deferred_startup'] = _asyncio.create_task(_run_heavy_initializations(deferred=True))
        except Exception as _ds_e:
            logger.debug(f"Failed to schedule deferred startup task: {_ds_e}")
    else:
        await _run_heavy_initializations(deferred=False)

    # Note: Audit service now uses dependency injection
    # No need to initialize globally - use get_audit_service_for_user dependency in endpoints
    logger.info("App Startup: Audit service available via dependency injection")

    # Start background workers: ephemeral collections cleanup, core Jobs (chatbooks), audio Jobs (MVP), claims rebuild
    cleanup_task = None
    core_jobs_task = None
    audio_jobs_task = None
    claims_task = None
    jobs_metrics_task = None
    reembed_task = None
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.core.DB_Management.DB_Manager import (
            create_evaluations_database as _create_evals_db,
        )
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths as _DBP
        from tldw_Server_API.app.core.RAG.rag_service.vector_stores import VectorStoreFactory as _VSF, create_from_settings_for_user as _create_vs_from_settings
        from tldw_Server_API.app.core.config import settings as _app_settings

        # Use per-user evaluations DB for cleanup; default to single-user ID
        _single_uid = int(_app_settings.get("SINGLE_USER_FIXED_ID", "1"))
        _db_path = str(_DBP.get_evaluations_db_path(_single_uid))
        # Read settings
        _enabled = bool(_app_settings.get("EPHEMERAL_CLEANUP_ENABLED", True))
        _interval_sec = int(_app_settings.get("EPHEMERAL_CLEANUP_INTERVAL_SEC", 1800))

        async def _ephemeral_cleanup_loop():
            logger.info(f"Starting ephemeral collections cleanup worker (every {_interval_sec}s)")
            # Use backend-aware factory so Postgres content backend is honored
            db = _create_evals_db(db_path=_db_path)
            adapter = _create_vs_from_settings(_app_settings, str(_app_settings.get("SINGLE_USER_FIXED_ID", "1")))
            await adapter.initialize()
            while True:
                try:
                    # Re-read settings each cycle
                    _enabled_dyn = bool(_app_settings.get("EPHEMERAL_CLEANUP_ENABLED", True))
                    _interval_dyn = int(_app_settings.get("EPHEMERAL_CLEANUP_INTERVAL_SEC", _interval_sec))
                    if not _enabled_dyn:
                        await _asyncio.sleep(_interval_sec)
                        continue
                    expired = db.list_expired_ephemeral_collections()
                    if expired:
                        deleted = 0
                        for cname in expired:
                            try:
                                await adapter.delete_collection(cname)
                                db.mark_ephemeral_deleted(cname)
                                deleted += 1
                            except Exception as ce:
                                logger.warning(f"Ephemeral cleanup: failed to delete {cname}: {ce}")
                        if deleted:
                            logger.info(f"Ephemeral cleanup: deleted {deleted}/{len(expired)} expired collections")
                except Exception as ce:
                    logger.warning(f"Ephemeral cleanup loop error: {ce}")
                await _asyncio.sleep(_interval_dyn)

        if _enabled:
            cleanup_task = _asyncio.create_task(_ephemeral_cleanup_loop())
        else:
            logger.info("Ephemeral cleanup worker disabled by settings")
    except Exception as e:
        logger.warning(f"Failed to start ephemeral cleanup worker: {e}")

    # Core Jobs worker (Chatbooks, if backend=core)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.core_jobs_worker import run_chatbooks_core_jobs_worker as _run_cb_jobs
        _backend = (_os.getenv("CHATBOOKS_JOBS_BACKEND") or _os.getenv("TLDW_JOBS_BACKEND") or "").lower()
        _is_core = (_backend == "core") or (not _backend)
        _core_worker_enabled = (_os.getenv("CHATBOOKS_CORE_WORKER_ENABLED", "true").lower() in {"true", "1", "yes", "y", "on"})
        if _is_core and _core_worker_enabled:
            core_jobs_stop_event = _asyncio.Event()
            core_jobs_task = _asyncio.create_task(_run_cb_jobs(core_jobs_stop_event))
            logger.info("Core Jobs worker (Chatbooks) started with explicit stop_event signal")
        else:
            logger.info("Core Jobs worker (Chatbooks) disabled by backend selection or flag")
    except Exception as e:
        logger.warning(f"Failed to start core Jobs worker (Chatbooks): {e}")

    # Embeddings Vector Compactor (soft-delete propagation)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.core.Embeddings.services.vector_compactor import run as _run_vec_compactor
        _enabled = (_os.getenv("EMBEDDINGS_COMPACTOR_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"})
        if _enabled:
            embeddings_compactor_stop_event = _asyncio.Event()
            embeddings_compactor_task = _asyncio.create_task(_run_vec_compactor(embeddings_compactor_stop_event))
            logger.info("Embeddings Vector Compactor started with explicit stop_event signal")
        else:
            logger.info("Embeddings Vector Compactor disabled by flag (EMBEDDINGS_COMPACTOR_ENABLED)")
    except Exception as e:
        logger.warning(f"Failed to start Embeddings Vector Compactor: {e}")

    # Audio Jobs worker (MVP)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.audio_jobs_worker import run_audio_jobs_worker as _run_audio_jobs
        _enabled = (_os.getenv("AUDIO_JOBS_WORKER_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"})
        if _enabled:
            audio_jobs_stop_event = _asyncio.Event()
            audio_jobs_task = _asyncio.create_task(_run_audio_jobs(audio_jobs_stop_event))
            logger.info("Audio Jobs worker started with explicit stop_event signal")
        else:
            logger.info("Audio Jobs worker disabled by flag (AUDIO_JOBS_WORKER_ENABLED)")
    except Exception as e:
        logger.warning(f"Failed to start Audio Jobs worker: {e}")

    # Jobs metrics gauges worker (SLO percentiles)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.jobs_metrics_service import run_jobs_metrics_gauges as _run_jobs_metrics
        _enabled = (_os.getenv("JOBS_METRICS_GAUGES_ENABLED", "true").lower() in {"true", "1", "yes", "y", "on"})
        if _enabled:
            jobs_metrics_stop_event = _asyncio.Event()
            jobs_metrics_task = _asyncio.create_task(_run_jobs_metrics(jobs_metrics_stop_event))
            logger.info("Jobs metrics gauge worker started with explicit stop_event signal")
        else:
            logger.info("Jobs metrics gauge worker disabled by flag")
    except Exception as e:
        logger.warning(f"Failed to start Jobs metrics gauge worker: {e}")

    # Jobs metrics reconcile worker (job_counters/gauges amortized refresh)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.jobs_metrics_service import run_jobs_metrics_reconcile as _run_jobs_reconcile
        _enabled_recon = (_os.getenv("JOBS_METRICS_RECONCILE_ENABLE", "false").lower() in {"true", "1", "yes", "y", "on"})
        if _enabled_recon:
            jobs_metrics_reconcile_stop = _asyncio.Event()
            _ = _asyncio.create_task(_run_jobs_reconcile(jobs_metrics_reconcile_stop))
            logger.info("Jobs metrics reconcile worker started with explicit stop_event signal")
        else:
            logger.info("Jobs metrics reconcile worker disabled by flag (JOBS_METRICS_RECONCILE_ENABLE)")
    except Exception as e:
        logger.warning(f"Failed to start Jobs metrics reconcile worker: {e}")

    # Jobs crypto rotate worker (optional staged rotation)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.jobs_crypto_rotate_service import run_jobs_crypto_rotate as _run_jobs_crypto
        _enabled = (_os.getenv("JOBS_CRYPTO_ROTATE_SERVICE_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"})
        if _enabled:
            jobs_crypto_rotate_stop_event = _asyncio.Event()
            jobs_crypto_rotate_task = _asyncio.create_task(_run_jobs_crypto(jobs_crypto_rotate_stop_event))
            logger.info("Jobs crypto rotate worker started with explicit stop_event signal")
        else:
            logger.info("Jobs crypto rotate worker disabled by flag")
    except Exception as e:
        logger.warning(f"Failed to start Jobs crypto rotate worker: {e}")

    # Jobs webhooks worker (signed callbacks)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.jobs_webhooks_service import run_jobs_webhooks_worker as _run_jobs_webhooks
        _enabled = (_os.getenv("JOBS_WEBHOOKS_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"}) and bool(_os.getenv("JOBS_WEBHOOKS_URL"))
        if _enabled:
            jobs_webhooks_stop_event = _asyncio.Event()
            jobs_webhooks_task = _asyncio.create_task(_run_jobs_webhooks(jobs_webhooks_stop_event))
            logger.info("Jobs webhooks worker started with explicit stop_event signal")
        else:
            logger.info("Jobs webhooks worker disabled by flag or missing URL")
    except Exception as e:
        logger.warning(f"Failed to start Jobs webhooks worker: {e}")

    # Workflows webhook DLQ retry worker
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.workflows_webhook_dlq_service import run_workflows_webhook_dlq_worker as _run_wf_dlq
        _wf_enabled = (_os.getenv("WORKFLOWS_WEBHOOK_DLQ_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"})
        if _wf_enabled:
            workflows_dlq_stop_event = _asyncio.Event()
            workflows_dlq_task = _asyncio.create_task(_run_wf_dlq(workflows_dlq_stop_event))
            logger.info("Workflows webhook DLQ worker started with explicit stop_event signal")
        else:
            logger.info("Workflows webhook DLQ worker disabled by flag")
    except Exception as e:
        logger.warning(f"Failed to start Workflows webhook DLQ worker: {e}")

    # Workflows artifact GC worker
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.workflows_artifact_gc_service import run_workflows_artifact_gc_worker as _run_wf_gc
        _wf_gc_enabled = (_os.getenv("WORKFLOWS_ARTIFACT_GC_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"})
        if _wf_gc_enabled:
            workflows_gc_stop_event = _asyncio.Event()
            workflows_gc_task = _asyncio.create_task(_run_wf_gc(workflows_gc_stop_event))
            logger.info("Workflows artifact GC worker started with explicit stop_event signal")
        else:
            logger.info("Workflows artifact GC worker disabled by flag")
    except Exception as e:
        logger.warning(f"Failed to start Workflows artifact GC worker: {e}")

    # Workflows DB maintenance worker (checkpoint/VACUUM)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.workflows_db_maintenance import run_workflows_db_maintenance as _run_wf_maint
        _wf_maint_enabled = (_os.getenv("WORKFLOWS_DB_MAINTENANCE_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"})
        if _wf_maint_enabled:
            workflows_maint_stop_event = _asyncio.Event()
            workflows_maint_task = _asyncio.create_task(_run_wf_maint(workflows_maint_stop_event))
            logger.info("Workflows DB maintenance worker started with explicit stop_event signal")
        else:
            logger.info("Workflows DB maintenance worker disabled by flag")
    except Exception as e:
        logger.warning(f"Failed to start Workflows DB maintenance worker: {e}")

    # Embeddings Re-embed expansion worker (Jobs-driven)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.core.Embeddings.services.reembed_worker import run as _run_reembed
        _enabled = (_os.getenv("EMBEDDINGS_REEMBED_WORKER_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"})
        if _enabled:
            reembed_stop_event = _asyncio.Event()
            reembed_task = _asyncio.create_task(_run_reembed(reembed_stop_event))
            logger.info("Embeddings re-embed expansion worker started with explicit stop_event signal")
        else:
            logger.info("Embeddings re-embed expansion worker disabled by flag (EMBEDDINGS_REEMBED_WORKER_ENABLED)")
    except Exception as e:
        logger.warning(f"Failed to start re-embed expansion worker: {e}")

    # Jobs integrity sweeper (periodic validator)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.jobs_integrity_service import run_jobs_integrity_sweeper as _run_jobs_integrity
        _enabled = (_os.getenv("JOBS_INTEGRITY_SWEEP_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"})
        if _enabled:
            jobs_integrity_stop_event = _asyncio.Event()
            jobs_integrity_task = _asyncio.create_task(_run_jobs_integrity(jobs_integrity_stop_event))
            logger.info("Jobs integrity sweeper started with explicit stop_event signal")
        else:
            logger.info("Jobs integrity sweeper disabled by flag")
    except Exception as e:
        logger.warning(f"Failed to start Jobs integrity sweeper: {e}")

    # Claims rebuild worker (periodic)
    try:
        import asyncio as _asyncio
        from tldw_Server_API.app.core.config import settings as _app_settings
        from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path as _get_media_db_path
        from tldw_Server_API.app.services.claims_rebuild_service import get_claims_rebuild_service as _get_claims_svc
        from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase as _MediaDB

        _claims_enabled = bool(_app_settings.get("CLAIMS_REBUILD_ENABLED", False))
        _claims_interval = int(_app_settings.get("CLAIMS_REBUILD_INTERVAL_SEC", 3600))
        _claims_policy = str(_app_settings.get("CLAIMS_REBUILD_POLICY", "missing")).lower()

        async def _claims_rebuild_loop():
            if not _claims_enabled:
                logger.info("Claims rebuild worker disabled by settings")
                return
            logger.info(f"Starting claims rebuild worker (every {_claims_interval}s, policy={_claims_policy})")
            svc = _get_claims_svc()
            while True:
                try:
                    # Single-user path; for multi-user extend with per-user iteration
                    user_id = int(_app_settings.get("SINGLE_USER_FIXED_ID", "1"))
                    db_path = _get_media_db_path(user_id)
                    db = _MediaDB(db_path=db_path, client_id=str(_app_settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")))
                    # Find media missing claims
                    if _claims_policy == "missing":
                        sql = (
                            "SELECT m.id FROM Media m "
                            "WHERE m.deleted = 0 AND m.is_trash = 0 AND NOT EXISTS ("
                            "  SELECT 1 FROM Claims c WHERE c.media_id = m.id AND c.deleted = 0"
                            ") LIMIT 25"
                        )
                    elif _claims_policy == "all":
                        sql = "SELECT m.id FROM Media m WHERE m.deleted=0 AND m.is_trash=0 LIMIT 25"
                    else:
                        # rudimentary stale policy: claims older than N days since media last_modified
                        days = int(_app_settings.get("CLAIMS_STALE_DAYS", 7))
                        sql = (
                            "SELECT m.id FROM Media m "
                            "LEFT JOIN (SELECT media_id, MAX(last_modified) AS lastc FROM Claims WHERE deleted=0 GROUP BY media_id) c ON c.media_id = m.id "
                            "WHERE m.deleted=0 AND m.is_trash=0 AND (c.lastc IS NULL OR julianday('now') - julianday(c.lastc) >= ?) "
                            "LIMIT 25"
                        )
                    if _claims_policy == "stale":
                        rows = db.execute_query(sql, (int(_app_settings.get("CLAIMS_STALE_DAYS", 7)),)).fetchall()
                    else:
                        rows = db.execute_query(sql).fetchall()
                    mids = [int(r[0]) for r in rows]
                    for mid in mids:
                        svc.submit(media_id=mid, db_path=db_path)
                    try:
                        db.close_connection()
                    except Exception:
                        pass
                except Exception as e:
                    logger.warning(f"Claims rebuild loop error: {e}")
                await _asyncio.sleep(_claims_interval)

        if _claims_enabled:
            claims_task = _asyncio.create_task(_claims_rebuild_loop())
        else:
            logger.info("Claims rebuild worker disabled by settings")
    except Exception as e:
        logger.warning(f"Failed to start claims rebuild worker: {e}")

    # Start usage aggregator (if enabled, and not disabled via env or test-mode)
    try:
        _disable_usage_agg = _env_os.getenv("DISABLE_USAGE_AGGREGATOR", "").lower() in {"1", "true", "yes", "on"}
        if _disable_usage_agg:
            logger.info("Usage aggregator disabled via DISABLE_USAGE_AGGREGATOR")
        else:
            from tldw_Server_API.app.services.usage_aggregator import start_usage_aggregator
            usage_task = await start_usage_aggregator()
            if usage_task:
                logger.info("Usage aggregator started")
    except Exception as e:
        logger.warning(f"Failed to start usage aggregator: {e}")

    # Start LLM usage aggregator (if enabled, and not disabled via env or test-mode)
    try:
        _disable_llm_usage_agg = _env_os.getenv("DISABLE_LLM_USAGE_AGGREGATOR", "").lower() in {"1", "true", "yes", "on"}
        if _disable_llm_usage_agg:
            logger.info("LLM usage aggregator disabled via DISABLE_LLM_USAGE_AGGREGATOR")
        else:
            from tldw_Server_API.app.services.llm_usage_aggregator import start_llm_usage_aggregator
            llm_usage_task = await start_llm_usage_aggregator()
            if llm_usage_task:
                logger.info("LLM usage aggregator started")
    except Exception as e:
        logger.warning(f"Failed to start LLM usage aggregator: {e}")

    # Start personalization consolidation service if enabled
    try:
        _personalization_enabled = bool(_app_settings.get("PERSONALIZATION_ENABLED", True))
        _skip_consolidation = _env_os.getenv("DISABLE_PERSONALIZATION_CONSOLIDATION", "").lower() in {"1", "true", "yes", "on"}
        if not _personalization_enabled or _skip_consolidation:
            logger.info("Personalization consolidation disabled (flag or env)")
        else:
            from tldw_Server_API.app.services.personalization_consolidation import get_consolidation_service
            _consol = get_consolidation_service()
            await _consol.start()
            logger.info("Personalization consolidation service started")
    except Exception as e:
        logger.warning(f"Failed to start personalization consolidation: {e}")

    # Ensure PG RLS policies (optional, guarded by env)
    try:
        _ensure_rls = _env_os.getenv("RAG_ENSURE_PG_RLS", "").lower() in {"1", "true", "yes", "on"}
        if _ensure_rls:
            from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
            from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig
            from tldw_Server_API.app.core.DB_Management.backends.pg_rls_policies import (
                ensure_prompt_studio_rls,
                ensure_chacha_rls,
            )
            _cfg = DatabaseConfig.from_env()
            _backend = DatabaseBackendFactory.create_backend(_cfg)
            _ps_ok = ensure_prompt_studio_rls(_backend)
            _cc_ok = ensure_chacha_rls(_backend)
            logger.info(
                f"PG RLS ensure invoked (prompt_studio_applied={_ps_ok}, chacha_applied={_cc_ok})"
            )
        else:
            logger.info("PG RLS auto-ensure disabled (set RAG_ENSURE_PG_RLS=true to enable)")
    except Exception as e:
        logger.warning(f"Failed to apply PG RLS policies automatically: {e}")

    # Start RAG quality eval scheduler (nightly dashboards)
    try:
        _disable_quality_eval = _env_os.getenv("RAG_QUALITY_EVAL_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}
        if _disable_quality_eval:
            logger.info("RAG quality eval scheduler disabled (RAG_QUALITY_EVAL_ENABLED != true)")
        else:
            from tldw_Server_API.app.services.quality_eval_scheduler import start_quality_eval_scheduler
            _quality_task = await start_quality_eval_scheduler()
            if _quality_task:
                logger.info("RAG quality eval scheduler started")
    except Exception as e:
        logger.warning(f"Failed to start RAG quality eval scheduler: {e}")

    # Start Outputs purge scheduler (daily maintenance)
    try:
        _enable_outputs_purge = _env_os.getenv("OUTPUTS_PURGE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        if not _enable_outputs_purge:
            logger.info("Outputs purge scheduler disabled (OUTPUTS_PURGE_ENABLED != true)")
        else:
            from tldw_Server_API.app.services.outputs_purge_scheduler import start_outputs_purge_scheduler
            _purge_task = await start_outputs_purge_scheduler()
            if _purge_task:
                logger.info("Outputs purge scheduler started")
    except Exception as e:
        logger.warning(f"Failed to start Outputs purge scheduler: {e}")

    # Start Connectors worker (scaffold; opt-in via env)
    try:
        from tldw_Server_API.app.services.connectors_worker import start_connectors_worker
        _conn_task = await start_connectors_worker()
        if _conn_task:
            logger.info("Connectors worker started")
        else:
            logger.info("Connectors worker disabled (CONNECTORS_WORKER_ENABLED != true)")
    except Exception as e:
        logger.warning(f"Failed to start Connectors worker: {e}")

    # Start AuthNZ scheduler (retention/cleanup tasks) with env guard
    _authnz_sched_started = False
    try:
        _disable_authnz_sched = _env_os.getenv("DISABLE_AUTHNZ_SCHEDULER", "").lower() in {"1", "true", "yes", "on"}
        if _disable_authnz_sched:
            logger.info("AuthNZ scheduler disabled via DISABLE_AUTHNZ_SCHEDULER env var")
        else:
            from tldw_Server_API.app.core.AuthNZ.scheduler import start_authnz_scheduler
            await start_authnz_scheduler()
            _authnz_sched_started = True
            logger.info("AuthNZ scheduler started")
    except Exception as e:
        logger.warning(f"Failed to start AuthNZ scheduler: {e}")

    # Start Workflows recurring scheduler (cron-based submission into core Scheduler)
    workflows_sched_task = None
    try:
        from tldw_Server_API.app.services.workflows_scheduler import start_workflows_scheduler
        workflows_sched_task = await start_workflows_scheduler()
        if workflows_sched_task:
            logger.info("Workflows recurring scheduler started")
        else:
            logger.info("Workflows recurring scheduler disabled (WORKFLOWS_SCHEDULER_ENABLED != true)")
    except Exception as e:
        logger.warning(f"Failed to start Workflows recurring scheduler: {e}")

    # Display authentication mode (mask API key in production)
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings, is_single_user_mode
        settings = get_settings()
        import os as _os
        def _mask_key(_key: str) -> str:
            if not _key or len(_key) < 8:
                return "********"
            return f"{_key[:4]}...{_key[-4:]}"
        _is_prod = _os.getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}
        _show_key = _os.getenv("SHOW_API_KEY_ON_STARTUP", "false").lower() in {"true", "1", "yes"}

        logger.info("=" * 60)
        logger.info("🚀 TLDW Server Started Successfully")
        logger.info("=" * 60)

        if is_single_user_mode():
            logger.info(f"🔐 Authentication Mode: SINGLE USER")
            # Never log full API key in production unless explicitly allowed
            if _is_prod and not _show_key:
                logger.info(f"🔑 API Key: {_mask_key(settings.SINGLE_USER_API_KEY)} (masked)")
            else:
                logger.info(f"🔑 API Key: {settings.SINGLE_USER_API_KEY}")
            logger.info("=" * 60)
            logger.info("Use this API key in the X-API-KEY header for requests")
        else:
            logger.info(f"🔐 Authentication Mode: MULTI USER")
            try:
                # Prefer unified backend detector for diagnostics
                from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend as _is_pg_backend
                _is_pg = await _is_pg_backend()
                if _is_pg:
                    logger.info("JWT Bearer tokens required for authentication")
                else:
                    logger.info("JWT Bearer tokens or X-API-KEY (per-user) supported for SQLite setups")
            except Exception:
                logger.info("JWT Bearer tokens required for authentication")
            logger.info("=" * 60)

        logger.info(f"📍 API Documentation: http://127.0.0.1:8000/docs")
        logger.info(f"🌐 WebUI: http://127.0.0.1:8000/webui/")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Failed to display startup info: {e}")

    # Preflight environment report (non-blocking)
    try:
        import os as _os
        from tldw_Server_API.app.core.AuthNZ.csrf_protection import global_settings as _csrf_globals
        from tldw_Server_API.app.core.Chat.provider_manager import get_provider_manager as _get_pm
        from tldw_Server_API.app.core.Metrics import OTEL_AVAILABLE as _OTEL
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
        from tldw_Server_API.app.core.config import (
            ALLOWED_ORIGINS as _ALLOWED_ORIGINS,
            should_disable_cors as _should_disable_cors,
        )

        _s = _get_settings()
        _prod = _os.getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}
        _auth_mode = _s.AUTH_MODE
        _db_url = _s.DATABASE_URL
        # Use the unified backend detector for the engine label in diagnostics
        try:
            from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend as _is_pg_backend
            _is_pg = await _is_pg_backend()
            _db_engine = "postgresql" if _is_pg else ("sqlite" if str(_db_url).startswith("sqlite") else "other")
        except Exception:
            _db_engine = "other"
        _redis_url = _s.REDIS_URL or ""
        _redis_enabled = bool(_s.REDIS_URL) or bool(_os.getenv("REDIS_ENABLED", "false").lower() in {"true", "1", "yes", "y", "on"})
        _csrf_enabled = (_auth_mode == "multi_user") or (_csrf_globals.get('CSRF_ENABLED', None) is True)
        _cors_count = len(_ALLOWED_ORIGINS) if isinstance(_ALLOWED_ORIGINS, list) else 0
        _has_limiter = hasattr(app.state, 'limiter')
        _pm = _get_pm()
        _providers = len(_pm.providers) if _pm and hasattr(_pm, 'providers') else 0

        logger.info("Preflight Environment Report ─────────────────────────────────────────")
        logger.info(f"• Mode: {_auth_mode} | Production: {_prod}")
        logger.info(f"• Database: engine={_db_engine}")
        if _db_engine == "sqlite" and _auth_mode == "multi_user":
            if _prod:
                logger.error("• Database check: FAIL (SQLite in multi-user prod not supported)")
            else:
                logger.warning("• Database check: WARN (SQLite in multi-user; prefer PostgreSQL)")
        else:
            logger.info("• Database check: OK")
        logger.info(f"• Redis: enabled={_redis_enabled}")
        logger.info(f"• CSRF: enabled={_csrf_enabled}")
        if _should_disable_cors():
            logger.info("• CORS: disabled")
        else:
            logger.info(f"• CORS: allowed_origins={_cors_count}")
        logger.info(f"• Global rate limiter: {_has_limiter}")
        logger.info(f"• Providers configured: {_providers}")
        logger.info(f"• OpenTelemetry available: {bool(_OTEL)}")
        logger.info("──────────────────────────────────────────────────────────────────────")

        # Warn if test-mode gates/toggles are enabled in a production environment
        try:
            if _prod:
                _test_flags = {
                    "TEST_MODE": _os.getenv("TEST_MODE", ""),
                    "TLDW_TEST_MODE": _os.getenv("TLDW_TEST_MODE", ""),
                    "WORKFLOWS_DISABLE_RATE_LIMITS": _os.getenv("WORKFLOWS_DISABLE_RATE_LIMITS", ""),
                }
                _enabled = [k for k, v in _test_flags.items() if str(v).lower() in {"1", "true", "yes", "on"}]
                if _enabled:
                    logger.warning(
                        f"Test-mode toggles enabled in production: {', '.join(_enabled)} - disable these for secure deployments"
                    )
        except Exception:
            pass
    except Exception as _pf_e:
        logger.warning(f"Preflight report could not be generated: {_pf_e}")

    yield

    # Flip readiness early and gate new job acquisitions for graceful shutdown
    try:
        READINESS_STATE["ready"] = False
        from tldw_Server_API.app.core.Jobs.manager import JobManager as _JM
        _JM.set_acquire_gate(True)
    except Exception:
        pass

    # Optionally wait for leases to finish (bounded wait)
    try:
        import os as _os
        import asyncio as _asyncio
        _max_wait = int(_os.getenv("JOBS_SHUTDOWN_WAIT_FOR_LEASES_SEC", "0") or "0")
        if _max_wait > 0:
            jm_chk = _JM()
            deadline = _asyncio.get_event_loop().time() + float(_max_wait)
            while _asyncio.get_event_loop().time() < deadline:
                try:
                    active = jm_chk.count_active_processing()
                except Exception:
                    active = 0
                if active <= 0:
                    break
                await _asyncio.sleep(0.5)
    except Exception:
        pass

    # Cancel/stop background worker(s)
    try:
        bg = getattr(app.state, 'bg_tasks', None)
        if isinstance(bg, dict):
            task = bg.get('deferred_startup')
            if task:
                try:
                    task.cancel()
                except Exception:
                    pass
    except Exception:
        pass
    try:
        if 'cleanup_task' in locals() and cleanup_task:
            cleanup_task.cancel()
        if 'core_jobs_task' in locals() and core_jobs_task:
            # Prefer graceful stop via explicit stop_event
            if 'core_jobs_stop_event' in locals() and core_jobs_stop_event:
                try:
                    core_jobs_stop_event.set()
                    await _asyncio.wait_for(core_jobs_task, timeout=5.0)
                    logger.info("Core Jobs worker (Chatbooks) stopped via stop_event")
                except Exception:
                    core_jobs_task.cancel()
            else:
                core_jobs_task.cancel()
        if 'audio_jobs_task' in locals() and audio_jobs_task:
            # Prefer graceful stop via explicit stop_event
            if 'audio_jobs_stop_event' in locals() and audio_jobs_stop_event:
                try:
                    audio_jobs_stop_event.set()
                    await _asyncio.wait_for(audio_jobs_task, timeout=5.0)
                    logger.info("Audio Jobs worker stopped via stop_event")
                except Exception:
                    audio_jobs_task.cancel()
            else:
                audio_jobs_task.cancel()
        if 'claims_task' in locals() and claims_task:
            claims_task.cancel()
        if 'embeddings_compactor_task' in locals() and embeddings_compactor_task:
            if 'embeddings_compactor_stop_event' in locals() and embeddings_compactor_stop_event:
                try:
                    embeddings_compactor_stop_event.set()
                    await _asyncio.wait_for(embeddings_compactor_task, timeout=5.0)
                    logger.info("Embeddings Vector Compactor stopped via stop_event")
                except Exception:
                    embeddings_compactor_task.cancel()
            else:
                embeddings_compactor_task.cancel()
        # Stop usage aggregators gracefully
        try:
            if 'usage_task' in locals() and usage_task:
                from tldw_Server_API.app.services.usage_aggregator import stop_usage_aggregator as _stop_usage
                await _stop_usage(usage_task)
        except Exception:
            try:
                usage_task.cancel()
            except Exception:
                pass
        try:
            if 'llm_usage_task' in locals() and llm_usage_task:
                from tldw_Server_API.app.services.llm_usage_aggregator import stop_llm_usage_aggregator as _stop_llm
                await _stop_llm(llm_usage_task)
        except Exception:
            try:
                llm_usage_task.cancel()
            except Exception:
                pass
        # Stop Workflows recurring scheduler
        try:
            if 'workflows_sched_task' in locals() and workflows_sched_task:
                from tldw_Server_API.app.services.workflows_scheduler import stop_workflows_scheduler as _stop_wf_sched
                await _stop_wf_sched(workflows_sched_task)
        except Exception:
            try:
                if 'workflows_sched_task' in locals() and workflows_sched_task:
                    workflows_sched_task.cancel()
            except Exception:
                pass
        # Jobs metrics gauges worker shutdown
        if 'jobs_metrics_task' in locals() and jobs_metrics_task:
            try:
                if 'jobs_metrics_stop_event' in locals() and jobs_metrics_stop_event:
                    jobs_metrics_stop_event.set()
                    await _asyncio.wait_for(jobs_metrics_task, timeout=5.0)
                    logger.info("Jobs metrics gauge worker stopped via stop_event")
                else:
                    jobs_metrics_task.cancel()
            except Exception:
                try:
                    jobs_metrics_task.cancel()
                except Exception:
                    pass

        # Personalization consolidation service shutdown
        try:
            from tldw_Server_API.app.services.personalization_consolidation import get_consolidation_service
            _consol = get_consolidation_service()
            await _consol.stop()
            logger.info("Personalization consolidation service stopped")
        except Exception:
            pass

        # Jobs crypto rotate worker shutdown
        if 'jobs_crypto_rotate_task' in locals() and jobs_crypto_rotate_task:
            try:
                if 'jobs_crypto_rotate_stop_event' in locals() and jobs_crypto_rotate_stop_event:
                    jobs_crypto_rotate_stop_event.set()
                    await _asyncio.wait_for(jobs_crypto_rotate_task, timeout=5.0)
                    logger.info("Jobs crypto rotate worker stopped via stop_event")
                else:
                    jobs_crypto_rotate_task.cancel()
            except Exception:
                try:
                    jobs_crypto_rotate_task.cancel()
                except Exception:
                    pass

        # Jobs integrity sweeper shutdown
        if 'jobs_integrity_task' in locals() and jobs_integrity_task:
            try:
                if 'jobs_integrity_stop_event' in locals() and jobs_integrity_stop_event:
                    jobs_integrity_stop_event.set()
                    await _asyncio.wait_for(jobs_integrity_task, timeout=5.0)
                    logger.info("Jobs integrity sweeper stopped via stop_event")
                else:
                    jobs_integrity_task.cancel()
            except Exception:
                try:
                    jobs_integrity_task.cancel()
                except Exception:
                    pass

        # Jobs webhooks worker shutdown
        if 'jobs_webhooks_task' in locals() and jobs_webhooks_task:
            try:
                if 'jobs_webhooks_stop_event' in locals() and jobs_webhooks_stop_event:
                    jobs_webhooks_stop_event.set()
                    await _asyncio.wait_for(jobs_webhooks_task, timeout=5.0)
                    logger.info("Jobs webhooks worker stopped via stop_event")
                else:
                    jobs_webhooks_task.cancel()
            except Exception:
                try:
                    jobs_webhooks_task.cancel()
                except Exception:
                    pass

        # Workflows webhook DLQ worker shutdown
        if 'workflows_dlq_task' in locals() and workflows_dlq_task:
            try:
                if 'workflows_dlq_stop_event' in locals() and workflows_dlq_stop_event:
                    workflows_dlq_stop_event.set()
                    await _asyncio.wait_for(workflows_dlq_task, timeout=5.0)
                    logger.info("Workflows webhook DLQ worker stopped via stop_event")
                else:
                    workflows_dlq_task.cancel()
            except Exception:
                try:
                    workflows_dlq_task.cancel()
                except Exception:
                    pass

        # Workflows artifact GC worker shutdown
        if 'workflows_gc_task' in locals() and workflows_gc_task:
            try:
                if 'workflows_gc_stop_event' in locals() and workflows_gc_stop_event:
                    workflows_gc_stop_event.set()
                    await _asyncio.wait_for(workflows_gc_task, timeout=5.0)
                    logger.info("Workflows artifact GC worker stopped via stop_event")
                else:
                    workflows_gc_task.cancel()
            except Exception:
                try:
                    workflows_gc_task.cancel()
                except Exception:
                    pass

        # Workflows DB maintenance worker shutdown
        if 'workflows_maint_task' in locals() and workflows_maint_task:
            try:
                if 'workflows_maint_stop_event' in locals() and workflows_maint_stop_event:
                    workflows_maint_stop_event.set()
                    await _asyncio.wait_for(workflows_maint_task, timeout=5.0)
                    logger.info("Workflows DB maintenance worker stopped via stop_event")
                else:
                    workflows_maint_task.cancel()
            except Exception:
                try:
                    workflows_maint_task.cancel()
                except Exception:
                    pass
    except Exception:
        pass

    # Shutdown: Clean up resources
    logger.info("App Shutdown: Cleaning up resources...")

    # Note: Audit service cleanup handled via dependency injection
    # No global shutdown needed
    logger.info("App Shutdown: Audit services cleanup handled by dependency injection")

    # Close auth database pool (skip in test contexts to avoid closing shared pool)
    try:
        if 'db_pool' in locals():
            import os as _os, sys as _sys
            _in_pytest = bool(_os.getenv("PYTEST_CURRENT_TEST") or ("pytest" in _sys.modules))
            try:
                _is_test_mode = _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")
            except Exception:
                _is_test_mode = False
            if not (_is_test_mode or _in_pytest):
                await db_pool.close()
                logger.info("App Shutdown: Auth database pool closed")
            else:
                logger.info("App Shutdown: Skipping DB pool close in test context")
    except Exception as e:
        logger.error(f"App Shutdown: Error closing auth database pool: {e}")

    # Shutdown session manager
    try:
        if 'session_manager' in locals():
            await session_manager.shutdown()
            logger.info("App Shutdown: Session manager shutdown")
    except Exception as e:
        logger.error(f"App Shutdown: Error shutting down session manager: {e}")

    # Shutdown MCP Unified server
    try:
        if 'mcp_server' in locals() and mcp_server is not None:
            await mcp_server.shutdown()
            logger.info("App Shutdown: MCP Unified server shutdown")
    except Exception as e:
        logger.error(f"App Shutdown: Error shutting down MCP Unified server: {e}")

    # Shutdown MCP Unified rate limiter cleanup task (if any)
    try:
        from tldw_Server_API.app.core.MCP_unified.auth.rate_limiter import (
            shutdown_rate_limiter as _mcp_shutdown_rl,
        )
        await _mcp_shutdown_rl()
        logger.info("App Shutdown: MCP rate limiter cleanup task cancelled")
    except Exception as e:
        logger.debug(f"App Shutdown: MCP rate limiter shutdown skipped/failed: {e}")

    # Shutdown TTS Service
    try:
        from tldw_Server_API.app.core.TTS.tts_service_v2 import close_tts_service_v2
        await close_tts_service_v2()
        logger.info("App Shutdown: TTS service shutdown complete")
    except Exception as e:
        logger.error(f"App Shutdown: Error shutting down TTS service: {e}")

    # Shutdown Chat Module Components
    logger.info("App Shutdown: Cleaning up Chat module components...")

    # Shutdown Provider Manager
    try:
        if 'provider_manager' in locals() and provider_manager is not None:
            await provider_manager.stop_health_checks()
            logger.info("App Shutdown: Provider manager stopped")
    except Exception as e:
        logger.error(f"App Shutdown: Error stopping provider manager: {e}")

    # Shutdown Request Queue
    try:
        if 'request_queue' in locals() and request_queue is not None:
            await request_queue.stop()
            logger.info("App Shutdown: Request queue stopped")
    except Exception as e:
        logger.error(f"App Shutdown: Error stopping request queue: {e}")

    # Shutdown Evaluations connection manager (stops maintenance thread for tests)
    try:
        from tldw_Server_API.app.core.Evaluations.connection_pool import connection_manager

        if connection_manager is not None:
            connection_manager.shutdown()
            logger.info("App Shutdown: Evaluations connection manager shutdown")
    except Exception as e:
        logger.error(f"App Shutdown: Error shutting down evaluations connection manager: {e}")

    # Shutdown Unified Audit Services (via DI cache)
    try:
        from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
            shutdown_all_audit_services,
        )
        await shutdown_all_audit_services()
        logger.info("App Shutdown: Unified audit services stopped")
    except Exception as e:
        logger.error(f"App Shutdown: Error stopping unified audit services: {e}")

    # Shutdown registered executors (thread/process pools)
    try:
        from tldw_Server_API.app.core.Utils.executor_registry import shutdown_all_registered_executors
        await shutdown_all_registered_executors(wait=True, cancel_futures=True)
        logger.info("App Shutdown: Registered executors shutdown")
    except Exception as e:
        logger.error(f"App Shutdown: Error shutting down executors: {e}")

    # Cleanup CPU pools
    try:
        from tldw_Server_API.app.core.Utils.cpu_bound_handler import cleanup_pools
        cleanup_pools()
        logger.info("App Shutdown: CPU pools cleaned up")
    except Exception as e:
        logger.error(f"App Shutdown: Error cleaning up CPU pools: {e}")

    # Stop usage aggregator
    try:
        if 'usage_task' in locals() and usage_task:
            from tldw_Server_API.app.services.usage_aggregator import stop_usage_aggregator
            await stop_usage_aggregator(usage_task)
            logger.info("Usage aggregator stopped")
    except Exception as e:
        logger.error(f"App Shutdown: Error stopping usage aggregator: {e}")

    # Shutdown telemetry
    try:
        # Stop AuthNZ scheduler if started
        try:
            if '_authnz_sched_started' in locals() and _authnz_sched_started:
                from tldw_Server_API.app.core.AuthNZ.scheduler import stop_authnz_scheduler
                await stop_authnz_scheduler()
                logger.info("AuthNZ scheduler stopped")
        except Exception as _e:
            logger.debug(f"AuthNZ scheduler shutdown skipped: {_e}")

        # Shutdown cached audit adapter services (Embeddings adapter)
        try:
            from tldw_Server_API.app.core.Embeddings.audit_adapter import (
                shutdown_audit_adapter_services as _shutdown_audit_adapter,
            )
            await _shutdown_audit_adapter()
            logger.info("Embeddings audit adapter services shutdown")
        except Exception as _e:
            logger.debug(f"Embeddings audit adapter shutdown skipped: {_e}")

        shutdown_telemetry()
        logger.info("App Shutdown: Telemetry shutdown")
    except Exception as e:
        logger.error(f"App Shutdown: Error shutting down telemetry: {e}")

    # Close shared content database backend pool (PostgreSQL content mode)
    try:
        from tldw_Server_API.app.core.DB_Management.DB_Manager import shutdown_content_backend as _shutdown_content_backend
        _shutdown_content_backend()
        logger.info("App Shutdown: Content DB backend pool closed")
    except Exception as e:
        logger.debug(f"App Shutdown: Content backend pool close skipped/failed: {e}")

    # Original test DB cleanup
    global test_db_instance_ref
    if test_db_instance_ref and hasattr(test_db_instance_ref, 'close_all_connections'):
        logger.info("App Shutdown: Closing test DB connections")
        test_db_instance_ref.close_all_connections()
    else:
        logger.info("App Shutdown: No test DB instance found to close")
#
############################# End of Test DB Handling###################

# Create FastAPI app with lifespan
from fastapi.openapi.utils import get_openapi

# --- OpenAPI / Docs configuration ---

# Curated tag metadata to improve /docs grouping and clarity

import os as _env_os  # ensure available for _ext_url during module import

# Build absolute externalDocs URLs for OpenAPI (Pydantic v2 requires absolute URLs)
def _ext_url(path: str) -> str:
    base = _env_os.getenv("OPENAPI_EXTERNAL_DOCS_BASE_URL")
    if base and (base.startswith("http://") or base.startswith("https://")):
        return base.rstrip("/") + path
    fallback = _env_os.getenv("OPENAPI_SERVER_BASE_URL", "http://127.0.0.1:8000")
    return fallback.rstrip("/") + path
OPENAPI_TAGS = [
    {"name": "health", "description": "Health and status checks."},
    {"name": "authentication", "description": "AuthNZ endpoints for API key and JWT-based auth.",
     "externalDocs": {"description": "AuthNZ usage", "url": _ext_url("/docs-static/AUTHNZ_USAGE_EXAMPLES.md")}},
    {"name": "users", "description": "User management: create, list, roles, and profiles.",
     "externalDocs": {"description": "Permission matrix", "url": _ext_url("/docs-static/AUTHNZ_PERMISSION_MATRIX.md")}},
    {"name": "admin", "description": "Administrative operations and diagnostics (non-Jobs). For Jobs Admin endpoints (stats, prune, TTL sweep, requeue quarantined, integrity sweep), see the 'jobs' tag.",
     "externalDocs": {"description": "Jobs Admin Examples", "url": _ext_url("/docs-static/Code_Documentation/Jobs_Admin_Examples.md")}},
    {"name": "jobs", "description": "Jobs queue manager and admin (SQLite/PG).",
     "externalDocs": {"description": "Jobs Manager ordering", "url": _ext_url("/docs-static/Code_Documentation/Jobs_Manager.md")}},
    {"name": "media", "description": "Ingest and process media (video/audio/PDF/EPUB/HTML/Markdown).",
     "externalDocs": {"description": "Overview", "url": _ext_url("/docs-static/Documentation.md")}},
    {"name": "audio", "description": "Audio transcription and TTS (OpenAI-compatible).",
     "externalDocs": {"description": "Nemo STT setup", "url": _ext_url("/docs-static/NEMO_STT_DOCUMENTATION.md")}},
    {"name": "audio-websocket", "description": "Real-time streaming transcription over WebSocket.",
     "externalDocs": {"description": "Streaming STT", "url": _ext_url("/docs-static/NEMO_STREAMING_DOCUMENTATION.md")}},
    {"name": "audio-jobs", "description": "Background audio processing via Jobs (fan-out pipeline).",
     "externalDocs": {"description": "Audio Jobs API", "url": _ext_url("/docs-static/API-related/Audio_Jobs_API.md")}},
    {"name": "chat", "description": "Chat completions and conversation management (OpenAI-compatible).",
     "externalDocs": {"description": "Chat API", "url": _ext_url("/docs-static/API-related/Chat_API_Documentation.md")}},
    {"name": "characters", "description": "Character cards/personas and related operations.",
     "externalDocs": {"description": "Character Chat API", "url": _ext_url("/docs-static/CHARACTER_CHAT_API_DOCUMENTATION.md")}},
    {"name": "character-chat-sessions", "description": "Character chat sessions lifecycle management.",
     "externalDocs": {"description": "Character Chat API", "url": _ext_url("/docs-static/CHARACTER_CHAT_API_DOCUMENTATION.md")}},
    {"name": "character-messages", "description": "Character message creation, retrieval, and search.",
     "externalDocs": {"description": "Character Chat API", "url": _ext_url("/docs-static/CHARACTER_CHAT_API_DOCUMENTATION.md")}},
    {"name": "metrics", "description": "Metrics and monitoring endpoints.",
     "externalDocs": {"description": "Metrics design", "url": _ext_url("/docs-static/Design/Metrics.md")}},
    {"name": "monitoring", "description": "OpenTelemetry/metrics reporting in JSON."},
    {"name": "audit", "description": "Audit export, count, and tools. Includes /audit/export and /audit/count.",
     "externalDocs": {"description": "Audit Export & Count API", "url": _ext_url("/docs-static/API/Audit_Export.md")}},
    {"name": "chunking", "description": "Content chunking operations and utilities.",
     "externalDocs": {"description": "Chunking design", "url": _ext_url("/docs-static/Design/Chunking.md")}},
    {"name": "chunking-templates", "description": "Chunking template management (create, list, update).",
     "externalDocs": {"description": "Templates", "url": _ext_url("/docs-static/Chunking_Templates.md")}},
    {"name": "embeddings", "description": "OpenAI-compatible embeddings generation.",
     "externalDocs": {"description": "Embeddings API Guide", "url": _ext_url("/docs-static/Embeddings/Embeddings-API-Guide.md")}},
    {"name": "vector-stores", "description": "OpenAI-compatible vector store APIs (indexes, vectors).",
     "externalDocs": {"description": "Embedding & Vector Store Config", "url": _ext_url("/docs-static/Development/Embedding-and-Vectorstore-Config.md")}},
    {"name": "claims", "description": "Claims extraction, indexing, and maintenance for media.",
     "externalDocs": {"description": "Claims design", "url": _ext_url("/docs-static/Design/ingestion_claims.md")}},
    {"name": "media-embeddings", "description": "Generate embeddings for uploaded/ingested media.",
     "externalDocs": {"description": "Embeddings docs", "url": _ext_url("/docs-static/Embeddings/Embeddings-Documentation.md")}},
    {"name": "notes", "description": "Notes and knowledge management."},
    {"name": "prompts", "description": "Prompt library management (import/export).",
     "externalDocs": {"description": "Prompts design", "url": _ext_url("/docs-static/Design/Prompts.md")}},
    {"name": "prompt-studio", "description": "Projects, prompts, tests, optimization, and background jobs (experimental).",
     "externalDocs": {"description": "Prompt Studio API", "url": _ext_url("/docs-static/API-related/Prompt_Studio_API.md")}},
    {"name": "rag-health", "description": "RAG health, caching, and metrics.",
     "externalDocs": {"description": "RAG notes", "url": _ext_url("/docs-static/RAG_Notes.md")}},
    {"name": "rag-unified", "description": "Unified RAG: FTS5 + embeddings + re-ranking.",
     "externalDocs": {"description": "RAG notes", "url": _ext_url("/docs-static/RAG_Notes.md")}},
    {"name": "workflows", "description": "Workflow definitions and execution (scaffolding, experimental).",
     "externalDocs": {"description": "Workflows", "url": _ext_url("/docs-static/Design/Workflows.md")}},
    {"name": "research", "description": "Research providers and web data collection.",
     "externalDocs": {"description": "Researcher", "url": _ext_url("/docs-static/Design/Researcher.md")}},
    {"name": "paper-search", "description": "Provider-specific paper search (arXiv, BioRxiv/MedRxiv, PubMed, Semantic Scholar).",
     "externalDocs": {"description": "Paper Search", "url": _ext_url("/docs-static/Design/PaperSearch.md")}},
    {"name": "evaluations", "description": "Unified evaluation APIs (geval, batch, metrics).",
     "externalDocs": {"description": "Eval report", "url": _ext_url("/docs-static/EVALUATION_TEST_REPORT.md")}},
    {"name": "benchmarks", "description": "Benchmarking endpoints and utilities.",
     "externalDocs": {"description": "RAG benchmarks", "url": _ext_url("/docs-static/RAG_Benchmarks.md")}},
    {"name": "config", "description": "Server configuration and capability info."},
    {"name": "sync", "description": "Synchronization operations and helpers."},
    {"name": "tools", "description": "Tooling endpoints (utilities)."},
    {"name": "mcp-unified", "description": "MCP server + endpoints (JWT/RBAC) - experimental surface in 0.1.",
     "externalDocs": {"description": "MCP Unified Developer Guide", "url": _ext_url("/docs-static/MCP/Unified/Developer_Guide.md")}},
    {"name": "flashcards", "description": "Flashcards/Decks (ChaChaNotes)"},
    {"name": "chatbooks", "description": "Import/export chatbooks (backup/restore).",
     "externalDocs": {"description": "Chatbooks API", "url": _ext_url("/docs-static/API-related/Chatbook_Features_API_Documentation.md")}},
    {"name": "llm", "description": "LLM provider configuration and discovery.",
     "externalDocs": {"description": "Chat developer guide", "url": _ext_url("/docs-static/Code_Documentation/Chat_Developer_Guide.md")}},
    {"name": "llamacpp", "description": "Llama.cpp helpers and management.",
     "externalDocs": {"description": "Inference engines", "url": _ext_url("/docs-static/Design/Inference_Engines.md")}},
    {"name": "web-scraping", "description": "Web scraping management and job control.",
     "externalDocs": {"description": "Web scraping design", "url": _ext_url("/docs-static/Design/WebScraping.md")}},
    {"name": "chat-dictionaries", "description": "Per-user/domain dictionaries for chat preprocessing and postprocessing.",
     "externalDocs": {"description": "Character Chat API", "url": _ext_url("/docs-static/CHARACTER_CHAT_API_DOCUMENTATION.md")}},
    {"name": "chat-documents", "description": "Generate documents from conversations and templates."},
    {"name": "personalization", "description": "Opt-in user profiles, memories, and RAG biasing.",
     "externalDocs": {"description": "Personalization design", "url": _ext_url("/docs-static/Design/Personalization_Design.md")}},
    {"name": "persona", "description": "Persona agent (voice, tools, MCP).",
     "externalDocs": {"description": "Persona design", "url": _ext_url("/docs-static/Design/Persona_Agent_Design.md")}},
]

import os as _env_os

_prod_flag = _env_os.getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}

APP_DESCRIPTION = (
    """
    Too Long; Didn't Watch Server (tldw_server) - unified research assistant and media analysis platform.

    Auth: Click the “Authorize” button.
    - Single-user mode: use header X-API-KEY with the printed key.
    - Multi-user mode: use Bearer JWT tokens (login endpoints under authentication).

    Highlights
    - Media ingestion (video/audio/docs) with automatic metadata
    - STT (file + real-time WS) and TTS (OpenAI-compatible)
    - RAG: SQLite FTS5 + embeddings + re-ranking
    - Chat: OpenAI-compatible /chat/completions across providers
    - Notes, prompts, evaluations, MCP Unified server

    Helpful paths
    - Web UI: /webui
    - OpenAPI JSON: /openapi.json
    - Metrics: /metrics and /api/v1/metrics
    """
    .strip()
)

# Always expose docs and redoc; remove ENABLE_OPENAPI toggle
_docs_url = "/docs"
_redoc_url = "/redoc"
# Always serve OpenAPI JSON regardless of docs gating
_openapi_url = "/openapi.json"

_startup_trace("Creating FastAPI app instance")

# Prefer locally-served Swagger UI assets when available to avoid CSP/CDN issues
_swagger_static_dir = BASE_DIR / "static" / "swagger"
_swagger_bundle = _swagger_static_dir / "swagger-ui-bundle.js"
_swagger_css = _swagger_static_dir / "swagger-ui.css"
_swagger_use_local = _swagger_bundle.exists() and _swagger_css.exists()
_swagger_ui_js_url = "/static/swagger/swagger-ui-bundle.js" if _swagger_use_local else None
_swagger_ui_css_url = "/static/swagger/swagger-ui.css" if _swagger_use_local else None

# Merge Swagger UI parameters and include our overrides via customCssUrl
_swagger_ui_params = {
    "displayRequestDuration": True,
    "deepLinking": True,
    "docExpansion": "none",
    "defaultModelsExpandDepth": -1,
    "defaultModelExpandDepth": 2,
    "persistAuthorization": True,
    "tryItOutEnabled": True,
    "tagsSorter": "alpha",
    "operationsSorter": "alpha",
    "filter": True,
    # Inject our optional overrides stylesheet without replacing the base CSS
    "customCssUrl": "/static/swagger-overrides.css",
}

app = FastAPI(
    title="tldw API",
    version="0.1.0",
    description=APP_DESCRIPTION,
    terms_of_service="https://github.com/cpacker/tldw_server",
    contact={
        "name": "tldw_server Maintainers",
        "url": "https://github.com/cpacker/tldw_server/issues",
    },
    license_info={
        "name": "GNU GPL v2.0",
        "url": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html",
    },
    openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters=_swagger_ui_params,
    swagger_ui_js_url=_swagger_ui_js_url,
    swagger_ui_css_url=_swagger_ui_css_url,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
    lifespan=lifespan,
)
_startup_trace("FastAPI app created")

# Early middleware to guard workflow templates path traversal attempts
from starlette.responses import JSONResponse  # noqa: E402

@app.middleware("http")
async def _guard_workflow_templates_traversal(request, call_next):
    try:
        p = request.url.path or ""
        # Only inspect under the workflows templates prefix
        prefix = "/api/v1/workflows/templates/"
        if p.startswith(prefix):
            tail = p[len(prefix):]
            # If any traversal segments are found in the raw path, reject early with 400
            # This runs before route resolution so it also handles router-level 404 shortcuts.
            if ".." in tail.split("/"):
                return JSONResponse({"detail": "Invalid template name"}, status_code=400)
    except Exception:
        pass
    return await call_next(request)

# Early middleware to guard sandbox artifact path traversal/double-slash before Starlette routing
@app.middleware("http")
async def _guard_sandbox_artifact_path(request: Request, call_next):
    try:
        # Inspect raw ASGI path first to avoid client/Starlette normalization
        raw_path = request.scope.get("raw_path")
        path_raw = raw_path.decode("utf-8", "ignore") if isinstance(raw_path, (bytes, bytearray)) else (request.url.path or "")
        # Debug logging removed after verification
        # Quick filter: only check sandbox artifact endpoints
        # Example: /api/v1/sandbox/runs/{run_id}/artifacts/{path}
        if "/api/v1/sandbox/runs/" in path_raw and "/artifacts/" in path_raw:
            from urllib.parse import unquote
            # Segment after /artifacts/
            idx = path_raw.find("/artifacts/")
            tail = path_raw[idx + len("/artifacts/"):]
            tail_unquoted = unquote(tail)
            # Reject traversal attempts and absolute/double-slash paths
            if (
                ".." in tail_unquoted.split("/")
                or tail_unquoted.startswith("/")
                or "//" in tail
            ):
                return JSONResponse({"detail": "invalid_path"}, status_code=400)
    except Exception:
        # Fail open: if guard fails, let the request proceed
        pass
    return await call_next(request)

# Add global security schemes, servers, and branding to the generated OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )

    # Servers for common deployments
    openapi_schema["servers"] = [
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "http://127.0.0.1:8000", "description": "Loopback"},
    ]

    # Security schemes to document both supported auth modes
    components = openapi_schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes.update(
        {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-KEY",
                "description": "Single-user mode API key authentication.",
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Multi-user mode JWT bearer token.",
            },
        }
    )

    # Optional: top-level external docs and logo
    openapi_schema["externalDocs"] = {
        "description": "Project documentation",
        "url": "/docs-static",
    }
    openapi_schema.setdefault("info", {}).setdefault("x-logo", {"url": "/static/favicon.ico"})

    # Default security: show lock icons by default in Swagger UI
    # Endpoints can override with openapi_extra={"security": []} to be public
    openapi_schema["security"] = [
        {"ApiKeyAuth": []},
        {"BearerAuth": []},
    ]

    # ReDoc tag grouping for better navigation in /redoc
    openapi_schema["x-tagGroups"] = [
        {
            "name": "Core",
            "tags": ["health", "authentication", "users", "admin"],
        },
        {
            "name": "Media",
            "tags": ["media", "audio", "media-embeddings", "web-scraping", "research", "paper-search"],
        },
        {
            "name": "Chat & TTS",
            "tags": [
                "chat",
                "chat-dictionaries",
                "chat-documents",
                "audio-websocket",
                "characters",
                "character-chat-sessions",
                "character-messages",
                "persona",
            ],
        },
        {
            "name": "RAG & Evals",
            "tags": ["rag-health", "rag-unified", "evaluations", "benchmarks"],
        },
        {
            "name": "Embeddings & Vectors",
            "tags": ["embeddings", "vector-stores", "claims"],
        },
        {
            "name": "Studio & Knowledge",
            "tags": ["prompt-studio", "prompts", "notes", "personalization", "chatbooks", "tools"],
        },
        {
            "name": "Infra",
            "tags": ["metrics", "monitoring", "config", "sync", "llm", "llamacpp", "mcp-unified", "workflows"],
        },
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Global SlowAPI rate limiting (skip in test mode)
import os as _os_mod
# Skip global rate limiter when running tests: honor either TESTING=true or TEST_MODE=true
if _os_mod.getenv("TESTING", "").lower() != "true" and _os_mod.getenv("TEST_MODE", "").lower() != "true":
    try:
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware
        # Use the central limiter instance so decorators and middleware share the same limiter
        from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import limiter as _global_limiter
        app.state.limiter = _global_limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)
        logger.info("Global rate limiter initialized (SlowAPI)")
    except Exception as _e:
        logger.warning(f"Global rate limiter not initialized: {_e}")
else:
    logger.info("Test mode detected: Skipping global rate limiter initialization (TESTING/TEST_MODE)")

# Display API key information on startup for single user mode
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, is_single_user_mode

async def _display_startup_info_and_warm():
    """Startup banner and optional warm-up tasks (moved to lifespan)."""
    if is_single_user_mode():
        settings = get_settings()
        api_key = settings.SINGLE_USER_API_KEY
        import os as _os
        def _mask_key(_key: str) -> str:
            if not _key or len(_key) < 8:
                return "********"
            return f"{_key[:4]}...{_key[-4:]}"
        _is_prod = _os.getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}
        _show_key = _os.getenv("SHOW_API_KEY_ON_STARTUP", "false").lower() in {"true", "1", "yes"}
        logger.info("="*70)
        logger.info("🚀 TLDW Server Started in SINGLE USER MODE")
        logger.info("="*70)
        logger.info("📌 API Key for authentication:")
        logger.info(f"   {_mask_key(api_key) if (_is_prod and not _show_key) else api_key}")
        logger.info("🌐 Access URLs:")
        logger.info("   WebUI:    http://localhost:8000/webui/")
        logger.info("   API Docs: http://localhost:8000/docs")
        logger.info("   ReDoc:    http://localhost:8000/redoc")
        logger.info("💡 The WebUI will automatically use this API key")
        logger.info("="*70)
    else:
        logger.info("="*70)
        logger.info("🚀 TLDW Server Started in MULTI-USER MODE")
        logger.info("="*70)
        logger.info("Authentication required via JWT tokens")
        logger.info("="*70)

    # Optional pre-warm
    try:
        await asyncio.to_thread(get_cached_evaluation_manager)
    except Exception as exc:
        logger.error(f"Failed to initialize evaluation manager during startup: {exc}")
    try:
        if needs_setup():
            logger.info("First-time setup is enabled. Open http://localhost:8000/setup to configure the server.")
    except FileNotFoundError:
        logger.warning("Configuration file missing; unable to determine setup state. Ensure config.txt exists.")

# --- FIX: Add CORS Middleware ---
# Import from config
from tldw_Server_API.app.core.config import ALLOWED_ORIGINS, API_V1_PREFIX, should_disable_cors, route_enabled

# FIXME - CORS
if should_disable_cors():
    logger.warning("CORS middleware disabled via configuration/ENV flag.")
else:
    origins = ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"]
    # # -- If you have any global middleware, add it here --
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"], # Must include OPTIONS, GET, POST, DELETE etc.
        allow_headers=["*"],
    )

    # Ensure OpenAPI schema is consumable across common local origins (helpful when docs are
    # viewed via alternate hostnames like 127.0.0.1 vs localhost). We only set headers if the
    # CORS middleware didn't already do so.
    @app.middleware("http")
    async def _openapi_cors_helper(request, call_next):
        response = await call_next(request)
        try:
            if request.url.path == _openapi_url:
                origin = request.headers.get("origin")
                if origin:
                    response.headers.setdefault("Access-Control-Allow-Origin", origin)
                    response.headers.setdefault("Vary", "Origin")
                else:
                    response.headers.setdefault("Access-Control-Allow-Origin", "*")
                response.headers.setdefault("Access-Control-Allow-Methods", "GET, OPTIONS")
                response.headers.setdefault("Access-Control-Allow-Headers", "*")
        except Exception:
            pass
        return response

# Add CSRF Protection Middleware (NEW) with friendly error logging for misconfiguration
from tldw_Server_API.app.core.AuthNZ.csrf_protection import add_csrf_protection
try:
    add_csrf_protection(app)
except Exception as _csrf_e:
    logger.error(f"Failed to configure CSRF middleware: {_csrf_e}")
    logger.error(
        "Auth configuration error. If running in single-user mode, ensure SINGLE_USER_API_KEY is set.\n"
        "If running in multi-user mode, ensure JWT_SECRET_KEY is set (>=32 chars).\n"
        "See README: Authentication Setup and .env templates."
    )
    raise

# Static files serving
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Security middleware (headers + request size limit)
from tldw_Server_API.app.core.Security.middleware import SecurityHeadersMiddleware
from tldw_Server_API.app.core.Security.webui_csp import WebUICSPMiddleware
from tldw_Server_API.app.core.Security.webui_access_guard import WebUIAccessGuardMiddleware
from tldw_Server_API.app.core.Security.request_id_middleware import RequestIDMiddleware
from tldw_Server_API.app.core.Metrics.http_middleware import HTTPMetricsMiddleware
from tldw_Server_API.app.core.AuthNZ.usage_logging_middleware import UsageLoggingMiddleware
from tldw_Server_API.app.core.AuthNZ.llm_budget_middleware import LLMBudgetMiddleware

_TEST_MODE = (
    _env_os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")
    or bool(_env_os.getenv("PYTEST_CURRENT_TEST"))
)

if _TEST_MODE:
    logger.info("TEST_MODE detected: Skipping non-essential middlewares (security headers, metrics, usage logging)")
    # Provide request id + trace headers even in tests for assertions
    app.add_middleware(RequestIDMiddleware)
    # Apply WebUI CSP nonce injection even in tests to keep behavior consistent
    try:
        app.add_middleware(WebUICSPMiddleware)
    except Exception as _e:
        logger.debug(f"Skipping WebUICSPMiddleware in tests: {_e}")
    # Guard WebUI remote access in tests too (should evaluate loopback as allowed)
    try:
        app.add_middleware(WebUIAccessGuardMiddleware)
    except Exception as _e:
        logger.debug(f"Skipping WebUIAccessGuardMiddleware in tests: {_e}")

    @app.middleware("http")
    async def _trace_headers_middleware(request: Request, call_next):
        from tldw_Server_API.app.core.Metrics.traces import get_tracing_manager
        tm = get_tracing_manager()
        # Ensure request_id is in baggage (RequestIDMiddleware already set it)
        try:
            req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
            if req_id:
                tm.set_baggage("request_id", str(req_id))
        except Exception as _baggage_err:
            logger.debug(f"Trace headers: failed to set baggage request_id: {_baggage_err}")
        response = await call_next(request)
        # Add trace headers to response
        try:
            span = tm.get_current_span()
            if span:
                ctx = span.get_span_context()
                if ctx and getattr(ctx, "is_valid", False):
                    trace_id = f"{ctx.trace_id:032x}"
                    span_id = f"{ctx.span_id:016x}"
                    response.headers.setdefault("X-Trace-Id", trace_id)
                    response.headers.setdefault("traceparent", f"00-{trace_id}-{span_id}-01")
                else:
                    # No active span; synthesize a valid W3C traceparent for tests
                    try:
                        from secrets import token_hex as _th
                        trace_id = _th(16)  # 32 hex chars
                        span_id = _th(8)    # 16 hex chars
                        response.headers.setdefault("X-Trace-Id", trace_id)
                        response.headers.setdefault("traceparent", f"00-{trace_id}-{span_id}-01")
                    except Exception as _synth_err:
                        logger.debug(f"Trace headers: failed to synthesize traceparent: {_synth_err}")
            else:
                # No span; synthesize trace headers
                try:
                    from secrets import token_hex as _th
                    trace_id = _th(16)
                    span_id = _th(8)
                    response.headers.setdefault("X-Trace-Id", trace_id)
                    response.headers.setdefault("traceparent", f"00-{trace_id}-{span_id}-01")
                except Exception as _synth_err2:
                    logger.debug(f"Trace headers: failed to synthesize trace headers (no-span case): {_synth_err2}")
        except Exception as _trace_hdr_err:
            logger.debug(f"Trace headers: middleware error while setting headers: {_trace_hdr_err}")
        return response
else:
    _enable_sec_headers_env = _env_os.getenv("ENABLE_SECURITY_HEADERS")
    _enable_sec_headers = True if (_prod_flag and _enable_sec_headers_env is None) else (
        (_enable_sec_headers_env or "true").lower() in {"true", "1", "yes", "y", "on"}
    )
    # Apply WebUI CSP nonce injection before security headers
    try:
        app.add_middleware(WebUICSPMiddleware)
    except Exception as _e:
        logger.debug(f"Skipping WebUICSPMiddleware: {_e}")
    # Enforce WebUI remote access policy
    try:
        app.add_middleware(WebUIAccessGuardMiddleware)
    except Exception as _e:
        logger.debug(f"Skipping WebUIAccessGuardMiddleware: {_e}")

    if _enable_sec_headers:
        app.add_middleware(SecurityHeadersMiddleware, enabled=True)

    # HTTP request metrics middleware (records count and latency per route)
    app.add_middleware(HTTPMetricsMiddleware)

    # Per-request usage logging (guarded by settings flag)
    app.add_middleware(UsageLoggingMiddleware)

    # Request ID propagation (adds X-Request-ID header)
    app.add_middleware(RequestIDMiddleware)

    # Add trace headers middleware: propagate trace context to HTTP responses
    @app.middleware("http")
    async def _trace_headers_middleware(request: Request, call_next):
        from tldw_Server_API.app.core.Metrics.traces import get_tracing_manager
        tm = get_tracing_manager()
        # Ensure request_id is in baggage (RequestIDMiddleware already set it)
        try:
            req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
            if req_id:
                tm.set_baggage("request_id", str(req_id))
        except Exception:
            pass
        response = await call_next(request)
        # Add trace headers to response
        try:
            span = tm.get_current_span()
            if span:
                ctx = span.get_span_context()
                if ctx and getattr(ctx, "is_valid", False):
                    trace_id = f"{ctx.trace_id:032x}"
                    span_id = f"{ctx.span_id:016x}"
                    response.headers.setdefault("X-Trace-Id", trace_id)
                    response.headers.setdefault("traceparent", f"00-{trace_id}-{span_id}-01")
                else:
                    # No active span; synthesize a valid W3C traceparent
                    try:
                        from secrets import token_hex as _th
                        trace_id = _th(16)
                        span_id = _th(8)
                        response.headers.setdefault("X-Trace-Id", trace_id)
                        response.headers.setdefault("traceparent", f"00-{trace_id}-{span_id}-01")
                    except Exception:
                        pass
            else:
                # No span; synthesize trace headers
                try:
                    from secrets import token_hex as _th
                    trace_id = _th(16)
                    span_id = _th(8)
                    response.headers.setdefault("X-Trace-Id", trace_id)
                    response.headers.setdefault("traceparent", f"00-{trace_id}-{span_id}-01")
                except Exception:
                    pass
        except Exception:
            pass
        return response

# Always apply LLM budget middleware (guarded by settings) even in tests so allowlists/budgets are enforced
try:
    app.add_middleware(LLMBudgetMiddleware)
except Exception as _e:
    logger.debug(f"Skipping LLMBudgetMiddleware: {_e}")

# WebUI serving - Serve the WebUI from the same origin to avoid CORS issues
WEBUI_DIR = BASE_DIR.parent / "WebUI"
if WEBUI_DIR.exists():
    # First, define a dynamic config endpoint for single user mode (registered conditionally below)
    async def get_webui_config():
        """Dynamically generate WebUI configuration with API key in single user mode."""
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings, is_single_user_mode
        from tldw_Server_API.app.api.v1.endpoints.llm_providers import get_configured_providers
        from fastapi.responses import JSONResponse
        from tldw_Server_API.app.core.config import load_comprehensive_config

        config = {
            "apiUrl": "",  # Empty means use same origin
            "apiKey": "",  # Default empty
            "_comment": "Auto-generated configuration"
        }

        # In single user mode, include the API key unless running in production
        import os as _os
        _is_prod_env = _os.getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}
        if is_single_user_mode():
            settings = get_settings()
            config["mode"] = "single-user"
            if not _is_prod_env:
                config["apiKey"] = settings.SINGLE_USER_API_KEY
                config["_comment"] = "Auto-configured for single user mode"
            else:
                # Omit API key in production environment for security
                config["apiKey"] = ""
                config["_comment"] = "Single-user mode (production): API key omitted"
        else:
            config["mode"] = "multi-user"
            config["_comment"] = "Multi-user mode - manual authentication required"
            try:
                from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend as _is_pg_backend
                _is_pg = await _is_pg_backend()
                config.setdefault("auth", {})
                if _is_pg:
                    config["auth"]["multiUserSupportsApiKey"] = False
                    config["auth"]["preferApiKeyInMultiUser"] = False
                else:
                    # Expose hint so the WebUI can prefer X-API-KEY in multi-user SQLite setups
                    config["auth"]["multiUserSupportsApiKey"] = True
                    config["auth"]["preferApiKeyInMultiUser"] = True
            except Exception:
                pass

        # Add LLM providers information
        try:
            providers_info = get_configured_providers()
            config["llm_providers"] = providers_info
        except Exception as e:
            logger.warning(f"Failed to get LLM providers for config: {e}")
            config["llm_providers"] = {"providers": [], "default_provider": "openai", "total_configured": 0}

        # Add chat defaults (e.g., default save_to_db)
        try:
            cfg = load_comprehensive_config()
            chat_cfg = {}
            if cfg and cfg.has_section('Chat-Module'):
                chat_cfg = dict(cfg.items('Chat-Module'))

            def _to_bool(val: str) -> bool:
                return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}

            env_default = _os.getenv('CHAT_SAVE_DEFAULT') or _os.getenv('DEFAULT_CHAT_SAVE')
            default_save = None
            if env_default is not None:
                default_save = _to_bool(env_default)
            elif chat_cfg.get('chat_save_default') or chat_cfg.get('default_save_to_db'):
                default_save = _to_bool(chat_cfg.get('chat_save_default') or chat_cfg.get('default_save_to_db'))
            elif cfg and cfg.has_section('Auto-Save'):
                try:
                    auto_val = cfg.get('Auto-Save', 'save_character_chats', fallback=None)
                    if auto_val is not None:
                        default_save = _to_bool(auto_val)
                except Exception:
                    default_save = None
            if default_save is None:
                default_save = False

            config["chat"] = {"default_save_to_db": default_save}
        except Exception as e:
            logger.warning(f"Failed to compute chat defaults for WebUI config: {e}")

        return JSONResponse(content=config)

    # Gate WebUI static mount and config endpoint
    try:
        if route_enabled("webui"):
            app.add_api_route("/webui/config.json", get_webui_config, include_in_schema=False)
            # Mount the WebUI static files (except config.json which is handled above)
            app.mount("/webui", StaticFiles(directory=str(WEBUI_DIR), html=True), name="webui")
            logger.info(f"WebUI mounted at /webui from {WEBUI_DIR}")
        else:
            logger.info("Route disabled by policy: webui (static + /webui/config.json)")
    except Exception as _webui_rt_err:
        logger.warning(f"Route gating error for webui; mounting by default. Error: {_webui_rt_err}")
        app.add_api_route("/webui/config.json", get_webui_config, include_in_schema=False)
        app.mount("/webui", StaticFiles(directory=str(WEBUI_DIR), html=True), name="webui")
        logger.info(f"WebUI mounted at /webui from {WEBUI_DIR}")
else:
    logger.warning(f"WebUI directory not found at {WEBUI_DIR}")

SETUP_PAGE_PATH = WEBUI_DIR / "setup.html"


async def serve_setup_page():
    """Serve the first-time setup UI when required."""
    try:
        setup_required = needs_setup()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Configuration file missing; cannot render setup UI.")

    if not setup_required:
        return RedirectResponse(url="/webui/", status_code=307)

    if not SETUP_PAGE_PATH.exists():
        raise HTTPException(status_code=404, detail="Setup UI assets missing. Reinstall the WebUI bundle.")

    return FileResponse(SETUP_PAGE_PATH)

# Register setup UI route conditionally
try:
    if route_enabled("setup"):
        app.add_api_route("/setup", serve_setup_page, methods=["GET"], include_in_schema=False, openapi_extra={"security": []})
    else:
        logger.info("Route disabled by policy: setup (UI)")
except Exception as _setup_rt_err:
    logger.warning(f"Route gating error for setup UI; including by default. Error: {_setup_rt_err}")
    app.add_api_route("/setup", serve_setup_page, methods=["GET"], include_in_schema=False, openapi_extra={"security": []})

# Mount project Docs (read-only) for WebUI links, if present
DOCS_DIR = BASE_DIR.parent.parent / "Docs"
if DOCS_DIR.exists():
    app.mount("/docs-static", StaticFiles(directory=str(DOCS_DIR), html=False), name="docs-static")
    logger.info(f"Docs mounted at /docs-static from {DOCS_DIR}")
else:
    logger.warning(f"Docs directory not found at {DOCS_DIR}")

# Favicon serving
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(FAVICON_PATH, media_type="image/x-icon")

@app.get("/", openapi_extra={"security": []})
async def root():
    try:
        if needs_setup():
            try:
                if route_enabled("setup"):
                    return RedirectResponse(url="/setup", status_code=307)
            except Exception:
                pass
    except FileNotFoundError:
        logger.warning("config.txt missing while handling root request; serving default message.")

    return {
        "message": "Welcome to the tldw API; If you're seeing this, the server is running!" "Check out /webui , /docs or /metrics to get started!"
    }

# Metrics endpoint for Prometheus scraping (registered conditionally below)
async def metrics():
    """Prometheus metrics endpoint.

    Exposes both the internal registry (JSON-backed) and the default
    prometheus_client REGISTRY used by embeddings/orchestrator code paths.
    """
    from fastapi.responses import PlainTextResponse
    try:
        from prometheus_client import REGISTRY as PC_REGISTRY, generate_latest as pc_generate_latest
    except Exception:
        PC_REGISTRY = None
        pc_generate_latest = None

    registry = get_metrics_registry()
    combined = registry.export_prometheus_format() or ""
    try:
        if pc_generate_latest and PC_REGISTRY:
            combined = (combined + "\n" + pc_generate_latest(PC_REGISTRY).decode("utf-8")).strip() + "\n"
    except Exception:
        # If prometheus_client is unavailable, ignore
        pass
    return PlainTextResponse(combined, media_type="text/plain; version=0.0.4")

# OpenTelemetry metrics endpoint (if using OTLP) - registered conditionally below
@track_metrics(labels={"endpoint": "metrics"})
async def api_metrics():
    """Get current metrics in JSON format."""
    registry = get_metrics_registry()
    return registry.get_all_metrics()

# Router for health monitoring endpoints (NEW)
if _MINIMAL_TEST_APP:
    # Minimal set for paper_search tests
    app.include_router(research_router, prefix=f"{API_V1_PREFIX}/research", tags=["research"])
    app.include_router(paper_search_router, prefix=f"{API_V1_PREFIX}/paper-search", tags=["paper-search"])
    # Include lightweight chat/character routes needed by tests
    app.include_router(chat_router, prefix=f"{API_V1_PREFIX}/chat")
    app.include_router(character_router, prefix=f"{API_V1_PREFIX}/characters", tags=["characters"])
    app.include_router(character_chat_sessions_router, prefix=f"{API_V1_PREFIX}/chats", tags=["character-chat-sessions"])
    app.include_router(character_messages_router, prefix=f"{API_V1_PREFIX}", tags=["character-messages"])
    # Include Jobs admin endpoints for tests that exercise jobs stats/counters
    try:
        from tldw_Server_API.app.api.v1.endpoints.jobs_admin import router as jobs_admin_router
        app.include_router(jobs_admin_router, prefix=f"{API_V1_PREFIX}", tags=["jobs"])
    except Exception as _e:
        logger.debug(f"Skipping jobs_admin router in minimal test app: {_e}")
    # AuthNZ debug routes for tests
    try:
        from tldw_Server_API.app.api.v1.endpoints.authnz_debug import router as authnz_debug_router
        app.include_router(authnz_debug_router, prefix=f"{API_V1_PREFIX}", tags=["authnz-debug"])
    except Exception as _e:
        logger.debug(f"Skipping authnz_debug router in tests: {_e}")
    # Sandbox (scaffold) - include in minimal test app to support sandbox tests
    try:
        from tldw_Server_API.app.api.v1.endpoints.sandbox import router as sandbox_router
        app.include_router(sandbox_router, prefix=f"{API_V1_PREFIX}", tags=["sandbox"])
    except Exception as _sandbox_err:
        # Never let optional sandbox break startup in tests
        logger.debug(f"Skipping sandbox router in minimal test app: {_sandbox_err}")
else:
    # Small helper to guard route inclusion via config.txt and ENV
    def _include_if_enabled(route_key: str, router, *, prefix: str = "", tags: list | None = None, default_stable: bool = True) -> None:
        try:
            if route_enabled(route_key, default_stable=default_stable):
                app.include_router(router, prefix=prefix, tags=tags)
            else:
                logger.info(f"Route disabled by policy: {route_key}")
        except Exception as _rt_err:  # noqa: BLE001
            logger.warning(f"Route gating error for {route_key}; including by default. Error: {_rt_err}")
            app.include_router(router, prefix=prefix, tags=tags)
    try:
        from tldw_Server_API.app.api.v1.endpoints.health import router as health_router
        _HAS_HEALTH = True
    except Exception as _health_import_err:  # noqa: BLE001
        logger.warning(f"Health endpoints unavailable; skipping import: {_health_import_err}")
        _HAS_HEALTH = False
    from tldw_Server_API.app.api.v1.endpoints.moderation import router as moderation_router
    from tldw_Server_API.app.api.v1.endpoints.monitoring import router as monitoring_router
    if _HAS_HEALTH:
        _include_if_enabled("health", health_router, prefix=f"{API_V1_PREFIX}", tags=["health"])  # /api/v1/healthz, /api/v1/readyz
        _include_if_enabled("health", health_router, prefix="", tags=["health"])  # /healthz, /readyz
    _include_if_enabled("moderation", moderation_router, prefix=f"{API_V1_PREFIX}", tags=["moderation"])
    _include_if_enabled("monitoring", monitoring_router, prefix=f"{API_V1_PREFIX}", tags=["monitoring"])
    from tldw_Server_API.app.api.v1.endpoints.audit import router as audit_router
    _include_if_enabled("audit", audit_router, prefix=f"{API_V1_PREFIX}", tags=["audit"])
    _include_if_enabled("auth", auth_router, prefix=f"{API_V1_PREFIX}", tags=["authentication"])
    if _HAS_AUTH_ENHANCED:
        _include_if_enabled("auth-enhanced", auth_enhanced_router, prefix=f"{API_V1_PREFIX}", tags=["authentication-enhanced"])
    _include_if_enabled("users", users_router, prefix=f"{API_V1_PREFIX}", tags=["users"])

    # Include AuthNZ debug endpoints once via the gated path.
    # Force-enable when _TEST_MODE is true; otherwise respect route policy.
    try:
        from tldw_Server_API.app.api.v1.endpoints.authnz_debug import router as authnz_debug_router
        _include_if_enabled(
            "authnz-debug",
            authnz_debug_router,
            prefix=f"{API_V1_PREFIX}",
            tags=["authnz-debug"],
            default_stable=True if _TEST_MODE else False,
        )
    except Exception as _e:
        logger.debug(f"Skipping authnz_debug router: {_e}")
    _include_if_enabled("privileges", privileges_router, prefix=f"{API_V1_PREFIX}", tags=["privileges"])
    from tldw_Server_API.app.api.v1.endpoints.admin import router as admin_router
    from tldw_Server_API.app.api.v1.endpoints.mcp_catalogs_manage import router as mcp_catalogs_manage_router
    _include_if_enabled("admin", admin_router, prefix=f"{API_V1_PREFIX}", tags=["admin"])
    _include_if_enabled("mcp-catalogs", mcp_catalogs_manage_router, prefix=f"{API_V1_PREFIX}")
    if _HAS_MEDIA:
        _include_if_enabled("media", media_router, prefix=f"{API_V1_PREFIX}/media", tags=["media"])
    if _HAS_AUDIO:
        _include_if_enabled("audio", audio_router, prefix=f"{API_V1_PREFIX}/audio", tags=["audio"])
    if _HAS_AUDIO_JOBS:
        _include_if_enabled("audio-jobs", audio_jobs_router, prefix=f"{API_V1_PREFIX}/audio", tags=["audio-jobs"])
    if _HAS_AUDIO:
        _include_if_enabled("audio-websocket", audio_ws_router, prefix=f"{API_V1_PREFIX}/audio", tags=["audio-websocket"])
    _include_if_enabled("chat", chat_router, prefix=f"{API_V1_PREFIX}/chat")
    # Tools (MCP-backed server tool execution) - include if initial guarded import succeeded
    if 'tools_router' in locals() and tools_router is not None:
        _include_if_enabled("tools", tools_router, prefix=f"{API_V1_PREFIX}", tags=["tools"], default_stable=False)
    _include_if_enabled("characters", character_router, prefix=f"{API_V1_PREFIX}/characters", tags=["characters"])
    _include_if_enabled("character-chat-sessions", character_chat_sessions_router, prefix=f"{API_V1_PREFIX}/chats", tags=["character-chat-sessions"])
    _include_if_enabled("character-messages", character_messages_router, prefix=f"{API_V1_PREFIX}", tags=["character-messages"])
    _include_if_enabled("metrics", metrics_router, prefix=f"{API_V1_PREFIX}", tags=["metrics"])
    _include_if_enabled("chunking", chunking_router, prefix=f"{API_V1_PREFIX}/chunking", tags=["chunking"])
    _include_if_enabled("chunking-templates", chunking_templates_router, prefix=f"{API_V1_PREFIX}", tags=["chunking-templates"])
    if _HAS_OUTPUT_TEMPLATES:
        _include_if_enabled("outputs-templates", outputs_templates_router, prefix=f"{API_V1_PREFIX}", tags=["outputs-templates"])
    try:
        # Optional outputs artifacts endpoint
        from tldw_Server_API.app.api.v1.endpoints.outputs import router as _outputs_router
        _include_if_enabled("outputs", _outputs_router, prefix=f"{API_V1_PREFIX}", tags=["outputs"])
    except Exception as _e:
        logger.warning(f"Outputs endpoint not available: {_e}")
    _include_if_enabled("embeddings", embeddings_router, prefix=f"{API_V1_PREFIX}", tags=["embeddings"])
    _include_if_enabled("vector-stores", vector_stores_router, prefix=f"{API_V1_PREFIX}", tags=["vector-stores"])
    # External connectors (Drive/Notion) scaffold
    try:
        from tldw_Server_API.app.api.v1.endpoints.connectors import router as connectors_router
        _include_if_enabled("connectors", connectors_router, prefix=f"{API_V1_PREFIX}", tags=["connectors"], default_stable=False)
    except Exception as _conn_e:
        logger.warning(f"Connectors endpoints unavailable; skipping import: {_conn_e}")
    _include_if_enabled("claims", claims_router, prefix=f"{API_V1_PREFIX}")
    _include_if_enabled("media-embeddings", media_embeddings_router, prefix=f"{API_V1_PREFIX}", tags=["media-embeddings"])
    try:
        # Unified items endpoint
        from tldw_Server_API.app.api.v1.endpoints.items import router as _items_router
        _include_if_enabled("items", _items_router, prefix=f"{API_V1_PREFIX}", tags=["items"])
    except Exception as _e:
        logger.warning(f"Items endpoint not available: {_e}")
    try:
        from tldw_Server_API.app.api.v1.endpoints.reading import router as _reading_router
        _include_if_enabled("reading", _reading_router, prefix=f"{API_V1_PREFIX}", tags=["reading"])
    except Exception as _e:
        logger.warning(f"Reading endpoint not available: {_e}")
    # Watchlists endpoints (sources/groups/tags/jobs/runs)
    try:
        from tldw_Server_API.app.api.v1.endpoints.watchlists import router as _watchlists_router
        _include_if_enabled("watchlists", _watchlists_router, prefix=f"{API_V1_PREFIX}", tags=["watchlists"])
    except Exception as _e:
        logger.warning(f"Watchlists endpoint not available: {_e}")
    # Legacy subscriptions API deprecation shim (returns 410 with replacement link)
    try:
        from tldw_Server_API.app.api.v1.endpoints.subscriptions_legacy import router as _subs_legacy_router
        _include_if_enabled("subscriptions-deprecated", _subs_legacy_router, prefix=f"{API_V1_PREFIX}", tags=["subscriptions-deprecated"])
    except Exception as _e:
        logger.warning(f"Legacy subscriptions shim not available: {_e}")
    _include_if_enabled("notes", notes_router, prefix=f"{API_V1_PREFIX}/notes", tags=["notes"])
    _include_if_enabled("prompts", prompt_router, prefix=f"{API_V1_PREFIX}/prompts", tags=["prompts"])
    if _HAS_READING_HIGHLIGHTS:
        _include_if_enabled("reading-highlights", reading_highlights_router, prefix=f"{API_V1_PREFIX}", tags=["reading-highlights"])
    if _HAS_PROMPT_STUDIO:
        _include_if_enabled("prompt-studio", prompt_studio_projects_router, tags=["prompt-studio"])
        _include_if_enabled("prompt-studio", prompt_studio_prompts_router, tags=["prompt-studio"])
        _include_if_enabled("prompt-studio", prompt_studio_test_cases_router, tags=["prompt-studio"])
        _include_if_enabled("prompt-studio", prompt_studio_optimization_router, tags=["prompt-studio"])
        _include_if_enabled("prompt-studio", prompt_studio_status_router, tags=["prompt-studio"])
        _include_if_enabled("prompt-studio", prompt_studio_evaluations_router, tags=["prompt-studio"])
        _include_if_enabled("prompt-studio", prompt_studio_websocket_router, tags=["prompt-studio"])
    _include_if_enabled("rag-health", rag_health_router, tags=["rag-health"])
    _include_if_enabled("rag-unified", rag_unified_router, tags=["rag-unified"])
    if _HAS_WORKFLOWS:
        _include_if_enabled("workflows", workflows_router, tags=["workflows"], default_stable=False)
    try:
        from tldw_Server_API.app.api.v1.endpoints.scheduler_workflows import router as scheduler_workflows_router
        _HAS_SCHEDULER_WF = True
    except Exception as _sch_import_err:  # noqa: BLE001
        logger.warning(f"Scheduler Workflows endpoints unavailable; skipping import: {_sch_import_err}")
        _HAS_SCHEDULER_WF = False
    if _HAS_SCHEDULER_WF:
        _include_if_enabled("scheduler", scheduler_workflows_router, tags=["scheduler"], default_stable=False)
    _include_if_enabled("research", research_router, prefix=f"{API_V1_PREFIX}/research", tags=["research"])
    _include_if_enabled("paper-search", paper_search_router, prefix=f"{API_V1_PREFIX}/paper-search", tags=["paper-search"])
    if _HAS_UNIFIED_EVALUATIONS:
        _include_if_enabled("evaluations", unified_evaluation_router, prefix=f"{API_V1_PREFIX}", tags=["evaluations"])
    _include_if_enabled("ocr", ocr_router, prefix=f"{API_V1_PREFIX}", tags=["ocr"])
    _include_if_enabled("vlm", vlm_router, prefix=f"{API_V1_PREFIX}", tags=["vlm"])
    _include_if_enabled("benchmarks", benchmark_router, prefix=f"{API_V1_PREFIX}", tags=["benchmarks"], default_stable=False)
    from tldw_Server_API.app.api.v1.endpoints.config_info import router as config_info_router
    try:
        from tldw_Server_API.app.api.v1.endpoints.jobs_admin import router as jobs_admin_router
        _HAS_JOBS_ADMIN = True
    except Exception as _e:
        _HAS_JOBS_ADMIN = False
        try:
            from loguru import logger as _logger
            _logger.warning(f"Skipping jobs_admin router due to import error: {_e}")
        except Exception:
            pass
    _include_if_enabled("setup", setup_router, prefix=f"{API_V1_PREFIX}", tags=["setup"])
    _include_if_enabled("config", config_info_router, prefix=f"{API_V1_PREFIX}", tags=["config"])
    if _HAS_JOBS_ADMIN:
        if _TEST_MODE:
            # In tests, include Jobs admin endpoints unconditionally to avoid
            # config-based gating interfering with unit tests that rely on them.
            app.include_router(jobs_admin_router, prefix=f"{API_V1_PREFIX}", tags=["jobs"])
        else:
            _include_if_enabled(
                "jobs",
                jobs_admin_router,
                prefix=f"{API_V1_PREFIX}",
                tags=["jobs"],
                default_stable=False,
            )
    _include_if_enabled("sync", sync_router, prefix=f"{API_V1_PREFIX}/sync", tags=["sync"])
    # Tools router included above with prefix f"{API_V1_PREFIX}"; avoid duplicate nested path
    # Sandbox (scaffold)
    if _HAS_SANDBOX:
        if _TEST_MODE:
            # In tests, force-include sandbox endpoints regardless of route policy
            app.include_router(sandbox_router, prefix=f"{API_V1_PREFIX}", tags=["sandbox"])
        else:
            _include_if_enabled("sandbox", sandbox_router, prefix=f"{API_V1_PREFIX}", tags=["sandbox"], default_stable=False)
    # Flashcards are now considered stable; include by default unless disabled
    _include_if_enabled("flashcards", flashcards_router, prefix=f"{API_V1_PREFIX}", tags=["flashcards"], default_stable=True)
    from tldw_Server_API.app.api.v1.endpoints.personalization import (router as personalization_router,)
    from tldw_Server_API.app.api.v1.endpoints.persona import (router as persona_router,)
    _include_if_enabled("personalization", personalization_router, prefix=f"{API_V1_PREFIX}/personalization", tags=["personalization"], default_stable=False)
    _include_if_enabled("persona", persona_router, prefix=f"{API_V1_PREFIX}/persona", tags=["persona"], default_stable=False)
    _include_if_enabled("mcp-unified", mcp_unified_router, prefix=f"{API_V1_PREFIX}", tags=["mcp-unified"])
    _include_if_enabled("chatbooks", chatbooks_router, prefix=f"{API_V1_PREFIX}", tags=["chatbooks"])
    _include_if_enabled("llm", llm_providers_router, prefix=f"{API_V1_PREFIX}", tags=["llm"])
    _include_if_enabled("llamacpp", llamacpp_router, prefix=f"{API_V1_PREFIX}", tags=["llamacpp"])
    _include_if_enabled("llamacpp", llamacpp_public_router, prefix="", tags=["llamacpp"])
    _include_if_enabled("web-scraping", web_scraping_router, tags=["web-scraping"])
    _include_if_enabled("web-scraping", web_scraping_router, prefix=f"{API_V1_PREFIX}", tags=["web-scraping"])

# Register control-plane metrics endpoints (works in both minimal and full modes)
try:
    if route_enabled("metrics"):
        app.add_api_route("/metrics", metrics, include_in_schema=False)
        app.add_api_route(f"{API_V1_PREFIX}/metrics", api_metrics, methods=["GET"], tags=["monitoring"])
    else:
        logger.info("Route disabled by policy: metrics")
except Exception as _metrics_rt_err:
    logger.warning(f"Route gating error for metrics; including by default. Error: {_metrics_rt_err}")
    app.add_api_route("/metrics", metrics, include_in_schema=False)
    app.add_api_route(f"{API_V1_PREFIX}/metrics", api_metrics, methods=["GET"], tags=["monitoring"])

# Router for trash endpoints - deletion of media items / trash file handling (FIXME: Secure delete vs lag on delete?)
#app.include_router(trash_router, prefix=f"{API_V1_PREFIX}/trash", tags=["trash"])

# Router for authentication endpoint
#app.include_router(auth_router, prefix=f"{API_V1_PREFIX}/auth", tags=["auth"])
# The docs at http://localhost:8000/docs will show an “Authorize” button. You can log in by calling POST /api/v1/auth/login with a form that includes username and password. The docs interface is automatically aware because we used OAuth2PasswordBearer.

# Health check (registered conditionally below)
async def health_check():
    return {"status": "healthy"}

# Readiness check (verifies critical dependencies) - registered conditionally below
async def readiness_check():
    """Readiness probe for orchestrators and load balancers."""
    try:
        # Early flip: when shutting down, report not ready immediately
        if not READINESS_STATE.get("ready", True):
            return {"status": "not_ready", "reason": "shutdown_in_progress"}
        # Engine stats
        try:
            from tldw_Server_API.app.core.Workflows.engine import WorkflowScheduler as _WS
            engine_stats = _WS.instance().stats()
        except Exception:
            engine_stats = {"queue_depth": None, "active_tenants": None, "active_workflows": None}

        # DB health (AuthNZ pool basic health for API; Workflows DB schema check below)
        from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
        db_pool = await get_db_pool()
        db_health = await db_pool.health_check()

        # Workflows backend schema check
        try:
            from tldw_Server_API.app.core.DB_Management.DB_Manager import create_workflows_database, get_content_backend_instance
            from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase as _WDB
            backend = get_content_backend_instance()
            wdb: _WDB = create_workflows_database(backend=backend)
            if wdb._using_backend():
                with wdb.backend.transaction() as conn:  # type: ignore[union-attr]
                    try:
                        wf_schema_version = int(wdb._get_backend_schema_version(conn))  # type: ignore[attr-defined]
                        wf_expected_version = int(wdb._CURRENT_SCHEMA_VERSION)  # type: ignore[attr-defined]
                    except Exception:
                        wf_schema_version = None
                        wf_expected_version = None
            else:
                wf_schema_version = None
                wf_expected_version = None
        except Exception:
            wf_schema_version = None
            wf_expected_version = None

        # Provider manager health (if initialized)
        try:
            from tldw_Server_API.app.core.Chat.provider_manager import get_provider_manager
            pm = get_provider_manager()
            provider_health = pm.get_health_report() if pm else {}
            providers_ok = pm is not None
        except Exception:
            provider_health = {}
            providers_ok = False

        # OTEL status
        from tldw_Server_API.app.core.Metrics import OTEL_AVAILABLE

        ready = (db_health.get("status") == "healthy")
        # If workflows backend reports schema version, ensure it matches expected
        if wf_schema_version is not None and wf_expected_version is not None:
            ready = ready and (wf_schema_version == wf_expected_version)
        body = {
            "status": "ready" if ready else "not_ready",
            "database": db_health,
            "workflows_db": {
                "schema_version": wf_schema_version,
                "expected_version": wf_expected_version,
            },
            "engine": engine_stats,
            "providers_initialized": providers_ok,
            "provider_health": provider_health,
            "otel_available": bool(OTEL_AVAILABLE),
        }
        from fastapi.responses import JSONResponse as _JR
        return _JR(body, status_code=(200 if ready else 503))
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}

# /health/ready alias for some orchestrators (registered conditionally below)
async def readiness_alias():
    return await readiness_check()

# Register control-plane health endpoints (works in both minimal and full modes)
try:
    if route_enabled("health"):
        app.add_api_route("/health", health_check, methods=["GET"], openapi_extra={"security": []})
        app.add_api_route("/ready", readiness_check, methods=["GET"], openapi_extra={"security": []})
        app.add_api_route("/health/ready", readiness_alias, methods=["GET"], openapi_extra={"security": []})
    else:
        logger.info("Route disabled by policy: health (/health, /ready, /health/ready)")
except Exception as _health_rt_err:
    logger.warning(f"Route gating error for health; including by default. Error: {_health_rt_err}")
    app.add_api_route("/health", health_check, methods=["GET"], openapi_extra={"security": []})
    app.add_api_route("/ready", readiness_check, methods=["GET"], openapi_extra={"security": []})
    app.add_api_route("/health/ready", readiness_alias, methods=["GET"], openapi_extra={"security": []})

#
## Entry point for running the server
########################################################################################################################
def run_server():
    """Run the FastAPI server using uvicorn."""
    import uvicorn
    uvicorn.run(
        "tldw_Server_API.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    run_server()

#
## End of main.py
########################################################################################################################
