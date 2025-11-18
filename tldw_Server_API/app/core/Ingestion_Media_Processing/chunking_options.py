from __future__ import annotations

from typing import Any, Dict, Optional

from tldw_Server_API.app.core.Utils.Utils import logging
from tldw_Server_API.app.core.config import load_and_log_configs, settings


def prepare_chunking_options_dict(form_data: Any) -> Optional[Dict[str, Any]]:
    """
    Prepare the dictionary of chunking options based on form data.

    This is extracted from `_legacy_media._prepare_chunking_options_dict`
    so it can be reused by core ingestion helpers and modular endpoints.
    """
    if not getattr(form_data, "perform_chunking", False):
        logging.info("Chunking disabled.")
        return None

    default_chunk_method = "sentences"
    media_type = str(getattr(form_data, "media_type", "") or "")
    if media_type == "ebook":
        default_chunk_method = "ebook_chapters"
        logging.info("Setting chunk method to 'ebook_chapters' for ebook type.")
    elif media_type in ["video", "audio"]:
        default_chunk_method = "sentences"

    final_chunk_method = getattr(form_data, "chunk_method", None) or default_chunk_method

    chunk_size_used = getattr(form_data, "chunk_size", None)
    chunk_overlap_used = getattr(form_data, "chunk_overlap", None)

    if media_type in ["document", "email"]:
        try:
            if chunk_size_used is None or int(chunk_size_used) == 500:
                chunk_size_used = 1000
        except Exception:
            chunk_size_used = 1000

    if media_type == "email":
        try:
            if chunk_overlap_used is None or int(chunk_overlap_used) == 200:
                chunk_overlap_used = 150
        except Exception:
            chunk_overlap_used = 150

    if media_type == "ebook":
        final_chunk_method = "ebook_chapters"

    inferred_enable_contextual = bool(
        getattr(form_data, "contextual_llm_model", None)
        or getattr(form_data, "context_window_size", None)
    )

    language: Optional[str]
    if media_type in ["audio", "video"]:
        language = getattr(form_data, "chunk_language", None) or getattr(
            form_data, "transcription_language", None
        )
    else:
        language = getattr(form_data, "chunk_language", None)

    chunk_options: Dict[str, Any] = {
        "method": final_chunk_method,
        "max_size": chunk_size_used,
        "overlap": chunk_overlap_used,
        "adaptive": getattr(form_data, "use_adaptive_chunking", False),
        "multi_level": getattr(form_data, "use_multi_level_chunking", False),
        "language": language,
        "custom_chapter_pattern": getattr(form_data, "custom_chapter_pattern", None),
        "enable_contextual_chunking": bool(
            getattr(form_data, "enable_contextual_chunking", False)
            or inferred_enable_contextual
        ),
        "contextual_llm_model": getattr(form_data, "contextual_llm_model", None),
        "context_window_size": getattr(form_data, "context_window_size", None),
        "context_strategy": getattr(form_data, "context_strategy", None),
        "context_token_budget": getattr(form_data, "context_token_budget", None),
    }

    try:
        hier_flag = getattr(form_data, "hierarchical_chunking", None)
        hier_template = getattr(form_data, "hierarchical_template", None)
        if hier_flag is True or (hier_template and isinstance(hier_template, dict)):
            chunk_options["hierarchical"] = True
            if isinstance(hier_template, dict):
                chunk_options["hierarchical_template"] = hier_template
            chunk_options.setdefault("method", "sentences")
    except Exception:
        pass

    if final_chunk_method == "propositions":
        try:
            cfg = load_and_log_configs()
            cfg_dict = cfg if isinstance(cfg, dict) else {}
            c = cfg_dict.get("chunking_config", {}) if isinstance(cfg_dict, dict) else {}
            if "proposition_engine" in c:
                chunk_options["proposition_engine"] = c.get("proposition_engine")
            if "proposition_prompt_profile" in c:
                chunk_options["proposition_prompt_profile"] = c.get(
                    "proposition_prompt_profile"
                )
            if "proposition_aggressiveness" in c:
                try:
                    chunk_options["proposition_aggressiveness"] = int(
                        c.get("proposition_aggressiveness")
                    )
                except Exception:
                    pass
            if "proposition_min_proposition_length" in c:
                try:
                    chunk_options["proposition_min_proposition_length"] = int(
                        c.get("proposition_min_proposition_length")
                    )
                except Exception:
                    pass
        except Exception as cfg_err:
            logging.debug(f"Proposition config defaults not loaded: {cfg_err}")

    logging.info("Chunking enabled with options: {}", chunk_options)
    return chunk_options


def prepare_common_options(
    form_data: Any,
    chunk_options: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Prepare the dictionary of common processing options for ingestion.

    Extracted from `_legacy_media._prepare_common_options` to share
    behavior between the legacy and modular `/media/add` paths.
    """
    return {
        "keywords": getattr(form_data, "keywords", []),
        "custom_prompt": getattr(form_data, "custom_prompt", None),
        "system_prompt": getattr(form_data, "system_prompt", None),
        "overwrite_existing": bool(getattr(form_data, "overwrite_existing", False)),
        "perform_analysis": bool(getattr(form_data, "perform_analysis", False)),
        "chunk_options": chunk_options,
        "api_name": getattr(form_data, "api_name", None),
        "api_provider": getattr(form_data, "api_provider", None),
        "model_name": getattr(form_data, "model_name", None),
        "store_in_db": True,
        "summarize_recursively": bool(
            getattr(form_data, "summarize_recursively", False)
        ),
        "author": getattr(form_data, "author", None),
    }

