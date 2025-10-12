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
import threading
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Set

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
    # Compiled rules; each rule includes the regex and optional per-pattern action/replacement
    block_patterns: List[object] = None  # list of PatternRule (backward field name)
    # Enabled categories filter (None or empty means allow all)
    categories_enabled: Optional[Set[str]] = None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable snapshot of the policy (without raw regex objects)."""
        patterns: List[str] = []
        try:
            if self.block_patterns:
                # Backward-friendly: expose raw patterns as strings
                tmp: List[str] = []
                for p in self.block_patterns:
                    pat = getattr(p, 'pattern', None)
                    if pat is None and isinstance(p, PatternRule):
                        pat = getattr(p.regex, 'pattern', '')
                    tmp.append(pat or '')
                patterns = tmp
        except Exception:
            patterns = []
        # Provide richer rule view
        rules: List[Dict[str, str]] = []
        try:
            if self.block_patterns:
                for p in self.block_patterns:
                    if isinstance(p, PatternRule):
                        rules.append({
                            "pattern": p.regex.pattern,
                            "action": p.action or "",
                            "replacement": p.replacement or "",
                            "categories": ",".join(sorted(p.categories)) if p.categories else "",
                        })
                    else:
                        rules.append({"pattern": getattr(p, 'pattern', ''), "action": "", "replacement": "", "categories": ""})
        except Exception:
            rules = []
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
            "rules": rules,
            "categories_enabled": sorted(self.categories_enabled) if self.categories_enabled else [],
        }


@dataclass
class PatternRule:
    regex: re.Pattern
    action: Optional[str] = None  # block | redact | warn | None
    replacement: Optional[str] = None  # only used when action=redact
    categories: Optional[Set[str]] = None  # e.g., {"pii", "confidential"}


class ModerationService:
    """Loads moderation configuration and evaluates content against policies."""

    def __init__(self) -> None:
        self._config = load_and_log_configs() or {}
        self._lock = threading.RLock()
        # Safety/performance limits (overridable via config or env)
        self._max_scan_chars = int(os.getenv("MODERATION_MAX_SCAN_CHARS", "200000"))
        self._max_replacements_per_pattern = int(os.getenv("MODERATION_MAX_REPLACEMENTS_PER_PATTERN", "1000"))
        self._runtime_override: Dict[str, object] = {}
        self._runtime_overrides_path: Optional[str] = None
        self._global_policy = self._load_global_policy()
        # Load runtime overrides file (if any) and re-apply policy
        try:
            self._load_runtime_overrides_file()
            self._global_policy = self._load_global_policy()
        except Exception:
            pass
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
        runtime_overrides_path = mod_cfg.get("runtime_overrides_file") or os.getenv("MODERATION_RUNTIME_OVERRIDES_FILE")
        # Optional safety/perf overrides
        try:
            self._max_scan_chars = int(mod_cfg.get("max_scan_chars", self._max_scan_chars))
        except Exception:
            pass
        try:
            self._max_replacements_per_pattern = int(mod_cfg.get("max_replacements_per_pattern", self._max_replacements_per_pattern))
        except Exception:
            pass
        # Categories
        cats_raw = (mod_cfg.get("categories_enabled") or os.getenv("MODERATION_CATEGORIES_ENABLED") or "").strip()
        categories_enabled = set()
        if cats_raw:
            categories_enabled = {c.strip().lower() for c in cats_raw.split(',') if c.strip()}
        pii_enabled = str(mod_cfg.get("pii_enabled", os.getenv("MODERATION_PII_ENABLED", "false"))).strip().lower() in {"1","true","yes","on","y"}
        # Apply runtime overrides if present
        try:
            if isinstance(self._runtime_override.get("categories_enabled"), (set, list)):
                categories_enabled = set(self._runtime_override.get("categories_enabled") or [])
            if "pii_enabled" in self._runtime_override:
                pii_enabled = bool(self._runtime_override.get("pii_enabled"))
        except Exception:
            pass

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
            categories_enabled=categories_enabled or None,
        )

        # Store paths for overrides
        self._user_overrides_path = user_overrides_path
        self._blocklist_path = blocklist_path
        if runtime_overrides_path:
            self._runtime_overrides_path = runtime_overrides_path
        else:
            self._runtime_overrides_path = "tldw_Server_API/Config_Files/moderation_runtime_overrides.json"

        # Optionally augment with built-in PII rules
        if pii_enabled:
            try:
                pii_rules = self._load_builtin_pii_rules()
                if pii_rules:
                    policy.block_patterns.extend(pii_rules)
            except Exception as e:
                logger.warning(f"Failed to load builtin PII rules: {e}")
        return policy

    def _parse_rule_line(self, s: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[Set[str]]]:
        """Parse a single blocklist line into (pattern_expr, action, replacement).
        Supported formats:
          - literal
          - /regex/
          - literal -> block|warn
          - literal -> redact:REPL
          - /regex/ -> block|warn|redact:REPL
        Returns (expr, action, repl). expr has slashes for regex, or literal text.
        """
        if not s:
            return None, None, None, None
        text = s
        action = None
        repl = None
        categories: Optional[Set[str]] = None
        # Extract categories suffix if present (e.g., "... #pii,confidential")
        if '#' in text:
            # Split on last '#'
            before, after = text.rsplit('#', 1)
            cats = {c.strip().lower() for c in after.split(',') if c.strip()}
            if cats:
                categories = cats
                text = before.strip()
        if '->' in s:
            parts = s.split('->', 1)
            text = parts[0].strip()
            rhs = parts[1].strip()
            if rhs:
                rhs_l = rhs.lower()
                if rhs_l.startswith('redact:'):
                    action = 'redact'
                    repl = rhs[len('redact:'):].strip()
                elif rhs_l in ('block', 'warn', 'redact'):
                    action = rhs_l
                else:
                    # Unknown directive; treat as literal action text
                    action = rhs
        return text, action, repl, categories

    def _load_block_patterns(self, path: Optional[str]) -> List[PatternRule]:
        patterns: List[PatternRule] = []
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
                        expr, action, repl, cats = self._parse_rule_line(s)
                        if expr is None:
                            continue
                        # Treat lines starting and ending with / as regex; otherwise escape for literal match
                        if len(expr) >= 2 and expr.startswith("/") and expr.endswith("/"):
                            raw = expr[1:-1]
                            if self._is_regex_dangerous(raw):
                                logger.warning(f"Skipped dangerous regex in blocklist: {raw}")
                                continue
                            pat = re.compile(raw, flags=re.IGNORECASE)
                        else:
                            pat = re.compile(re.escape(expr), flags=re.IGNORECASE)
                        patterns.append(PatternRule(regex=pat, action=(action or None), replacement=(repl or None), categories=(cats or None)))
                    except re.error as e:
                        logger.warning(f"Invalid blocklist pattern '{s}': {e}")
        except Exception as e:
            logger.error(f"Failed to load moderation blocklist: {e}")
        return patterns

    def _load_builtin_pii_rules(self) -> List[PatternRule]:
        """Create PatternRule list for common PII if available and enabled."""
        rules: List[PatternRule] = []
        try:
            from tldw_Server_API.app.core.Audit.unified_audit_service import PIIDetector
            for name, compiled in getattr(PIIDetector, 'PII_PATTERNS', {}).items():
                try:
                    # Ensure it's a compiled regex
                    if isinstance(compiled, re.Pattern):
                        rules.append(PatternRule(regex=compiled, action='redact', replacement='[PII]', categories={'pii', name}))
                except Exception:
                    continue
        except Exception:
            # Fallback minimal PII patterns
            try:
                basic = {
                    'pii_email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', re.IGNORECASE),
                    'pii_phone': re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
                }
                for name, pat in basic.items():
                    rules.append(PatternRule(regex=pat, action='redact', replacement='[PII]', categories={'pii', name}))
            except Exception:
                return []
        return rules

    @staticmethod
    def _has_nested_quantifiers(expr: str) -> bool:
        """Heuristic check for nested quantifiers like (.*)+ or (.+)* that can cause catastrophic backtracking."""
        try:
            return bool(re.search(r"\((?:[^)(]|\([^)(]*\))*[+*][^)]*\)\s*[+*]", expr))
        except Exception:
            return False

    @staticmethod
    def _too_many_groups(expr: str, limit: int = 100) -> bool:
        try:
            return expr.count("(") - expr.count("\\(") > limit
        except Exception:
            return False

    def _is_regex_dangerous(self, expr: str) -> bool:
        if not expr:
            return True
        if len(expr) > 2000:
            return True
        if self._has_nested_quantifiers(expr):
            return True
        if self._too_many_groups(expr):
            return True
        return False

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
        with self._lock:
            self._config = load_and_log_configs() or {}
            self._global_policy = self._load_global_policy()
            # Load runtime overrides from file and re-apply
            try:
                self._load_runtime_overrides_file()
                self._global_policy = self._load_global_policy()
            except Exception:
                pass
            self._user_overrides = self._load_user_overrides()

    # --------------- Settings helpers (runtime) ---------------
    def get_settings(self) -> Dict[str, object]:
        pol = self._global_policy
        return {
            "pii_enabled": bool(self._runtime_override.get("pii_enabled", None)) if ("pii_enabled" in self._runtime_override) else None,
            "categories_enabled": list(self._runtime_override.get("categories_enabled") or []) if ("categories_enabled" in self._runtime_override) else None,
            "effective": {
                "pii_enabled": any(isinstance(r, PatternRule) and r.categories and ("pii" in r.categories) for r in (pol.block_patterns or [])),
                "categories_enabled": sorted(pol.categories_enabled) if pol.categories_enabled else [],
            }
        }

    def update_settings(self, pii_enabled: Optional[bool] = None, categories_enabled: Optional[List[str]] = None, persist: bool = False) -> Dict[str, object]:
        with self._lock:
            if pii_enabled is not None:
                self._runtime_override["pii_enabled"] = bool(pii_enabled)
            if categories_enabled is not None:
                cats = [str(c).strip().lower() for c in categories_enabled if str(c).strip()]
                self._runtime_override["categories_enabled"] = set(cats)
            if persist:
                self._save_runtime_overrides_file()
            # Recompute policy with overrides
            self._global_policy = self._load_global_policy()
            return self.get_settings()

    def _load_runtime_overrides_file(self) -> None:
        path = self._runtime_overrides_path
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                ro: Dict[str, object] = {}
                if "pii_enabled" in data:
                    ro["pii_enabled"] = bool(data.get("pii_enabled"))
                cats = data.get("categories_enabled")
                if isinstance(cats, list):
                    ro["categories_enabled"] = {str(c).strip().lower() for c in cats if str(c).strip()}
                elif isinstance(cats, str):
                    ro["categories_enabled"] = {c.strip().lower() for c in cats.split(',') if c.strip()}
                self._runtime_override = ro
        except Exception as e:
            logger.warning(f"Failed to load runtime overrides file: {e}")

    def _save_runtime_overrides_file(self) -> None:
        path = self._runtime_overrides_path
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            out: Dict[str, object] = {}
            if "pii_enabled" in self._runtime_override:
                out["pii_enabled"] = bool(self._runtime_override.get("pii_enabled"))
            if "categories_enabled" in self._runtime_override:
                cats = self._runtime_override.get("categories_enabled")
                if isinstance(cats, set):
                    out["categories_enabled"] = sorted(list(cats))
                elif isinstance(cats, list):
                    out["categories_enabled"] = cats
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save runtime overrides file: {e}")

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
            categories_enabled=self._parse_categories_override(u.get("categories_enabled")) or p.categories_enabled,
        )
        return policy

    @staticmethod
    def _parse_categories_override(v: Optional[str]) -> Optional[Set[str]]:
        if v is None:
            return None
        try:
            if isinstance(v, list):
                return {str(x).strip().lower() for x in v if str(x).strip()}
            if isinstance(v, str):
                txt = v.strip()
                if not txt:
                    return set()
                return {c.strip().lower() for c in txt.split(',') if c.strip()}
        except Exception:
            return None
        return None

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
        scan_text = text[: self._max_scan_chars]
        for rule in policy.block_patterns:
            pat = rule.regex if isinstance(rule, PatternRule) else rule
            if pat.search(scan_text):
                snippet = pat.pattern
                return True, snippet
        return False, None

    def redact_text(self, text: str, policy: ModerationPolicy) -> str:
        if not text or not policy.block_patterns:
            return text
        # Operate on a bounded slice for safety
        head = text[: self._max_scan_chars]
        tail = text[self._max_scan_chars:]
        redacted = head
        for rule in policy.block_patterns:
            pat = rule.regex if isinstance(rule, PatternRule) else rule
            repl = None
            if isinstance(rule, PatternRule) and rule.replacement:
                repl = rule.replacement
            try:
                redacted = pat.sub(repl or policy.redact_replacement, redacted, count=self._max_replacements_per_pattern)
            except re.error:
                # in case of unexpected regex issue, skip
                continue
        return redacted + tail

    # --------------- Decision helpers ---------------
    def evaluate_action(self, text: str, policy: ModerationPolicy, phase: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """Decide the action for a given text and phase.
        Returns (action, redacted_text, matched_pattern, category)
          - action in {'pass','warn','redact','block'}
          - redacted_text only provided for 'redact'
        Pattern-level action overrides global defaults.
        """
        if not text:
            return 'pass', None, None, None
        if not policy.enabled:
            return 'pass', None, None, None
        enabled_phase = policy.input_enabled if phase == 'input' else policy.output_enabled
        if not enabled_phase:
            return 'pass', None, None, None
        scan_text = text[: self._max_scan_chars]
        for rule in policy.block_patterns or []:
            pat = rule.regex if isinstance(rule, PatternRule) else rule
            # Category gating
            if isinstance(rule, PatternRule) and policy.categories_enabled:
                rcats = rule.categories or set()
                if not (rcats & policy.categories_enabled):
                    continue
            m = pat.search(scan_text)
            if not m:
                continue
            # Prefer rule action if specified, else global
            default_action = policy.input_action if phase == 'input' else policy.output_action
            action = None
            if isinstance(rule, PatternRule) and rule.action:
                action = rule.action
            else:
                action = default_action
            action = (action or 'warn').lower()
            if action == 'redact':
                # Apply per-rule replacement if present
                head = text[: self._max_scan_chars]
                tail = text[self._max_scan_chars:]
                repl = rule.replacement if isinstance(rule, PatternRule) and rule.replacement else policy.redact_replacement
                try:
                    red = pat.sub(repl, head, count=self._max_replacements_per_pattern)
                except re.error:
                    red = head
                cat = None
                if isinstance(rule, PatternRule) and rule.categories:
                    # Prefer specific subtype over generic 'pii' if present
                    sub = sorted([c for c in rule.categories if c != "pii"]) or ["pii"]
                    cat = sub[0]
                return 'redact', red + tail, pat.pattern, cat
            if action == 'block':
                cat = None
                if isinstance(rule, PatternRule) and rule.categories:
                    sub = sorted([c for c in rule.categories if c != "pii"]) or ["pii"]
                    cat = sub[0]
                return 'block', None, pat.pattern, cat
            if action == 'warn':
                cat = None
                if isinstance(rule, PatternRule) and rule.categories:
                    sub = sorted([c for c in rule.categories if c != "pii"]) or ["pii"]
                    cat = sub[0]
                return 'warn', None, pat.pattern, cat
            # Unknown -> treat as warn
            return 'warn', None, pat.pattern, None
        return 'pass', None, None, None

    # --------------- Persistence helpers ---------------
    def list_user_overrides(self) -> Dict[str, Dict[str, str]]:
        """Return a shallow copy of all user overrides."""
        return dict(self._user_overrides or {})

    def set_user_override(self, user_id: str, override: Dict[str, str]) -> bool:
        """Create or update a user override and persist to file if configured."""
        if not user_id:
            return False
        with self._lock:
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
        with self._lock:
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
            with self._lock:
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
        with self._lock:
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
        with self._lock:
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
