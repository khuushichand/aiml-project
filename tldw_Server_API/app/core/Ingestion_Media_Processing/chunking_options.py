from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.config import load_and_log_configs
from tldw_Server_API.app.core.Utils.Utils import logging


def prepare_chunking_options_dict(form_data: Any) -> dict[str, Any] | None:
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

    language: str | None
    if media_type in ["audio", "video"]:
        language = getattr(form_data, "chunk_language", None) or getattr(
            form_data, "transcription_language", None
        )
    else:
        language = getattr(form_data, "chunk_language", None)

    chunk_options: dict[str, Any] = {
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


def apply_chunking_template_if_any(
    form_data: Any,
    db: Any,
    chunking_options_dict: dict[str, Any] | None,
    *,
    TemplateClassifier: Any | None = None,
    first_url: str | None = None,
    first_filename: str | None = None,
) -> dict[str, Any] | None:
    """
    Apply an explicit or auto-selected chunking template to the provided
    chunking options dictionary.

    This helper encapsulates the template application logic that was
    previously embedded in the `/media/add` orchestration so it can be
    reused by process-* endpoints without duplicating behaviour.
    """
    try:
        if not getattr(form_data, "perform_chunking", False):
            return chunking_options_dict

        opts = chunking_options_dict or {}

        # 1) Apply explicit template by name when provided.
        template_name = getattr(form_data, "chunking_template_name", None)
        if template_name:
            try:
                tpl = db.get_chunking_template(name=template_name)
            except Exception as db_err:
                logging.warning("Failed to load chunking template '%s': %s", template_name, db_err)
                return opts

            if tpl and tpl.get("template_json"):
                import json as _json

                raw_cfg = tpl["template_json"]
                try:
                    cfg = _json.loads(raw_cfg) if isinstance(raw_cfg, str) else raw_cfg
                except Exception:
                    cfg = {}
                cfg = cfg or {}
                hier_cfg = (cfg.get("chunking") or {}).get("config", {}) or {}
                hier_tpl = hier_cfg.get("hierarchical_template")
                if isinstance(hier_tpl, dict):
                    opts = opts or {}
                    tpl_method = (cfg.get("chunking") or {}).get("method") or "sentences"
                    # Respect explicit user chunk_method if set, but let the
                    # template override any default method chosen earlier.
                    if not getattr(form_data, "chunk_method", None):
                        opts["method"] = tpl_method

                    # Allow template to provide max_size/overlap so callers do
                    # not need to redundantly pass chunk_size/chunk_overlap.
                    tpl_max_size = hier_cfg.get("max_size")
                    tpl_overlap = hier_cfg.get("overlap")
                    if isinstance(tpl_max_size, int):
                        opts["max_size"] = tpl_max_size
                    if isinstance(tpl_overlap, int):
                        opts["overlap"] = tpl_overlap

                    opts["hierarchical"] = True
                    opts["hierarchical_template"] = hier_tpl
            return opts

        # 2) Respect explicit user hierarchical/method flags (already
        # encoded in chunking_options_dict by prepare_chunking_options_dict).

        # 3) Auto-match a template when requested and the user has not
        # explicitly requested hierarchical chunking.
        if (
            getattr(form_data, "auto_apply_template", False)
            and not getattr(form_data, "hierarchical_chunking", False)
            and TemplateClassifier is not None
        ):
            try:
                candidates = db.list_chunking_templates(
                    include_builtin=True,
                    include_custom=True,
                    tags=None,
                    user_id=None,
                    include_deleted=False,
                )
            except Exception as list_err:
                logging.warning("Failed to list chunking templates for auto-apply: {}", list_err)
                return opts

            best_cfg: dict[str, Any] | None = None
            best_key: tuple[float, int] | None = None

            for t in candidates:
                try:
                    import json as _json

                    cfg = _json.loads(t.get("template_json") or "{}")
                    if not isinstance(cfg, dict):
                        cfg = {}
                except Exception:
                    cfg = {}

                try:
                    score = TemplateClassifier.score(  # type: ignore[call-arg]
                        cfg,
                        media_type=getattr(form_data, "media_type", None),
                        title=getattr(form_data, "title", None),
                        url=first_url,
                        filename=first_filename,
                    )
                except Exception:
                    score = 0.0

                if score <= 0:
                    continue

                priority = ((cfg.get("classifier") or {}).get("priority") or 0)  # type: ignore[assignment]
                key = (float(score), int(priority))

                if best_cfg is None or best_key is None or key > best_key:
                    best_cfg, best_key = cfg, key

            if best_cfg:
                hier_cfg = (best_cfg.get("chunking") or {}).get("config") or {}
                tpl = hier_cfg.get("hierarchical_template")
                if isinstance(tpl, dict):
                    opts = opts or {}
                    tpl_method = (best_cfg.get("chunking") or {}).get("method", "sentences")
                    if not getattr(form_data, "chunk_method", None):
                        opts["method"] = tpl_method

                    tpl_max_size = hier_cfg.get("max_size")
                    tpl_overlap = hier_cfg.get("overlap")
                    if isinstance(tpl_max_size, int):
                        opts["max_size"] = tpl_max_size
                    if isinstance(tpl_overlap, int):
                        opts["overlap"] = tpl_overlap

                    opts["hierarchical"] = True
                    opts["hierarchical_template"] = tpl

        return opts
    except Exception as auto_err:  # Defensive: never break callers
        logging.warning("Auto-apply chunking template helper failed: {}", auto_err)
        return chunking_options_dict


def prepare_common_options(
    form_data: Any,
    chunk_options: dict[str, Any] | None,
) -> dict[str, Any]:
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
