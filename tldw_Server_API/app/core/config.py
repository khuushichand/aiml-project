# config.py
# Description: Configuration settings for the tldw server application.
#
# Imports
import configparser
import json
import os
import yaml
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv


#
# 3rd-party Libraries
from loguru import logger#
# Local Imports
#
########################################################################################################################
#
# Functions:

# --- Constants ---
# Client ID used by the Server API itself when writing to sync logs
SERVER_CLIENT_ID = "SERVER_API_V1"

# --- CORS Configuration ---
# List of allowed origins for CORS (env override supported)
def _parse_allowed_origins_env(raw: str):
    try:
        # Support JSON array
        if raw.strip().startswith("["):
            vals = json.loads(raw)
            return [str(v).strip() for v in vals if str(v).strip()]
    except Exception:
        pass
    # Fallback: comma-separated list
    return [s.strip() for s in raw.split(",") if s.strip()]

_ENV_ALLOWED = os.getenv("ALLOWED_ORIGINS")
if _ENV_ALLOWED:
    ALLOWED_ORIGINS = _parse_allowed_origins_env(_ENV_ALLOWED)
else:
    ALLOWED_ORIGINS = [
        "http://localhost",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
        "https://localhost",
        "https://localhost:8080",
    ]

# --- API Configuration ---
# API version prefix for all endpoints
API_V1_PREFIX = "/api/v1"

# Authentication prefix
AUTH_BEARER_PREFIX = "Bearer "

# --- Server Configuration ---
# Default server host and port
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# --- Database Configuration ---
# Default database type
DEFAULT_DB_TYPE = "sqlite3"

# --- File Validation/YARA Settings ---
YARA_RULES_PATH: Optional[str] = None # e.g., "/app/yara_rules/index.yar"
MAGIC_FILE_PATH: Optional[str] = os.getenv("MAGIC_FILE_PATH", None) # e.g., "/app/magic.mgc"

# --- Chunking Settings ---
global_default_chunk_language = "en"


# FIXME - TTS Config
APP_CONFIG = {
    "OPENAI_API_KEY": "sk-...",
    "KOKORO_ONNX_MODEL_PATH_DEFAULT": "path/to/your/downloaded/kokoro-v0_19.onnx",
    "KOKORO_ONNX_VOICES_JSON_DEFAULT": "path/to/your/downloaded/voices.json",
    "KOKORO_DEVICE_DEFAULT": "cpu", # or "cuda"
    "ELEVENLABS_API_KEY": "el-...",
    "local_kokoro_default_onnx": { # Specific overrides for this backend_id
        "KOKORO_DEVICE": "cuda:0"
    },
    "global_tts_settings": {
        # shared settings
    }
}

DATABASE_CONFIG = {
    }

RAG_SEARCH_CONFIG = {
    "fts_top_k": 10,
    "vector_top_k": 10,
    "web_vector_top_k": 10,
    "llm_context_document_limit": 10,
    "chat_context_limit": 10,
    # Database query limits
    "max_conversations_per_character": 1000,
    "max_conversations_for_keyword": 500,
    "max_notes_for_keyword": 500,
    "max_character_cards_fetch": 100000,
    "max_notes_fetch": 100000,
    "max_media_search_limit": 10000,
    # Embedding and vector search
    "max_embedding_batch_size": 100,
    "max_vector_search_results": 1000,
    # Content limits
    "max_context_chars_rag": 15000,
    "metadata_content_preview_chars": 256,
    # Cleanup settings
    "temp_file_cleanup_hours": 24,
    # Pagination defaults
    "default_results_per_page": 50,
}

# Configuration for the new modular RAG service
RAG_SERVICE_CONFIG = {
    # General settings
    "batch_size": 32,
    "num_workers": 4,  # Limited for multi-user server
    "log_level": "INFO",
    "log_performance_metrics": True,
    
    # Cache configuration
    "cache": {
        "enable_cache": True,
        "max_cache_size": 1000,
        "cache_ttl": 3600,  # 1 hour
        "cache_search_results": True,
        "cache_embeddings": True,
        "cache_llm_responses": False  # Don't cache LLM responses by default
    },
    
    # Retriever configuration
    "retriever": {
        "fts_top_k": 10,
        "vector_top_k": 10,
        "hybrid_alpha": 0.5,  # Balance between keyword and vector search
        "enable_web_search": False,
        "web_search_top_k": 5,
        "enable_re_ranking": True,
        "re_ranking_model": "flashrank",
        "timeout_seconds": 30
    },
    
    # Processor configuration
    "processor": {
        "enable_reranking": True,
        "reranking_model": "flashrank",
        "reranking_top_k": 10,
        "enable_deduplication": True,
        "dedup_threshold": 0.85,
        "max_context_length": 4096,
        "context_padding_tokens": 100,
        "enable_metadata_filtering": True,
        "token_counter": "tiktoken"
    },
    
    # Generator configuration
    "generator": {
        "default_model": "gpt-3.5-turbo",
        "default_temperature": 0.7,
        "default_max_tokens": 2000,
        "enable_streaming": True,
        "stream_chunk_size": 50,
        "enable_citations": True,
        "citation_style": "inline",
        "enable_fallback": True,
        "fallback_behavior": "simple_answer"
    }
}

# Configuration for speaker diarization
DIARIZATION_CONFIG = {
    # VAD (Voice Activity Detection) settings
    "vad_threshold": 0.5,  # Silero VAD confidence threshold
    "segment_duration": 30,  # Maximum segment duration in seconds
    "speech_pad_ms": 400,  # Padding around speech segments in milliseconds
    
    # Embedding model settings
    "embedding_model": "speechbrain/spkrec-ecapa-voxceleb",
    "embedding_batch_size": 32,
    "embedding_device": "auto",  # auto, cpu, cuda, or cuda:0
    
    # Clustering settings
    "clustering_method": "spectral",  # spectral or agglomerative
    "num_speakers": None,  # None for automatic detection
    "min_speakers": 1,
    "max_speakers": 10,
    
    # Post-processing settings
    "min_segment_duration": 0.5,  # Minimum segment duration in seconds
    "merge_threshold": 0.5,  # Threshold for merging adjacent segments
    "overlap_detection": True,  # Enable overlap detection
    "overlap_confidence_threshold": 0.7,
    
    # Performance settings
    "num_threads": 4,  # Number of threads for processing
    "use_auth_token": None,  # HuggingFace auth token if needed
    "cache_dir": None,  # Directory for model cache
    
    # Output settings
    "include_embeddings": False,  # Include embeddings in output
    "include_vad_scores": False,  # Include VAD scores in output
}


def load_tts_config() -> Dict[str, Any]:
    """
    Load TTS configuration from YAML file and integrate with existing config.
    
    Returns:
        Dictionary containing TTS configuration
    """
    current_file_path = Path(__file__).resolve()
    # Navigate to TTS config file: .../tldw_Server_API/app/core/TTS/tts_providers_config.yaml
    tts_config_path = current_file_path.parent / 'TTS' / 'tts_providers_config.yaml'
    
    logger.info(f"Loading TTS configuration from: {tts_config_path}")
    
    if not tts_config_path.exists():
        logger.warning(f"TTS config file not found at {tts_config_path}, using defaults")
        return _get_default_tts_config()
    
    try:
        with open(tts_config_path, 'r', encoding='utf-8') as f:
            tts_config = yaml.safe_load(f)
        
        # Validate and process the configuration
        processed_config = _process_tts_config(tts_config)
        logger.info("TTS configuration loaded successfully")
        return processed_config
        
    except Exception as e:
        logger.error(f"Error loading TTS configuration: {e}")
        logger.info("Falling back to default TTS configuration")
        return _get_default_tts_config()

