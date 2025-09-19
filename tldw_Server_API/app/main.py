# main.py
# Description: This file contains the main FastAPI application, which serves as the primary API for the tldw application.
#
# Imports
import logging
#
# 3rd-party Libraries
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from loguru import logger
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
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
# Media Endpoint
from tldw_Server_API.app.api.v1.endpoints.media import router as media_router
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
from tldw_Server_API.app.api.v1.endpoints.prompt_studio_projects import router as prompt_studio_projects_router
from tldw_Server_API.app.api.v1.endpoints.prompt_studio_prompts import router as prompt_studio_prompts_router
from tldw_Server_API.app.api.v1.endpoints.prompt_studio_test_cases import router as prompt_studio_test_cases_router
from tldw_Server_API.app.api.v1.endpoints.prompt_studio_optimization import router as prompt_studio_optimization_router
from tldw_Server_API.app.api.v1.endpoints.prompt_studio_websocket import router as prompt_studio_websocket_router
from tldw_Server_API.app.api.v1.endpoints.prompt_studio_evaluations import router as prompt_studio_evaluations_router
#
# RAG Endpoints
from tldw_Server_API.app.api.v1.endpoints.rag_health import router as rag_health_router  # RAG health/caching/metrics endpoints
from tldw_Server_API.app.api.v1.endpoints.rag_unified import router as rag_unified_router  # Unified RAG API with all features as parameters
# Legacy RAG Endpoint (Deprecated)
# from tldw_Server_API.app.api.v1.endpoints.rag import router as retrieval_agent_router
#
# Research Endpoint
from tldw_Server_API.app.api.v1.endpoints.research import router as research_router
#
# Evaluation Endpoint (OLD - to be removed)
# Legacy evaluation endpoint - replaced by unified router
# from tldw_Server_API.app.api.v1.endpoints.evals import router as evaluation_router
#
# OpenAI-compatible Evaluation Endpoint (NEW)
# Legacy OpenAI evaluation endpoint - replaced by unified router
# from tldw_Server_API.app.api.v1.endpoints.evals_openai import router as openai_evals_router

# Unified Evaluation endpoint
from tldw_Server_API.app.api.v1.endpoints.evaluations_unified import router as unified_evaluation_router
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
# LLM Providers Endpoint
from tldw_Server_API.app.api.v1.endpoints.llm_providers import router as llm_providers_router
from tldw_Server_API.app.api.v1.endpoints.llamacpp import router as llamacpp_router
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
    
    # Startup: Initialize auth services
    logger.info("App Startup: Initializing authentication services...")
    try:
        # Initialize database pool for auth
        from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
        db_pool = await get_db_pool()
        logger.info("App Startup: Database pool initialized")
        
        # Initialize session manager
        from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
        session_manager = await get_session_manager()
        logger.info("App Startup: Session manager initialized")
    except Exception as e:
        logger.error(f"App Startup: Failed to initialize auth services: {e}")
        # Continue startup even if auth services fail (for backward compatibility)
    
    # Initialize MCP Unified Server (secure, production-ready)
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
    logger.info("App Startup: Initializing Chat module components...")
    
    # Initialize Provider Manager
    try:
        from tldw_Server_API.app.core.Chat.provider_manager import initialize_provider_manager
        from tldw_Server_API.app.core.Chat.Chat_Functions import API_CALL_HANDLERS
        
        # Get list of configured providers
        providers = list(API_CALL_HANDLERS.keys())
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

    # Start background workers: ephemeral collections cleanup, claims rebuild
    cleanup_task = None
    claims_task = None
    try:
        import os as _os
        import asyncio as _asyncio
        from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase as _EvalsDB
        from tldw_Server_API.app.core.RAG.rag_service.vector_stores import VectorStoreFactory as _VSF
        from tldw_Server_API.app.core.config import settings as _app_settings

        _db_path = str(Path("Databases") / "evaluations.db")
        # Read settings
        _enabled = bool(_app_settings.get("EPHEMERAL_CLEANUP_ENABLED", True))
        _interval_sec = int(_app_settings.get("EPHEMERAL_CLEANUP_INTERVAL_SEC", 1800))

        async def _ephemeral_cleanup_loop():
            logger.info(f"Starting ephemeral collections cleanup worker (every {_interval_sec}s)")
            db = _EvalsDB(_db_path)
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

        if _enabled:
            cleanup_task = _asyncio.create_task(_ephemeral_cleanup_loop())
        else:
            logger.info("Ephemeral cleanup worker disabled by settings")
    except Exception as e:
        logger.warning(f"Failed to start ephemeral cleanup worker: {e}")

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
    except Exception as e:
        logger.warning(f"Failed to start claims rebuild worker: {e}")
    
    # Display authentication mode and API key for single-user mode
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings, is_single_user_mode
        settings = get_settings()
        
        logger.info("=" * 60)
        logger.info("🚀 TLDW Server Started Successfully")
        logger.info("=" * 60)
        
        if is_single_user_mode():
            logger.info(f"🔐 Authentication Mode: SINGLE USER")
            logger.info(f"🔑 API Key: {settings.SINGLE_USER_API_KEY}")
            logger.info("=" * 60)
            logger.info("Use this API key in the X-API-KEY header for requests")
        else:
            logger.info(f"🔐 Authentication Mode: MULTI USER")
            logger.info("JWT Bearer tokens required for authentication")
            logger.info("=" * 60)
        
        logger.info(f"📍 API Documentation: http://127.0.0.1:8000/docs")
        logger.info(f"🌐 WebUI: http://127.0.0.1:8000/webui/")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Failed to display startup info: {e}")
    
    yield
    
    # Cancel background worker(s)
    try:
        if 'cleanup_task' in locals() and cleanup_task:
            cleanup_task.cancel()
        if 'claims_task' in locals() and claims_task:
            claims_task.cancel()
    except Exception:
        pass

    # Shutdown: Clean up resources
    logger.info("App Shutdown: Cleaning up resources...")
    
    # Note: Audit service cleanup handled via dependency injection
    # No global shutdown needed
    logger.info("App Shutdown: Audit services cleanup handled by dependency injection")
    
    # Close auth database pool
    try:
        if 'db_pool' in locals():
            await db_pool.close()
            logger.info("App Shutdown: Auth database pool closed")
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
    
    # Shutdown Audit Logger
    try:
        if 'audit_logger' in locals():
            await audit_logger.stop()
            logger.info("App Shutdown: Audit logger stopped")
    except Exception as e:
        logger.error(f"App Shutdown: Error stopping audit logger: {e}")
    
    # Cleanup CPU pools
    try:
        from tldw_Server_API.app.core.Utils.cpu_bound_handler import cleanup_pools
        cleanup_pools()
        logger.info("App Shutdown: CPU pools cleaned up")
    except Exception as e:
        logger.error(f"App Shutdown: Error cleaning up CPU pools: {e}")
    
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
app = FastAPI(
    title="tldw API",
    version="0.0.1",
    description="Version 0.0.1: Smooth Slide | FastAPI Backend for the tldw project",
    lifespan=lifespan
)

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

