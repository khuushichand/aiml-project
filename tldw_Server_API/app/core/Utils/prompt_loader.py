import os
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


def _api_component_root() -> Path:
    """Return the path to the API component root (tldw_Server_API).

    Resolves relative to this file by walking up to the package root instead of
    joining "tldw_Server_API" onto a separately computed repo root. This avoids
    accidentally double-joining the component name in nested/in-tree installs.
    """
    here = Path(__file__).resolve()
    # .../tldw_Server_API/app/core/Utils/prompt_loader.py -> parents[3] == tldw_Server_API
    api_root = here.parents[3]
    if api_root.name != "tldw_Server_API":
        # Fall back by scanning ancestors for a directory named tldw_Server_API
        for anc in here.parents:
            if (anc / "Config_Files").exists() and anc.name == "tldw_Server_API":
                api_root = anc
                break
    logger.debug(f"Prompt loader API root resolved to: {api_root}")
    return api_root


def _prompts_dir() -> str:
    """Resolve the Prompts directory.

    Precedence:
      1) Env override via TLDW_CONFIG_DIR -> <dir>/Prompts (if exists)
      2) <tldw_Server_API>/Config_Files/Prompts
      3) <nearest ancestor with Config_Files>/Prompts
    """
    # 1) Env override
    cfg_dir = os.getenv("TLDW_CONFIG_DIR")
    if cfg_dir:
        p = Path(cfg_dir).expanduser() / "Prompts"
        if p.exists():
            logger.debug(f"Prompt loader using env TLDW_CONFIG_DIR Prompts at: {p}")
            return str(p)

    # 2) API component default
    api_root = _api_component_root()
    p2 = api_root / "Config_Files" / "Prompts"
    if p2.exists():
        return str(p2)

    # 3) Fallback: search ancestors for Config_Files/Prompts
    here = Path(__file__).resolve()
    for anc in here.parents:
        maybe = anc / "Config_Files" / "Prompts"
        if maybe.exists():
            logger.debug(f"Prompt loader fallback Prompts at: {maybe}")
            return str(maybe)

    # Last resort: return the API default (even if missing) without creating it
    logger.debug(f"Prompt loader defaulting to: {p2}")
    return str(p2)


def _module_file_base(module: str) -> str:
    # Map module to prompts filename
    # e.g., embeddings -> embeddings.prompts.md
    sanitized = re.sub(r"[^a-z0-9_\-]", "", module.strip().lower())
    return os.path.join(_prompts_dir(), f"{sanitized}.prompts")


def _norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", key.strip().lower())


def _load_yaml(path: str) -> Optional[Dict[str, Any]]:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def load_prompt(module: str, key: str) -> Optional[str]:
    """Load a named prompt snippet from Prompts folder.

    Searches for a markdown heading containing the key, then returns the
    first fenced code block following that heading. If not found, returns None.
    """
    base = _module_file_base(module)
    norm = _norm_key(key)

    # Prefer YAML
    yaml_path_1 = base + ".yaml"
    yaml_path_2 = base + ".yml"
    for ypath in (yaml_path_1, yaml_path_2):
        if os.path.exists(ypath):
            ydata = _load_yaml(ypath)
            if isinstance(ydata, dict):
                # two shapes supported: {key: str} or {templates: {name: {template:..., type:...}}}
                # Try flat map first
                if norm in {_norm_key(k): k for k in ydata.keys()}:
                    # Find original key name casing
                    for k, v in ydata.items():
                        if _norm_key(k) == norm and isinstance(v, str):
                            return v.strip()
                        if _norm_key(k) == norm and isinstance(v, dict) and isinstance(v.get("template"), str):
                            return v["template"].strip()
                # Try nested under 'templates'
                tmap = ydata.get("templates") if isinstance(ydata.get("templates"), dict) else None
                if tmap:
                    for k, v in tmap.items():
                        if _norm_key(k) == norm and isinstance(v, dict) and isinstance(v.get("template"), str):
                            return v["template"].strip()
            # If YAML present but key not found, continue to JSON/MD fallback

    # Try JSON
    json_path = base + ".json"
    if os.path.exists(json_path):
        jdata = _load_json(json_path)
        if isinstance(jdata, dict):
            for k, v in jdata.items():
                if _norm_key(k) == norm and isinstance(v, str):
                    return v.strip()
                if _norm_key(k) == norm and isinstance(v, dict) and isinstance(v.get("template"), str):
                    return v["template"].strip()

    # Find a heading that contains the key (case-insensitive)
    # Then capture the next fenced code block ```...```
    md_path = base + ".md"
    if os.path.exists(md_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            text = ""
        if text:
            pattern = re.compile(
                r"^\s*#{1,6}\s*([^\n]+?%s[^\n]*)\n+```([\s\S]*?)```" % re.escape(key),
                re.IGNORECASE | re.MULTILINE,
            )
            m = pattern.search(text)
            if m:
                return m.group(2).strip()
            # Fallback: first fenced code block in file
            any_block = re.search(r"```([\s\S]*?)```", text)
            if any_block:
                return any_block.group(1).strip()

    return None
