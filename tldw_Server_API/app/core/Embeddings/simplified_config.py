# simplified_config.py
# Simplified configuration system for embeddings module

import copy
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from loguru import logger

from tldw_Server_API.app.core.config import get_config_section
from tldw_Server_API.app.core.config_utils import (
    apply_default_sources,
    load_module_yaml,
    merge_config_layers,
)


@dataclass
class ProviderConfig:
    """Configuration for a single embedding provider"""
    name: str
    priority: int = 1
    enabled: bool = True
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    models: list[str] = field(default_factory=list)
    max_connections: int = 10
    timeout_seconds: int = 30
    rate_limit: Optional[str] = None  # e.g., "100/min"
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None

    def __post_init__(self):
        # Load API key from environment if not provided
        if not self.api_key:
            env_key = f"{self.name.upper()}_API_KEY"
            self.api_key = os.getenv(env_key)


@dataclass
class CacheConfig:
    """Cache configuration"""
    enabled: bool = True
    ttl_seconds: int = 3600
    max_size: int = 10000
    cleanup_interval: int = 300


@dataclass
class ResourceConfig:
    """Resource management configuration"""
    max_models_in_memory: int = 3
    max_memory_gb: float = 8.0
    model_ttl_seconds: int = 3600
    enable_model_warmup: bool = False
    warmup_models: list[str] = field(default_factory=list)


@dataclass
class BatchingConfig:
    """Request batching configuration"""
    enabled: bool = True
    max_batch_size: int = 32
    batch_timeout_ms: int = 100
    adaptive_batching: bool = True


@dataclass
class SecurityConfig:
    """Security configuration"""
    enable_request_signing: bool = True
    enable_audit_logging: bool = True
    enable_rate_limiting: bool = True
    max_input_length: int = 100000
    validate_embeddings: bool = True


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_health_check: bool = True
    health_check_interval: int = 30