@app.on_event("startup")
async def display_startup_info():
    """Display important startup information including API key in single user mode."""
    if is_single_user_mode():
        settings = get_settings()
        api_key = settings.SINGLE_USER_API_KEY
        
        # Create a visually prominent display
        logger.info("="*70)
        logger.info("🚀 TLDW Server Started in SINGLE USER MODE")
        logger.info("="*70)
        logger.info("")
        logger.info("📌 API Key for authentication:")
        logger.info(f"   {api_key}")
        logger.info("")
        logger.info("🌐 Access URLs:")
        logger.info("   WebUI:    http://localhost:8000/webui/")
        logger.info("   API Docs: http://localhost:8000/docs")
        logger.info("   ReDoc:    http://localhost:8000/redoc")
        logger.info("")
        logger.info("💡 The WebUI will automatically use this API key")
        logger.info("="*70)
    else:
        logger.info("="*70)
        logger.info("🚀 TLDW Server Started in MULTI-USER MODE")
        logger.info("="*70)
        logger.info("Authentication required via JWT tokens")
        logger.info("="*70)

# --- FIX: Add CORS Middleware ---
# Import from config
from tldw_Server_API.app.core.config import ALLOWED_ORIGINS, API_V1_PREFIX

# Use configured origins
origins = ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"]

# FIXME - CORS
# # -- If you have any global middleware, add it here --
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Must include OPTIONS, GET, POST, DELETE etc.
    allow_headers=["*"],
)

# Add CSRF Protection Middleware (NEW)
from tldw_Server_API.app.core.AuthNZ.csrf_protection import add_csrf_protection
add_csrf_protection(app)

# Static files serving
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

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
        
        # In single user mode, include the API key
        if is_single_user_mode():
            settings = get_settings()
            config["apiKey"] = settings.SINGLE_USER_API_KEY
            config["mode"] = "single-user"
            config["_comment"] = "Auto-configured for single user mode"
        else:
            config["mode"] = "multi-user"
            config["_comment"] = "Multi-user mode - manual authentication required"
        
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

            import os as _os
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

# Favicon serving
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(FAVICON_PATH, media_type="image/x-icon")

@app.get("/")
async def root():
    return {"message": "Welcome to the tldw API; If you're seeing this, the server is running!" + "Check out /webui , /docs or /metrics to get started!"}

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
app.include_router(health_router, prefix=f"{API_V1_PREFIX}", tags=["health"])

# Router for authentication endpoints (NEW)
app.include_router(auth_router, prefix=f"{API_V1_PREFIX}", tags=["authentication"])

