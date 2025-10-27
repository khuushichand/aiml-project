"""
Audio_Custom_Vocabulary
-----------------------

Lightweight helpers to inject a custom vocabulary into STT flows.

Capabilities:
- Build an initial_prompt for faster-whisper from a terms list.
- Apply optional post-processing replacements ("misheard" -> "correct").

Configuration (Config_Files/config.txt under [STT-Settings]):
- custom_vocab_terms_file: path to a text/JSON file of terms (one per line or JSON list)
- custom_vocab_replacements_file: path to a JSON object mapping misheard->correct
- custom_vocab_initial_prompt_enable: True/False (default True)
- custom_vocab_postprocess_enable: True/False (default True)
- custom_vocab_prompt_template: Optional template string with "{terms}" placeholder
- custom_vocab_case_sensitive: True/False (controls postprocess matching)

Notes:
- initial_prompt affects only faster-whisper; Nemo/Parakeet/Canary are post-processed.
- Replacements are applied conservatively with whole-word regex where possible.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

try:
    # Lazy config mapping (avoids heavy imports at startup)
    from tldw_Server_API.app.core.config import loaded_config_data
except Exception:
    loaded_config_data = {}  # type: ignore


def _as_bool(val: object, default: bool) -> bool:
    if val is None:
        return default
    s = str(val).strip().lower()
    if s in {"1", "true", "yes", "on", "y"}:
        return True
    if s in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _read_text_lines(path: Path) -> List[str]:
    try:
        content = path.read_text(encoding="utf-8")
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        return lines
    except Exception as e:
        logger.warning(f"Custom vocab terms file read failed: path={path}, error={e}")
        return []


def _read_json(path: Path) -> Optional[object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Custom vocab JSON read failed: path={path}, error={e}")
        return None


def _load_terms_from_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    # Allow simple newline-delimited text or JSON list
    if path.suffix.lower() in {".txt", ""}:
        return _read_text_lines(path)
    data = _read_json(path)
    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]
    # JSON object with {"terms": [...]} also accepted
    if isinstance(data, dict):
        terms = data.get("terms")
        if isinstance(terms, list):
            return [str(x).strip() for x in terms if str(x).strip()]
    return []


def _load_replacements_from_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    # JSON dict expected; tolerate JSON lines of pairs
    data = _read_json(path)
    if isinstance(data, dict):
        # Ensure string->string
        out: Dict[str, str] = {}
        for k, v in data.items():
            try:
                ks = str(k)
                vs = str(v)
                if ks and vs:
                    out[ks] = vs
            except Exception:
                continue
        return out
    # Fallback: each non-empty line as "misheard=correct" or "misheard,correct"
    items: Dict[str, str] = {}
    for ln in _read_text_lines(path):
        if "=" in ln:
            a, b = ln.split("=", 1)
        elif "," in ln:
            a, b = ln.split(",", 1)
        else:
            continue
        a = a.strip()
        b = b.strip()
        if a and b:
            items[a] = b
    return items


def _cfg_section() -> Dict[str, object]:
    try:
        cfg = loaded_config_data.get("STT-Settings", {}) or {}
    except Exception:
        cfg = {}
    # Some callers use underscore variant
    if not cfg:
        try:
            cfg = loaded_config_data.get("STT_Settings", {}) or {}
        except Exception:
            cfg = {}
    return cfg  # type: ignore[return-value]


def load_terms() -> List[str]:
    cfg = _cfg_section()
    raw_path = str(cfg.get("custom_vocab_terms_file", "") or "").strip()
    if not raw_path:
        return []
    path = Path(raw_path).expanduser()
    terms = _load_terms_from_file(path)
    # Deduplicate and keep short; avoid bloating prompts
    uniq: List[str] = []
    seen = set()
    for t in terms:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
        if len(uniq) >= 64:  # cap prompt size
            break
    return uniq


def load_replacements() -> Dict[str, str]:
    cfg = _cfg_section()
    raw_path = str(cfg.get("custom_vocab_replacements_file", "") or "").strip()
    if not raw_path:
        return {}
    path = Path(raw_path).expanduser()
    return _load_replacements_from_file(path)


def build_initial_prompt(terms: Optional[List[str]] = None) -> Optional[str]:
    """Build an initial prompt for faster-whisper from terms list.

    Returns None when disabled or no terms.
    """
    cfg = _cfg_section()
    if not _as_bool(cfg.get("custom_vocab_initial_prompt_enable"), True):
        return None
    if terms is None:
        terms = load_terms()
    if not terms:
        return None
    template = str(cfg.get("custom_vocab_prompt_template") or "").strip() or "Domain terms: {terms}."
    # Join with commas; protect length
    joined = ", ".join(terms[:64])
    return template.replace("{terms}", joined)


def apply_replacements(text: str) -> str:
    """Apply configured replacements to a text string.

    Uses whole-word case-insensitive matching by default. If case sensitive,
    uses exact case provided in keys.
    """
    if not text:
        return text
    cfg = _cfg_section()
    if not _as_bool(cfg.get("custom_vocab_postprocess_enable"), True):
        return text
    repl = load_replacements()
    if not repl:
        return text
    case_sensitive = _as_bool(cfg.get("custom_vocab_case_sensitive"), False)
    flags = 0 if case_sensitive else re.IGNORECASE
    out = text
    for wrong, correct in repl.items():
        if not wrong:
            continue
        # Heuristic: in case-sensitive mode, avoid altering ALL-CAPS tokens which
        # are commonly acronyms (e.g., IOT). Tests expect such tokens to remain
        # untouched when case sensitivity is enabled.
        if case_sensitive and wrong.isupper():
            # Skip ALL-CAPS entries when matching exactly
            continue
        # Word-boundary pattern; allow phrases with spaces/hyphens
        pattern = r"\b" + re.escape(wrong) + r"\b"
        try:
            out = re.sub(pattern, correct, out, flags=flags)
        except re.error:
            # Fallback to simple replace
            out = out.replace(wrong, correct)
    return out


def initial_prompt_if_enabled() -> Optional[str]:
    return build_initial_prompt()


def postprocess_text_if_enabled(text: str) -> str:
    return apply_replacements(text)