@dataclass
class EmbeddingsConfig:
    """Main configuration for embeddings module"""
    providers: list[ProviderConfig] = field(default_factory=list)
    cache: CacheConfig = field(default_factory=CacheConfig)
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    batching: BatchingConfig = field(default_factory=BatchingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # Global settings
    default_provider: str = "openai"
    default_model: str = "text-embedding-3-small"
    chunk_size: int = 400
    chunk_overlap: int = 200

    @classmethod
    def from_yaml(cls, path: str) -> 'EmbeddingsConfig':
        """Load configuration from YAML file"""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'EmbeddingsConfig':
        """Create configuration from dictionary"""
        # Parse providers
        providers = []
        for provider_data in data.get('providers', []):
            providers.append(ProviderConfig(**provider_data))

        # Parse sub-configurations
        config = cls(
            providers=providers,
            cache=CacheConfig(**data.get('cache', {})),
            resources=ResourceConfig(**data.get('resources', {})),
            batching=BatchingConfig(**data.get('batching', {})),
            security=SecurityConfig(**data.get('security', {})),
            monitoring=MonitoringConfig(**data.get('monitoring', {})),
            default_provider=data.get('default_provider', 'openai'),
            default_model=data.get('default_model', 'text-embedding-3-small'),
            chunk_size=data.get('chunk_size', 400),
            chunk_overlap=data.get('chunk_overlap', 200)
        )

        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'providers': [asdict(p) for p in self.providers],
            'cache': asdict(self.cache),
            'resources': asdict(self.resources),
            'batching': asdict(self.batching),
            'security': asdict(self.security),
            'monitoring': asdict(self.monitoring),
            'default_provider': self.default_provider,
            'default_model': self.default_model,
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap
        }

    def to_yaml(self, path: str):
        """Save configuration to YAML file"""
        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get provider configuration by name"""
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None

    def get_enabled_providers(self) -> list[ProviderConfig]:
        """Get list of enabled providers sorted by priority"""
        enabled = [p for p in self.providers if p.enabled]
        return sorted(enabled, key=lambda x: x.priority)

    def validate(self) -> list[str]:
        """Validate configuration and return list of issues"""
        issues = []

        # Check for at least one enabled provider
        if not self.get_enabled_providers():
            issues.append("No enabled providers configured")

        # Check for API keys
        for provider in self.providers:
            if provider.enabled and not provider.api_key and provider.name not in {"local", "local_api"}:
                issues.append(f"Provider {provider.name} is enabled but has no API key")

        # Check resource limits
        if self.resources.max_models_in_memory < 1:
            issues.append("max_models_in_memory must be at least 1")

        if self.resources.max_memory_gb < 0.5:
            issues.append("max_memory_gb should be at least 0.5 GB")

        # Check cache settings
        if self.cache.enabled and self.cache.max_size < 100:
            issues.append("Cache size should be at least 100 entries")

        return issues


def create_default_config() -> EmbeddingsConfig:
    """Create a default configuration"""
    return EmbeddingsConfig(
        providers=[
            ProviderConfig(
                name="openai",
                priority=1,
                models=["text-embedding-3-small", "text-embedding-3-large"],
                rate_limit="3000/min",
                fallback_provider="huggingface"
            ),
            ProviderConfig(
                name="huggingface",
                priority=2,
                models=[
                    "sentence-transformers/all-MiniLM-L6-v2",
                    "sentence-transformers/all-mpnet-base-v2",
                    "intfloat/multilingual-e5-large-instruct",
                    "Qwen/Qwen3-Embedding-0.6B",
                    # Newly added supported models
                    "NovaSearch/stella_en_1.5B_v5",
                    "NovaSearch/stella_en_400M_v5",
                    "jinaai/jina-embeddings-v4",
                    "intfloat/multilingual-e5-large",
                    "mixedbread-ai/mxbai-embed-large-v1",
                    "jinaai/jina-embeddings-v3",
                    "BAAI/bge-large-en-v1.5",
                    "BAAI/bge-small-en-v1.5",
                ],
                rate_limit="1000/min"
            ),
            ProviderConfig(
                name="local",
                priority=3,
                api_url="http://localhost:8080/v1/embeddings",
                enabled=False
            )
        ]
    )


def load_config(path: Optional[str] = None) -> EmbeddingsConfig:
    """
    Load configuration from file or create default.

    Args:
        path: Optional path to configuration file

    Returns:
        EmbeddingsConfig instance
    """
    override_path = path or os.getenv("EMBEDDINGS_CONFIG_PATH")
    if override_path:
        override_obj = Path(override_path).expanduser()
        if not override_obj.exists():
            logger.warning(f"Embeddings config override not found: {override_obj}")

    yaml_config, yaml_path = load_module_yaml("embeddings", filename_override=override_path)
    if yaml_config:
        base_data = dict(yaml_config)
        base_source = "yaml"
        logger.info(f"Loaded embeddings config from {yaml_path}")
    else:
        base_data = create_default_config().to_dict()
        base_source = "default"
        if yaml_path:
            logger.info(f"Using default embeddings configuration (no YAML at {yaml_path})")
        else:
            logger.info("Using default embeddings configuration")

    cfg_txt = _load_config_txt_overrides()
    env_overrides = _load_env_overrides()
    providers = base_data.pop("providers", [])
    if isinstance(providers, dict):
        normalized: list[dict[str, Any]] = []
        for name, provider_cfg in providers.items():
            if isinstance(provider_cfg, dict):
                entry = dict(provider_cfg)
                entry.setdefault("name", name)
                normalized.append(entry)
        providers = normalized
    if providers is None:
        providers = []
    provider_overrides: list[tuple[str, str, dict[str, Any]]] = []
    provider_overrides.extend(_provider_updates_from_config_txt())
    provider_overrides.extend(_provider_updates_from_env())
    for source, name, updates in provider_overrides:
        if isinstance(providers, list):
            _apply_provider_override(providers, name, updates)

    merged, sources = merge_config_layers(
        [
            (base_source, base_data),
            ("config", cfg_txt),
            ("env", env_overrides),
        ]
    )
    merged["providers"] = providers
    if provider_overrides:
        sources["providers"] = "env" if any(s == "env" for s, _, _ in provider_overrides) else "config"
    else:
        sources["providers"] = base_source

    config = EmbeddingsConfig.from_dict(merged)
    sources = apply_default_sources(config.to_dict(), sources)
    global _config_sources
    _config_sources = sources
    logger.debug(f"Embeddings config sources: {sources}")
    return config


def _coerce_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _apply_provider_override(
    providers: list[dict[str, Any]],
    name: str,
    updates: dict[str, Any],
) -> None:
    for provider in providers:
        if provider.get("name") == name:
            provider.update(updates)
            return
    providers.append({"name": name, **updates})


def _load_config_txt_overrides() -> dict[str, Any]:
    section = get_config_section("Embeddings")
    if not section:
        return {}

    overrides: dict[str, Any] = {}
    provider = section.get("embedding_provider")
    model = section.get("embedding_model")
    chunk_size = _coerce_int(section.get("chunk_size"))
    overlap = _coerce_int(section.get("overlap"))

    if provider:
        overrides["default_provider"] = provider
    if model:
        overrides["default_model"] = model
    if chunk_size is not None:
        overrides["chunk_size"] = chunk_size
    if overlap is not None:
        overrides["chunk_overlap"] = overlap

    max_models = _coerce_int(section.get("max_models_in_memory"))
    max_memory = _coerce_float(section.get("max_model_memory_gb"))
    ttl_seconds = _coerce_int(section.get("model_lru_ttl_seconds"))
    if max_models is not None or max_memory is not None or ttl_seconds is not None:
        resources = overrides.setdefault("resources", {})
        if max_models is not None:
            resources["max_models_in_memory"] = max_models
        if max_memory is not None:
            resources["max_memory_gb"] = max_memory
        if ttl_seconds is not None:
            resources["model_ttl_seconds"] = ttl_seconds

    return overrides


def _provider_updates_from_config_txt() -> list[tuple[str, str, dict[str, Any]]]:
    section = get_config_section("Embeddings")
    if not section:
        return []
    api_url = section.get("embedding_api_url")
    if not api_url:
        return []
    return [("config", "local", {"api_url": api_url})]


def _load_env_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}

    def _env_first(*names: str) -> Optional[str]:
        for name in names:
            value = os.getenv(name)
            if value:
                return value
        return None

    provider = _env_first("EMBEDDINGS_DEFAULT_PROVIDER", "EMBEDDINGS_PROVIDER")
    model = _env_first("EMBEDDINGS_DEFAULT_MODEL", "EMBEDDINGS_MODEL")
    chunk_size = _coerce_int(_env_first("EMBEDDINGS_CHUNK_SIZE"))
    overlap = _coerce_int(_env_first("EMBEDDINGS_CHUNK_OVERLAP"))

    if provider:
        overrides["default_provider"] = provider
    if model:
        overrides["default_model"] = model
    if chunk_size is not None:
        overrides["chunk_size"] = chunk_size
    if overlap is not None:
        overrides["chunk_overlap"] = overlap

    return overrides


def _provider_updates_from_env() -> list[tuple[str, str, dict[str, Any]]]:
    api_url = os.getenv("EMBEDDINGS_API_URL") or os.getenv("EMBEDDINGS_LOCAL_API_URL")
    if not api_url:
        return []
    return [("env", "local", {"api_url": api_url})]


# Example YAML configuration
EXAMPLE_CONFIG_YAML = """
# Embeddings Configuration

