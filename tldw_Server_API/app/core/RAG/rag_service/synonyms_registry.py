"""
Synonyms/Alias Registry per corpus/namespace.

Loads optional JSON files from Config_Files/Synonyms/<corpus>.json with a mapping of
term -> [aliases]. Used to enrich both FTS (where integrated) and query rewrites.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import json

from loguru import logger


def _find_project_root(start: Optional[Path] = None) -> Path:
    """Locate the project root by finding a parent that contains 'tldw_Server_API'."""
    p = (start or Path(__file__).resolve())
    for anc in p.parents:
        if (anc / "tldw_Server_API").exists():
            return anc
    return p.parents[-1]


def get_corpus_synonyms(corpus: str | None) -> Dict[str, List[str]]:
    if not corpus:
        return {}
    # Prefer repo root containing tldw_Server_API; fallback to CWD
    base = _find_project_root()
    candidates = [
        base / "tldw_Server_API" / "Config_Files" / "Synonyms" / f"{corpus}.json",
        base / "Config_Files" / "Synonyms" / f"{corpus}.json",
    ]
    # Also walk ancestors to be resilient to how tests compute roots
    start = Path(__file__).resolve()
    for anc in start.parents:
        candidates.append(anc / "tldw_Server_API" / "Config_Files" / "Synonyms" / f"{corpus}.json")
        candidates.append(anc / "Config_Files" / "Synonyms" / f"{corpus}.json")
    path = next((c for c in candidates if c.exists()), candidates[0])
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # normalize to str -> list[str]
                    out: Dict[str, List[str]] = {}
                    for k, v in data.items():
                        if isinstance(k, str):
                            if isinstance(v, list):
                                out[k.lower()] = [str(x).lower() for x in v]
                            elif isinstance(v, str):
                                out[k.lower()] = [v.lower()]
                    return out
    except Exception as e:
        logger.warning(f"Failed to load synonyms for corpus '{corpus}': {e}")
    return {}