# Router for user management endpoints (NEW)
app.include_router(users_router, prefix=f"{API_V1_PREFIX}", tags=["users"])

# Router for admin endpoints (NEW)
from tldw_Server_API.app.api.v1.endpoints.admin import router as admin_router
app.include_router(admin_router, prefix=f"{API_V1_PREFIX}", tags=["admin"])

# Router for media endpoints/media file handling
app.include_router(media_router, prefix=f"{API_V1_PREFIX}/media", tags=["media"])

# Router for /audio/ endpoints
app.include_router(audio_router, prefix=f"{API_V1_PREFIX}/audio", tags=["audio"])

# WebSocket router for audio streaming (separate to avoid authentication conflicts)
app.include_router(audio_ws_router, prefix=f"{API_V1_PREFIX}/audio", tags=["audio-websocket"])

# Router for chat endpoints/chat temp-file handling
app.include_router(chat_router, prefix=f"{API_V1_PREFIX}/chat", tags=["chat"])


# Router for character endpoints
app.include_router(character_router, prefix=f"{API_V1_PREFIX}/characters", tags=["character, persona"])

# Router for character chat sessions
app.include_router(character_chat_sessions_router, prefix=f"{API_V1_PREFIX}/chats", tags=["character chat sessions"])

# Router for character messages (Note: uses multiple prefixes for different endpoints)
app.include_router(character_messages_router, prefix=f"{API_V1_PREFIX}", tags=["character messages"])


# Router for metrics endpoints
app.include_router(metrics_router, prefix=f"{API_V1_PREFIX}", tags=["metrics"])


# Router for Chunking Endpoint
app.include_router(chunking_router, prefix=f"{API_V1_PREFIX}/chunking", tags=["chunking"])

# Router for Chunking Templates
app.include_router(chunking_templates_router, prefix=f"{API_V1_PREFIX}", tags=["chunking templates"])


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
app.include_router(prompt_studio_projects_router, tags=["Prompt Studio"])
app.include_router(prompt_studio_prompts_router, tags=["Prompt Studio"])
app.include_router(prompt_studio_test_cases_router, tags=["Prompt Studio"])
app.include_router(prompt_studio_optimization_router, tags=["Prompt Studio"])
app.include_router(prompt_studio_evaluations_router, tags=["Prompt Studio"])
app.include_router(prompt_studio_websocket_router, tags=["Prompt Studio"])


# Router for RAG endpoints
# Register health router first to serve /api/v1/rag/health* shape expected by tests
app.include_router(rag_health_router, tags=["RAG - Health"])
# RAG API - Production API using unified pipeline
app.include_router(rag_unified_router, tags=["RAG - Unified"])


# Router for Research endpoint
app.include_router(research_router, prefix=f"{API_V1_PREFIX}/research", tags=["research"])


# Router for Unified Evaluation endpoint (combines both legacy endpoints)
app.include_router(unified_evaluation_router, prefix=f"{API_V1_PREFIX}", tags=["evaluations"])

# Router for Benchmark endpoint (NEW)
app.include_router(benchmark_router, prefix=f"{API_V1_PREFIX}", tags=["benchmarks"])

# Router for Configuration Info endpoint (for documentation)
from tldw_Server_API.app.api.v1.endpoints.config_info import router as config_info_router
app.include_router(config_info_router, prefix=f"{API_V1_PREFIX}", tags=["config"])

# Router for Sync endpoint
app.include_router(sync_router, prefix=f"{API_V1_PREFIX}/sync", tags=["sync"])


# Router for Tools endpoint
app.include_router(tools_router, prefix=f"{API_V1_PREFIX}/tools", tags=["tools"])


# Router for MCP Unified (Secure, production-ready implementation)
app.include_router(mcp_unified_router, prefix=f"{API_V1_PREFIX}", tags=["MCP Unified"])
# Note: Old MCP routers have been archived due to security vulnerabilities

# Router for Chatbooks - import/export functionality
app.include_router(chatbooks_router, prefix=f"{API_V1_PREFIX}", tags=["chatbooks"])
# Router for LLM providers endpoint
app.include_router(llm_providers_router, prefix=f"{API_V1_PREFIX}", tags=["llm"])

# Router for Llama.cpp (LLM inference helper)
app.include_router(llamacpp_router, prefix=f"{API_V1_PREFIX}", tags=["llamacpp"])

# Router for trash endpoints - deletion of media items / trash file handling (FIXME: Secure delete vs lag on delete?)
#app.include_router(trash_router, prefix=f"{API_V1_PREFIX}/trash", tags=["trash"])

# Router for authentication endpoint
#app.include_router(auth_router, prefix=f"{API_V1_PREFIX}/auth", tags=["auth"])
# The docs at http://localhost:8000/docs will show an “Authorize” button. You can log in by calling POST /api/v1/auth/login with a form that includes username and password. The docs interface is automatically aware because we used OAuth2PasswordBearer.

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

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
