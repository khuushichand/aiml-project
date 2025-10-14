# main.py
# Description: This file contains the main FastAPI application, which serves as the primary API for the tldw application.
#
# Imports
import logging
import asyncio
#
# 3rd-party Libraries
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from loguru import logger
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles
#
# Local Imports
#
# Auth Endpoint (NEW)
from tldw_Server_API.app.api.v1.endpoints.auth import router as auth_router
#
# Audio Endpoint (includes WebSocket streaming transcription)
from tldw_Server_API.app.api.v1.endpoints.audio import router as audio_router, ws_router as audio_ws_router
#
# Chat Endpoint
from tldw_Server_API.app.api.v1.endpoints.chat import router as chat_router
#
# Character Endpoint
from tldw_Server_API.app.api.v1.endpoints.characters_endpoint import router as character_router
# Character Chat Sessions Endpoint
from tldw_Server_API.app.api.v1.endpoints.character_chat_sessions import router as character_chat_sessions_router
# Character Messages Endpoint
from tldw_Server_API.app.api.v1.endpoints.character_messages import router as character_messages_router
#
# Metrics Endpoint
from tldw_Server_API.app.api.v1.endpoints.metrics import router as metrics_router
#
# Chunking Endpoints
from tldw_Server_API.app.api.v1.endpoints.chunking import chunking_router as chunking_router
from tldw_Server_API.app.api.v1.endpoints.chunking_templates import router as chunking_templates_router
#
# Embedding Endpoint (v5 enhanced version with circuit breaker)
from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import router as embeddings_router
from tldw_Server_API.app.api.v1.endpoints.vector_stores_openai import router as vector_stores_router
from tldw_Server_API.app.api.v1.endpoints.claims import router as claims_router
#
# Media Endpoint (guarded import; not critical for unrelated tests)
try:
    from tldw_Server_API.app.api.v1.endpoints.media import router as media_router
    _HAS_MEDIA = True
except Exception as _media_import_err:  # noqa: BLE001 - log and continue for deterministic test startup
    logger.warning(f"Media endpoints unavailable; skipping import: {_media_import_err}")
    _HAS_MEDIA = False
# Media Embeddings Endpoint (for generating embeddings for uploaded media)
from tldw_Server_API.app.api.v1.endpoints.media_embeddings import router as media_embeddings_router
#
# Notes Endpoint
from tldw_Server_API.app.api.v1.endpoints.notes import router as notes_router
#
# Prompt Management Endpoint
from tldw_Server_API.app.api.v1.endpoints.prompts import router as prompt_router
#
# Prompt Studio Endpoints
try:
    from tldw_Server_API.app.api.v1.endpoints.prompt_studio_projects import router as prompt_studio_projects_router
    from tldw_Server_API.app.api.v1.endpoints.prompt_studio_prompts import router as prompt_studio_prompts_router
    from tldw_Server_API.app.api.v1.endpoints.prompt_studio_test_cases import router as prompt_studio_test_cases_router
    from tldw_Server_API.app.api.v1.endpoints.prompt_studio_optimization import router as prompt_studio_optimization_router
    from tldw_Server_API.app.api.v1.endpoints.prompt_studio_status import router as prompt_studio_status_router
    from tldw_Server_API.app.api.v1.endpoints.prompt_studio_websocket import router as prompt_studio_websocket_router
    from tldw_Server_API.app.api.v1.endpoints.prompt_studio_evaluations import router as prompt_studio_evaluations_router
    _HAS_PROMPT_STUDIO = True
except Exception as _ps_import_err:  # noqa: BLE001 - log and continue, not critical for unrelated tests
    logger.warning(f"Prompt Studio endpoints unavailable; skipping import: {_ps_import_err}")
    _HAS_PROMPT_STUDIO = False
#
# RAG Endpoints
from tldw_Server_API.app.api.v1.endpoints.rag_health import router as rag_health_router  # RAG health/caching/metrics endpoints
from tldw_Server_API.app.api.v1.endpoints.rag_unified import router as rag_unified_router  # Unified RAG API with all features as parameters
from tldw_Server_API.app.api.v1.endpoints.workflows import router as workflows_router
# Legacy RAG Endpoint (Deprecated)
# from tldw_Server_API.app.api.v1.endpoints.rag import router as retrieval_agent_router
#
# Research Endpoint
from tldw_Server_API.app.api.v1.endpoints.research import router as research_router
# Paper Search Endpoint (provider-specific)
from tldw_Server_API.app.api.v1.endpoints.paper_search import router as paper_search_router
#
# Evaluation Endpoint (OLD - to be removed)
# Legacy evaluation endpoint - replaced by unified router
# from tldw_Server_API.app.api.v1.endpoints.evals import router as evaluation_router
#
# OpenAI-compatible Evaluation Endpoint (NEW)
# Legacy OpenAI evaluation endpoint - replaced by unified router
# from tldw_Server_API.app.api.v1.endpoints.evals_openai import router as openai_evals_router