def _process_tts_config(tts_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process and validate TTS configuration from YAML.
    
    Args:
        tts_config: Raw configuration from YAML file
        
    Returns:
        Processed configuration dictionary
    """
    processed = {}
    
    # Extract provider priority
    if 'provider_priority' in tts_config:
        processed['provider_priority'] = tts_config['provider_priority']
    
    # Process provider configurations
    if 'providers' in tts_config:
        for provider_name, provider_config in tts_config['providers'].items():
            processed[f'{provider_name}_config'] = provider_config
            
            # Enable/disable flags
            processed[f'{provider_name}_enabled'] = provider_config.get('enabled', True)
    
    # Extract voice mappings
    if 'voice_mappings' in tts_config:
        processed['voice_mappings'] = tts_config['voice_mappings']
    
    # Extract format preferences
    if 'format_preferences' in tts_config:
        processed['format_preferences'] = tts_config['format_preferences']
    
    # Extract performance settings
    if 'performance' in tts_config:
        processed.update(tts_config['performance'])
    
    # Extract fallback settings
    if 'fallback' in tts_config:
        processed.update(tts_config['fallback'])
    
    # Extract logging settings
    if 'logging' in tts_config:
        processed['tts_logging'] = tts_config['logging']
    
    return processed

def _get_default_tts_config() -> Dict[str, Any]:
    """
    Get default TTS configuration when YAML config is not available.
    
    Returns:
        Default configuration dictionary
    """
    return {
        'provider_priority': ['openai', 'kokoro'],
        'openai_enabled': True,
        'kokoro_enabled': True,
        'higgs_enabled': False,
        'dia_enabled': False,
        'chatterbox_enabled': False,
        'max_concurrent_generations': 4,
        'fallback_enabled': True,
        'max_attempts': 3,
        'retry_delay_ms': 1000
    }

def load_openai_mappings() -> Dict:
    # Determine path relative to this file.
    # config.py is in project_root/tldw_server_api/app/core/config.py
    # Config_Files is assumed to be in project_root/tldw_server_api/Config_Files/
    current_file_path = Path(__file__).resolve()
    api_component_root = current_file_path.parent.parent.parent  # This should be /project_root/tldw_server_api/

    mapping_path = api_component_root / "Config_Files" / "openai_tts_mappings.json"
    logger.debug(f"Attempting to load OpenAI TTS mappings from: {str(mapping_path)}")
    try:
        with open(mapping_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.debug(f"Failed to load OpenAI TTS mappings from {mapping_path}: {e}")
        # Fallback to a default or raise an error
        return {
            "models": {"tts-1": "openai_official_tts-1"},
            "voices": {"alloy": "alloy"}
        }

_openai_mappings = load_openai_mappings()

openai_tts_mappings = {
    "models": {
        "tts-1": "openai_official_tts-1",
        "tts-1-hd": "openai_official_tts-1-hd",
        "eleven_monolingual_v1": "elevenlabs_english_v1",
        "kokoro": "local_kokoro_default_onnx"
    },
    "voices": {
        "alloy": "alloy", "echo": "echo", "fable": "fable",
        "onyx": "onyx", "nova": "nova", "shimmer": "shimmer",

        "RachelEL": "21m00Tcm4TlvDq8ikWAM",

        "k_bella": "af_bella",
        "k_adam" : "am_v0adam"
    }
}


# --- Helper Function (Optional but can keep dictionary creation clean) ---
def load_settings():
    """Loads all settings from environment variables or defaults into a dictionary."""

    # Determine Actual Project Root based on the location of this file
    # config.py is in project_root/tldw_server_api/app/core/config.py
    # ACTUAL_PROJECT_ROOT will be /project_root/
    ACTUAL_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    logger.info(f"Determined ACTUAL_PROJECT_ROOT for database paths: {ACTUAL_PROJECT_ROOT}")

    # --- Application Mode ---
    single_user_mode_str = os.getenv("APP_MODE", "single").lower()
    single_user_mode = single_user_mode_str != "multi"

    # --- Single-User Settings ---
    # Use a fixed ID for the single user's database path and cache key
    # Default to 1 for single-user mode (0 is typically reserved for system/admin)
    single_user_fixed_id = int(os.getenv("SINGLE_USER_FIXED_ID", "1")) # Default to user ID 1
    # API Key for accessing the single-user instance
    # Check both SINGLE_USER_API_KEY (AuthNZ standard) and API_KEY (legacy) environment variables
    single_user_api_key = os.getenv("SINGLE_USER_API_KEY") or os.getenv("API_KEY")

    # --- Multi-User Settings (JWT) ---
    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "a_very_insecure_default_secret_key_for_dev_only")
    jwt_algorithm = "HS256"
    access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # --- Redis Configuration ---
    # Initialize comprehensive_config early to avoid UnboundLocalError
    comprehensive_config = {}
    
    # Load from comprehensive config first, then environment variables, then defaults
    if comprehensive_config and 'Redis' in comprehensive_config:
        redis_config = comprehensive_config.get('Redis', {})
        redis_host = os.getenv("REDIS_HOST", redis_config.get('redis_host', 'localhost'))
        redis_port = int(os.getenv("REDIS_PORT", redis_config.get('redis_port', '6379')))
        redis_db = int(os.getenv("REDIS_DB", redis_config.get('redis_db', '0')))
        cache_ttl = int(os.getenv("CACHE_TTL", redis_config.get('cache_ttl', '300')))
        redis_enabled = os.getenv("REDIS_ENABLED", str(redis_config.get('redis_enabled', 'false'))).lower() == "true"
    else:
        # Fallback to environment variables and defaults
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        cache_ttl = int(os.getenv("CACHE_TTL", "300"))
        redis_enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"
    
    redis_url = os.getenv("REDIS_URL", f"redis://{redis_host}:{redis_port}/{redis_db}")

    # Base directory for all user-specific data: ACTUAL_PROJECT_ROOT/Databases/user_databases/
    default_user_data_base_dir = ACTUAL_PROJECT_ROOT / "Databases" / "user_databases"
    user_data_base_dir_str = os.getenv("USER_DB_BASE_DIR", str(default_user_data_base_dir.resolve()))
    user_data_base_dir = Path(user_data_base_dir_str)

    # Main/central SQLite database: ACTUAL_PROJECT_ROOT/Databases/user_databases/databases/tldw.db
    default_main_db_path = (ACTUAL_PROJECT_ROOT / "Databases" / "user_databases" / f"{single_user_fixed_id}" / "tldw.db").resolve()
    default_database_url = f"sqlite:///{default_main_db_path}"
    database_url = os.getenv("DATABASE_URL", default_database_url)

    users_db_configured = os.getenv("USERS_DB_ENABLED", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Load comprehensive configurations (API keys, embedding settings, etc.)
    try:
        comprehensive_config = load_and_log_configs() # This function is already defined in your provided code
        if comprehensive_config is None:
            logger.error("Failed to load comprehensive_config, will use fallbacks for some settings.")
            comprehensive_config = {} # Ensure it's a dict to avoid errors on .get()
    except Exception as e:
        logger.error(f"Error loading comprehensive_config: {e}", exc_info=True)
        comprehensive_config = {}


    config_dict = {
        # General App
        "APP_MODE_STR": single_user_mode_str,
        "SINGLE_USER_MODE": single_user_mode,
        "LOG_LEVEL": log_level,
        "PROJECT_ROOT": ACTUAL_PROJECT_ROOT, # Centralized project root definition

        # Single User
        "SINGLE_USER_FIXED_ID": single_user_fixed_id,
        "SINGLE_USER_API_KEY": single_user_api_key,

        # Multi User / Auth
        "JWT_SECRET_KEY": jwt_secret_key,
        "JWT_ALGORITHM": jwt_algorithm,
        "ACCESS_TOKEN_EXPIRE_MINUTES": access_token_expire_minutes,
        "DATABASE_URL": database_url,
        "USER_DB_BASE_DIR": user_data_base_dir, # Renamed for clarity (was user_db_base_dir)
        "USERS_DB_CONFIGURED": users_db_configured,
        "SERVER_CLIENT_ID": SERVER_CLIENT_ID,

        # Redis Configuration
        "REDIS_HOST": redis_host,
        "REDIS_PORT": redis_port,
        "REDIS_DB": redis_db,
        "REDIS_URL": redis_url,
        "CACHE_TTL": cache_ttl,
        "REDIS_ENABLED": redis_enabled,

        # Chat Configuration - Load from config file with default
        "CHAT_DICT_MAX_TOKENS": int(
            comprehensive_config.get('Chat-Dictionaries', {}).get('max_tokens', '5000')
        ),

        # Web Scraping Configuration - Load from config file with default
        "STEALTH_WAIT_MS": int(
            comprehensive_config.get('Web-Scraping', {}).get('stealth_wait_ms', '5000')
        ),

        # Merge relevant parts from comprehensive_config
        # Embedding Config: support both 'embedding_config' and 'Embeddings' sections
        "EMBEDDING_CONFIG": (
            comprehensive_config.get("embedding_config")
            or comprehensive_config.get("Embeddings")
            or comprehensive_config.get("EMBEDDINGS")
            or {
                'embedding_provider': 'openai', # Fallback defaults
                'embedding_model': 'text-embedding-3-small',
                'onnx_model_path': "./Models/onnx_models/text-embedding-3-small.onnx",
                'model_dir': "./Models",
                'embedding_api_url': "http://localhost:8080/v1/embeddings",
                'embedding_api_key': '',
                'chunk_size': 400,
                'chunk_overlap': 200
            }
        ),
        # HuggingFace remote code allowlist (wildcards supported via fnmatch)
        # HuggingFace remote code allowlist (wildcards supported via fnmatch)
        # Precedence: ENV > config.txt (Embeddings.trusted_hf_remote_code_models) > default
        "TRUSTED_HF_REMOTE_CODE_MODELS": (lambda _env_val, _cfg: (
            [s.strip() for s in _env_val.split(",") if s.strip()] if _env_val is not None else (
                [s.strip() for s in str(_cfg).split(",") if s.strip()] if _cfg is not None else ["*stella*"]
            )
        ))(
            os.getenv("TRUSTED_HF_REMOTE_CODE_MODELS"),
            (
                (comprehensive_config.get('embedding_config') or {}).get('trusted_hf_remote_code_models')
                if isinstance(comprehensive_config, dict) else None
            )
        ),
        # --- HYDE/doc2query (per-chunk) feature flags ---
        "HYDE_ENABLED": (lambda v: (str(v).lower() in ("1","true","yes","on")))(os.getenv("HYDE_ENABLED", "false")),
        "HYDE_QUESTIONS_PER_CHUNK": int(os.getenv("HYDE_QUESTIONS_PER_CHUNK", "0")),
        "HYDE_PROVIDER": os.getenv("HYDE_PROVIDER"),
        "HYDE_MODEL": os.getenv("HYDE_MODEL"),
        "HYDE_TEMPERATURE": float(os.getenv("HYDE_TEMPERATURE", "0.2")),
        "HYDE_MAX_TOKENS": int(os.getenv("HYDE_MAX_TOKENS", "96")),
        "HYDE_LANGUAGE": os.getenv("HYDE_LANGUAGE", "auto"),
        "HYDE_PROMPT_VERSION": int(os.getenv("HYDE_PROMPT_VERSION", "1")),
        # Retrieval side HYDE controls
        "HYDE_WEIGHT_QUESTION_MATCH": float(os.getenv("HYDE_WEIGHT_QUESTION_MATCH", "0.05")),
        "HYDE_K_FRACTION": float(os.getenv("HYDE_K_FRACTION", "0.5")),
        "HYDE_ONLY_IF_NEEDED": (lambda v: (str(v).lower() in ("1","true","yes","on")))(os.getenv("HYDE_ONLY_IF_NEEDED", "true")),
        "HYDE_SCORE_FLOOR": float(os.getenv("HYDE_SCORE_FLOOR", "0.30")),
        "HYDE_DEDUPE_BY_PARENT": (lambda v: (str(v).lower() in ("1","true","yes","on")))(os.getenv("HYDE_DEDUPE_BY_PARENT", "false")),
        # Add other configs from comprehensive_config as needed
        "OPENAI_API_KEY": comprehensive_config.get("openai_api", {}).get("api_key", os.getenv("OPENAI_API_KEY")),
        # You can continue to merge other specific keys or whole sections
        "COMPREHENSIVE_CONFIG_RAW": comprehensive_config, # Store the raw one if needed elsewhere

        # Ephemeral cleanup worker (evals/rag pipeline ephemeral collections)
        "EPHEMERAL_CLEANUP_ENABLED": os.getenv("EPHEMERAL_CLEANUP_ENABLED", "false").lower() == "true",
        "EPHEMERAL_CLEANUP_INTERVAL_SEC": int(os.getenv("EPHEMERAL_CLEANUP_INTERVAL_SEC", "1800")),

        # Ingestion-time claims (factual statements) - env overrides config.txt [Claims]
        **(lambda: (
            (lambda _cp: (
                (lambda _env: (
                    {
                        "ENABLE_INGESTION_CLAIMS": (
                            (_env.get("ENABLE_INGESTION_CLAIMS").lower() == "true") if _env.get("ENABLE_INGESTION_CLAIMS") is not None else (
                                (_cp.getboolean('Claims', 'ENABLE_INGESTION_CLAIMS', fallback=False) if _cp else False)
                            )
                        ),
                        "CLAIM_EXTRACTOR_MODE": (
                            _env.get("CLAIM_EXTRACTOR_MODE") if _env.get("CLAIM_EXTRACTOR_MODE") is not None else (
                                _cp.get('Claims', 'CLAIM_EXTRACTOR_MODE', fallback='heuristic') if _cp else 'heuristic'
                            )
                        ),
                        "CLAIMS_MAX_PER_CHUNK": (
                            int(_env.get("CLAIMS_MAX_PER_CHUNK")) if _env.get("CLAIMS_MAX_PER_CHUNK") is not None else (
                                _cp.getint('Claims', 'CLAIMS_MAX_PER_CHUNK', fallback=3) if _cp else 3
                            )
                        ),
                        "CLAIMS_EMBED": (
                            (_env.get("CLAIMS_EMBED").lower() == "true") if _env.get("CLAIMS_EMBED") is not None else (
                                _cp.getboolean('Claims', 'CLAIMS_EMBED', fallback=False) if _cp else False
                            )
                        ),
                        "CLAIMS_EMBED_MODEL_ID": (
                            _env.get("CLAIMS_EMBED_MODEL_ID") if _env.get("CLAIMS_EMBED_MODEL_ID") is not None else (
                                _cp.get('Claims', 'CLAIMS_EMBED_MODEL_ID', fallback='') if _cp else ''
                            )
                        ),
                        # Claims LLM selection (provider + optional knobs)
                        "CLAIMS_LLM_PROVIDER": (
                            _env.get("CLAIMS_LLM_PROVIDER") if _env.get("CLAIMS_LLM_PROVIDER") is not None else (
                                _cp.get('Claims', 'CLAIMS_LLM_PROVIDER', fallback='') if _cp else ''
                            )
                        ),
                        "CLAIMS_LLM_MODEL": (
                            _env.get("CLAIMS_LLM_MODEL") if _env.get("CLAIMS_LLM_MODEL") is not None else (
                                _cp.get('Claims', 'CLAIMS_LLM_MODEL', fallback='') if _cp else ''
                            )
                        ),
                        "CLAIMS_LLM_TEMPERATURE": (
                            (float(_env.get("CLAIMS_LLM_TEMPERATURE")) if _env.get("CLAIMS_LLM_TEMPERATURE") is not None else (
                                float(_cp.get('Claims', 'CLAIMS_LLM_TEMPERATURE', fallback='0.1')) if _cp else 0.1
                            ))
                        ),
                        # Optional: allow local NER model name in config for users who want NER
                        "CLAIMS_LOCAL_NER_MODEL": (
                            _env.get("CLAIMS_LOCAL_NER_MODEL") if _env.get("CLAIMS_LOCAL_NER_MODEL") is not None else (
                                _cp.get('Claims', 'CLAIMS_LOCAL_NER_MODEL', fallback='en_core_web_sm') if _cp else 'en_core_web_sm'
                            )
                        ),
                    }
                ))({
                    k: os.getenv(k) for k in [
                        "ENABLE_INGESTION_CLAIMS", "CLAIM_EXTRACTOR_MODE", "CLAIMS_MAX_PER_CHUNK",
                        "CLAIMS_EMBED", "CLAIMS_EMBED_MODEL_ID", "CLAIMS_LLM_PROVIDER",
                        "CLAIMS_LLM_TEMPERATURE", "CLAIMS_LOCAL_NER_MODEL"
                    ]
                })
            ))(load_comprehensive_config())
        ))(),

        # Claims periodic rebuild worker
        "CLAIMS_REBUILD_ENABLED": os.getenv("CLAIMS_REBUILD_ENABLED", "false").lower() == "true",
        "CLAIMS_REBUILD_INTERVAL_SEC": int(os.getenv("CLAIMS_REBUILD_INTERVAL_SEC", "3600")),
        # Policy: missing | all | stale (stale requires CLAIMS_STALE_DAYS)
        "CLAIMS_REBUILD_POLICY": os.getenv("CLAIMS_REBUILD_POLICY", "missing"),
        "CLAIMS_STALE_DAYS": int(os.getenv("CLAIMS_STALE_DAYS", "7")),

        # Contextual retrieval defaults (parent/siblings) - from env or config.txt [RAG] section
        "RAG_CONTEXTUAL_DEFAULTS": (lambda: (
            # Build contextual defaults from env first, then config.txt [RAG] section
            (lambda _envs, _cfg: {
                "include_parent_document": (
                    (_envs.get("RAG_INCLUDE_PARENT_DOCUMENT").lower() == "true") if _envs.get("RAG_INCLUDE_PARENT_DOCUMENT") is not None else (
                        str(_cfg.get('include_parent_document', 'false')).lower() == 'true'
                    )
                ),
                "parent_max_tokens": (
                    int(_envs.get("RAG_PARENT_MAX_TOKENS")) if _envs.get("RAG_PARENT_MAX_TOKENS") is not None else int(str(_cfg.get('parent_max_tokens', '1200')) or 1200)
                ),
                "include_sibling_chunks": (
                    (_envs.get("RAG_INCLUDE_SIBLING_CHUNKS").lower() == "true") if _envs.get("RAG_INCLUDE_SIBLING_CHUNKS") is not None else (
                        str(_cfg.get('include_sibling_chunks', 'false')).lower() == 'true'
                    )
                ),
                "sibling_window": (
                    int(_envs.get("RAG_SIBLING_WINDOW")) if _envs.get("RAG_SIBLING_WINDOW") is not None else int(str(_cfg.get('sibling_window', '1')) or 1)
                ),
            })(
                {
                    "RAG_INCLUDE_PARENT_DOCUMENT": os.getenv("RAG_INCLUDE_PARENT_DOCUMENT"),
                    "RAG_PARENT_MAX_TOKENS": os.getenv("RAG_PARENT_MAX_TOKENS"),
                    "RAG_INCLUDE_SIBLING_CHUNKS": os.getenv("RAG_INCLUDE_SIBLING_CHUNKS"),
                    "RAG_SIBLING_WINDOW": os.getenv("RAG_SIBLING_WINDOW"),
                },
                (lambda _cp: (
                    (lambda d: d)(
                        {k: (_cp.get('RAG', k, fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None)
                         for k in ['include_parent_document', 'parent_max_tokens', 'include_sibling_chunks', 'sibling_window']}
                    )
                ))(load_comprehensive_config())
            )
        ))(),

        # RAG LLM reranker configuration (provider/model)
        "RAG_LLM_RERANKER_PROVIDER": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llm_reranker_provider', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_LLM_RERANKER_PROVIDER'), load_comprehensive_config()),
        "RAG_LLM_RERANKER_MODEL": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llm_reranker_model', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_LLM_RERANKER_MODEL'), load_comprehensive_config()),

        # RAG llama.cpp (GGUF) reranker configuration
        "RAG_LLAMA_RERANKER_BIN": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llama_reranker_binary', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_BIN'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_MODEL": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llama_reranker_model', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_MODEL'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_NGL": (lambda _env, _cp: (
            int(_env) if _env is not None else (
                int(_cp.get('RAG', 'llama_reranker_ngl', fallback='0')) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else 0
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_NGL'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_SEP": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llama_reranker_separator', fallback='<#sep#>') if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else '<#sep#>'
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_SEP'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_OUTPUT": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llama_reranker_output', fallback='json+') if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else 'json+'
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_OUTPUT'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_POOLING": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llama_reranker_pooling', fallback='last') if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else 'last'
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_POOLING'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_NORMALIZE": (lambda _env, _cp: (
            int(_env) if _env is not None else (
                int(_cp.get('RAG', 'llama_reranker_normalize', fallback='-1')) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else -1
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_NORMALIZE'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_MAX_DOC_CHARS": (lambda _env, _cp: (
            int(_env) if _env is not None else (
                int(_cp.get('RAG', 'llama_reranker_max_doc_chars', fallback='2000')) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else 2000
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_MAX_DOC_CHARS'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_TEMPLATE_MODE": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llama_reranker_template_mode', fallback='auto') if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else 'auto'
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_TEMPLATE_MODE'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_QUERY_PREFIX": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llama_reranker_query_prefix', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_QUERY_PREFIX'), load_comprehensive_config()),
        "RAG_LLAMA_RERANKER_DOC_PREFIX": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'llama_reranker_doc_prefix', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_LLAMA_RERANKER_DOC_PREFIX'), load_comprehensive_config()),

        # Transformers cross-encoder reranker defaults
        "RAG_TRANSFORMERS_RERANKER_MODEL": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'transformers_reranker_model', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_TRANSFORMERS_RERANKER_MODEL'), load_comprehensive_config()),

        # RAG HyDE configuration (provider/model)
        "RAG_HYDE_PROVIDER": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'hyde_provider', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_HYDE_PROVIDER'), load_comprehensive_config()),
        "RAG_HYDE_MODEL": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'hyde_model', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_HYDE_MODEL'), load_comprehensive_config()),

        # RAG default LLM (used for general lightweight tasks like query expansion/gap analysis)
        "RAG_DEFAULT_LLM_PROVIDER": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'default_llm_provider', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_DEFAULT_LLM_PROVIDER'), load_comprehensive_config()),
        "RAG_DEFAULT_LLM_MODEL": (lambda _env, _cp: (
            _env if _env is not None else (
                _cp.get('RAG', 'default_llm_model', fallback=None) if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else None
            )
        ))(os.getenv('RAG_DEFAULT_LLM_MODEL'), load_comprehensive_config()),

        # RAG default FTS level ('media' or 'chunk')
        "RAG_DEFAULT_FTS_LEVEL": (lambda _env, _cp: (
            (_env.lower() if isinstance(_env, str) else None) if _env is not None else (
                (_cp.get('RAG', 'default_fts_level', fallback='media').lower() if _cp and hasattr(_cp, 'get') and _cp.has_section('RAG') else 'media')
            )
        ))(os.getenv('RAG_DEFAULT_FTS_LEVEL'), load_comprehensive_config()),

        # --- Feature Flags: Personalization & Persona Agent ---
        # Personalization
        "PERSONALIZATION_ENABLED": (lambda _cp: (
            _cp.getboolean('personalization', 'enabled', fallback=True) if _cp and hasattr(_cp, 'has_section') and _cp.has_section('personalization') else True
        ))(load_comprehensive_config()),
        "PERSONALIZATION_ALPHA": (lambda _cp: (
            float(_cp.get('personalization', 'alpha', fallback='0.2')) if _cp and _cp.has_section('personalization') else 0.2
        ))(load_comprehensive_config()),
        "PERSONALIZATION_BETA": (lambda _cp: (
            float(_cp.get('personalization', 'beta', fallback='0.6')) if _cp and _cp.has_section('personalization') else 0.6
        ))(load_comprehensive_config()),
        "PERSONALIZATION_GAMMA": (lambda _cp: (
            float(_cp.get('personalization', 'gamma', fallback='0.2')) if _cp and _cp.has_section('personalization') else 0.2
        ))(load_comprehensive_config()),
        "PERSONALIZATION_RECENCY_HALF_LIFE_DAYS": (lambda _cp: (
            int(_cp.get('personalization', 'recency_half_life_days', fallback='14')) if _cp and _cp.has_section('personalization') else 14
        ))(load_comprehensive_config()),

        # Persona Agent and RBAC
        "PERSONA_ENABLED": (lambda _cp: (
            _cp.getboolean('persona', 'enabled', fallback=True) if _cp and hasattr(_cp, 'has_section') and _cp.has_section('persona') else True
        ))(load_comprehensive_config()),
        "PERSONA_DEFAULT_PERSONA": (lambda _cp: (
            _cp.get('persona', 'default_persona', fallback='Research Assistant') if _cp and _cp.has_section('persona') else 'Research Assistant'
        ))(load_comprehensive_config()),
        "PERSONA_VOICE": (lambda _cp: (
            _cp.get('persona', 'voice', fallback='default') if _cp and _cp.has_section('persona') else 'default'
        ))(load_comprehensive_config()),
        "PERSONA_STT": (lambda _cp: (
            _cp.get('persona', 'stt', fallback='faster_whisper') if _cp and _cp.has_section('persona') else 'faster_whisper'
        ))(load_comprehensive_config()),
        "PERSONA_MAX_TOOL_STEPS": (lambda _cp: (
            int(_cp.get('persona', 'max_tool_steps', fallback='3')) if _cp and _cp.has_section('persona') else 3
        ))(load_comprehensive_config()),
        "PERSONA_RBAC_ALLOW_EXPORT": (lambda _cp: (
            _cp.getboolean('persona.rbac', 'allow_export', fallback=False) if _cp and _cp.has_section('persona.rbac') else False
        ))(load_comprehensive_config()),
        "PERSONA_RBAC_ALLOW_DELETE": (lambda _cp: (
            _cp.getboolean('persona.rbac', 'allow_delete', fallback=False) if _cp and _cp.has_section('persona.rbac') else False
        ))(load_comprehensive_config()),
    }

    # --- Warnings ---
    if config_dict["SINGLE_USER_MODE"]:
        if not config_dict["SINGLE_USER_API_KEY"]:
            logger.error(
                "SINGLE_USER_API_KEY is not configured. The server will refuse to start in single-user mode.\n"
                "Run `python -m tldw_Server_API.app.core.AuthNZ.initialize` and generate secure keys, "
                "then set SINGLE_USER_API_KEY in your environment or .env file."
            )
    if not config_dict["SINGLE_USER_MODE"] and config_dict["JWT_SECRET_KEY"] == "a_very_insecure_default_secret_key_for_dev_only":
        logger.critical("SECURITY WARNING: Using default JWT_SECRET_KEY in multi-user mode. Set a strong JWT_SECRET_KEY environment variable!")
    if not config_dict["SINGLE_USER_MODE"] and not config_dict["USERS_DB_CONFIGURED"]:
         logger.warning("Multi-user mode enabled (APP_MODE=multi), but USERS_DB_ENABLED is not 'true'. User authentication will likely fail.")

    # Create necessary directories if they don't exist
    # Ensure main SQLite database directory exists
    if config_dict["DATABASE_URL"].startswith("sqlite:///"):
        main_db_file_path_str = config_dict["DATABASE_URL"].replace("sqlite:///", "")
        # Path() can take a full file path string.
        main_db_file_path = Path(main_db_file_path_str)
        # Ensure the path is absolute if it was constructed from env var and relative
        if not main_db_file_path.is_absolute():
             main_db_file_path = ACTUAL_PROJECT_ROOT / main_db_file_path
        main_db_file_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured main SQLite database directory exists: {main_db_file_path.parent}")

    # Ensure USER_DB_BASE_DIR exists (base for user-specific SQLite and ChromaDB)
    config_dict["USER_DB_BASE_DIR"].mkdir(parents=True, exist_ok=True)
    logger.info(f"Ensured user data base directory exists: {config_dict['USER_DB_BASE_DIR']}")

    return config_dict


def load_comprehensive_config():
    current_file_path = Path(__file__).resolve()
    # Correct project_root calculation:
    # __file__ is .../tldw_Server_API/app/core/config.py
    # .parent -> .../app/core
    # .parent.parent -> .../app
    # .parent.parent.parent -> .../tldw_Server_API (This is the project root)
    project_root = current_file_path.parent.parent.parent

    # Load .env file if it exists (API keys should be here)
    env_path = project_root / 'Config_Files' / '.env'
    if env_path.exists():
        logger.info(f"Loading environment variables from: {str(env_path)}")
        load_dotenv(dotenv_path=str(env_path), override=False)
    else:
        logger.info(f"No .env file found at {str(env_path)}, will use config.txt and system environment variables")

    config_path_obj = project_root / 'Config_Files' / 'config.txt'

    logger.info(f"Attempting to load comprehensive config from: {str(config_path_obj)}")

    if not config_path_obj.exists():
        logger.error(f"Config file not found at {str(config_path_obj)}")
        raise FileNotFoundError(f"Config file not found at {str(config_path_obj)}")

    config_parser = configparser.ConfigParser()
    try:
        config_parser.read(config_path_obj)  # configparser can read Path objects directly
    except configparser.Error as e:
        logger.error(f"Error parsing config file {str(config_path_obj)}: {e}", exc_info=True)
        raise  # Re-raise the parsing error to be caught by load_and_log_configs

    logger.info(f"load_comprehensive_config(): Sections found in config: {config_parser.sections()}")
    return config_parser


@lru_cache(maxsize=1)
def should_disable_cors() -> bool:
    """Return True if CORS middleware should be skipped."""
    env_value = os.getenv("DISABLE_CORS")
    if env_value is not None:
        return env_value.strip().lower() in {"true", "1", "yes", "on"}

    try:
        config_parser = load_comprehensive_config()
        if config_parser.has_section('Server'):
            return config_parser.getboolean('Server', 'disable_cors', fallback=False)
    except Exception as exc:
        logger.debug(f"Unable to read disable_cors flag from config: {exc}")
    return False

def load_comprehensive_config_with_tts():
    """
    Load comprehensive configuration including TTS settings.
    
    Returns:
        Combined configuration object with TTS settings integrated
    """
    # Load main config
    config_parser = load_comprehensive_config()
    
    # Load TTS config
    tts_config = load_tts_config()
    
    # Create combined configuration object
    class CombinedConfig:
        def __init__(self, config_parser: configparser.ConfigParser, tts_config: Dict[str, Any]):
            self.config_parser = config_parser
            self.tts_config = tts_config
        
        def get(self, section: str, key: str, fallback=None):
            """Get value from main config"""
            return self.config_parser.get(section, key, fallback=fallback)
        
        def has_section(self, section: str) -> bool:
            """Check if section exists in main config"""
            return self.config_parser.has_section(section)
        
        def has_option(self, section: str, key: str) -> bool:
            """Check if option exists in main config"""
            return self.config_parser.has_option(section, key)
        
        def items(self, section: str):
            """Get items from main config section"""
            return self.config_parser.items(section)
        
        def sections(self):
            """Get sections from main config"""
            return self.config_parser.sections()
        
        def get_tts_config(self) -> Dict[str, Any]:
            """Get TTS configuration"""
            # Merge with API keys from main config for convenience
            merged_tts = self.tts_config.copy()
            
            # Add API keys if available
            if self.config_parser.has_option('API', 'openai_api_key'):
                merged_tts['openai_api_key'] = self.config_parser.get('API', 'openai_api_key')
            if self.config_parser.has_option('API', 'elevenlabs_api_key'):
                merged_tts['elevenlabs_api_key'] = self.config_parser.get('API', 'elevenlabs_api_key')
            
            return merged_tts
    
    return CombinedConfig(config_parser, tts_config)

def load_and_log_configs():
    logger.debug("load_and_log_configs(): Loading and logging configurations...")
    try:
        # The 'config' variable below should be the result from load_comprehensive_config()
        config_parser_object = load_comprehensive_config()

        # This check might be redundant if load_comprehensive_config always raises on critical failure
        if config_parser_object is None:
            logger.error("Comprehensive config object is None, cannot proceed")  # Changed to logger
            return None
        # API Keys - Check environment variables first, then config file
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY') or config_parser_object.get('API', 'anthropic_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded Anthropic API Key: {anthropic_api_key[:5]}...{anthropic_api_key[-5:] if anthropic_api_key else None}")

        cohere_api_key = os.getenv('COHERE_API_KEY') or config_parser_object.get('API', 'cohere_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded Cohere API Key: {cohere_api_key[:5]}...{cohere_api_key[-5:] if cohere_api_key else None}")

        groq_api_key = os.getenv('GROQ_API_KEY') or config_parser_object.get('API', 'groq_api_key', fallback=None)
        # logging.debug(f"Loaded Groq API Key: {groq_api_key[:5]}...{groq_api_key[-5:] if groq_api_key else None}")

        openai_api_key = os.getenv('OPENAI_API_KEY') or config_parser_object.get('API', 'openai_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded OpenAI API Key: {openai_api_key[:5]}...{openai_api_key[-5:] if openai_api_key else None}")

        huggingface_api_key = os.getenv('HUGGINGFACE_API_KEY') or config_parser_object.get('API', 'huggingface_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded HuggingFace API Key: {huggingface_api_key[:5]}...{huggingface_api_key[-5:] if huggingface_api_key else None}")

        openrouter_api_key = os.getenv('OPENROUTER_API_KEY') or config_parser_object.get('API', 'openrouter_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded OpenRouter API Key: {openrouter_api_key[:5]}...{openrouter_api_key[-5:] if openrouter_api_key else None}")

        deepseek_api_key = os.getenv('DEEPSEEK_API_KEY') or config_parser_object.get('API', 'deepseek_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded DeepSeek API Key: {deepseek_api_key[:5]}...{deepseek_api_key[-5:] if deepseek_api_key else None}")

        qwen_api_key = os.getenv('QWEN_API_KEY') or config_parser_object.get('API', 'qwen_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded Qwen API Key: {qwen_api_key[:5]}...{qwen_api_key[-5:] if qwen_api_key else None}")

        mistral_api_key = os.getenv('MISTRAL_API_KEY') or config_parser_object.get('API', 'mistral_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded Mistral API Key: {mistral_api_key[:5]}...{mistral_api_key[-5:] if mistral_api_key else None}")

        google_api_key = os.getenv('GOOGLE_API_KEY') or config_parser_object.get('API', 'google_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded Google API Key: {google_api_key[:5]}...{google_api_key[-5:] if google_api_key else None}")

        elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY') or config_parser_object.get('API', 'elevenlabs_api_key', fallback=None)
        # logging.debug(
        #     f"Loaded elevenlabs API Key: {elevenlabs_api_key[:5]}...{elevenlabs_api_key[-5:] if elevenlabs_api_key else None}")

        # LLM API Settings - streaming / temperature / top_p / min_p
        # Anthropic
        anthropic_model = config_parser_object.get('API', 'anthropic_model', fallback='claude-3-5-sonnet-20240620')
        anthropic_streaming = config_parser_object.get('API', 'anthropic_streaming', fallback='False')
        anthropic_temperature = config_parser_object.get('API', 'anthropic_temperature', fallback='0.7')
        anthropic_top_p = config_parser_object.get('API', 'anthropic_top_p', fallback='0.95')
        anthropic_top_k = config_parser_object.get('API', 'anthropic_top_k', fallback='100')
        anthropic_max_tokens = config_parser_object.get('API', 'anthropic_max_tokens', fallback='4096')
        anthropic_api_timeout = config_parser_object.get('API', 'anthropic_api_timeout', fallback='90')
        anthropic_api_retries = config_parser_object.get('API', 'anthropic_api_retry', fallback='3')
        anthropic_api_retry_delay = config_parser_object.get('API', 'anthropic_api_retry_delay', fallback='5')

        # Cohere
        cohere_streaming = config_parser_object.get('API', 'cohere_streaming', fallback='False')
        cohere_temperature = config_parser_object.get('API', 'cohere_temperature', fallback='0.7')
        cohere_max_p = config_parser_object.get('API', 'cohere_max_p', fallback='0.95')
        cohere_top_k = config_parser_object.get('API', 'cohere_top_k', fallback='100')
        cohere_model = config_parser_object.get('API', 'cohere_model', fallback='command-r-plus')
        cohere_max_tokens = config_parser_object.get('API', 'cohere_max_tokens', fallback='4096')
        cohere_api_timeout = config_parser_object.get('API', 'cohere_api_timeout', fallback='90')
        cohere_api_retries = config_parser_object.get('API', 'cohere_api_retry', fallback='3')
        cohere_api_retry_delay = config_parser_object.get('API', 'cohere_api_retry_delay', fallback='5')

        # Deepseek
        deepseek_streaming = config_parser_object.get('API', 'deepseek_streaming', fallback='False')
        deepseek_temperature = config_parser_object.get('API', 'deepseek_temperature', fallback='0.7')
        deepseek_top_p = config_parser_object.get('API', 'deepseek_top_p', fallback='0.95')
        deepseek_min_p = config_parser_object.get('API', 'deepseek_min_p', fallback='0.05')
        deepseek_model = config_parser_object.get('API', 'deepseek_model', fallback='deepseek-chat')
        deepseek_max_tokens = config_parser_object.get('API', 'deepseek_max_tokens', fallback='4096')
        deepseek_api_timeout = config_parser_object.get('API', 'deepseek_api_timeout', fallback='90')
        deepseek_api_retries = config_parser_object.get('API', 'deepseek_api_retry', fallback='3')
        deepseek_api_retry_delay = config_parser_object.get('API', 'deepseek_api_retry_delay', fallback='5')

        # Qwen (DashScope-compatible)
        qwen_model = config_parser_object.get('API', 'qwen_model', fallback='qwen-plus')
        qwen_streaming = config_parser_object.get('API', 'qwen_streaming', fallback='True')
        qwen_temperature = config_parser_object.get('API', 'qwen_temperature', fallback='0.7')
        qwen_top_p = config_parser_object.get('API', 'qwen_top_p', fallback='0.8')
        qwen_max_tokens = config_parser_object.get('API', 'qwen_max_tokens', fallback='4096')
        qwen_api_timeout = config_parser_object.get('API', 'qwen_api_timeout', fallback='90')
        qwen_api_retries = config_parser_object.get('API', 'qwen_api_retry', fallback='3')
        qwen_api_retry_delay = config_parser_object.get('API', 'qwen_api_retry_delay', fallback='1')
        qwen_api_base_url = config_parser_object.get(
            'API', 'qwen_api_base_url', fallback='https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
        )

        # Groq
        groq_model = config_parser_object.get('API', 'groq_model', fallback='llama3-70b-8192')
        groq_streaming = config_parser_object.get('API', 'groq_streaming', fallback='False')
        groq_temperature = config_parser_object.get('API', 'groq_temperature', fallback='0.7')
        groq_top_p = config_parser_object.get('API', 'groq_top_p', fallback='0.95')
        groq_max_tokens = config_parser_object.get('API', 'groq_max_tokens', fallback='4096')
        groq_api_timeout = config_parser_object.get('API', 'groq_api_timeout', fallback='90')
        groq_api_retries = config_parser_object.get('API', 'groq_api_retry', fallback='3')
        groq_api_retry_delay = config_parser_object.get('API', 'groq_api_retry_delay', fallback='5')

        # Google
        google_model = config_parser_object.get('API', 'google_model', fallback='gemini-1.5-pro')
        google_streaming = config_parser_object.get('API', 'google_streaming', fallback='False')
        google_temperature = config_parser_object.get('API', 'google_temperature', fallback='0.7')
        google_top_p = config_parser_object.get('API', 'google_top_p', fallback='0.95')
        google_min_p = config_parser_object.get('API', 'google_min_p', fallback='0.05')
        google_max_tokens = config_parser_object.get('API', 'google_max_tokens', fallback='4096')
        google_api_timeout = config_parser_object.get('API', 'google_api_timeout', fallback='90')
        google_api_retries = config_parser_object.get('API', 'google_api_retry', fallback='3')
        google_api_retry_delay = config_parser_object.get('API', 'google_api_retry_delay', fallback='5')

        # HuggingFace
        huggingface_use_router_url_format = config_parser_object.getboolean('API', 'huggingface_use_router_url_format', fallback=False)
        huggingface_router_base_url = config_parser_object.get('API', 'huggingface_router_base_url', fallback='https://router.huggingface.co/hf-inference')
        huggingface_api_base_url = config_parser_object.get('API', 'huggingface_api_base_url', fallback='https://router.huggingface.co/hf-inference/models')
        huggingface_model = config_parser_object.get('API', 'huggingface_model', fallback='/Qwen/Qwen3-235B-A22B')
        huggingface_streaming = config_parser_object.get('API', 'huggingface_streaming', fallback='False')
        huggingface_temperature = config_parser_object.get('API', 'huggingface_temperature', fallback='0.7')
        huggingface_top_p = config_parser_object.get('API', 'huggingface_top_p', fallback='0.95')
        huggingface_min_p = config_parser_object.get('API', 'huggingface_min_p', fallback='0.05')
        huggingface_max_tokens = config_parser_object.get('API', 'huggingface_max_tokens', fallback='4096')
        huggingface_api_timeout = config_parser_object.get('API', 'huggingface_api_timeout', fallback='90')
        huggingface_api_retries = config_parser_object.get('API', 'huggingface_api_retry', fallback='3')
        huggingface_api_retry_delay = config_parser_object.get('API', 'huggingface_api_retry_delay', fallback='5')

        # Mistral
        mistral_model = config_parser_object.get('API', 'mistral_model', fallback='mistral-large-latest')
        mistral_streaming = config_parser_object.get('API', 'mistral_streaming', fallback='False')
        mistral_temperature = config_parser_object.get('API', 'mistral_temperature', fallback='0.7')
        mistral_top_p = config_parser_object.get('API', 'mistral_top_p', fallback='0.95')
        mistral_max_tokens = config_parser_object.get('API', 'mistral_max_tokens', fallback='4096')
        mistral_api_timeout = config_parser_object.get('API', 'mistral_api_timeout', fallback='90')
        mistral_api_retries = config_parser_object.get('API', 'mistral_api_retry', fallback='3')
        mistral_api_retry_delay = config_parser_object.get('API', 'mistral_api_retry_delay', fallback='5')

        # OpenAI
        openai_model = config_parser_object.get('API', 'openai_model', fallback='gpt-4o')
        openai_streaming = config_parser_object.get('API', 'openai_streaming', fallback='False')
        openai_temperature = config_parser_object.get('API', 'openai_temperature', fallback='0.7')
        openai_top_p = config_parser_object.get('API', 'openai_top_p', fallback='0.95')
        openai_max_tokens = config_parser_object.get('API', 'openai_max_tokens', fallback='4096')
        openai_api_timeout = config_parser_object.get('API', 'openai_api_timeout', fallback='90')
        openai_api_retries = config_parser_object.get('API', 'openai_api_retry', fallback='3')
        openai_api_retry_delay = config_parser_object.get('API', 'openai_api_retry_delay', fallback='5')

        # OpenRouter
        openrouter_model = config_parser_object.get('API', 'openrouter_model', fallback='microsoft/wizardlm-2-8x22b')
        openrouter_streaming = config_parser_object.get('API', 'openrouter_streaming', fallback='False')
        openrouter_temperature = config_parser_object.get('API', 'openrouter_temperature', fallback='0.7')
        openrouter_top_p = config_parser_object.get('API', 'openrouter_top_p', fallback='0.95')
        openrouter_min_p = config_parser_object.get('API', 'openrouter_min_p', fallback='0.05')
        openrouter_top_k = config_parser_object.get('API', 'openrouter_top_k', fallback='100')
        openrouter_max_tokens = config_parser_object.get('API', 'openrouter_max_tokens', fallback='4096')
        openrouter_api_timeout = config_parser_object.get('API', 'openrouter_api_timeout', fallback='90')
        openrouter_api_retries = config_parser_object.get('API', 'openrouter_api_retry', fallback='3')
        openrouter_api_retry_delay = config_parser_object.get('API', 'openrouter_api_retry_delay', fallback='5')

        # Bedrock
        bedrock_api_key = os.getenv('BEDROCK_API_KEY') or os.getenv('AWS_BEARER_TOKEN_BEDROCK') or config_parser_object.get('API', 'bedrock_api_key', fallback=None)
        bedrock_region = os.getenv('BEDROCK_REGION') or config_parser_object.get('API', 'bedrock_region', fallback='us-west-2')
        bedrock_runtime_endpoint = os.getenv('BEDROCK_RUNTIME_ENDPOINT') or config_parser_object.get('API', 'bedrock_runtime_endpoint', fallback=None)
        bedrock_model = os.getenv('BEDROCK_MODEL') or config_parser_object.get('API', 'bedrock_model', fallback=None)
        bedrock_streaming = config_parser_object.get('API', 'bedrock_streaming', fallback='False')
        bedrock_temperature = config_parser_object.get('API', 'bedrock_temperature', fallback='0.7')
        bedrock_top_p = config_parser_object.get('API', 'bedrock_top_p', fallback='')
        bedrock_max_tokens = config_parser_object.get('API', 'bedrock_max_tokens', fallback='')
        bedrock_api_timeout = config_parser_object.get('API', 'bedrock_api_timeout', fallback='90')
        bedrock_api_retries = config_parser_object.get('API', 'bedrock_api_retry', fallback='3')
        bedrock_api_retry_delay = config_parser_object.get('API', 'bedrock_api_retry_delay', fallback='5')

        # Logging Checks for model loads
        # logging.debug(f"Loaded Anthropic Model: {anthropic_model}")
        # logging.debug(f"Loaded Cohere Model: {cohere_model}")
        # logging.debug(f"Loaded Groq Model: {groq_model}")
        # logging.debug(f"Loaded OpenAI Model: {openai_model}")
        # logging.debug(f"Loaded HuggingFace Model: {huggingface_model}")
        # logging.debug(f"Loaded OpenRouter Model: {openrouter_model}")
        # logging.debug(f"Loaded Deepseek Model: {deepseek_model}")
        # logging.debug(f"Loaded Mistral Model: {mistral_model}")

        # Local-Models
        kobold_api_ip = config_parser_object.get('Local-API', 'kobold_api_IP', fallback='http://127.0.0.1:5000/api/v1/generate')
        kobold_openai_api_IP = config_parser_object.get('Local-API', 'kobold_openai_api_IP', fallback='http://127.0.0.1:5001/v1/chat/completions')
        kobold_api_key = config_parser_object.get('Local-API', 'kobold_api_key', fallback='')
        kobold_streaming = config_parser_object.get('Local-API', 'kobold_streaming', fallback='False')
        kobold_temperature = config_parser_object.get('Local-API', 'kobold_temperature', fallback='0.7')
        kobold_top_p = config_parser_object.get('Local-API', 'kobold_top_p', fallback='0.95')
        kobold_top_k = config_parser_object.get('Local-API', 'kobold_top_k', fallback='100')
        kobold_max_tokens = config_parser_object.get('Local-API', 'kobold_max_tokens', fallback='4096')
        kobold_api_timeout = config_parser_object.get('Local-API', 'kobold_api_timeout', fallback='90')
        kobold_api_retries = config_parser_object.get('Local-API', 'kobold_api_retry', fallback='3')
        kobold_api_retry_delay = config_parser_object.get('Local-API', 'kobold_api_retry_delay', fallback='5')

        llama_api_IP = config_parser_object.get('Local-API', 'llama_api_IP', fallback='http://127.0.0.1:8080/v1/chat/completions')
        llama_api_key = config_parser_object.get('Local-API', 'llama_api_key', fallback='')
        llama_streaming = config_parser_object.get('Local-API', 'llama_streaming', fallback='False')
        llama_temperature = config_parser_object.get('Local-API', 'llama_temperature', fallback='0.7')
        llama_top_p = config_parser_object.get('Local-API', 'llama_top_p', fallback='0.95')
        llama_min_p = config_parser_object.get('Local-API', 'llama_min_p', fallback='0.05')
        llama_top_k = config_parser_object.get('Local-API', 'llama_top_k', fallback='100')
        llama_max_tokens = config_parser_object.get('Local-API', 'llama_max_tokens', fallback='4096')
        llama_api_timeout = config_parser_object.get('Local-API', 'llama_api_timeout', fallback='90')
        llama_api_retries = config_parser_object.get('Local-API', 'llama_api_retry', fallback='3')
        llama_api_retry_delay = config_parser_object.get('Local-API', 'llama_api_retry_delay', fallback='5')

        ooba_api_IP = config_parser_object.get('Local-API', 'ooba_api_IP', fallback='http://127.0.0.1:5000/v1/chat/completions')
        ooba_api_key = config_parser_object.get('Local-API', 'ooba_api_key', fallback='')
        ooba_streaming = config_parser_object.get('Local-API', 'ooba_streaming', fallback='False')
        ooba_temperature = config_parser_object.get('Local-API', 'ooba_temperature', fallback='0.7')
        ooba_top_p = config_parser_object.get('Local-API', 'ooba_top_p', fallback='0.95')
        ooba_min_p = config_parser_object.get('Local-API', 'ooba_min_p', fallback='0.05')
        ooba_top_k = config_parser_object.get('Local-API', 'ooba_top_k', fallback='100')
        ooba_max_tokens = config_parser_object.get('Local-API', 'ooba_max_tokens', fallback='4096')
        ooba_api_timeout = config_parser_object.get('Local-API', 'ooba_api_timeout', fallback='90')
        ooba_api_retries = config_parser_object.get('Local-API', 'ooba_api_retry', fallback='3')
        ooba_api_retry_delay = config_parser_object.get('Local-API', 'ooba_api_retry_delay', fallback='5')

        tabby_api_IP = config_parser_object.get('Local-API', 'tabby_api_IP', fallback='http://127.0.0.1:5000/api/v1/generate')
        tabby_api_key = config_parser_object.get('Local-API', 'tabby_api_key', fallback=None)
        tabby_model = config_parser_object.get('models', 'tabby_model', fallback=None)
        tabby_streaming = config_parser_object.get('Local-API', 'tabby_streaming', fallback='False')
        tabby_temperature = config_parser_object.get('Local-API', 'tabby_temperature', fallback='0.7')
        tabby_top_p = config_parser_object.get('Local-API', 'tabby_top_p', fallback='0.95')
        tabby_top_k = config_parser_object.get('Local-API', 'tabby_top_k', fallback='100')
        tabby_min_p = config_parser_object.get('Local-API', 'tabby_min_p', fallback='0.05')
        tabby_max_tokens = config_parser_object.get('Local-API', 'tabby_max_tokens', fallback='4096')
        tabby_api_timeout = config_parser_object.get('Local-API', 'tabby_api_timeout', fallback='90')
        tabby_api_retries = config_parser_object.get('Local-API', 'tabby_api_retry', fallback='3')
        tabby_api_retry_delay = config_parser_object.get('Local-API', 'tabby_api_retry_delay', fallback='5')

        vllm_api_url = config_parser_object.get('Local-API', 'vllm_api_IP', fallback='http://127.0.0.1:500/api/v1/chat/completions')
        vllm_api_key = config_parser_object.get('Local-API', 'vllm_api_key', fallback=None)
        vllm_model = config_parser_object.get('Local-API', 'vllm_model', fallback=None)
        vllm_streaming = config_parser_object.get('Local-API', 'vllm_streaming', fallback='False')
        vllm_temperature = config_parser_object.get('Local-API', 'vllm_temperature', fallback='0.7')
        vllm_top_p = config_parser_object.get('Local-API', 'vllm_top_p', fallback='0.95')
        vllm_top_k = config_parser_object.get('Local-API', 'vllm_top_k', fallback='100')
        vllm_min_p = config_parser_object.get('Local-API', 'vllm_min_p', fallback='0.05')
        vllm_max_tokens = config_parser_object.get('Local-API', 'vllm_max_tokens', fallback='4096')
        vllm_api_timeout = config_parser_object.get('Local-API', 'vllm_api_timeout', fallback='90')
        vllm_api_retries = config_parser_object.get('Local-API', 'vllm_api_retry', fallback='3')
        vllm_api_retry_delay = config_parser_object.get('Local-API', 'vllm_api_retry_delay', fallback='5')

        ollama_api_url = config_parser_object.get('Local-API', 'ollama_api_IP', fallback='http://127.0.0.1:11434/api/generate')
        ollama_api_key = config_parser_object.get('Local-API', 'ollama_api_key', fallback=None)
        ollama_model = config_parser_object.get('Local-API', 'ollama_model', fallback=None)
        ollama_streaming = config_parser_object.get('Local-API', 'ollama_streaming', fallback='False')
        ollama_temperature = config_parser_object.get('Local-API', 'ollama_temperature', fallback='0.7')
        ollama_top_p = config_parser_object.get('Local-API', 'ollama_top_p', fallback='0.95')
        ollama_max_tokens = config_parser_object.get('Local-API', 'ollama_max_tokens', fallback='4096')
        ollama_api_timeout = config_parser_object.get('Local-API', 'ollama_api_timeout', fallback='90')
        ollama_api_retries = config_parser_object.get('Local-API', 'ollama_api_retry', fallback='3')
        ollama_api_retry_delay = config_parser_object.get('Local-API', 'ollama_api_retry_delay', fallback='5')

        aphrodite_api_url = config_parser_object.get('Local-API', 'aphrodite_api_IP', fallback='http://127.0.0.1:8080/v1/chat/completions')
        aphrodite_api_key = config_parser_object.get('Local-API', 'aphrodite_api_key', fallback='')
        aphrodite_model = config_parser_object.get('Local-API', 'aphrodite_model', fallback='')
        aphrodite_max_tokens = config_parser_object.get('Local-API', 'aphrodite_max_tokens', fallback='4096')
        aphrodite_streaming = config_parser_object.get('Local-API', 'aphrodite_streaming', fallback='False')
        aphrodite_api_timeout = config_parser_object.get('Local-API', 'llama_api_timeout', fallback='90')
        aphrodite_api_retries = config_parser_object.get('Local-API', 'aphrodite_api_retry', fallback='3')
        aphrodite_api_retry_delay = config_parser_object.get('Local-API', 'aphrodite_api_retry_delay', fallback='5')

        custom_openai_api_key = config_parser_object.get('API', 'custom_openai_api_key', fallback=None)
        custom_openai_api_ip = config_parser_object.get('API', 'custom_openai_api_ip', fallback=None)
        custom_openai_api_model = config_parser_object.get('API', 'custom_openai_api_model', fallback=None)
        custom_openai_api_streaming = config_parser_object.get('API', 'custom_openai_api_streaming', fallback='False')
        custom_openai_api_temperature = config_parser_object.get('API', 'custom_openai_api_temperature', fallback='0.7')
        custom_openai_api_top_p = config_parser_object.get('API', 'custom_openai_api_top_p', fallback='0.95')
        custom_openai_api_min_p = config_parser_object.get('API', 'custom_openai_api_top_k', fallback='100')
        custom_openai_api_max_tokens = config_parser_object.get('API', 'custom_openai_api_max_tokens', fallback='4096')
        custom_openai_api_timeout = config_parser_object.get('API', 'custom_openai_api_timeout', fallback='90')
        custom_openai_api_retries = config_parser_object.get('API', 'custom_openai_api_retry', fallback='3')
        custom_openai_api_retry_delay = config_parser_object.get('API', 'custom_openai_api_retry_delay', fallback='5')

        # 2nd Custom OpenAI API
        custom_openai2_api_key = config_parser_object.get('API', 'custom_openai2_api_key', fallback=None)
        custom_openai2_api_ip = config_parser_object.get('API', 'custom_openai2_api_ip', fallback=None)
        custom_openai2_api_model = config_parser_object.get('API', 'custom_openai2_api_model', fallback=None)
        custom_openai2_api_streaming = config_parser_object.get('API', 'custom_openai2_api_streaming', fallback='False')
        custom_openai2_api_temperature = config_parser_object.get('API', 'custom_openai2_api_temperature', fallback='0.7')
        custom_openai2_api_top_p = config_parser_object.get('API', 'custom_openai_api2_top_p', fallback='0.95')
        custom_openai2_api_min_p = config_parser_object.get('API', 'custom_openai_api2_top_k', fallback='100')
        custom_openai2_api_max_tokens = config_parser_object.get('API', 'custom_openai2_api_max_tokens', fallback='4096')
        custom_openai2_api_timeout = config_parser_object.get('API', 'custom_openai2_api_timeout', fallback='90')
        custom_openai2_api_retries = config_parser_object.get('API', 'custom_openai2_api_retry', fallback='3')
        custom_openai2_api_retry_delay = config_parser_object.get('API', 'custom_openai2_api_retry_delay', fallback='5')

        # Logging Checks for Local API IP loads
        # logging.debug(f"Loaded Kobold API IP: {kobold_api_ip}")
        # logging.debug(f"Loaded Llama API IP: {llama_api_IP}")
        # logging.debug(f"Loaded Ooba API IP: {ooba_api_IP}")
        # logging.debug(f"Loaded Tabby API IP: {tabby_api_IP}")
        # logging.debug(f"Loaded VLLM API URL: {vllm_api_url}")

        # Retrieve default API choices from the configuration file
        default_api = config_parser_object.get('API', 'default_api', fallback='openai')

        # Retrieve LLM API settings from the configuration file
        local_api_retries = config_parser_object.get('Local-API', 'Settings', fallback='3')
        local_api_retry_delay = config_parser_object.get('Local-API', 'local_api_retry_delay', fallback='5')

        # Retrieve output paths from the configuration file
        output_path = config_parser_object.get('Paths', 'output_path', fallback='results')
        logger.trace(f"Output path set to: {output_path}")

        # Save video transcripts
        save_video_transcripts = config_parser_object.get('Paths', 'save_video_transcripts', fallback='True')

        # Retrieve logging settings from the configuration file
        log_level = config_parser_object.get('Logging', 'log_level', fallback='INFO')
        log_file = config_parser_object.get('Logging', 'log_file', fallback='./Logs/tldw_logs.json')
        log_metrics_file = config_parser_object.get('Logging', 'log_metrics_file', fallback='./Logs/tldw_metrics_logs.json')

        # Retrieve processing choice from the configuration file
        processing_choice = config_parser_object.get('Processing', 'processing_choice', fallback='cpu')
        logger.trace(f"Processing choice set to: {processing_choice}")

        # [Chunking]
        # # Chunking Defaults
        # #
        # # Default Chunking Options for each media type
        chunking_method = config_parser_object.get('Chunking', 'chunking_method', fallback='words')
        chunk_max_size = config_parser_object.get('Chunking', 'chunk_max_size', fallback='400')
        chunk_overlap = config_parser_object.get('Chunking', 'chunk_overlap', fallback='200')
        adaptive_chunking = config_parser_object.get('Chunking', 'adaptive_chunking', fallback='False')
        chunking_multi_level = config_parser_object.get('Chunking', 'chunking_multi_level', fallback='False')
        chunk_language = config_parser_object.get('Chunking', 'chunk_language', fallback='en')
        #
        # Article Chunking
        article_chunking_method = config_parser_object.get('Chunking', 'article_chunking_method', fallback='words')
        article_chunk_max_size = config_parser_object.get('Chunking', 'article_chunk_max_size', fallback='400')
        article_chunk_overlap = config_parser_object.get('Chunking', 'article_chunk_overlap', fallback='200')
        article_adaptive_chunking = config_parser_object.get('Chunking', 'article_adaptive_chunking', fallback='False')
        article_chunking_multi_level = config_parser_object.get('Chunking', 'article_chunking_multi_level', fallback='False')
        article_language = config_parser_object.get('Chunking', 'article_language', fallback='english')
        #
        # Audio file Chunking
        audio_chunking_method = config_parser_object.get('Chunking', 'audio_chunking_method', fallback='words')
        audio_chunk_max_size = config_parser_object.get('Chunking', 'audio_chunk_max_size', fallback='400')
        audio_chunk_overlap = config_parser_object.get('Chunking', 'audio_chunk_overlap', fallback='200')
        audio_adaptive_chunking = config_parser_object.get('Chunking', 'audio_adaptive_chunking', fallback='False')
        audio_chunking_multi_level = config_parser_object.get('Chunking', 'audio_chunking_multi_level', fallback='False')
        audio_language = config_parser_object.get('Chunking', 'audio_language', fallback='english')
        #
        # Book Chunking
        book_chunking_method = config_parser_object.get('Chunking', 'book_chunking_method', fallback='words')
        book_chunk_max_size = config_parser_object.get('Chunking', 'book_chunk_max_size', fallback='400')
        book_chunk_overlap = config_parser_object.get('Chunking', 'book_chunk_overlap', fallback='200')
        book_adaptive_chunking = config_parser_object.get('Chunking', 'book_adaptive_chunking', fallback='False')
        book_chunking_multi_level = config_parser_object.get('Chunking', 'book_chunking_multi_level', fallback='False')
        book_language = config_parser_object.get('Chunking', 'book_language', fallback='english')
        #
        # Document Chunking
        document_chunking_method = config_parser_object.get('Chunking', 'document_chunking_method', fallback='words')
        document_chunk_max_size = config_parser_object.get('Chunking', 'document_chunk_max_size', fallback='400')
        document_chunk_overlap = config_parser_object.get('Chunking', 'document_chunk_overlap', fallback='200')
        document_adaptive_chunking = config_parser_object.get('Chunking', 'document_adaptive_chunking', fallback='False')
        document_chunking_multi_level = config_parser_object.get('Chunking', 'document_chunking_multi_level', fallback='False')
        document_language = config_parser_object.get('Chunking', 'document_language', fallback='english')
        #
        # Mediawiki Article Chunking
        mediawiki_article_chunking_method = config_parser_object.get('Chunking', 'mediawiki_article_chunking_method', fallback='words')
        mediawiki_article_chunk_max_size = config_parser_object.get('Chunking', 'mediawiki_article_chunk_max_size', fallback='400')
        mediawiki_article_chunk_overlap = config_parser_object.get('Chunking', 'mediawiki_article_chunk_overlap', fallback='200')
        mediawiki_article_adaptive_chunking = config_parser_object.get('Chunking', 'mediawiki_article_adaptive_chunking', fallback='False')
        mediawiki_article_chunking_multi_level = config_parser_object.get('Chunking', 'mediawiki_article_chunking_multi_level', fallback='False')
        mediawiki_article_language = config_parser_object.get('Chunking', 'mediawiki_article_language', fallback='english')
        #
        # Mediawiki Dump Chunking
        mediawiki_dump_chunking_method = config_parser_object.get('Chunking', 'mediawiki_dump_chunking_method', fallback='words')
        mediawiki_dump_chunk_max_size = config_parser_object.get('Chunking', 'mediawiki_dump_chunk_max_size', fallback='400')
        mediawiki_dump_chunk_overlap = config_parser_object.get('Chunking', 'mediawiki_dump_chunk_overlap', fallback='200')
        mediawiki_dump_adaptive_chunking = config_parser_object.get('Chunking', 'mediawiki_dump_adaptive_chunking', fallback='False')
        mediawiki_dump_chunking_multi_level = config_parser_object.get('Chunking', 'mediawiki_dump_chunking_multi_level', fallback='False')
        mediawiki_dump_language = config_parser_object.get('Chunking', 'mediawiki_dump_language', fallback='english')
        #
        # Obsidian Note Chunking
        obsidian_note_chunking_method = config_parser_object.get('Chunking', 'obsidian_note_chunking_method', fallback='words')
        obsidian_note_chunk_max_size = config_parser_object.get('Chunking', 'obsidian_note_chunk_max_size', fallback='400')
        obsidian_note_chunk_overlap = config_parser_object.get('Chunking', 'obsidian_note_chunk_overlap', fallback='200')
        obsidian_note_adaptive_chunking = config_parser_object.get('Chunking', 'obsidian_note_adaptive_chunking', fallback='False')
        obsidian_note_chunking_multi_level = config_parser_object.get('Chunking', 'obsidian_note_chunking_multi_level', fallback='False')
        obsidian_note_language = config_parser_object.get('Chunking', 'obsidian_note_language', fallback='english')
        #
        # Podcast Chunking
        podcast_chunking_method = config_parser_object.get('Chunking', 'podcast_chunking_method', fallback='words')
        podcast_chunk_max_size = config_parser_object.get('Chunking', 'podcast_chunk_max_size', fallback='400')
        podcast_chunk_overlap = config_parser_object.get('Chunking', 'podcast_chunk_overlap', fallback='200')
        podcast_adaptive_chunking = config_parser_object.get('Chunking', 'podcast_adaptive_chunking', fallback='False')
        podcast_chunking_multi_level = config_parser_object.get('Chunking', 'podcast_chunking_multi_level', fallback='False')
        podcast_language = config_parser_object.get('Chunking', 'podcast_language', fallback='english')
        #
        # Text Chunking
        text_chunking_method = config_parser_object.get('Chunking', 'text_chunking_method', fallback='words')
        text_chunk_max_size = config_parser_object.get('Chunking', 'text_chunk_max_size', fallback='400')
        text_chunk_overlap = config_parser_object.get('Chunking', 'text_chunk_overlap', fallback='200')
        text_adaptive_chunking = config_parser_object.get('Chunking', 'text_adaptive_chunking', fallback='False')
        text_chunking_multi_level = config_parser_object.get('Chunking', 'text_chunking_multi_level', fallback='False')
        text_language = config_parser_object.get('Chunking', 'text_language', fallback='english')
        #
        # Video Transcription Chunking
        video_chunking_method = config_parser_object.get('Chunking', 'video_chunking_method', fallback='words')
        video_chunk_max_size = config_parser_object.get('Chunking', 'video_chunk_max_size', fallback='400')
        video_chunk_overlap = config_parser_object.get('Chunking', 'video_chunk_overlap', fallback='200')
        video_adaptive_chunking = config_parser_object.get('Chunking', 'video_adaptive_chunking', fallback='False')
        video_chunking_multi_level = config_parser_object.get('Chunking', 'video_chunking_multi_level', fallback='False')
        video_language = config_parser_object.get('Chunking', 'video_language', fallback='english')
        #
        # Proposition Chunking Defaults
        proposition_engine = config_parser_object.get('Chunking', 'proposition_engine', fallback='heuristic')
        proposition_prompt_profile = config_parser_object.get('Chunking', 'proposition_prompt_profile', fallback='generic')
        proposition_aggressiveness = config_parser_object.get('Chunking', 'proposition_aggressiveness', fallback='1')
        proposition_min_proposition_length = config_parser_object.get('Chunking', 'proposition_min_proposition_length', fallback='15')
        #
        chunking_types = 'article', 'audio', 'book', 'document', 'mediawiki_article', 'mediawiki_dump', 'obsidian_note', 'podcast', 'text', 'video'

        # Retrieve Embedding model settings from the configuration file
        # Default to Qwen3-Embedding-4B-GGUF if not specified
        embedding_model = config_parser_object.get('Embeddings', 'embedding_model', fallback='Qwen/Qwen3-Embedding-4B-GGUF')
        logger.trace(f"Embedding model set to: {embedding_model}")
        embedding_provider = config_parser_object.get('Embeddings', 'embedding_provider', fallback='huggingface')
        # Note: duplicate line removed - embedding_model already retrieved above
        onnx_model_path = config_parser_object.get('Embeddings', 'onnx_model_path', fallback="./App_Function_Libraries/onnx_models/text-embedding-3-small.onnx")
        model_dir = config_parser_object.get('Embeddings', 'model_dir', fallback="./App_Function_Libraries/onnx_models")
        embedding_api_url = config_parser_object.get('Embeddings', 'embedding_api_url', fallback="http://localhost:8080/v1/embeddings")
        embedding_api_key = config_parser_object.get('Embeddings', 'embedding_api_key', fallback='')
        # Fallback model if primary model fails
        embedding_fallback_model = config_parser_object.get('Embeddings', 'embedding_fallback_model', fallback='sentence-transformers/all-MiniLM-L6-v2')
        # Auto-generate embeddings on upload
        auto_generate_embeddings = config_parser_object.get('Embeddings', 'auto_generate_on_upload', fallback='false').lower() == 'true'
        chunk_size = config_parser_object.get('Embeddings', 'chunk_size', fallback=400)
        overlap = config_parser_object.get('Embeddings', 'overlap', fallback=200)
        # Contextual chunking defaults for embeddings
        enable_contextual_chunking_cfg = config_parser_object.get('Embeddings', 'enable_contextual_chunking', fallback='false')
        try:
            enable_contextual_chunking_flag = str(enable_contextual_chunking_cfg).strip().lower() in {"true","1","yes","on"}
        except Exception:
            enable_contextual_chunking_flag = False
        # Allow contextual LLM model in Embeddings (fallback to Claims section for backward compat)
        contextual_llm_model_cfg = config_parser_object.get('Embeddings', 'contextual_llm_model', fallback=None)
        contextual_llm_provider_cfg = config_parser_object.get('Embeddings', 'contextual_llm_provider', fallback=None)
        # Temperature for contextualization LLM
        contextual_llm_temperature_cfg = None
        try:
            _temp_val = config_parser_object.get('Embeddings', 'contextual_llm_temperature', fallback='')
            if _temp_val is not None and str(_temp_val).strip() != '':
                contextual_llm_temperature_cfg = float(_temp_val)
        except Exception:
            contextual_llm_temperature_cfg = None
        if not contextual_llm_model_cfg:
            contextual_llm_model_cfg = config_parser_object.get('Claims', 'contextual_llm_model', fallback=None)
        # Window size: allow None to lock full-doc behavior
        context_window_size_cfg = config_parser_object.get('Embeddings', 'context_window_size', fallback=None)
        if context_window_size_cfg is None:
            # Fallback to chunking section if not specified under Embeddings
            context_window_size_cfg = config_parser_object.get('Chunking', 'context_window_size', fallback=None)
        def _parse_optional_int(val):
            if val is None:
                return None
            s = str(val).strip().lower()
            if s in {"", "none", "null"}:
                return None
            try:
                return int(s)
            except Exception:
                return None
        context_window_size_val = _parse_optional_int(context_window_size_cfg)
        # Strategy/budget
        context_strategy_cfg = config_parser_object.get('Embeddings', 'context_strategy', fallback='auto')
        context_strategy_val = str(context_strategy_cfg).strip().lower() if context_strategy_cfg else 'auto'
        context_token_budget_cfg = config_parser_object.get('Embeddings', 'context_token_budget', fallback='6000')
        try:
            context_token_budget_val = int(str(context_token_budget_cfg).strip())
        except Exception:
            context_token_budget_val = 6000

        # Prompts - FIXME
        prompt_path = config_parser_object.get('Prompts', 'prompt_path', fallback='Databases/prompts.db')

        # Chat Dictionaries
        enable_chat_dictionaries = config_parser_object.get('Chat-Dictionaries', 'enable_chat_dictionaries', fallback='False')
        post_gen_replacement = config_parser_object.get('Chat-Dictionaries', 'post_gen_replacement', fallback='False')
        post_gen_replacement_dict = config_parser_object.get('Chat-Dictionaries', 'post_gen_replacement_dict', fallback='')
        chat_dict_chat_prompts = config_parser_object.get('Chat-Dictionaries', 'chat_dictionary_chat_prompts', fallback='')
        chat_dict_rag_prompts = config_parser_object.get('Chat-Dictionaries', 'chat_dictionary_RAG_prompts', fallback='')
        chat_dict_replacement_strategy = config_parser_object.get('Chat-Dictionaries', 'chat_dictionary_replacement_strategy', fallback='character_lore_first')
        chat_dict_max_tokens = config_parser_object.get('Chat-Dictionaries', 'chat_dictionary_max_tokens', fallback='1000')
        default_rag_prompt = config_parser_object.get('Chat-Dictionaries', 'default_rag_prompt', fallback='')

        # Auto-Save Values
        save_character_chats = config_parser_object.get('Auto-Save', 'save_character_chats', fallback='False')
        save_rag_chats = config_parser_object.get('Auto-Save', 'save_rag_chats', fallback='False')

        # Media Processing Limits
        max_audio_file_size_mb = int(config_parser_object.get('Media-Processing', 'max_audio_file_size_mb', fallback='500'))
        max_pdf_file_size_mb = int(config_parser_object.get('Media-Processing', 'max_pdf_file_size_mb', fallback='50'))
        max_video_file_size_mb = int(config_parser_object.get('Media-Processing', 'max_video_file_size_mb', fallback='1000'))
        max_epub_file_size_mb = int(config_parser_object.get('Media-Processing', 'max_epub_file_size_mb', fallback='100'))
        max_document_file_size_mb = int(config_parser_object.get('Media-Processing', 'max_document_file_size_mb', fallback='50'))
        # Processing timeouts
        pdf_conversion_timeout_seconds = int(config_parser_object.get('Media-Processing', 'pdf_conversion_timeout_seconds', fallback='300'))
        audio_processing_timeout_seconds = int(config_parser_object.get('Media-Processing', 'audio_processing_timeout_seconds', fallback='600'))
        video_processing_timeout_seconds = int(config_parser_object.get('Media-Processing', 'video_processing_timeout_seconds', fallback='1200'))
        # Archive processing limits
        max_archive_internal_files = int(config_parser_object.get('Media-Processing', 'max_archive_internal_files', fallback='100'))
        max_archive_uncompressed_size_mb = int(config_parser_object.get('Media-Processing', 'max_archive_uncompressed_size_mb', fallback='200'))
        # Transcription settings
        audio_transcription_buffer_size_mb = int(config_parser_object.get('Media-Processing', 'audio_transcription_buffer_size_mb', fallback='10'))
        # General settings
        uuid_generation_length = int(config_parser_object.get('Media-Processing', 'uuid_generation_length', fallback='8'))

        # Local API Timeout
        local_api_timeout = config_parser_object.get('Local-API', 'local_api_timeout', fallback='90')

        # STT Settings
        default_stt_provider = config_parser_object.get('STT-Settings', 'default_stt_provider', fallback='faster_whisper')
        default_transcriber = config_parser_object.get('STT-Settings', 'default_transcriber', fallback='faster-whisper')
        nemo_model_variant = config_parser_object.get('STT-Settings', 'nemo_model_variant', fallback='standard')
        nemo_device = config_parser_object.get('STT-Settings', 'nemo_device', fallback='cuda')
        nemo_cache_dir = config_parser_object.get('STT-Settings', 'nemo_cache_dir', fallback='./models/nemo')

        # TTS Settings
        # FIXME
        local_tts_device = config_parser_object.get('TTS-Settings', 'local_tts_device', fallback='cpu')
        default_tts_provider = config_parser_object.get('TTS-Settings', 'default_tts_provider', fallback='openai')
        tts_voice = config_parser_object.get('TTS-Settings', 'default_tts_voice', fallback='shimmer')
        # Open AI TTS
        default_openai_tts_model = config_parser_object.get('TTS-Settings', 'default_openai_tts_model', fallback='tts-1-hd')
        default_openai_tts_voice = config_parser_object.get('TTS-Settings', 'default_openai_tts_voice', fallback='shimmer')
        default_openai_tts_speed = config_parser_object.get('TTS-Settings', 'default_openai_tts_speed', fallback='1')
        default_openai_tts_output_format = config_parser_object.get('TTS-Settings', 'default_openai_tts_output_format', fallback='mp3')
        default_openai_tts_streaming = config_parser_object.get('TTS-Settings', 'default_openai_tts_streaming', fallback='False')
        # Google TTS
        # FIXME - FIX THESE DEFAULTS
        default_google_tts_model = config_parser_object.get('TTS-Settings', 'default_google_tts_model', fallback='en')
        default_google_tts_voice = config_parser_object.get('TTS-Settings', 'default_google_tts_voice', fallback='en')
        default_google_tts_speed = config_parser_object.get('TTS-Settings', 'default_google_tts_speed', fallback='1')
        # ElevenLabs TTS
        default_eleven_tts_model = config_parser_object.get('TTS-Settings', 'default_eleven_tts_model', fallback='FIXME')
        default_eleven_tts_voice = config_parser_object.get('TTS-Settings', 'default_eleven_tts_voice', fallback='FIXME')
        default_eleven_tts_language_code = config_parser_object.get('TTS-Settings', 'default_eleven_tts_language_code', fallback='FIXME')
        default_eleven_tts_voice_stability = config_parser_object.get('TTS-Settings', 'default_eleven_tts_voice_stability', fallback='FIXME')
        default_eleven_tts_voice_similiarity_boost = config_parser_object.get('TTS-Settings', 'default_eleven_tts_voice_similiarity_boost', fallback='FIXME')
        default_eleven_tts_voice_style = config_parser_object.get('TTS-Settings', 'default_eleven_tts_voice_style', fallback='FIXME')
        default_eleven_tts_voice_use_speaker_boost = config_parser_object.get('TTS-Settings', 'default_eleven_tts_voice_use_speaker_boost', fallback='FIXME')
        default_eleven_tts_output_format = config_parser_object.get('TTS-Settings', 'default_eleven_tts_output_format',
                                                      fallback='mp3_44100_192')
        # AllTalk TTS
        alltalk_api_ip = config_parser_object.get('TTS-Settings', 'alltalk_api_ip', fallback='http://127.0.0.1:7851/v1/audio/speech')
        default_alltalk_tts_model = config_parser_object.get('TTS-Settings', 'default_alltalk_tts_model', fallback='alltalk_model')
        default_alltalk_tts_voice = config_parser_object.get('TTS-Settings', 'default_alltalk_tts_voice', fallback='alloy')
        default_alltalk_tts_speed = config_parser_object.get('TTS-Settings', 'default_alltalk_tts_speed', fallback=1.0)
        default_alltalk_tts_output_format = config_parser_object.get('TTS-Settings', 'default_alltalk_tts_output_format', fallback='mp3')

        # Kokoro TTS
        kokoro_model_path = config_parser_object.get('TTS-Settings', 'kokoro_model_path', fallback='Databases/kokoro_models')
        default_kokoro_tts_model = config_parser_object.get('TTS-Settings', 'default_kokoro_tts_model', fallback='pht')
        default_kokoro_tts_voice = config_parser_object.get('TTS-Settings', 'default_kokoro_tts_voice', fallback='sky')
        default_kokoro_tts_speed = config_parser_object.get('TTS-Settings', 'default_kokoro_tts_speed', fallback=1.0)
        default_kokoro_tts_output_format = config_parser_object.get('TTS-Settings', 'default_kokoro_tts_output_format', fallback='wav')


        # Self-hosted OpenAI API TTS
        default_openai_api_tts_model = config_parser_object.get('TTS-Settings', 'default_openai_api_tts_model', fallback='tts-1-hd')
        default_openai_api_tts_voice = config_parser_object.get('TTS-Settings', 'default_openai_api_tts_voice', fallback='shimmer')
        default_openai_api_tts_speed = config_parser_object.get('TTS-Settings', 'default_openai_api_tts_speed', fallback='1')
        default_openai_api_tts_output_format = config_parser_object.get('TTS-Settings', 'default_openai_tts_api_output_format', fallback='mp3')
        default_openai_api_tts_streaming = config_parser_object.get('TTS-Settings', 'default_openai_tts_streaming', fallback='False')


        # Search Engines
        search_provider_default = config_parser_object.get('Search-Engines', 'search_provider_default', fallback='google')
        search_language_query = config_parser_object.get('Search-Engines', 'search_language_query', fallback='en')
        search_language_results = config_parser_object.get('Search-Engines', 'search_language_results', fallback='en')
        search_language_analysis = config_parser_object.get('Search-Engines', 'search_language_analysis', fallback='en')
        search_default_max_queries = 10
        search_enable_subquery = config_parser_object.get('Search-Engines', 'search_enable_subquery', fallback='True')
        search_enable_subquery_count_max = config_parser_object.get('Search-Engines', 'search_enable_subquery_count_max', fallback=5)
        search_result_rerank = config_parser_object.get('Search-Engines', 'search_result_rerank', fallback='True')
        search_result_max = config_parser_object.get('Search-Engines', 'search_result_max', fallback=10)
        search_result_max_per_query = config_parser_object.get('Search-Engines', 'search_result_max_per_query', fallback=10)
        search_result_blacklist = config_parser_object.get('Search-Engines', 'search_result_blacklist', fallback='')
        search_result_display_type = config_parser_object.get('Search-Engines', 'search_result_display_type', fallback='list')
        search_result_display_metadata = config_parser_object.get('Search-Engines', 'search_result_display_metadata', fallback='False')
        search_result_save_to_db = config_parser_object.get('Search-Engines', 'search_result_save_to_db', fallback='True')
        search_result_analysis_tone = config_parser_object.get('Search-Engines', 'search_result_analysis_tone', fallback='')
        relevance_analysis_llm = config_parser_object.get('Search-Engines', 'relevance_analysis_llm', fallback='False')
        final_answer_llm = config_parser_object.get('Search-Engines', 'final_answer_llm', fallback='False')
        # Search Engine Specifics
        baidu_search_api_key = config_parser_object.get('Search-Engines', 'search_engine_api_key_baidu', fallback='')
        # Bing Search Settings
        bing_search_api_key = config_parser_object.get('Search-Engines', 'search_engine_api_key_bing', fallback='')
        bing_country_code = config_parser_object.get('Search-Engines', 'search_engine_country_code_bing', fallback='us')
        bing_search_api_url = config_parser_object.get('Search-Engines', 'search_engine_api_url_bing', fallback='')
        # Brave Search Settings
        brave_search_api_key = config_parser_object.get('Search-Engines', 'search_engine_api_key_brave_regular', fallback='')
        brave_search_ai_api_key = config_parser_object.get('Search-Engines', 'search_engine_api_key_brave_ai', fallback='')
        brave_country_code = config_parser_object.get('Search-Engines', 'search_engine_country_code_brave', fallback='us')
        # DuckDuckGo Search Settings
        duckduckgo_search_api_key = config_parser_object.get('Search-Engines', 'search_engine_api_key_duckduckgo', fallback='')
        # Google Search Settings
        google_search_api_url = config_parser_object.get('Search-Engines', 'search_engine_api_url_google', fallback='')
        google_search_api_key = config_parser_object.get('Search-Engines', 'search_engine_api_key_google', fallback='')
        google_search_engine_id = config_parser_object.get('Search-Engines', 'search_engine_id_google', fallback='')
        google_simp_trad_chinese = config_parser_object.get('Search-Engines', 'enable_traditional_chinese', fallback='0')
        limit_google_search_to_country = config_parser_object.get('Search-Engines', 'limit_google_search_to_country', fallback='0')
        google_search_country = config_parser_object.get('Search-Engines', 'google_search_country', fallback='us')
        google_search_country_code = config_parser_object.get('Search-Engines', 'google_search_country_code', fallback='us')
        google_filter_setting = config_parser_object.get('Search-Engines', 'google_filter_setting', fallback='1')
        google_user_geolocation = config_parser_object.get('Search-Engines', 'google_user_geolocation', fallback='')
        google_ui_language = config_parser_object.get('Search-Engines', 'google_ui_language', fallback='en')
        google_limit_search_results_to_language = config_parser_object.get('Search-Engines', 'google_limit_search_results_to_language', fallback='')
        google_default_search_results = config_parser_object.get('Search-Engines', 'google_default_search_results', fallback='10')
        google_safe_search = config_parser_object.get('Search-Engines', 'google_safe_search', fallback='active')
        google_enable_site_search = config_parser_object.get('Search-Engines', 'google_enable_site_search', fallback='0')
        google_site_search_include = config_parser_object.get('Search-Engines', 'google_site_search_include', fallback='')
        google_site_search_exclude = config_parser_object.get('Search-Engines', 'google_site_search_exclude', fallback='')
        google_sort_results_by = config_parser_object.get('Search-Engines', 'google_sort_results_by', fallback='relevance')
        # Kagi Search Settings
        kagi_search_api_key = config_parser_object.get('Search-Engines', 'search_engine_api_key_kagi', fallback='')
        # Searx Search Settings
        search_engine_searx_api = config_parser_object.get('Search-Engines', 'search_engine_searx_api', fallback='')
        # Tavily Search Settings
        tavily_search_api_key = config_parser_object.get('Search-Engines', 'search_engine_api_key_tavily', fallback='')
        # Yandex Search Settings
        yandex_search_api_key = config_parser_object.get('Search-Engines', 'search_engine_api_key_yandex', fallback='')
        yandex_search_engine_id = config_parser_object.get('Search-Engines', 'search_engine_id_yandex', fallback='')

        # Prompts
        sub_question_generation_prompt = config_parser_object.get('Prompts', 'sub_question_generation_prompt', fallback='')
        search_result_relevance_eval_prompt = config_parser_object.get('Prompts', 'search_result_relevance_eval_prompt', fallback='')
        analyze_search_results_prompt = config_parser_object.get('Prompts', 'analyze_search_results_prompt', fallback='')

        # Web Scraper settings
        web_scraper_api_key = config_parser_object.get('Web-Scraper', 'web_scraper_api_key', fallback='')
        web_scraper_api_url = config_parser_object.get('Web-Scraper', 'web_scraper_api_url', fallback='')
        web_scraper_api_timeout = config_parser_object.get('Web-Scraper', 'web_scraper_api_timeout', fallback='90')
        web_scraper_api_retries = config_parser_object.get('Web-Scraper', 'web_scraper_api_retries', fallback='3')
        web_scraper_api_retry_delay = config_parser_object.get('Web-Scraper', 'web_scraper_api_retry_delay', fallback='5')
        web_scraper_retry_count = config_parser_object.get('Web-Scraper', 'web_scraper_retry_count', fallback='3')
        web_scraper_retry_timeout = config_parser_object.get('Web-Scraper', 'web_scraper_retry_timeout', fallback='5')
        web_scraper_stealth_playwright = config_parser_object.get('Web-Scraper', 'web_scraper_stealth_playwright', fallback='False')

        return_dict = {
            'anthropic_api': {
                'api_key': anthropic_api_key,
                'model': anthropic_model,
                'streaming': anthropic_streaming,
                'temperature': anthropic_temperature,
                'top_p': anthropic_top_p,
                'top_k': anthropic_top_k,
                'max_tokens': anthropic_max_tokens,
                'api_timeout': anthropic_api_timeout,
                'api_retries': anthropic_api_retries,
                'api_retry_delay': anthropic_api_retry_delay
            },
            'cohere_api': {
                'api_key': cohere_api_key,
                'model': cohere_model,
                'streaming': cohere_streaming,
                'temperature': cohere_temperature,
                'max_p': cohere_max_p,
                'top_k': cohere_top_k,
                'max_tokens': cohere_max_tokens,
                'api_timeout': cohere_api_timeout,
                'api_retries': cohere_api_retries,
                'api_retry_delay': cohere_api_retry_delay
            },
            'deepseek_api': {
                'api_key': deepseek_api_key,
                'model': deepseek_model,
                'streaming': deepseek_streaming,
                'temperature': deepseek_temperature,
                'top_p': deepseek_top_p,
                'min_p': deepseek_min_p,
                'max_tokens': deepseek_max_tokens,
                'api_timeout': deepseek_api_timeout,
                'api_retries': deepseek_api_retries,
                'api_retry_delay': deepseek_api_retry_delay
            },
            'qwen_api': {
                'api_key': qwen_api_key,
                'model': qwen_model,
                'streaming': qwen_streaming,
                'temperature': qwen_temperature,
                'top_p': qwen_top_p,
                'max_tokens': qwen_max_tokens,
                'api_timeout': qwen_api_timeout,
                'api_retries': qwen_api_retries,
                'api_retry_delay': qwen_api_retry_delay,
                'api_base_url': qwen_api_base_url
            },
            'google_api': {
                'api_key': google_api_key,
                'model': google_model,
                'streaming': google_streaming,
                'temperature': google_temperature,
                'top_p': google_top_p,
                'min_p': google_min_p,
                'max_tokens': google_max_tokens,
                'api_timeout': google_api_timeout,
                'api_retries': google_api_retries,
                'api_retry_delay': google_api_retry_delay
            },
            'groq_api': {
                'api_key': groq_api_key,
                'model': groq_model,
                'streaming': groq_streaming,
                'temperature': groq_temperature,
                'top_p': groq_top_p,
                'max_tokens': groq_max_tokens,
                'api_timeout': groq_api_timeout,
                'api_retries': groq_api_retries,
                'api_retry_delay': groq_api_retry_delay
            },
            'huggingface_api': {
                'huggingface_use_router_url_format': huggingface_use_router_url_format,
                'huggingface_router_base_url': huggingface_router_base_url,
                'api_base_url': huggingface_api_base_url,
                'api_key': huggingface_api_key,
                'model': huggingface_model,
                'streaming': huggingface_streaming,
                'temperature': huggingface_temperature,
                'top_p': huggingface_top_p,
                'min_p': huggingface_min_p,
                'max_tokens': huggingface_max_tokens,
                'api_timeout': huggingface_api_timeout,
                'api_retries': huggingface_api_retries,
                'api_retry_delay': huggingface_api_retry_delay
            },
            'mistral_api': {
                'api_key': mistral_api_key,
                'model': mistral_model,
                'streaming': mistral_streaming,
                'temperature': mistral_temperature,
                'top_p': mistral_top_p,
                'max_tokens': mistral_max_tokens,
                'api_timeout': mistral_api_timeout,
                'api_retries': mistral_api_retries,
                'api_retry_delay': mistral_api_retry_delay
            },
            'openrouter_api': {
                'api_key': openrouter_api_key,
                'model': openrouter_model,
                'streaming': openrouter_streaming,
                'temperature': openrouter_temperature,
                'top_p': openrouter_top_p,
                'min_p': openrouter_min_p,
                'top_k': openrouter_top_k,
                'max_tokens': openrouter_max_tokens,
                'api_timeout': openrouter_api_timeout,
                'api_retries': openrouter_api_retries,
                'api_retry_delay': openrouter_api_retry_delay
            },
            'bedrock_api': {
                'api_key': bedrock_api_key,
                'region': bedrock_region,
                'runtime_endpoint': bedrock_runtime_endpoint,
                'model': bedrock_model,
                'streaming': bedrock_streaming,
                'temperature': bedrock_temperature,
                'top_p': bedrock_top_p,
                'max_tokens': bedrock_max_tokens,
                'api_timeout': bedrock_api_timeout,
                'api_retries': bedrock_api_retries,
                'api_retry_delay': bedrock_api_retry_delay
            },
            'openai_api': {
                'api_key': openai_api_key,
                'model': openai_model,
                'streaming': openai_streaming,
                'temperature': openai_temperature,
                'top_p': openai_top_p,
                'max_tokens': openai_max_tokens,
                'api_timeout': openai_api_timeout,
                'api_retries': openai_api_retries,
                'api_retry_delay': openai_api_retry_delay
            },
            'elevenlabs_api': {
                'api_key': elevenlabs_api_key,
            },
            'alltalk_api': {
                'api_ip': alltalk_api_ip,
                'default_alltalk_tts_model': default_alltalk_tts_model,
                'default_alltalk_tts_voice': default_alltalk_tts_voice,
                'default_alltalk_tts_speed': default_alltalk_tts_speed,
                'default_alltalk_tts_output_format': default_alltalk_tts_output_format,
            },
            'llama_api': {
                'api_ip': llama_api_IP,
                'api_key': llama_api_key,
                'streaming': llama_streaming,
                'temperature': llama_temperature,
                'top_p': llama_top_p,
                'min_p': llama_min_p,
                'top_k': llama_top_k,
                'max_tokens': llama_max_tokens,
                'api_timeout': llama_api_timeout,
                'api_retries': llama_api_retries,
                'api_retry_delay': llama_api_retry_delay
            },
            'ooba_api': {
                'api_ip': ooba_api_IP,
                'api_key': ooba_api_key,
                'streaming': ooba_streaming,
                'temperature': ooba_temperature,
                'top_p': ooba_top_p,
                'min_p': ooba_min_p,
                'top_k': ooba_top_k,
                'max_tokens': ooba_max_tokens,
                'api_timeout': ooba_api_timeout,
                'api_retries': ooba_api_retries,
                'api_retry_delay': ooba_api_retry_delay
            },
            'kobold_api': {
                'api_ip': kobold_api_ip,
                'api_streaming_ip': kobold_openai_api_IP,
                'api_key': kobold_api_key,
                'streaming': kobold_streaming,
                'temperature': kobold_temperature,
                'top_p': kobold_top_p,
                'top_k': kobold_top_k,
                'max_tokens': kobold_max_tokens,
                'api_timeout': kobold_api_timeout,
                'api_retries': kobold_api_retries,
                'api_retry_delay': kobold_api_retry_delay
            },
            'tabby_api': {
                'api_ip': tabby_api_IP,
                'api_key': tabby_api_key,
                'model': tabby_model,
                'streaming': tabby_streaming,
                'temperature': tabby_temperature,
                'top_p': tabby_top_p,
                'top_k': tabby_top_k,
                'min_p': tabby_min_p,
                'max_tokens': tabby_max_tokens,
                'api_timeout': tabby_api_timeout,
                'api_retries': tabby_api_retries,
                'api_retry_delay': tabby_api_retry_delay
            },
            'vllm_api': {
                'api_ip': vllm_api_url,
                'api_key': vllm_api_key,
                'model': vllm_model,
                'streaming': vllm_streaming,
                'temperature': vllm_temperature,
                'top_p': vllm_top_p,
                'top_k': vllm_top_k,
                'min_p': vllm_min_p,
                'max_tokens': vllm_max_tokens,
                'api_timeout': vllm_api_timeout,
                'api_retries': vllm_api_retries,
                'api_retry_delay': vllm_api_retry_delay
            },
            'ollama_api': {
                'api_url': ollama_api_url,
                'api_key': ollama_api_key,
                'model': ollama_model,
                'streaming': ollama_streaming,
                'temperature': ollama_temperature,
                'top_p': ollama_top_p,
                'max_tokens': ollama_max_tokens,
                'api_timeout': ollama_api_timeout,
                'api_retries': ollama_api_retries,
                'api_retry_delay': ollama_api_retry_delay
            },
            'aphrodite_api': {
                'api_ip': aphrodite_api_url,
                'api_key': aphrodite_api_key,
                'model': aphrodite_model,
                'max_tokens': aphrodite_max_tokens,
                'streaming': aphrodite_streaming,
                'api_timeout': aphrodite_api_timeout,
                'api_retries': aphrodite_api_retries,
                'api_retry_delay': aphrodite_api_retry_delay
            },
            'custom_openai_api': {
                'api_ip': custom_openai_api_ip,
                'api_key': custom_openai_api_key,
                'streaming': custom_openai_api_streaming,
                'model': custom_openai_api_model,
                'temperature': custom_openai_api_temperature,
                'max_tokens': custom_openai_api_max_tokens,
                'top_p': custom_openai_api_top_p,
                'min_p': custom_openai_api_min_p,
                'api_timeout': custom_openai_api_timeout,
                'api_retries': custom_openai_api_retries,
                'api_retry_delay': custom_openai_api_retry_delay
            },
            'custom_openai_api_2': {
                'api_ip': custom_openai2_api_ip,
                'api_key': custom_openai2_api_key,
                'streaming': custom_openai2_api_streaming,
                'model': custom_openai2_api_model,
                'temperature': custom_openai2_api_temperature,
                'max_tokens': custom_openai2_api_max_tokens,
                'top_p': custom_openai2_api_top_p,
                'min_p': custom_openai2_api_min_p,
                'api_timeout': custom_openai2_api_timeout,
                'api_retries': custom_openai2_api_retries,
                'api_retry_delay': custom_openai2_api_retry_delay
            },
            'llm_api_settings': {
                'default_api': default_api,
                'local_api_timeout': local_api_timeout,
                'local_api_retries': local_api_retries,
                'local_api_retry_delay': local_api_retry_delay,
            },
            'output_path': output_path,
            'system_preferences': {
                'save_video_transcripts': save_video_transcripts,
            },
            'processing_choice': processing_choice,
            'media_processing': {
                'max_audio_file_size_mb': max_audio_file_size_mb,
                'max_pdf_file_size_mb': max_pdf_file_size_mb,
                'max_video_file_size_mb': max_video_file_size_mb,
                'max_epub_file_size_mb': max_epub_file_size_mb,
                'max_document_file_size_mb': max_document_file_size_mb,
                'pdf_conversion_timeout_seconds': pdf_conversion_timeout_seconds,
                'audio_processing_timeout_seconds': audio_processing_timeout_seconds,
                'video_processing_timeout_seconds': video_processing_timeout_seconds,
                'max_archive_internal_files': max_archive_internal_files,
                'max_archive_uncompressed_size_mb': max_archive_uncompressed_size_mb,
                'audio_transcription_buffer_size_mb': audio_transcription_buffer_size_mb,
                'uuid_generation_length': uuid_generation_length
            },
            'chat_dictionaries': {
                'enable_chat_dictionaries': enable_chat_dictionaries,
                'post_gen_replacement': post_gen_replacement,
                'post_gen_replacement_dict': post_gen_replacement_dict,
                'chat_dict_chat_prompts': chat_dict_chat_prompts,
                'chat_dict_RAG_prompts': chat_dict_rag_prompts,
                'chat_dict_replacement_strategy': chat_dict_replacement_strategy,
                'chat_dict_max_tokens': chat_dict_max_tokens,
                'default_rag_prompt': default_rag_prompt
            },
            'chunking_config': {
                'chunking_method': chunking_method,
                'chunk_max_size': chunk_max_size,
                'adaptive_chunking': adaptive_chunking,
                'multi_level': chunking_multi_level,
                'chunk_language': chunk_language,
                'chunk_overlap': chunk_overlap,
                'article_chunking_method': article_chunking_method,
                'article_chunk_max_size': article_chunk_max_size,
                'article_chunk_overlap': article_chunk_overlap,
                'article_adaptive_chunking': article_adaptive_chunking,
                'article_chunking_multi_level': article_chunking_multi_level,
                'article_language': article_language,
                'audio_chunking_method': audio_chunking_method,
                'audio_chunk_max_size': audio_chunk_max_size,
                'audio_chunk_overlap': audio_chunk_overlap,
                'audio_adaptive_chunking': audio_adaptive_chunking,
                'audio_chunking_multi_level': audio_chunking_multi_level,
                'audio_language': audio_language,
                'book_chunking_method': book_chunking_method,
                'book_chunk_max_size': book_chunk_max_size,
                'book_chunk_overlap': book_chunk_overlap,
                'book_adaptive_chunking': book_adaptive_chunking,
                'book_chunking_multi_level': book_chunking_multi_level,
                'book_language': book_language,
                'document_chunking_method': document_chunking_method,
                'document_chunk_max_size': document_chunk_max_size,
                'document_chunk_overlap': document_chunk_overlap,
                'document_adaptive_chunking': document_adaptive_chunking,
                'document_chunking_multi_level': document_chunking_multi_level,
                'document_language': document_language,
                'mediawiki_article_chunking_method': mediawiki_article_chunking_method,
                'mediawiki_article_chunk_max_size': mediawiki_article_chunk_max_size,
                'mediawiki_article_chunk_overlap': mediawiki_article_chunk_overlap,
                'mediawiki_article_adaptive_chunking': mediawiki_article_adaptive_chunking,
                'mediawiki_article_chunking_multi_level': mediawiki_article_chunking_multi_level,
                'mediawiki_article_language': mediawiki_article_language,
                'mediawiki_dump_chunking_method': mediawiki_dump_chunking_method,
                'mediawiki_dump_chunk_max_size': mediawiki_dump_chunk_max_size,
                'mediawiki_dump_chunk_overlap': mediawiki_dump_chunk_overlap,
                'mediawiki_dump_adaptive_chunking': mediawiki_dump_adaptive_chunking,
                'mediawiki_dump_chunking_multi_level': mediawiki_dump_chunking_multi_level,
                'mediawiki_dump_language': mediawiki_dump_language,
                'obsidian_note_chunking_method': obsidian_note_chunking_method,
                'obsidian_note_chunk_max_size': obsidian_note_chunk_max_size,
                'obsidian_note_chunk_overlap': obsidian_note_chunk_overlap,
                'obsidian_note_adaptive_chunking': obsidian_note_adaptive_chunking,
                'obsidian_note_chunking_multi_level': obsidian_note_chunking_multi_level,
                'obsidian_note_language': obsidian_note_language,
                'podcast_chunking_method': podcast_chunking_method,
                'podcast_chunk_max_size': podcast_chunk_max_size,
                'podcast_chunk_overlap': podcast_chunk_overlap,
                'podcast_adaptive_chunking': podcast_adaptive_chunking,
                'podcast_chunking_multi_level': podcast_chunking_multi_level,
                'podcast_language': podcast_language,
                'text_chunking_method': text_chunking_method,
                'text_chunk_max_size': text_chunk_max_size,
                'text_chunk_overlap': text_chunk_overlap,
                'text_adaptive_chunking': text_adaptive_chunking,
                'text_chunking_multi_level': text_chunking_multi_level,
                'text_language': text_language,
                'video_chunking_method': video_chunking_method,
                'video_chunk_max_size': video_chunk_max_size,
                'video_chunk_overlap': video_chunk_overlap,
                'video_adaptive_chunking': video_adaptive_chunking,
                'video_chunking_multi_level': video_chunking_multi_level,
                'video_language': video_language,
                # Proposition-specific
                'proposition_engine': proposition_engine,
                'proposition_prompt_profile': proposition_prompt_profile,
                'proposition_aggressiveness': proposition_aggressiveness,
                'proposition_min_proposition_length': proposition_min_proposition_length,
            },
            'embedding_config': {
                'embedding_provider': embedding_provider,
                'embedding_model': embedding_model,
                'embedding_fallback_model': embedding_fallback_model,
                'auto_generate_on_upload': auto_generate_embeddings,
                'onnx_model_path': onnx_model_path,
                'model_dir': model_dir,
                'embedding_api_url': embedding_api_url,
                'embedding_api_key': embedding_api_key,
                'chunk_size': chunk_size,
                'chunk_overlap': overlap,
                # Contextual chunking defaults for embeddings
                'enable_contextual_chunking': enable_contextual_chunking_flag,
                'contextual_llm_model': contextual_llm_model_cfg,
                'contextual_llm_provider': contextual_llm_provider_cfg,
                'contextual_llm_temperature': contextual_llm_temperature_cfg,
                'context_window_size': context_window_size_val,  # None means full-doc by default
                'context_strategy': context_strategy_val,        # auto|full|window|outline_window
                'context_token_budget': context_token_budget_val,
            },
            'auto-save': {
                'save_character_chats': save_character_chats,
                'save_rag_chats': save_rag_chats,
            },
            'default_api': default_api,
            'local_api_timeout': local_api_timeout,
            'STT_Settings': {
                'default_stt_provider': default_stt_provider,
                'default_transcriber': default_transcriber,
                'nemo_model_variant': nemo_model_variant,
                'nemo_device': nemo_device,
                'nemo_cache_dir': nemo_cache_dir,
            },
            # Also provide with hyphen for backward compatibility
            'STT-Settings': {
                'default_stt_provider': default_stt_provider,
                'default_transcriber': default_transcriber,
                'nemo_model_variant': nemo_model_variant,
                'nemo_device': nemo_device,
                'nemo_cache_dir': nemo_cache_dir,
            },
            'tts_settings': {
                'default_tts_provider': default_tts_provider,
                'tts_voice': tts_voice,
                'local_tts_device': local_tts_device,
                # OpenAI
                'default_openai_tts_voice': default_openai_tts_voice,
                'default_openai_tts_speed': default_openai_tts_speed,
                'default_openai_tts_model': default_openai_tts_model,
                'default_openai_tts_output_format': default_openai_tts_output_format,
                # Google
                'default_google_tts_model': default_google_tts_model,
                'default_google_tts_voice': default_google_tts_voice,
                'default_google_tts_speed': default_google_tts_speed,
                # ElevenLabs
                'default_eleven_tts_model': default_eleven_tts_model,
                'default_eleven_tts_voice': default_eleven_tts_voice,
                'default_eleven_tts_language_code': default_eleven_tts_language_code,
                'default_eleven_tts_voice_stability': default_eleven_tts_voice_stability,
                'default_eleven_tts_voice_similiarity_boost': default_eleven_tts_voice_similiarity_boost,
                'default_eleven_tts_voice_style': default_eleven_tts_voice_style,
                'default_eleven_tts_voice_use_speaker_boost': default_eleven_tts_voice_use_speaker_boost,
                'default_eleven_tts_output_format': default_eleven_tts_output_format,
                # Open Source / Self-Hosted TTS
                # GPT SoVITS
                # 'default_gpt_tts_model': default_gpt_tts_model,
                # 'default_gpt_tts_voice': default_gpt_tts_voice,
                # 'default_gpt_tts_speed': default_gpt_tts_speed,
                # 'default_gpt_tts_output_format': default_gpt_tts_output_format
                # AllTalk
                'alltalk_api_ip': alltalk_api_ip,
                'default_alltalk_tts_model': default_alltalk_tts_model,
                'default_alltalk_tts_voice': default_alltalk_tts_voice,
                'default_alltalk_tts_speed': default_alltalk_tts_speed,
                'default_alltalk_tts_output_format': default_alltalk_tts_output_format,
                # Kokoro
                'default_kokoro_tts_model': default_kokoro_tts_model,
                'default_kokoro_tts_voice': default_kokoro_tts_voice,
                'default_kokoro_tts_speed': default_kokoro_tts_speed,
                'default_kokoro_tts_output_format': default_kokoro_tts_output_format,
                # Self-hosted OpenAI API
                'default_openai_api_tts_model': default_openai_api_tts_model,
                'default_openai_api_tts_voice': default_openai_api_tts_voice,
                'default_openai_api_tts_speed': default_openai_api_tts_speed,
                'default_openai_api_tts_output_format': default_openai_api_tts_output_format,
                'default_openai_api_tts_streaming': default_openai_api_tts_streaming,
            },
            'search_settings': {
                'default_search_provider': search_provider_default,
                'search_language_query': search_language_query,
                'search_language_results': search_language_results,
                'search_language_analysis': search_language_analysis,
                'search_default_max_queries': search_default_max_queries,
                'search_enable_subquery': search_enable_subquery,
                'search_enable_subquery_count_max': search_enable_subquery_count_max,
                'search_result_rerank': search_result_rerank,
                'search_result_max': search_result_max,
                'search_result_max_per_query': search_result_max_per_query,
                'search_result_blacklist': search_result_blacklist,
                'search_result_display_type': search_result_display_type,
                'search_result_display_metadata': search_result_display_metadata,
                'search_result_save_to_db': search_result_save_to_db,
                'search_result_analysis_tone': search_result_analysis_tone,
                'relevance_analysis_llm': relevance_analysis_llm,
                'final_answer_llm': final_answer_llm,
            },
            'search_engines': {
                'baidu_search_api_key': baidu_search_api_key,
                'bing_search_api_key': bing_search_api_key,
                'bing_country_code': bing_country_code,
                'bing_search_api_url': bing_search_api_url,
                'brave_search_api_key': brave_search_api_key,
                'brave_search_ai_api_key': brave_search_ai_api_key,
                'brave_country_code': brave_country_code,
                'duckduckgo_search_api_key': duckduckgo_search_api_key,
                'google_search_api_url': google_search_api_url,
                'google_search_api_key': google_search_api_key,
                'google_search_engine_id': google_search_engine_id,
                'google_simp_trad_chinese': google_simp_trad_chinese,
                'limit_google_search_to_country': limit_google_search_to_country,
                'google_search_country': google_search_country,
                'google_search_country_code': google_search_country_code,
                'google_search_filter_setting': google_filter_setting,
                'google_user_geolocation': google_user_geolocation,
                'google_ui_language': google_ui_language,
                'google_limit_search_results_to_language': google_limit_search_results_to_language,
                'google_site_search_include': google_site_search_include,
                'google_site_search_exclude': google_site_search_exclude,
                'google_sort_results_by': google_sort_results_by,
                'google_default_search_results': google_default_search_results,
                'google_safe_search': google_safe_search,
                'google_enable_site_search' : google_enable_site_search,
                'kagi_search_api_key': kagi_search_api_key,
                'searx_search_api_url': search_engine_searx_api,
                'tavily_search_api_key': tavily_search_api_key,
                'yandex_search_api_key': yandex_search_api_key,
                'yandex_search_engine_id': yandex_search_engine_id
            },
            'prompts': {
                'sub_question_generation_prompt': sub_question_generation_prompt,
                'search_result_relevance_eval_prompt': search_result_relevance_eval_prompt,
                'analyze_search_results_prompt': analyze_search_results_prompt,
            },
            'web_scraper':{
                'web_scraper_api_key': web_scraper_api_key,
                'web_scraper_api_url': web_scraper_api_url,
                'web_scraper_api_timeout': web_scraper_api_timeout,
                'web_scraper_api_retries': web_scraper_api_retries,
                'web_scraper_api_retry_delay': web_scraper_api_retry_delay,
                'web_scraper_retry_count': web_scraper_retry_count,
                'web_scraper_retry_timeout': web_scraper_retry_timeout,
                'web_scraper_stealth_playwright': web_scraper_stealth_playwright,
            },
            'Redis': config_parser_object['Redis'] if 'Redis' in config_parser_object else {},
            'Web-Scraping': config_parser_object['Web-Scraping'] if 'Web-Scraping' in config_parser_object else {}
        }
        # Assemble minimal RAG config section (vector store + pgvector params)
        try:
            rag_section = {}
            if config_parser_object.has_section('RAG'):
                rag_section['vector_store_type'] = config_parser_object.get('RAG', 'vector_store_type', fallback='chromadb')
                rag_section['distance_metric'] = config_parser_object.get('RAG', 'distance_metric', fallback='cosine')
                rag_section['collection_prefix'] = config_parser_object.get('RAG', 'collection_prefix', fallback='unified')
                # PGVector connection params under [RAG]
                rag_section['pgvector'] = {
                    'host': config_parser_object.get('RAG', 'pgvector_host', fallback=os.getenv('PGVECTOR_HOST', 'localhost')),
                    'port': config_parser_object.getint('RAG', 'pgvector_port', fallback=int(os.getenv('PGVECTOR_PORT', '5432'))),
                    'database': config_parser_object.get('RAG', 'pgvector_database', fallback=os.getenv('PGVECTOR_DATABASE', 'postgres')),
                    'user': config_parser_object.get('RAG', 'pgvector_user', fallback=os.getenv('PGVECTOR_USER', 'postgres')),
                    'password': config_parser_object.get('RAG', 'pgvector_password', fallback=os.getenv('PGVECTOR_PASSWORD', '')),
                    'sslmode': config_parser_object.get('RAG', 'pgvector_sslmode', fallback=os.getenv('PGVECTOR_SSLMODE', 'prefer')),
                    'dsn': config_parser_object.get('RAG', 'pgvector_dsn', fallback=os.getenv('PGVECTOR_DSN', '')) or None,
                    # Pool configuration (psycopg_pool)
                    'pool_min_size': config_parser_object.getint('RAG', 'pgvector_pool_min_size', fallback=int(os.getenv('PGVECTOR_POOL_MIN_SIZE', '1'))),
                    'pool_max_size': config_parser_object.getint('RAG', 'pgvector_pool_max_size', fallback=int(os.getenv('PGVECTOR_POOL_MAX_SIZE', '5'))),
                    'pool_size': config_parser_object.getint('RAG', 'pgvector_pool_size', fallback=int(os.getenv('PGVECTOR_POOL_SIZE', '5'))),
                    # HNSW tuning
                    'hnsw_ef_search': config_parser_object.getint('RAG', 'pgvector_hnsw_ef_search', fallback=int(os.getenv('PGVECTOR_HNSW_EF_SEARCH', '64'))),
                }
            return_dict['RAG'] = rag_section
        except Exception:
            # Non-fatal: keep defaults
            pass

        # Optional OCR section for backend preferences and defaults
        try:
            if config_parser_object.has_section('OCR'):
                ocr_section = {}
                backend_priority = config_parser_object.get('OCR', 'backend_priority', fallback='')
                if backend_priority:
                    ocr_section['backend_priority'] = backend_priority
                page_conc = config_parser_object.get('OCR', 'page_concurrency_default', fallback='')
                if page_conc:
                    ocr_section['page_concurrency_default'] = int(page_conc)
                sglang_timeout = config_parser_object.get('OCR', 'sglang_timeout', fallback='')
                if sglang_timeout:
                    ocr_section['sglang_timeout'] = int(sglang_timeout)
                if ocr_section:
                    return_dict['OCR'] = ocr_section
        except Exception:
            pass

        return return_dict
    except Exception as e:
        logging.error(f"Error loading config: {str(e)}")
        return None


# Global scope in config.py
try:
    loaded_config_data = load_and_log_configs()
    if loaded_config_data is None:  # Add a check here
        logger.critical("Failed to load configuration data at module import. `loaded_config_data` is None.")
        default_api_endpoint = "openai"  # Fallback
    else:
        default_api_endpoint = loaded_config_data.get('default_api', 'openai')  # Use .get() for safety
        logger.info(f"Default API Endpoint (from config.py global scope): {default_api_endpoint}")
except Exception as e:  # Should be less likely to hit this outer if inner one is robust
    logger.error(f"Critical error setting default_api_endpoint in config.py global scope: {str(e)}", exc_info=True)
    default_api_endpoint = "openai"  # Fallback


# --- Global Settings Object ---
# Load the settings when the module is imported
settings = load_settings()

# For backward compatibility with code expecting 'config'
config = settings


# --- Optional: Export individual variables if needed for backward compatibility (less recommended) ---
# SINGLE_USER_MODE = settings["SINGLE_USER_MODE"]
# SINGLE_USER_FIXED_ID = settings["SINGLE_USER_FIXED_ID"]
# ... etc ...
#
# End of config.py
#######################################################################################################################
