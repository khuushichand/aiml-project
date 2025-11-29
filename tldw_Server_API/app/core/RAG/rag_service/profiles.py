"""
Blessed configuration profiles for the unified RAG pipeline.

These profiles provide small, opinionated presets for `unified_rag_pipeline`
so callers do not need to reason about dozens of individual flags for
common scenarios.

Current built-in profiles:
    - "production"  : Safe, predictable defaults suitable for latency- and
                      safety-conscious deployments.
    - "research"    : High-quality, feature-rich configuration for analysis
                      and model/retrieval experiments.
    - "cheap"       : Cost- and latency-optimized configuration with most
                      expensive extras disabled.

Profiles are intentionally conservative: they override only a subset of
pipeline parameters and rely on function-level defaults for everything else.
Callers can always override any individual flag on top of a profile.
"""

from dataclasses import dataclass
from typing import Any, Dict, Literal, Mapping, MutableMapping, Optional


ProfileName = Literal["production", "research", "cheap"]


@dataclass(frozen=True)
class RAGProfile:
    """Container for a named RAG profile."""

    name: ProfileName
    description: str
    defaults: Mapping[str, Any]


_PROFILES: Dict[ProfileName, RAGProfile] = {
    "production": RAGProfile(
        name="production",
        description=(
            "Safe production profile: hybrid search with reranking, "
            "semantic cache, and stricter guardrails (numeric fidelity, "
            "citations, basic content filtering). Expensive research "
            "features remain disabled by default."
        ),
        defaults={
            # Retrieval
            "search_mode": "hybrid",
            "top_k": 12,
            "enable_cache": True,
            "adaptive_cache": True,
            # Query processing (lightweight)
            "expand_query": True,
            "expansion_strategies": ["acronym", "synonym"],
            "enable_query_decomposition": False,
            "enable_gap_analysis": False,
            "enable_hyde": False,
            "enable_prf": False,
            # Guardrails / safety
            "enable_security_filter": True,
            "content_filter": True,
            "enable_injection_filter": True,
            "enable_content_policy_filter": True,
            "content_policy_types": ["pii"],
            "content_policy_mode": "redact",
            "require_hard_citations": True,
            "enable_numeric_fidelity": True,
            "numeric_fidelity_behavior": "ask",
            "enable_post_verification": True,
            "adaptive_max_retries": 1,
            "low_confidence_behavior": "ask",
            # Generation
            "enable_generation": True,
            "strict_extractive": False,
            "max_generation_tokens": 512,
            # Reranking
            "enable_reranking": True,
            "reranking_strategy": "flashrank",
            # Monitoring / observability
            "enable_monitoring": True,
            "enable_observability": False,
        },
    ),
    "research": RAGProfile(
        name="research",
        description=(
            "Research profile: enables most advanced retrieval (expansion, "
            "PRF, HyDE, decomposition, multi-vector) and verification "
            "features for quality analysis. Higher latency and cost."
        ),
        defaults={
            # Retrieval
            "search_mode": "hybrid",
            "top_k": 20,
            "enable_cache": False,
            "adaptive_cache": False,
            "enable_multi_vector_passages": True,
            "enable_precomputed_spans": True,
            # Query processing
            "expand_query": True,
            "expansion_strategies": ["acronym", "synonym", "domain", "entity"],
            "spell_check": True,
            "enable_prf": True,
            "prf_terms": 12,
            "prf_top_n": 10,
            "enable_hyde": True,
            "enable_gap_analysis": True,
            "enable_query_decomposition": True,
            "max_subqueries": 4,
            # Guardrails / verification
            "enable_security_filter": True,
            "enable_injection_filter": True,
            "enable_content_policy_filter": True,
            "content_policy_types": ["pii"],
            "content_policy_mode": "redact",
            "require_hard_citations": True,
            "enable_numeric_fidelity": True,
            "numeric_fidelity_behavior": "ask",
            "enable_claims": True,
            "claims_top_k": 5,
            "claims_max": 20,
            "enable_post_verification": True,
            "adaptive_max_retries": 2,
            "adaptive_time_budget_sec": 20.0,
            "adaptive_rerun_on_low_confidence": True,
            "adaptive_rerun_time_budget_sec": 15.0,
            # Generation
            "enable_generation": True,
            "enable_multi_turn_synthesis": True,
            "synthesis_time_budget_sec": 30.0,
            "max_generation_tokens": 1024,
            # Reranking
            "enable_reranking": True,
            "reranking_strategy": "hybrid",
            "enable_learned_fusion": True,
            # Monitoring / observability
            "enable_monitoring": True,
            "enable_observability": True,
            "enable_performance_analysis": True,
            "track_cost": True,
            "debug_mode": False,
        },
    ),
    "cheap": RAGProfile(
        name="cheap",
        description=(
            "Cheap/fast profile: favors lower latency and cost by disabling "
            "most expensive extras (HyDE, PRF, claims, adaptive reruns) and "
            "using simpler retrieval/reranking. Guardrails remain on but "
            "post-verification and numeric checks are relaxed."
        ),
        defaults={
            # Retrieval
            "search_mode": "fts",
            "top_k": 8,
            "enable_cache": True,
            "adaptive_cache": False,
            # Query processing
            "expand_query": False,
            "enable_prf": False,
            "enable_hyde": False,
            "enable_gap_analysis": False,
            "enable_query_decomposition": False,
            # Guardrails (minimal but present)
            "enable_security_filter": True,
            "enable_injection_filter": True,
            "enable_content_policy_filter": False,
            "require_hard_citations": False,
            "enable_numeric_fidelity": False,
            "enable_claims": False,
            "enable_post_verification": False,
            # Generation
            "enable_generation": True,
            "strict_extractive": False,
            "max_generation_tokens": 384,
            # Reranking
            "enable_reranking": True,
            "reranking_strategy": "flashrank",
            # Monitoring / observability
            "enable_monitoring": False,
            "enable_observability": False,
            "enable_performance_analysis": False,
            "track_cost": False,
        },
    ),
}


