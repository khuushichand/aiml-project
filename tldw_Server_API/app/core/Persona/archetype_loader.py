"""
Archetype YAML Loader Service.

Loads persona archetype templates from YAML files, validates them with
Pydantic, and caches them in memory for fast access by API endpoints.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from threading import RLock

import yaml
from loguru import logger
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.archetype_schemas import (
    ArchetypeSummary,
    ArchetypeTemplate,
)

# Module-level cache
_CACHE: dict[str, ArchetypeTemplate] = {}
_CACHE_LOCK = RLock()


def load_archetypes_from_directory(
    directory: str | Path,
) -> dict[str, ArchetypeTemplate]:
    """Load all ``*.yaml`` files from *directory*, validate via Pydantic, and cache.

    Malformed files are logged with loguru and skipped so that one bad
    file does not prevent the rest from loading.  The glob results are
    sorted to guarantee deterministic ordering across platforms.

    The module-level ``_CACHE`` is cleared before populating so that
    repeated calls always reflect the current directory contents.

    Parameters
    ----------
    directory:
        Path to a directory containing archetype YAML files.

    Returns
    -------
    dict[str, ArchetypeTemplate]
        Mapping of archetype *key* to its validated template.
    """
    global _CACHE

    dir_path = Path(directory)
    new_cache: dict[str, ArchetypeTemplate] = {}

    if not dir_path.is_dir():
        with _CACHE_LOCK:
            _CACHE = new_cache
        logger.warning("Archetype directory does not exist: {}", dir_path)
        return new_cache.copy()

    yaml_files = sorted(dir_path.glob("*.yaml"))
    for yaml_file in yaml_files:
        try:
            raw = yaml_file.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            if not isinstance(data, dict) or "archetype" not in data:
                logger.warning(
                    "Skipping {}: missing top-level 'archetype' key", yaml_file.name
                )
                continue
            archetype_data = data["archetype"]
            if not isinstance(archetype_data, Mapping):
                logger.warning(
                    "Skipping {}: top-level 'archetype' value must be a mapping",
                    yaml_file.name,
                )
                continue
            template = ArchetypeTemplate.model_validate(archetype_data)
            new_cache[template.key] = template
            logger.debug("Loaded archetype '{}' from {}", template.key, yaml_file.name)
        except (OSError, ValidationError, yaml.YAMLError):
            logger.opt(exception=True).warning(
                "Skipping malformed archetype file: {}", yaml_file.name
            )

    with _CACHE_LOCK:
        _CACHE = new_cache
        snapshot = dict(_CACHE)

    logger.info("Loaded {} archetype(s) from {}", len(snapshot), dir_path)
    return snapshot


def list_archetypes() -> list[ArchetypeSummary]:
    """Return a summary (key, label, tagline, icon) of all cached archetypes."""
    with _CACHE_LOCK:
        values = list(_CACHE.values())

    return [
        ArchetypeSummary(
            key=t.key,
            label=t.label,
            tagline=t.tagline,
            icon=t.icon,
        )
        for t in values
    ]


def get_archetype(key: str) -> ArchetypeTemplate | None:
    """Return the cached archetype identified by *key*, or ``None``."""
    with _CACHE_LOCK:
        return _CACHE.get(key)
