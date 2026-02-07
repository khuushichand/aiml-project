# config_paths.py
"""Shared configuration path resolution helpers."""

from __future__ import annotations

import os
import platform
from pathlib import Path

_CONFIG_FILE_ENV = "TLDW_CONFIG_FILE"
_CONFIG_PATH_ENV = "TLDW_CONFIG_PATH"
_CONFIG_DIR_ENV = "TLDW_CONFIG_DIR"
_DEFAULT_CONFIG_FILENAME = "config.txt"
_DEFAULT_MODULE_YAML = {
    "tts": "tts_providers_config.yaml",
    "embeddings": "embeddings_config.yaml",
    "evaluations": "evaluations_config.yaml",
}


def _env_value(name: str) -> str | None:
    raw = os.getenv(name)
    if not raw:
        return None
    raw = raw.strip()
    return raw or None


def _interpret_config_path(raw: str) -> tuple[Path, bool]:
    path = Path(raw).expanduser()
    if path.exists():
        return path, path.is_file()
    if path.suffix or path.name.lower() == _DEFAULT_CONFIG_FILENAME:
        return path, True
    return path, False


def _find_repo_root(start: Path | None = None) -> Path | None:
    probe = start or Path(__file__).resolve()
    for anc in probe.parents:
        if (anc / ".git").exists():
            return anc
        if (anc / "pyproject.toml").exists() and (anc / "tldw_Server_API").is_dir():
            return anc
    return None


def _find_api_root(start: Path | None = None) -> Path:
    probe = start or Path(__file__).resolve()
    for anc in probe.parents:
        if anc.name == "tldw_Server_API":
            return anc
    parents = probe.parents
    return parents[2] if len(parents) > 2 else parents[-1]


def _user_config_dir() -> Path:
    system = platform.system().lower()
    if system == "windows":
        base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA") or "~/.config"
        return Path(base).expanduser() / "tldw"
    if system == "darwin":
        return Path("~/Library/Application Support").expanduser() / "tldw"
    base = os.getenv("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / "tldw"


def _resolve_env_root() -> Path | None:
    raw = _env_value(_CONFIG_FILE_ENV)
    if raw:
        path, is_file = _interpret_config_path(raw)
        return path.parent if is_file else path

    raw = _env_value(_CONFIG_PATH_ENV)
    if raw:
        path, is_file = _interpret_config_path(raw)
        return path.parent if is_file else path

    raw = _env_value(_CONFIG_DIR_ENV)
    if raw:
        return Path(raw).expanduser()

    return None


def _packaged_config_root() -> Path:
    return _find_api_root() / "Config_Files"


def resolve_config_root() -> Path:
    """Resolve the base directory for configuration assets."""
    env_root = _resolve_env_root()
    if env_root is not None:
        return env_root

    repo_root = _find_repo_root()
    if repo_root is not None:
        repo_config_root = repo_root / "Config_Files"
        if (repo_config_root / _DEFAULT_CONFIG_FILENAME).exists():
            return repo_config_root
        packaged_root = _packaged_config_root()
        if packaged_root.exists():
            return packaged_root
        if repo_config_root.exists():
            return repo_config_root
        return packaged_root

    user_config = _user_config_dir()
    if user_config.exists():
        return user_config

    return _packaged_config_root()


def resolve_config_file(filename: str = _DEFAULT_CONFIG_FILENAME) -> Path:
    """Resolve a config file path, honoring explicit overrides when set."""
    if filename == _DEFAULT_CONFIG_FILENAME:
        raw = _env_value(_CONFIG_FILE_ENV)
        if raw:
            path = Path(raw).expanduser()
            if path.exists() and path.is_dir():
                raise FileNotFoundError(
                    f"{_CONFIG_FILE_ENV} must point to a file, got directory: {path}"
                )
            if not path.exists():
                raise FileNotFoundError(
                    f"{_CONFIG_FILE_ENV} is set but missing: {path}"
                )
            return path

        raw = _env_value(_CONFIG_PATH_ENV)
        if raw:
            path, is_file = _interpret_config_path(raw)
            return path if is_file else (path / filename)

    return resolve_config_root() / filename


def resolve_prompts_dir() -> Path:
    """Resolve the Prompts directory using the shared config root."""
    return resolve_config_root() / "Prompts"


def resolve_module_yaml(
    module_name: str,
    filename_override: str | None = None,
) -> Path | None:
    """Resolve a module YAML configuration path."""
    if not module_name:
        return None

    key = module_name.strip().lower()
    filename = _DEFAULT_MODULE_YAML.get(key)
    if filename is None and (key.endswith(".yaml") or key.endswith(".yml")):
        filename = module_name
    elif filename is None:
        filename = f"{key}.yaml"

    if filename_override:
        override_path = Path(filename_override).expanduser()
        if override_path.is_dir():
            return override_path / filename
        return override_path

    return resolve_config_root() / filename