# Unified Evaluation endpoint (guarded; can be heavy and optional in some test contexts)
try:
    from tldw_Server_API.app.api.v1.endpoints.evaluations_unified import router as unified_evaluation_router
    _HAS_UNIFIED_EVALUATIONS = True
except Exception as _evals_import_err:  # noqa: BLE001 - log and continue for deterministic test startup
    logger.warning(f"Unified Evaluation endpoints unavailable; skipping import: {_evals_import_err}")
    _HAS_UNIFIED_EVALUATIONS = False
from tldw_Server_API.app.api.v1.endpoints.ocr import router as ocr_router
from tldw_Server_API.app.api.v1.endpoints.vlm import router as vlm_router
#
# Benchmark Endpoint
from tldw_Server_API.app.api.v1.endpoints.benchmark_api import router as benchmark_router
#
# Sync Endpoint
from tldw_Server_API.app.api.v1.endpoints.sync import router as sync_router
#
# Tools Endpoint
from tldw_Server_API.app.api.v1.endpoints.tools import router as tools_router
#
# Users Endpoint (NEW)
from tldw_Server_API.app.api.v1.endpoints.users import router as users_router
## Trash Endpoint
#from tldw_Server_API.app.api.v1.endpoints.trash import router as trash_router
#
# MCP Unified Endpoint (Production-ready, secure implementation)
from tldw_Server_API.app.api.v1.endpoints.mcp_unified_endpoint import router as mcp_unified_router
# Note: Old MCP endpoints have been archived due to security vulnerabilities
#
# Chatbooks Endpoint
from tldw_Server_API.app.api.v1.endpoints.chatbooks import router as chatbooks_router
#
# Flashcards Endpoint (V5 - ChaChaNotes)
from tldw_Server_API.app.api.v1.endpoints.flashcards import router as flashcards_router
#
# LLM Providers Endpoint
from tldw_Server_API.app.api.v1.endpoints.llm_providers import router as llm_providers_router
from tldw_Server_API.app.api.v1.endpoints.llamacpp import router as llamacpp_router, public_router as llamacpp_public_router
from tldw_Server_API.app.api.v1.endpoints.setup import router as setup_router
# Web Scraping Management Endpoints
from tldw_Server_API.app.api.v1.endpoints.web_scraping import router as web_scraping_router
#
# Metrics and Telemetry
from tldw_Server_API.app.core.Metrics import (
    initialize_telemetry,
    shutdown_telemetry,
    get_metrics_registry,
    track_metrics,
    OTEL_AVAILABLE
)
#
from tldw_Server_API.app.core.Evaluations.evaluation_manager import get_cached_evaluation_manager
from tldw_Server_API.app.core.Setup.setup_manager import needs_setup
from tldw_Server_API.app.core.AuthNZ.initialize import ensure_single_user_rbac_seed_if_needed
#
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
#
########################################################################################################################
#
# Functions:


# --- Loguru Configuration with Intercept Handler ---

# Define a handler class to intercept standard logging messages
class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

# Remove default handler
logger.remove()

# Add your desired Loguru sink (e.g., stderr)
log_level = "DEBUG"
logger.add(
    sys.stderr,
    level=log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
)

# Configure standard logging to use the InterceptHandler
loggers_to_intercept = ["uvicorn", "uvicorn.error", "uvicorn.access"] # Add other library names if needed
for logger_name in loggers_to_intercept:
    mod_logger = logging.getLogger(logger_name)
    mod_logger.handlers = [InterceptHandler()]
    mod_logger.propagate = False # Prevent messages from reaching the root logger
    # Optionally set level if you only want certain levels from that lib
    # mod_logger.setLevel(logging.DEBUG)

logger.info("Loguru logger configured with SPECIFIC standard logging interception!")


BASE_DIR     = Path(__file__).resolve().parent
FAVICON_PATH = BASE_DIR / "static" / "favicon.ico"

