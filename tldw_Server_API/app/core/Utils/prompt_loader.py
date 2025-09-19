import os
import re
import json
from typing import Optional, Dict, Any


def _repo_root() -> str:
    # Compute repo root from this file location
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))


def _prompts_dir() -> str:
    return os.path.join(_repo_root(), "tldw_Server_API", "Config_Files", "Prompts")


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

