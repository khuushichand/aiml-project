"""Bounded candidate planning helpers for the RAG retrieval tuning recipe."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

SUPPORTED_V1_KNOBS = {
    "search_mode",
    "top_k",
    "hybrid_alpha",
    "enable_reranking",
    "reranking_strategy",
    "rerank_top_k",
    "chunking_preset",
}

_RETRIEVAL_KNOBS = {
    "search_mode",
    "top_k",
    "hybrid_alpha",
    "enable_reranking",
    "reranking_strategy",
    "rerank_top_k",
}
_INDEXING_KNOBS = {"chunking_preset"}
_ALLOWED_TOP_LEVEL_KEYS = {
    "candidate_id",
    "description",
    "indexing_config",
    "metadata",
    "name",
    "retrieval_config",
    "tags",
}
_ALLOWED_SEARCH_MODES = {"fts", "vector", "hybrid"}
_ALLOWED_RERANKING_STRATEGIES = {"cross_encoder", "flashrank", "hybrid", "none"}
_ALLOWED_CHUNKING_PRESETS = {"baseline", "compact", "fixed_index"}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def normalize_candidate_config(
    candidate: Mapping[str, Any],
    *,
    default_candidate_id: str | None = None,
) -> dict[str, Any]:
    """Normalize a manual or generated candidate into the bounded V1 shape."""
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be an object.")

    raw_candidate = dict(candidate)
    retrieval_config = _extract_candidate_section(raw_candidate, "retrieval_config", _RETRIEVAL_KNOBS)
    indexing_config = _extract_candidate_section(raw_candidate, "indexing_config", _INDEXING_KNOBS)

    _reject_unknown_top_level_keys(raw_candidate)

    normalized_retrieval = _normalize_retrieval_config(retrieval_config)
    normalized_indexing = _normalize_indexing_config(indexing_config)

    candidate_id = str(
        raw_candidate.get("candidate_id")
        or default_candidate_id
        or _build_candidate_id(normalized_retrieval, normalized_indexing)
    ).strip()
    if not candidate_id:
        candidate_id = _build_candidate_id(normalized_retrieval, normalized_indexing)

    normalized: dict[str, Any] = {
        "candidate_id": candidate_id,
        "retrieval_config": normalized_retrieval,
    }
    if normalized_indexing:
        normalized["indexing_config"] = normalized_indexing
    if raw_candidate.get("name") is not None:
        normalized["name"] = str(raw_candidate["name"]).strip()
    if raw_candidate.get("description") is not None:
        normalized["description"] = str(raw_candidate["description"]).strip()
    if raw_candidate.get("metadata") is not None:
        if not isinstance(raw_candidate["metadata"], Mapping):
            raise ValueError("candidate.metadata must be an object when provided.")
        normalized["metadata"] = dict(raw_candidate["metadata"])
    if raw_candidate.get("tags") is not None:
        raw_tags = raw_candidate["tags"]
        if isinstance(raw_tags, str) or not isinstance(raw_tags, (list, tuple, set)):
            raise ValueError("candidate.tags must be a list of strings when provided.")
        normalized["tags"] = []
        for tag in raw_tags:
            if not isinstance(tag, str):
                raise ValueError("candidate.tags entries must be strings.")
            if tag.strip():
                normalized["tags"].append(tag.strip())
    return normalized


def build_auto_sweep(base_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a small, bounded auto-sweep around a base retrieval configuration."""
    base_candidate = _normalize_base_config(base_config)
    variants: list[dict[str, Any]] = [base_candidate]

    retrieval = base_candidate["retrieval_config"]
    indexing = base_candidate.get("indexing_config", {})

    top_k = int(retrieval.get("top_k", 10))
    lower_top_k = max(3, top_k // 2)
    higher_top_k = min(25, max(top_k + 2, top_k * 2))
    if lower_top_k != top_k:
        variants.append(
            _override_candidate(
                base_candidate,
                candidate_id="auto-topk-low",
                retrieval_overrides={"top_k": lower_top_k},
            )
        )
    if higher_top_k not in {top_k, lower_top_k}:
        variants.append(
            _override_candidate(
                base_candidate,
                candidate_id="auto-topk-high",
                retrieval_overrides={"top_k": higher_top_k},
            )
        )

    if str(retrieval.get("search_mode", "hybrid")) == "hybrid":
        lower_alpha = max(0.1, round(float(retrieval.get("hybrid_alpha", 0.7)) - 0.2, 2))
        higher_alpha = min(0.9, round(float(retrieval.get("hybrid_alpha", 0.7)) + 0.2, 2))
        if lower_alpha != float(retrieval.get("hybrid_alpha", 0.7)):
            variants.append(
                _override_candidate(
                    base_candidate,
                    candidate_id="auto-hybrid-fts-lean",
                    retrieval_overrides={"hybrid_alpha": lower_alpha},
                )
            )
        if higher_alpha != float(retrieval.get("hybrid_alpha", 0.7)):
            variants.append(
                _override_candidate(
                    base_candidate,
                    candidate_id="auto-hybrid-vector-lean",
                    retrieval_overrides={"hybrid_alpha": higher_alpha},
                )
            )

    if bool(retrieval.get("enable_reranking", True)):
        variants.append(
            _override_candidate(
                base_candidate,
                candidate_id="auto-rerank-off",
                retrieval_overrides={
                    "enable_reranking": False,
                    "reranking_strategy": "none",
                },
            )
        )

    if indexing.get("chunking_preset") != "compact":
        variants.append(
            _override_candidate(
                base_candidate,
                candidate_id="auto-compact-chunking",
                indexing_overrides={"chunking_preset": "compact"},
            )
        )

    deduped: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    for candidate in variants:
        signature = _candidate_signature(candidate)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped.append(candidate)
        if len(deduped) >= 8:
            break
    return deduped


def _normalize_base_config(base_config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(base_config, dict):
        raise ValueError("base_config must be an object.")

    payload = dict(base_config)
    candidate: dict[str, Any] = {}
    if isinstance(payload.get("retrieval_config"), Mapping):
        candidate["retrieval_config"] = dict(payload["retrieval_config"])
    else:
        candidate["retrieval_config"] = {}
    if isinstance(payload.get("indexing_config"), Mapping):
        candidate["indexing_config"] = dict(payload["indexing_config"])
    else:
        candidate["indexing_config"] = {}

    for key in _RETRIEVAL_KNOBS:
        if key in payload:
            candidate["retrieval_config"][key] = payload[key]
    for key in _INDEXING_KNOBS:
        if key in payload:
            candidate["indexing_config"][key] = payload[key]

    if payload.get("candidate_id") is not None:
        candidate["candidate_id"] = str(payload["candidate_id"])

    return normalize_candidate_config(candidate, default_candidate_id="auto-baseline")


def _override_candidate(
    base_candidate: dict[str, Any],
    *,
    candidate_id: str,
    retrieval_overrides: Mapping[str, Any] | None = None,
    indexing_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidate: dict[str, Any] = {
        "candidate_id": candidate_id,
        "retrieval_config": dict(base_candidate["retrieval_config"]),
    }
    if base_candidate.get("indexing_config"):
        candidate["indexing_config"] = dict(base_candidate["indexing_config"])

    if retrieval_overrides:
        candidate["retrieval_config"].update(dict(retrieval_overrides))
    if indexing_overrides:
        candidate.setdefault("indexing_config", {}).update(dict(indexing_overrides))
    return normalize_candidate_config(candidate, default_candidate_id=candidate_id)


def _extract_candidate_section(
    candidate: dict[str, Any],
    section_name: str,
    allowed_keys: set[str],
) -> dict[str, Any]:
    section = candidate.get(section_name)
    if section is None:
        return {key: candidate[key] for key in allowed_keys if key in candidate}
    if not isinstance(section, Mapping):
        raise ValueError(f"{section_name} must be an object.")
    section_dict = dict(section)
    unknown_keys = sorted(set(section_dict) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"unsupported candidate knob: {unknown_keys[0]}")
    return section_dict


def _reject_unknown_top_level_keys(candidate: dict[str, Any]) -> None:
    unknown_keys = sorted(
        set(candidate)
        - _ALLOWED_TOP_LEVEL_KEYS
        - _RETRIEVAL_KNOBS
        - _INDEXING_KNOBS
    )
    if unknown_keys:
        raise ValueError(f"unsupported candidate knob: {unknown_keys[0]}")


def _normalize_retrieval_config(retrieval_config: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "search_mode": "hybrid",
        "top_k": 10,
        "hybrid_alpha": 0.7,
        "enable_reranking": True,
        "reranking_strategy": "flashrank",
        "rerank_top_k": 10,
    }
    for key in retrieval_config:
        normalized[key] = retrieval_config[key]

    search_mode = str(normalized["search_mode"]).strip().lower()
    if search_mode not in _ALLOWED_SEARCH_MODES:
        raise ValueError(f"unsupported candidate knob: search_mode={search_mode}")
    normalized["search_mode"] = search_mode
    try:
        normalized["top_k"] = int(normalized["top_k"])
    except (TypeError, ValueError) as exc:
        raise ValueError("top_k must be a positive integer.") from exc
    try:
        normalized["hybrid_alpha"] = float(normalized["hybrid_alpha"])
    except (TypeError, ValueError) as exc:
        raise ValueError("hybrid_alpha must be between 0.0 and 1.0.") from exc
    if not 0.0 <= normalized["hybrid_alpha"] <= 1.0:
        raise ValueError("hybrid_alpha must be between 0.0 and 1.0.")
    normalized["enable_reranking"] = _normalize_bool_value(
        normalized["enable_reranking"],
        field_name="enable_reranking",
    )
    reranking_strategy = str(normalized["reranking_strategy"]).strip().lower()
    if reranking_strategy not in _ALLOWED_RERANKING_STRATEGIES:
        raise ValueError(f"unsupported candidate knob: reranking_strategy={reranking_strategy}")
    normalized["reranking_strategy"] = reranking_strategy
    try:
        normalized["rerank_top_k"] = int(normalized["rerank_top_k"])
    except (TypeError, ValueError) as exc:
        raise ValueError("rerank_top_k must be a positive integer.") from exc
    if normalized["top_k"] <= 0:
        raise ValueError("top_k must be a positive integer.")
    if normalized["rerank_top_k"] <= 0:
        raise ValueError("rerank_top_k must be a positive integer.")
    return normalized


def _normalize_indexing_config(indexing_config: Mapping[str, Any]) -> dict[str, Any]:
    if not indexing_config:
        return {}
    unknown_keys = sorted(set(indexing_config) - _INDEXING_KNOBS)
    if unknown_keys:
        raise ValueError(f"unsupported candidate knob: {unknown_keys[0]}")
    normalized = dict(indexing_config)
    chunking_preset = str(normalized.get("chunking_preset") or "").strip().lower()
    if not chunking_preset:
        return {}
    if chunking_preset not in _ALLOWED_CHUNKING_PRESETS:
        raise ValueError(f"unsupported candidate knob: chunking_preset={chunking_preset}")
    normalized["chunking_preset"] = chunking_preset
    return normalized


def _normalize_bool_value(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    raise ValueError(f"{field_name} must be a boolean value.")


def _candidate_signature(candidate: dict[str, Any]) -> str:
    payload = {
        "retrieval_config": candidate.get("retrieval_config", {}),
        "indexing_config": candidate.get("indexing_config", {}),
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_candidate_id(
    retrieval_config: Mapping[str, Any],
    indexing_config: Mapping[str, Any],
) -> str:
    payload = {
        "retrieval_config": dict(retrieval_config),
        "indexing_config": dict(indexing_config),
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"auto-{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:10]}"