############################# TEST DB Handling #####################################
# --- TEST DB Instance ---
test_db_instance_ref = None # Global or context variable to hold the test DB instance

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Test-aware flag to optionally skip heavy startup subsystems in tests
    import os as _startup_os
    _is_test_mode = _startup_os.getenv("TEST_MODE", "").lower() == "true"
    _disable_heavy_startup = _startup_os.getenv("DISABLE_HEAVY_STARTUP", "").lower() in {"1", "true", "yes", "on"}
    _skip_heavy = _is_test_mode or _disable_heavy_startup
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

        # Ensure SQLite AuthNZ schema (including RBAC) is migrated to latest
        try:
            if getattr(db_pool, 'pool', None) is None and getattr(db_pool, 'db_path', None):
                from pathlib import Path as _Path
                from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables as _ensure_authnz
                _ensure_authnz(_Path(db_pool.db_path))
                logger.info("App Startup: Ensured AuthNZ migrations (SQLite)")
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
    except Exception as e:
        logger.error(f"App Startup: Failed to initialize auth services: {e}")
        # Continue startup even if auth services fail (for backward compatibility)
    
    # Initialize MCP Unified Server (secure, production-ready)
    if _skip_heavy:
        logger.info("Test mode/heavy-startup disabled: Skipping MCP Unified server initialization")
    else:
        logger.info("App Startup: Initializing MCP Unified server...")
        try:
            from tldw_Server_API.app.core.MCP_unified import get_mcp_server
            mcp_server = get_mcp_server()
            await mcp_server.initialize()
            logger.info("App Startup: MCP Unified server initialized successfully")
        except Exception as e:
            logger.error(f"App Startup: Failed to initialize MCP Unified server: {e}")
            logger.warning("Ensure MCP_JWT_SECRET and MCP_API_KEY_SALT environment variables are set")
            # Continue startup even if MCP fails (for backward compatibility)
    
    # Initialize Chat Module Components
    if _skip_heavy:
        logger.info("Test mode/heavy-startup disabled: Skipping Chat provider manager and request queue initialization")
    else:
        logger.info("App Startup: Initializing Chat module components...")
        
        # Initialize Provider Manager
        try:
            from tldw_Server_API.app.core.Chat.provider_manager import initialize_provider_manager
            # Seed from authoritative provider configuration to avoid drift
            from tldw_Server_API.app.core.Chat.provider_config import API_CALL_HANDLERS as PROVIDER_API_CALL_HANDLERS

            # Get list of configured providers (authoritative mapping)
            providers = list(PROVIDER_API_CALL_HANDLERS.keys())
            provider_manager = initialize_provider_manager(providers, primary_provider=providers[0] if providers else None)
            await provider_manager.start_health_checks()
            logger.info(f"App Startup: Provider manager initialized with {len(providers)} providers")
        except Exception as e:
            logger.error(f"App Startup: Failed to initialize provider manager: {e}")
        
        # Initialize Request Queue
        try:
            from tldw_Server_API.app.core.Chat.request_queue import initialize_request_queue
            from tldw_Server_API.app.core.config import load_comprehensive_config
            
            config = load_comprehensive_config()
            chat_config = {}
            if config and config.has_section('Chat-Module'):
                chat_config = dict(config.items('Chat-Module'))
            
            request_queue = initialize_request_queue(
                max_queue_size=int(chat_config.get('max_queue_size', 100)),
                max_concurrent=int(chat_config.get('max_concurrent_requests', 10)),
                global_rate_limit=int(chat_config.get('rate_limit_per_minute', 60)),
                per_client_rate_limit=int(chat_config.get('rate_limit_per_conversation_per_minute', 20))
            )
            await request_queue.start(num_workers=4)
            logger.info("App Startup: Request queue initialized with 4 workers")
        except Exception as e:
            logger.error(f"App Startup: Failed to initialize request queue: {e}")
    
    # Initialize Rate Limiter
    try:
        from tldw_Server_API.app.core.Chat.rate_limiter import initialize_rate_limiter, RateLimitConfig
        
        rate_config = RateLimitConfig(
            global_rpm=int(chat_config.get('rate_limit_per_minute', 60)),
            per_user_rpm=int(chat_config.get('rate_limit_per_user_per_minute', 20)),
            per_conversation_rpm=int(chat_config.get('rate_limit_per_conversation_per_minute', 10)),
            per_user_tokens_per_minute=int(chat_config.get('rate_limit_tokens_per_minute', 10000))
        )
        rate_limiter = initialize_rate_limiter(rate_config)
        logger.info("App Startup: Rate limiter initialized")
    except Exception as e:
        logger.error(f"App Startup: Failed to initialize rate limiter: {e}")
    
    # Initialize TTS Service
    if _skip_heavy:
        logger.info("Test mode/heavy-startup disabled: Skipping TTS service initialization")
    else:
        logger.info("App Startup: Initializing TTS service...")
        try:
            from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
            from tldw_Server_API.app.core.config import load_comprehensive_config_with_tts
            
            # Load comprehensive config and extract TTS config dict
            cfg_obj = load_comprehensive_config_with_tts()
            tts_cfg_dict = cfg_obj.get_tts_config() if hasattr(cfg_obj, 'get_tts_config') else None
            
            # Initialize the TTS service with configuration (falls back to internal loader if None)
            await get_tts_service_v2(config=tts_cfg_dict)
            logger.info("App Startup: TTS service initialized successfully")
        except Exception as e:
            logger.error(f"App Startup: Failed to initialize TTS service: {e}")
            logger.warning("TTS functionality will be unavailable")
            # Continue startup even if TTS fails (for backward compatibility)
    
    # Initialize Chunking Templates
    if _skip_heavy:
        logger.info("Test mode/heavy-startup disabled: Skipping chunking template initialization")
    else:
        logger.info("App Startup: Initializing chunking templates...")
        try:
            from tldw_Server_API.app.core.Chunking.template_initialization import ensure_templates_initialized
            
            if ensure_templates_initialized():
                logger.info("App Startup: Chunking templates initialized successfully")
            else:
                logger.warning("App Startup: Chunking templates initialization incomplete")
        except Exception as e:
            logger.error(f"App Startup: Failed to initialize chunking templates: {e}")
            # Continue startup even if template initialization fails
    
    # Note: Audit service now uses dependency injection
    # No need to initialize globally - use get_audit_service_for_user dependency in endpoints
    logger.info("App Startup: Audit service available via dependency injection")

    # Start background workers: ephemeral collections cleanup, core Jobs (chatbooks), claims rebuild
    cleanup_task = None
    core_jobs_task = None
    claims_task = None
    jobs_metrics_task = None
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.core.DB_Management.DB_Manager import (
            create_evaluations_database as _create_evals_db,
        )
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths as _DBP
        from tldw_Server_API.app.core.RAG.rag_service.vector_stores import VectorStoreFactory as _VSF
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
            adapter = _VSF.create_from_settings(_app_settings, user_id=str(_app_settings.get("SINGLE_USER_FIXED_ID", "1")))
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

        if _skip_heavy:
            logger.info("Test mode/heavy-startup disabled: Skipping ephemeral cleanup worker")
        else:
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
        if _skip_heavy:
            logger.info("Test mode/heavy-startup disabled: Skipping core Jobs worker (Chatbooks)")
        else:
            if _is_core and _core_worker_enabled:
                core_jobs_stop_event = _asyncio.Event()
                core_jobs_task = _asyncio.create_task(_run_cb_jobs(core_jobs_stop_event))
                logger.info("Core Jobs worker (Chatbooks) started with explicit stop_event signal")
            else:
                logger.info("Core Jobs worker (Chatbooks) disabled by backend selection or flag")
    except Exception as e:
        logger.warning(f"Failed to start core Jobs worker (Chatbooks): {e}")

    # Jobs metrics gauges worker (stale processing)
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.services.jobs_metrics_service import run_jobs_metrics_gauges as _run_jobs_metrics
        if _skip_heavy:
            logger.info("Test mode/heavy-startup disabled: Skipping Jobs metrics gauge worker")
        else:
            _enabled = (_os.getenv("JOBS_METRICS_GAUGES_ENABLED", "true").lower() in {"true", "1", "yes", "y", "on"})
            if _enabled:
                jobs_metrics_stop_event = _asyncio.Event()
                jobs_metrics_task = _asyncio.create_task(_run_jobs_metrics(jobs_metrics_stop_event))
                logger.info("Jobs metrics gauge worker started with explicit stop_event signal")
            else:
                logger.info("Jobs metrics gauge worker disabled by flag")
    except Exception as e:
        logger.warning(f"Failed to start Jobs metrics gauge worker: {e}")

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

        if _skip_heavy:
            logger.info("Test mode/heavy-startup disabled: Skipping claims rebuild worker")
        elif _claims_enabled:
            claims_task = _asyncio.create_task(_claims_rebuild_loop())
    except Exception as e:
        logger.warning(f"Failed to start claims rebuild worker: {e}")
    
    # Start usage aggregator (if enabled)
    try:
        from tldw_Server_API.app.services.usage_aggregator import start_usage_aggregator
        usage_task = await start_usage_aggregator()
        if usage_task:
            logger.info("Usage aggregator started")
    except Exception as e:
        logger.warning(f"Failed to start usage aggregator: {e}")

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
                _s = get_settings()
                if isinstance(_s.DATABASE_URL, str) and _s.DATABASE_URL.startswith("sqlite"):
                    logger.info("JWT Bearer tokens or X-API-KEY (per-user) supported for SQLite setups")
                else:
                    logger.info("JWT Bearer tokens required for authentication")
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
        _db_engine = "postgresql" if _db_url.startswith("postgresql") else ("sqlite" if _db_url.startswith("sqlite") else "other")
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
    except Exception as _pf_e:
        logger.warning(f"Preflight report could not be generated: {_pf_e}")
    
    yield
    
    # Cancel/stop background worker(s)
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
        if 'claims_task' in locals() and claims_task:
            claims_task.cancel()
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
        if 'mcp_server' in locals():
            await mcp_server.shutdown()
            logger.info("App Shutdown: MCP Unified server shutdown")
    except Exception as e:
        logger.error(f"App Shutdown: Error shutting down MCP Unified server: {e}")
    
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
        if 'provider_manager' in locals():
            await provider_manager.stop_health_checks()
            logger.info("App Shutdown: Provider manager stopped")
    except Exception as e:
        logger.error(f"App Shutdown: Error stopping provider manager: {e}")
    
    # Shutdown Request Queue
    try:
        if 'request_queue' in locals():
            await request_queue.stop()
            logger.info("App Shutdown: Request queue stopped")
    except Exception as e:
        logger.error(f"App Shutdown: Error stopping request queue: {e}")
    
    # Shutdown Unified Audit Services (via DI cache)
    try:
        from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
            shutdown_all_audit_services,
        )
        await shutdown_all_audit_services()
        logger.info("App Shutdown: Unified audit services stopped")
    except Exception as e:
        logger.error(f"App Shutdown: Error stopping unified audit services: {e}")
    
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
        shutdown_telemetry()
        logger.info("App Shutdown: Telemetry shutdown")
    except Exception as e:
        logger.error(f"App Shutdown: Error shutting down telemetry: {e}")
    
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
    {"name": "admin", "description": "Administrative operations and diagnostics."},
    {"name": "media", "description": "Ingest and process media (video/audio/PDF/EPUB/HTML/Markdown).",
     "externalDocs": {"description": "Overview", "url": _ext_url("/docs-static/Documentation.md")}},
    {"name": "audio", "description": "Audio transcription and TTS (OpenAI-compatible).",
     "externalDocs": {"description": "Nemo STT setup", "url": _ext_url("/docs-static/NEMO_STT_DOCUMENTATION.md")}},
    {"name": "audio-websocket", "description": "Real-time streaming transcription over WebSocket.",
     "externalDocs": {"description": "Streaming STT", "url": _ext_url("/docs-static/NEMO_STREAMING_DOCUMENTATION.md")}},
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
    {"name": "mcp-unified", "description": "MCP server + endpoints (JWT/RBAC) – experimental surface in 0.1.",
     "externalDocs": {"description": "MCP v2 Developer Guide", "url": _ext_url("/docs-static/MCP_Docs/MCP_v2_Developer_Guide.md")}},
    {"name": "flashcards", "description": "Flashcards/Decks (ChaChaNotes) – experimental in 0.1."},
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
]