# Provider settings
providers:
  - name: openai
    priority: 1
    enabled: true
    models:
      - text-embedding-3-small
      - text-embedding-3-large
    max_connections: 10
    timeout_seconds: 30
    rate_limit: "3000/min"
    fallback_provider: huggingface

  - name: huggingface
    priority: 2
    enabled: true
    models:
      - sentence-transformers/all-MiniLM-L6-v2
      - sentence-transformers/all-mpnet-base-v2
    rate_limit: "1000/min"

  - name: cohere
    priority: 3
    enabled: false
    models:
      - embed-english-v3.0
    rate_limit: "1000/min"

  - name: local
    priority: 4
    enabled: false
    api_url: http://localhost:8080/v1/embeddings

# Cache settings
cache:
  enabled: true
  ttl_seconds: 3600
  max_size: 10000
  cleanup_interval: 300

# Resource management
resources:
  max_models_in_memory: 3
  max_memory_gb: 8.0
  model_ttl_seconds: 3600
  enable_model_warmup: false
  warmup_models: []

# Request batching
batching:
  enabled: true
  max_batch_size: 32
  batch_timeout_ms: 100
  adaptive_batching: true

# Security
security:
  enable_request_signing: true
  enable_audit_logging: true
  enable_rate_limiting: true
  max_input_length: 100000
  validate_embeddings: true

# Monitoring
monitoring:
  enable_metrics: true
  metrics_port: 9090
  enable_health_check: true
  health_check_interval: 30

# Global settings
default_provider: openai
default_model: text-embedding-3-small
chunk_size: 400
chunk_overlap: 200
"""


def create_example_config(path: str = "./embeddings_config.yaml"):
    """Create an example configuration file"""
    with open(path, 'w') as f:
        f.write(EXAMPLE_CONFIG_YAML)
    logger.info(f"Created example configuration at {path}")


# Global configuration instance
_config: Optional[EmbeddingsConfig] = None
_config_sources: dict[str, Any] = {}


def get_config() -> EmbeddingsConfig:
    """Get or load the global configuration"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_config_sources() -> dict[str, Any]:
    """Get source tags for the current configuration."""
    global _config
    if not _config_sources:
        _config = load_config()
    return copy.deepcopy(_config_sources)


def reload_config(path: Optional[str] = None):
    """Reload configuration from file"""
    global _config
    _config = load_config(path)

    # Validate configuration
    issues = _config.validate()
    if issues:
        logger.warning(f"Configuration validation issues: {issues}")

    return _config
