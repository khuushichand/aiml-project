"""Config profile management service.

Supports named config snapshots, rollback, import/export.
Stored in-memory with optional persistence to a JSON file.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

_PROFILES_FILE = os.getenv(
    "TLDW_CONFIG_PROFILES_FILE",
    "Databases/config_profiles.json",
)


class ConfigProfileStore:
    """In-memory config profile store with optional file-based persistence."""

    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            try:
                path = Path(_PROFILES_FILE)
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        self._profiles = data
                    logger.info("Loaded {} config profiles from {}", len(self._profiles), path)
            except Exception as exc:
                logger.warning("Failed to load config profiles: {}", exc)
            self._loaded = True

    async def _persist(self) -> None:
        """Best-effort persistence to disk."""
        try:
            path = Path(_PROFILES_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._profiles, indent=2, default=str), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist config profiles: {}", exc)

    async def list_profiles(self) -> list[dict[str, Any]]:
        await self._ensure_loaded()
        result = []
        for name, profile in self._profiles.items():
            result.append({
                "name": name,
                "created_at": profile.get("created_at", ""),
                "description": profile.get("description", ""),
                "section_count": len(profile.get("sections", {})),
            })
        result.sort(key=lambda p: p["created_at"], reverse=True)
        return result

    async def save_profile(
        self,
        name: str,
        sections: dict[str, dict[str, str]],
        description: str = "",
    ) -> dict[str, Any]:
        """Save a config snapshot as a named profile."""
        await self._ensure_loaded()
        now = datetime.now(timezone.utc).isoformat()
        profile = {
            "name": name,
            "description": description,
            "created_at": now,
            "sections": sections,
        }
        async with self._lock:
            self._profiles[name] = profile
        await self._persist()
        return profile

    async def get_profile(self, name: str) -> dict[str, Any] | None:
        await self._ensure_loaded()
        return self._profiles.get(name)

    async def delete_profile(self, name: str) -> bool:
        await self._ensure_loaded()
        async with self._lock:
            deleted = self._profiles.pop(name, None) is not None
        if deleted:
            await self._persist()
        return deleted

    async def snapshot_current_config(self, name: str, description: str = "") -> dict[str, Any]:
        """Snapshot the current config.txt into a named profile."""
        from tldw_Server_API.app.core.config import load_comprehensive_config
        from tldw_Server_API.app.core.config_paths import resolve_config_file

        config_file = resolve_config_file()
        config = load_comprehensive_config()
        sections: dict[str, dict[str, str]] = {}
        for section in config.sections():
            sections[section] = dict(config.items(section))
        return await self.save_profile(name, sections, description)

    async def export_config(self) -> dict[str, Any]:
        """Export the current config.txt as a structured dict."""
        from tldw_Server_API.app.core.config import load_comprehensive_config

        config = load_comprehensive_config()
        sections: dict[str, dict[str, str]] = {}
        for section in config.sections():
            sections[section] = dict(config.items(section))
        return {"sections": sections, "exported_at": datetime.now(timezone.utc).isoformat()}

    async def update_config_section(
        self,
        section: str,
        values: dict[str, str],
    ) -> dict[str, Any]:
        """Update a config.txt section with new values.

        Returns the updated section values.
        """
        import configparser
        from tldw_Server_API.app.core.config_paths import resolve_config_file

        config_path = resolve_config_file()

        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")

        if not config.has_section(section):
            config.add_section(section)

        for key, value in values.items():
            config.set(section, key, str(value))

        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)

        logger.info("Updated config section [{}] with {} keys", section, len(values))
        return dict(config.items(section))

    async def import_config(self, sections: dict[str, dict[str, str]]) -> dict[str, Any]:
        """Import config sections into config.txt, overwriting existing values.

        Returns summary of changes.
        """
        import configparser
        from tldw_Server_API.app.core.config_paths import resolve_config_file

        config_path = resolve_config_file()
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")

        updated_sections = []
        for section, values in sections.items():
            if not config.has_section(section):
                config.add_section(section)
            for key, value in values.items():
                config.set(section, key, str(value))
            updated_sections.append(section)

        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)

        logger.info("Imported config: {} sections updated", len(updated_sections))
        return {"updated_sections": updated_sections, "imported_at": datetime.now(timezone.utc).isoformat()}


# Singleton
_store: ConfigProfileStore | None = None
_store_lock = asyncio.Lock()


async def get_config_profile_store() -> ConfigProfileStore:
    global _store
    if _store is None:
        async with _store_lock:
            if _store is None:
                _store = ConfigProfileStore()
    return _store