import os as _env_os

_prod_flag = _env_os.getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}
_enable_openapi_env = _env_os.getenv("ENABLE_OPENAPI")
_enable_openapi = True if _enable_openapi_env is None else (_enable_openapi_env.lower() in {"true", "1", "yes", "y", "on"})
if _prod_flag and _enable_openapi_env is None:
    # Default to hidden docs in production unless explicitly enabled
    _enable_openapi = False

APP_DESCRIPTION = (
    """
    Too Long; Didn't Watch Server (tldw_server) — unified research assistant and media analysis platform.

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

_docs_url = "/docs" if _enable_openapi else None
_redoc_url = "/redoc" if _enable_openapi else None
_openapi_url = "/openapi.json" if _enable_openapi else None

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
    swagger_ui_parameters={
        "displayRequestDuration": True,
        "deepLinking": True,
        "docExpansion": "none",
        "defaultModelsExpandDepth": -1,
        "defaultModelExpandDepth": 2,
        "persistAuthorization": True,
        "tryItOutEnabled": True,
        "tagsSorter": "alpha",
        "operationsSorter": "alpha",
        # "syntaxHighlight.theme": "monokai",  # optional, supported by Swagger UI
        "filter": True,
    },
    swagger_ui_css_url="/static/swagger-overrides.css",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
    lifespan=lifespan,
)

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
            "tags": ["prompt-studio", "prompts", "notes", "chatbooks", "tools"],
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
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware
        app.state.limiter = Limiter(key_func=get_remote_address)
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
    import os as _event_os
    if _event_os.getenv("TEST_MODE", "").lower() != "true" and _event_os.getenv("DISABLE_HEAVY_STARTUP", "").lower() not in {"1", "true", "yes", "on"}:
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
from tldw_Server_API.app.core.config import ALLOWED_ORIGINS, API_V1_PREFIX, should_disable_cors

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
from tldw_Server_API.app.core.Security.request_id_middleware import RequestIDMiddleware
from tldw_Server_API.app.core.Metrics.http_middleware import HTTPMetricsMiddleware
from tldw_Server_API.app.core.AuthNZ.usage_logging_middleware import UsageLoggingMiddleware
from tldw_Server_API.app.core.AuthNZ.llm_budget_middleware import LLMBudgetMiddleware

_TEST_MODE = (
    _env_os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")
    or bool(_env_os.getenv("PYTEST_CURRENT_TEST"))
)

if _TEST_MODE:
    logger.info("TEST_MODE detected: Skipping non-essential middlewares (security headers, metrics, usage logging, request id)")
else:
    _enable_sec_headers_env = _env_os.getenv("ENABLE_SECURITY_HEADERS")
    _enable_sec_headers = True if (_prod_flag and _enable_sec_headers_env is None) else (
        (_enable_sec_headers_env or "true").lower() in {"true", "1", "yes", "y", "on"}
    )
    if _enable_sec_headers:
        app.add_middleware(SecurityHeadersMiddleware, enabled=True)

    # HTTP request metrics middleware (records count and latency per route)
    app.add_middleware(HTTPMetricsMiddleware)

    # Per-request usage logging (guarded by settings flag)
    app.add_middleware(UsageLoggingMiddleware)

    # Request ID propagation (adds X-Request-ID header)
    app.add_middleware(RequestIDMiddleware)

# Always apply LLM budget middleware (guarded by settings) even in tests so allowlists/budgets are enforced
try:
    app.add_middleware(LLMBudgetMiddleware)
except Exception as _e:
    logger.debug(f"Skipping LLMBudgetMiddleware: {_e}")

# WebUI serving - Serve the WebUI from the same origin to avoid CORS issues
WEBUI_DIR = BASE_DIR.parent / "WebUI"
if WEBUI_DIR.exists():
    # First, add a dynamic config endpoint for single user mode
    @app.get("/webui/config.json", include_in_schema=False)
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
                _settings = get_settings()
                dbu = _settings.DATABASE_URL or ""
                if isinstance(dbu, str) and dbu.startswith("sqlite"):
                    # Expose hint so the WebUI can prefer X-API-KEY in multi-user SQLite setups
                    config.setdefault("auth", {})
                    config["auth"]["multiUserSupportsApiKey"] = True
                    config["auth"]["preferApiKeyInMultiUser"] = True
                else:
                    config.setdefault("auth", {})
                    config["auth"]["multiUserSupportsApiKey"] = False
                    config["auth"]["preferApiKeyInMultiUser"] = False
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
    
    # Mount the WebUI static files (except config.json which is handled dynamically)
    app.mount("/webui", StaticFiles(directory=str(WEBUI_DIR), html=True), name="webui")
    logger.info(f"WebUI mounted at /webui from {WEBUI_DIR}")
else:
    logger.warning(f"WebUI directory not found at {WEBUI_DIR}")

SETUP_PAGE_PATH = WEBUI_DIR / "setup.html"


@app.get("/setup", include_in_schema=False, openapi_extra={"security": []})
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
            return RedirectResponse(url="/setup", status_code=307)
    except FileNotFoundError:
        logger.warning("config.txt missing while handling root request; serving default message.")

    return {
        "message": "Welcome to the tldw API; If you're seeing this, the server is running!" "Check out /webui , /docs or /metrics to get started!"
    }

# Metrics endpoint for Prometheus scraping
@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    from fastapi.responses import PlainTextResponse
    
    registry = get_metrics_registry()
    metrics_text = registry.export_prometheus_format()
    
    return PlainTextResponse(metrics_text, media_type="text/plain; version=0.0.4")

# OpenTelemetry metrics endpoint (if using OTLP)
@app.get("/api/v1/metrics", tags=["monitoring"])
@track_metrics(labels={"endpoint": "metrics"})
async def api_metrics():
    """Get current metrics in JSON format."""
    registry = get_metrics_registry()
    return registry.get_all_metrics()

# Router for health monitoring endpoints (NEW)
from tldw_Server_API.app.api.v1.endpoints.health import router as health_router
from tldw_Server_API.app.api.v1.endpoints.moderation import router as moderation_router
from tldw_Server_API.app.api.v1.endpoints.monitoring import router as monitoring_router
app.include_router(health_router, prefix=f"{API_V1_PREFIX}", tags=["health"])
app.include_router(moderation_router, prefix=f"{API_V1_PREFIX}", tags=["moderation"])
app.include_router(monitoring_router, prefix=f"{API_V1_PREFIX}", tags=["monitoring"])
from tldw_Server_API.app.api.v1.endpoints.audit import router as audit_router
app.include_router(audit_router, prefix=f"{API_V1_PREFIX}", tags=["audit"])

# Router for authentication endpoints (NEW)
app.include_router(auth_router, prefix=f"{API_V1_PREFIX}", tags=["authentication"])

# Router for user management endpoints (NEW)
app.include_router(users_router, prefix=f"{API_V1_PREFIX}", tags=["users"])

# Router for admin endpoints (NEW)
from tldw_Server_API.app.api.v1.endpoints.admin import router as admin_router
app.include_router(admin_router, prefix=f"{API_V1_PREFIX}", tags=["admin"])

# Router for media endpoints/media file handling
if _HAS_MEDIA:
    app.include_router(media_router, prefix=f"{API_V1_PREFIX}/media", tags=["media"])

# Router for /audio/ endpoints
app.include_router(audio_router, prefix=f"{API_V1_PREFIX}/audio", tags=["audio"])

# WebSocket router for audio streaming (separate to avoid authentication conflicts)
app.include_router(audio_ws_router, prefix=f"{API_V1_PREFIX}/audio", tags=["audio-websocket"])

# Router for chat endpoints/chat temp-file handling
app.include_router(chat_router, prefix=f"{API_V1_PREFIX}/chat")


# Router for character endpoints
app.include_router(character_router, prefix=f"{API_V1_PREFIX}/characters", tags=["characters"])

# Router for character chat sessions
app.include_router(character_chat_sessions_router, prefix=f"{API_V1_PREFIX}/chats", tags=["character-chat-sessions"])

# Router for character messages (Note: uses multiple prefixes for different endpoints)
app.include_router(character_messages_router, prefix=f"{API_V1_PREFIX}", tags=["character-messages"])


# Router for metrics endpoints
app.include_router(metrics_router, prefix=f"{API_V1_PREFIX}", tags=["metrics"])


# Router for Chunking Endpoint
app.include_router(chunking_router, prefix=f"{API_V1_PREFIX}/chunking", tags=["chunking"])

# Router for Chunking Templates
app.include_router(chunking_templates_router, prefix=f"{API_V1_PREFIX}", tags=["chunking-templates"])


# Router for Embedding Endpoint (OpenAI-compatible path)
app.include_router(embeddings_router, prefix=f"{API_V1_PREFIX}", tags=["embeddings"])
# Router for Vector Store (OpenAI-compatible) endpoints
app.include_router(vector_stores_router, prefix=f"{API_V1_PREFIX}", tags=["vector-stores"])
app.include_router(claims_router, prefix=f"{API_V1_PREFIX}")

# Router for Media Embeddings Endpoint
app.include_router(media_embeddings_router, prefix=f"{API_V1_PREFIX}", tags=["media-embeddings"])

# Router for Note Management endpoints
app.include_router(notes_router, prefix=f"{API_V1_PREFIX}/notes", tags=["notes"])


# Router for Prompt Management endpoints
app.include_router(prompt_router, prefix=f"{API_V1_PREFIX}/prompts", tags=["prompts"])


# Router for Prompt Studio endpoints
if _HAS_PROMPT_STUDIO:
    app.include_router(prompt_studio_projects_router, tags=["prompt-studio"])
    app.include_router(prompt_studio_prompts_router, tags=["prompt-studio"])
    app.include_router(prompt_studio_test_cases_router, tags=["prompt-studio"])
    app.include_router(prompt_studio_optimization_router, tags=["prompt-studio"])
    app.include_router(prompt_studio_status_router, tags=["prompt-studio"])
    app.include_router(prompt_studio_evaluations_router, tags=["prompt-studio"])
    app.include_router(prompt_studio_websocket_router, tags=["prompt-studio"])


# Router for RAG endpoints
# Register health router first to serve /api/v1/rag/health* shape expected by tests
app.include_router(rag_health_router, tags=["rag-health"])
# RAG API - Production API using unified pipeline
app.include_router(rag_unified_router, tags=["rag-unified"])


# Workflows API (v0.1 scaffolding)
app.include_router(workflows_router, tags=["workflows"])


# Router for Research endpoint
app.include_router(research_router, prefix=f"{API_V1_PREFIX}/research", tags=["research"])

# Router for Paper Search endpoints (arXiv, BioRxiv, Semantic Scholar)
app.include_router(paper_search_router, prefix=f"{API_V1_PREFIX}/paper-search", tags=["paper-search"])


# Router for Unified Evaluation endpoint (combines both legacy endpoints)
if _HAS_UNIFIED_EVALUATIONS:
    app.include_router(unified_evaluation_router, prefix=f"{API_V1_PREFIX}", tags=["evaluations"])
app.include_router(ocr_router, prefix=f"{API_V1_PREFIX}", tags=["ocr"])
app.include_router(vlm_router, prefix=f"{API_V1_PREFIX}", tags=["vlm"])

# Router for Benchmark endpoint (NEW)
app.include_router(benchmark_router, prefix=f"{API_V1_PREFIX}", tags=["benchmarks"])

# Router for Setup endpoints (first-time configuration)
from tldw_Server_API.app.api.v1.endpoints.config_info import router as config_info_router
from tldw_Server_API.app.api.v1.endpoints.jobs_admin import router as jobs_admin_router
app.include_router(setup_router, prefix=f"{API_V1_PREFIX}", tags=["setup"])

# Router for Configuration Info endpoint (for documentation)
app.include_router(config_info_router, prefix=f"{API_V1_PREFIX}", tags=["config"])
app.include_router(jobs_admin_router, prefix=f"{API_V1_PREFIX}", tags=["jobs"])

# Router for Sync endpoint
app.include_router(sync_router, prefix=f"{API_V1_PREFIX}/sync", tags=["sync"])


# Router for Tools endpoint
app.include_router(tools_router, prefix=f"{API_V1_PREFIX}/tools", tags=["tools"])

# Router for Flashcards
app.include_router(flashcards_router, prefix=f"{API_V1_PREFIX}", tags=["flashcards"])


# Router for MCP Unified (Secure, production-ready implementation)
app.include_router(mcp_unified_router, prefix=f"{API_V1_PREFIX}", tags=["mcp-unified"])
# Note: Old MCP routers have been archived due to security vulnerabilities

# Router for Chatbooks - import/export functionality
app.include_router(chatbooks_router, prefix=f"{API_V1_PREFIX}", tags=["chatbooks"])
# Router for LLM providers endpoint
app.include_router(llm_providers_router, prefix=f"{API_V1_PREFIX}", tags=["llm"])

# Router for Llama.cpp (LLM inference helper)
# Llama.cpp endpoints under /api/v1 and public aliases (/reranking, /v1/rerank, etc.)
app.include_router(llamacpp_router, prefix=f"{API_V1_PREFIX}", tags=["llamacpp"])
app.include_router(llamacpp_public_router, prefix="", tags=["llamacpp"])

# Web Scraping management endpoints
# Include both root-level (back-compat) and versioned paths (used by WebUI)
app.include_router(web_scraping_router, tags=["web-scraping"])
app.include_router(web_scraping_router, prefix=f"{API_V1_PREFIX}", tags=["web-scraping"])

# Router for trash endpoints - deletion of media items / trash file handling (FIXME: Secure delete vs lag on delete?)
#app.include_router(trash_router, prefix=f"{API_V1_PREFIX}/trash", tags=["trash"])

# Router for authentication endpoint
#app.include_router(auth_router, prefix=f"{API_V1_PREFIX}/auth", tags=["auth"])
# The docs at http://localhost:8000/docs will show an “Authorize” button. You can log in by calling POST /api/v1/auth/login with a form that includes username and password. The docs interface is automatically aware because we used OAuth2PasswordBearer.

# Health check
@app.get("/health", openapi_extra={"security": []})
async def health_check():
    return {"status": "healthy"}

# Readiness check (verifies critical dependencies)
@app.get("/ready", openapi_extra={"security": []})
async def readiness_check():
    """Readiness probe for orchestrators and load balancers."""
    try:
        # DB health
        from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
        db_pool = await get_db_pool()
        db_health = await db_pool.health_check()

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
        status = "ready" if ready else "not_ready"
        return {
            "status": status,
            "database": db_health,
            "providers_initialized": providers_ok,
            "provider_health": provider_health,
            "otel_available": bool(OTEL_AVAILABLE),
        }
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}

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