def list_profiles() -> Dict[ProfileName, RAGProfile]:
    """Return a copy of all registered profiles keyed by name."""
    return dict(_PROFILES)


def get_profile(name: ProfileName) -> RAGProfile:
    """Fetch a profile by name."""
    if name not in _PROFILES:
        # Defensive: keep error message explicit for callers
        raise ValueError(f"Unknown RAG profile: {name!r}")
    return _PROFILES[name]


def get_profile_kwargs(
    name: ProfileName,
    overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build keyword arguments for `unified_rag_pipeline` from a profile.

    The returned dict can be passed as `**kwargs` to the pipeline. Any
    provided overrides take precedence over profile defaults.
    """
    profile = get_profile(name)
    kwargs: Dict[str, Any] = dict(profile.defaults)
    if overrides:
        # Copy into a mutable dict to avoid mutating caller mappings
        for key, value in overrides.items():
            kwargs[key] = value
    return kwargs


def apply_profile_to_kwargs(
    name: ProfileName,
    existing: Optional[MutableMapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Merge a profile into an existing kwargs-style mapping.

    This is useful when a caller already has a dict of parameters and wants
    to layer a profile underneath as a set of defaults.
    """
    base = dict(get_profile(name).defaults)
    if existing:
        base.update(existing)
    return base


def get_multi_tenant_safe_kwargs(
    namespace: str,
    overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build kwargs for a multi-tenant-safe production configuration.

    This helper layers stricter defaults for multi-tenant deployments on top
    of the "production" profile:

    - Requires a non-empty `namespace` and sets it as `index_namespace`.
    - Disables OTEL-style observability (`enable_observability=False`) while
      keeping lightweight metrics via `enable_monitoring=True`.

    Callers should still configure global settings such as
    `RAG_PAYLOAD_EXEMPLAR_SAMPLING=0` if they want to fully disable payload
    exemplars in shared storage.
    """
    if not namespace or not str(namespace).strip():
        raise ValueError("Multi-tenant safe profile requires a non-empty namespace.")

    # Start from production defaults so we inherit guardrails and safety knobs.
    base = get_profile_kwargs("production", overrides=overrides)

    # Enforce per-tenant namespace and disable OTEL observability by default.
    base["index_namespace"] = str(namespace).strip()
    base["enable_observability"] = False
    base.setdefault("enable_monitoring", True)

    return base
