"""
moderation_service.py
Description: Centralized, configurable moderation/guardrails for chat content

Features:
- Global moderation settings (from config.txt [Moderation])
- Optional per-user overrides via a JSON mapping file
- Simple, local rule-based checks using blocklist (literals or regex)
- Redaction or blocking actions for inputs and outputs

Notes:
- No network calls; designed to function offline by default
- For streaming responses, only redaction is applied (blocking mid-stream is avoided)
"""

from __future__ import annotations

import json
import os
import re
import hashlib
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.config import load_and_log_configs, load_comprehensive_config


@dataclass
class ModerationPolicy:
    enabled: bool = False
    input_enabled: bool = True
    output_enabled: bool = True
    input_action: str = "block"  # block | redact | warn
    output_action: str = "redact"  # redact | block | warn (block only applies to non-streaming)
    redact_replacement: str = "[REDACTED]"
    per_user_overrides: bool = True
    block_patterns: List[re.Pattern] = None  # compiled regex patterns

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable snapshot of the policy (without raw regex objects)."""
        patterns: List[str] = []
        try:
            if self.block_patterns:
                patterns = [getattr(p, 'pattern', '') for p in self.block_patterns]
        except Exception:
            patterns = []
        return {
            "enabled": self.enabled,
            "input_enabled": self.input_enabled,
            "output_enabled": self.output_enabled,
            "input_action": self.input_action,
            "output_action": self.output_action,
            "redact_replacement": self.redact_replacement,
            "per_user_overrides": self.per_user_overrides,
            "blocklist_count": len(patterns),
            "block_patterns": patterns,
        }


class ModerationService:
    """Loads moderation configuration and evaluates content against policies."""

    def __init__(self) -> None:
        self._config = load_and_log_configs() or {}
        self._global_policy = self._load_global_policy()
        self._user_overrides: Dict[str, Dict[str, str]] = self._load_user_overrides()

    def _load_global_policy(self) -> ModerationPolicy:
        # Try modern dict config first
        mod_cfg = (self._config.get("moderation") or {}) if isinstance(self._config, dict) else {}
        # If not present, fall back to ConfigParser direct section
        if not mod_cfg:
            try:
                parser = load_comprehensive_config()
                if parser and parser.has_section('Moderation'):
                    # Convert to plain dict
                    mod_cfg = {k: v for k, v in parser.items('Moderation')}
            except Exception:
                mod_cfg = {}

        # Boolean helpers
        def _b(key: str, default: bool) -> bool:
            val = str(mod_cfg.get(key, default)).strip().lower()
            return val in {"1", "true", "yes", "y", "on"}

        # Paths
        blocklist_path = mod_cfg.get("blocklist_file") or os.getenv("MODERATION_BLOCKLIST_FILE")
        user_overrides_path = mod_cfg.get("user_overrides_file") or os.getenv("MODERATION_USER_OVERRIDES_FILE")

        # Build policy
        policy = ModerationPolicy(
            enabled=_b("enabled", False),
            input_enabled=_b("input_enabled", True),
            output_enabled=_b("output_enabled", True),
            input_action=str(mod_cfg.get("input_action", "block")).lower(),
            output_action=str(mod_cfg.get("output_action", "redact")).lower(),
            redact_replacement=str(mod_cfg.get("redact_replacement", "[REDACTED]")),
            per_user_overrides=_b("per_user_overrides", True),
            block_patterns=self._load_block_patterns(blocklist_path),
        )

        # Store paths for overrides
        self._user_overrides_path = user_overrides_path
        self._blocklist_path = blocklist_path
        return policy

    def _load_block_patterns(self, path: Optional[str]) -> List[re.Pattern]:
        patterns: List[re.Pattern] = []
        if not path:
            return patterns
        try:
            if not os.path.exists(path):
                logger.warning(f"Moderation blocklist file not found: {path}")
                return patterns
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    try:
                        # Treat lines starting and ending with / as regex; otherwise escape for literal match
                        if len(s) >= 2 and s.startswith("/") and s.endswith("/"):
                            pat = re.compile(s[1:-1], flags=re.IGNORECASE)
                        else:
                            pat = re.compile(re.escape(s), flags=re.IGNORECASE)
                        patterns.append(pat)
                    except re.error as e:
                        logger.warning(f"Invalid blocklist pattern '{s}': {e}")
        except Exception as e:
            logger.error(f"Failed to load moderation blocklist: {e}")
        return patterns

    def _load_user_overrides(self) -> Dict[str, Dict[str, str]]:
        overrides: Dict[str, Dict[str, str]] = {}
        p = getattr(self, "_user_overrides_path", None)
        if not p:
            return overrides
        try:
            if not os.path.exists(p):
                logger.info(f"Moderation user overrides file not found (optional): {p}")
                return overrides
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    overrides = {str(k): v for k, v in data.items() if isinstance(v, dict)}
        except Exception as e:
            logger.error(f"Failed to load user overrides: {e}")
        return overrides

    def reload(self) -> None:
        """Reload global config and overrides from disk."""
        self._config = load_and_log_configs() or {}
        self._global_policy = self._load_global_policy()
        self._user_overrides = self._load_user_overrides()

    def get_effective_policy(self, user_id: Optional[str]) -> ModerationPolicy:
        """Return policy after applying per-user overrides if enabled."""
        p = self._global_policy
        if not p.per_user_overrides or not user_id:
            return p
        u = self._user_overrides.get(str(user_id))
        if not u:
            return p
        # Clone and override selected fields
        policy = ModerationPolicy(
            enabled=self._coalesce_bool(u.get("enabled"), p.enabled),
            input_enabled=self._coalesce_bool(u.get("input_enabled"), p.input_enabled),
            output_enabled=self._coalesce_bool(u.get("output_enabled"), p.output_enabled),
            input_action=str(u.get("input_action", p.input_action)).lower(),
            output_action=str(u.get("output_action", p.output_action)).lower(),
            redact_replacement=str(u.get("redact_replacement", p.redact_replacement)),
            per_user_overrides=p.per_user_overrides,
            block_patterns=p.block_patterns,  # same global patterns for now
        )
        return policy

    def effective_policy_snapshot(self, user_id: Optional[str]) -> Dict[str, object]:
        """Return a serializable dict of the effective policy for inspection."""
        return self.get_effective_policy(user_id).to_dict()

    @staticmethod
    def _coalesce_bool(v: Optional[str | bool], default: bool) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return default
        return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

    # --------------- Checking and transformations ---------------
    def check_text(self, text: str, policy: ModerationPolicy) -> Tuple[bool, Optional[str]]:
        """Return (is_flagged, matched_sample)."""
        if not policy.enabled or not text:
            return False, None
        if not policy.block_patterns:
            return False, None
        for pat in policy.block_patterns:
            if pat.search(text):
                snippet = pat.pattern
                return True, snippet
        return False, None

    def redact_text(self, text: str, policy: ModerationPolicy) -> str:
        if not text or not policy.block_patterns:
            return text
        redacted = text
        for pat in policy.block_patterns:
            try:
                redacted = pat.sub(policy.redact_replacement, redacted)
            except re.error:
                # in case of unexpected regex issue, skip
                continue
        return redacted

    # --------------- Persistence helpers ---------------
    def list_user_overrides(self) -> Dict[str, Dict[str, str]]:
        """Return a shallow copy of all user overrides."""
        return dict(self._user_overrides or {})

    def set_user_override(self, user_id: str, override: Dict[str, str]) -> bool:
        """Create or update a user override and persist to file if configured."""
        if not user_id:
            return False
        self._user_overrides[str(user_id)] = {k: str(v) for k, v in override.items()}
        path = getattr(self, "_user_overrides_path", None)
        if not path:
            logger.warning("User override path not configured; changes will not persist across restarts")
            return True
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._user_overrides, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved moderation user overrides to {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save user overrides: {e}")
            return False

    def delete_user_override(self, user_id: str) -> bool:
        """Delete a user override and persist to file if configured."""
        if str(user_id) in self._user_overrides:
            self._user_overrides.pop(str(user_id), None)
            path = getattr(self, "_user_overrides_path", None)
            try:
                if path:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(self._user_overrides, f, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                logger.error(f"Failed to persist user override deletion: {e}")
                return False
        return False

    def get_blocklist_lines(self) -> List[str]:
        """Read current blocklist file lines (without trailing newlines)."""
        path = getattr(self, "_blocklist_path", None)
        if not path or not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return [ln.rstrip("\n") for ln in f.readlines()]
        except Exception as e:
            logger.error(f"Failed to read blocklist: {e}")
            return []

    def set_blocklist_lines(self, lines: List[str]) -> bool:
        """Write blocklist lines to file and reload compiled patterns."""
        path = getattr(self, "_blocklist_path", None)
        if not path:
            logger.warning("Blocklist path not configured; cannot persist blocklist")
            return False
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # Normalize line endings; ensure trailing newline for POSIX friendliness
            text = "\n".join(lines).rstrip("\n") + "\n"
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            # Reload patterns
            self._global_policy.block_patterns = self._load_block_patterns(path)
            logger.info(f"Updated moderation blocklist at {path} ({len(lines)} lines)")
            return True
        except Exception as e:
            logger.error(f"Failed to write blocklist: {e}")
            return False

    # --------------- Managed blocklist with versioning ---------------
    @staticmethod
    def _normalize_lines(lines: List[str]) -> List[str]:
        return [str(ln).rstrip("\n") for ln in (lines or [])]

    @staticmethod
    def _compute_version(lines: List[str]) -> str:
        """Compute a stable version string (ETag) for the blocklist content."""
        norm = ModerationService._normalize_lines(lines)
        payload = ("\n".join(norm) + "\n").encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def get_blocklist_state(self) -> Dict[str, object]:
        """Return current blocklist with a content hash version and indexed items."""
        lines = self.get_blocklist_lines()
        version = self._compute_version(lines)
        items = [{"id": i, "line": ln} for i, ln in enumerate(lines)]
        return {"version": version, "items": items}

    def append_blocklist_line(self, expected_version: str, line: str) -> Tuple[bool, Dict[str, object]]:
        """Append a line with optimistic concurrency control. Returns (ok, state)."""
        if line is None:
            return False, {"error": "line required"}
        current = self.get_blocklist_lines()
        cur_version = self._compute_version(current)
        if expected_version and cur_version != expected_version:
            return False, {"version": cur_version, "conflict": True}
        new_lines = current + [str(line).rstrip("\n")]
        ok = self.set_blocklist_lines(new_lines)
        state = self.get_blocklist_state() if ok else {"error": "persist failed"}
        return ok, state

    def delete_blocklist_index(self, expected_version: str, index: int) -> Tuple[bool, Dict[str, object]]:
        """Delete a line by index with optimistic concurrency control. Returns (ok, state)."""
        current = self.get_blocklist_lines()
        cur_version = self._compute_version(current)
        if expected_version and cur_version != expected_version:
            return False, {"version": cur_version, "conflict": True}
        if index < 0 or index >= len(current):
            return False, {"error": "index out of range", "count": len(current)}
        new_lines = current[:index] + current[index+1:]
        ok = self.set_blocklist_lines(new_lines)
        state = self.get_blocklist_state() if ok else {"error": "persist failed"}
        return ok, state


# Singleton accessor
_moderation_service: Optional[ModerationService] = None


def get_moderation_service() -> ModerationService:
    global _moderation_service
    if _moderation_service is None:
        _moderation_service = ModerationService()
    return _moderation_service
