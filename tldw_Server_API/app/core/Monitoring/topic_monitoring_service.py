from __future__ import annotations

"""
Topic Monitoring Service

Detects configured topics in text and emits non-blocking alerts for admins/owners.

Design goals:
- Local, offline-first; regex/literal patterns
- Safe regex compilation (reuse heuristics from moderation)
- Simple per-user scoping in Phase 1
- Bounded scanning and dedup window to avoid alert spam
"""

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.monitoring_schemas import Watchlist, WatchlistRule
from tldw_Server_API.app.core.DB_Management.TopicMonitoring_DB import (
    TopicMonitoringDB,
    TopicAlert,
)
from tldw_Server_API.app.core.config import load_and_log_configs
from tldw_Server_API.app.core.Monitoring.notification_service import get_notification_service


@dataclass
class CompiledRule:
    regex: re.Pattern
    category: Optional[str]
    severity: Optional[str]
    pattern_text: str  # original pattern or regex body
    note: Optional[str] = None


class TopicMonitoringService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._config = load_and_log_configs() or {}
        self._max_scan_chars = int(os.getenv("TOPIC_MONITOR_MAX_SCAN_CHARS", "200000"))
        self._dedup_window_seconds = int(os.getenv("TOPIC_MONITOR_DEDUP_SECONDS", "300"))
        raw_watchlists = (
            self._config.get("monitoring", {}).get("watchlists_file")
            if isinstance(self._config, dict)
            else None
        ) or os.getenv("MONITORING_WATCHLISTS_FILE", "tldw_Server_API/Config_Files/monitoring_watchlists.json")
        raw_db_path = os.getenv("MONITORING_ALERTS_DB", "Databases/monitoring_alerts.db")
        # Anchor relative paths to project root to avoid creating dirs from CWD
        try:
            from pathlib import Path as _Path
            from tldw_Server_API.app.core.Utils.Utils import get_project_root as _gpr
            _root = _Path(_gpr())
        except Exception:
            from pathlib import Path as _Path
            _root = _Path(__file__).resolve().parents[5]
        try:
            wl_p = _Path(str(raw_watchlists))
        except Exception:
            wl_p = _Path("tldw_Server_API/Config_Files/monitoring_watchlists.json")
        if not wl_p.is_absolute():
            wl_p = (_root / wl_p).resolve()
        try:
            db_p = _Path(str(raw_db_path))
        except Exception:
            db_p = _Path("Databases/monitoring_alerts.db")
        if not db_p.is_absolute():
            db_p = (_root / db_p).resolve()
        self._watchlists_path = str(wl_p)
        self._db_path = str(db_p)
        self._db = TopicMonitoringDB(db_path=self._db_path)
        self._watchlists: Dict[str, Watchlist] = {}
        # Cached compiled patterns per watchlist id
        self._compiled: Dict[str, List[CompiledRule]] = {}
        self._load_watchlists_file()

    # --------------------- File I/O ---------------------
    def _load_watchlists_file(self) -> None:
        try:
            if not self._watchlists_path or not os.path.exists(self._watchlists_path):
                logger.info(f"Topic monitoring: watchlists file not found at {self._watchlists_path}, starting empty")
                self._watchlists = {}
                self._compiled = {}
                return
            with open(self._watchlists_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("watchlists") if isinstance(data, dict) else data
            if not isinstance(raw, list):
                raw = []
            self._watchlists = {}
            for it in raw:
                try:
                    wl = Watchlist(**it)
                    if not wl.id:
                        wl.id = str(uuid.uuid4())
                    self._watchlists[wl.id] = wl
                except Exception as e:
                    logger.warning(f"Skipping invalid watchlist entry: {e}")
            self._recompile_all()
        except Exception as e:
            logger.error(f"Failed to load watchlists: {e}")
            self._watchlists = {}
            self._compiled = {}

    def _save_watchlists_file(self) -> bool:
        try:
            os.makedirs(os.path.dirname(self._watchlists_path), exist_ok=True)
            payload = {"watchlists": [wl.model_dump() for wl in self._watchlists.values()]}
            with open(self._watchlists_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save watchlists: {e}")
            return False

    def reload(self) -> None:
        with self._lock:
            self._load_watchlists_file()

    # --------------------- Rule compilation ---------------------
    @staticmethod
    def _is_regex_dangerous(expr: str) -> bool:
        if not expr:
            return True
        if len(expr) > 2000:
            return True
        # Nested quantifiers heuristic
        try:
            if re.search(r"\((?:[^)(]|\([^)(]*\))*[+*][^)]*\)\s*[+*]", expr):
                return True
        except Exception:
            return True
        # Too many groups
        try:
            if expr.count("(") - expr.count("\\(") > 100:
                return True
        except Exception:
            return True
        return False

    def _compile_rule(self, rule: WatchlistRule) -> Optional[CompiledRule]:
        pat_text = rule.pattern or ""
        try:
            if len(pat_text) >= 2 and pat_text.startswith("/") and pat_text.endswith("/"):
                raw = pat_text[1:-1]
                if self._is_regex_dangerous(raw):
                    logger.warning(f"Topic monitor: skipped dangerous regex: {raw}")
                    return None
                rgx = re.compile(raw, re.IGNORECASE)
                patt_for_log = raw
            else:
                rgx = re.compile(re.escape(pat_text), re.IGNORECASE)
                patt_for_log = pat_text
            return CompiledRule(
                regex=rgx,
                category=(rule.category or None),
                severity=(rule.severity or None),
                pattern_text=patt_for_log,
                note=rule.note,
            )
        except re.error as e:
            logger.warning(f"Invalid watchlist pattern '{pat_text}': {e}")
            return None

    def _recompile_all(self) -> None:
        self._compiled = {}
        for wid, wl in self._watchlists.items():
            compiled: List[CompiledRule] = []
            for r in wl.rules or []:
                cr = self._compile_rule(r)
                if cr is not None:
                    compiled.append(cr)
            self._compiled[wid] = compiled

    # --------------------- Public CRUD ---------------------
    def list_watchlists(self) -> List[Watchlist]:
        return list(self._watchlists.values())

    def upsert_watchlist(self, wl: Watchlist) -> Watchlist:
        with self._lock:
            if not wl.id:
                wl.id = str(uuid.uuid4())
            self._watchlists[wl.id] = wl
            self._save_watchlists_file()
            # Recompile this one
            compiled: List[CompiledRule] = []
            for r in wl.rules or []:
                cr = self._compile_rule(r)
                if cr is not None:
                    compiled.append(cr)
            self._compiled[wl.id] = compiled
            return wl

    def delete_watchlist(self, watchlist_id: str) -> bool:
        with self._lock:
            if watchlist_id in self._watchlists:
                self._watchlists.pop(watchlist_id, None)
                self._compiled.pop(watchlist_id, None)
                return self._save_watchlists_file()
            return False

    # --------------------- Evaluation ---------------------
    @staticmethod
    def _snippet_around(text: str, start: int, end: int, max_len: int = 200) -> str:
        # Provide a bounded snippet around the match
        mid = (start + end) // 2
        half = max_len // 2
        s = max(0, mid - half)
        e = min(len(text), s + max_len)
        return text[s:e]

    def _applicable_watchlists(self, user_id: Optional[str], team_ids: Optional[List[str]] = None, org_ids: Optional[List[str]] = None) -> List[Tuple[str, Watchlist]]:
        out: List[Tuple[str, Watchlist]] = []
        if not user_id:
            return out
        for wid, wl in self._watchlists.items():
            if not wl.enabled:
                continue
            # Phase 1: per-user scoping + simple global support
            if wl.scope_type == "user" and str(wl.scope_id) == str(user_id):
                out.append((wid, wl))
            elif wl.scope_type in ("global", "all"):
                out.append((wid, wl))
            elif wl.scope_type == "team" and team_ids:
                try:
                    if str(wl.scope_id) in {str(t) for t in team_ids}:
                        out.append((wid, wl))
                except Exception:
                    pass
            elif wl.scope_type == "org" and org_ids:
                try:
                    if str(wl.scope_id) in {str(o) for o in org_ids}:
                        out.append((wid, wl))
                except Exception:
                    pass
            # Future: team/org support
        return out

    def evaluate_and_alert(
        self,
        user_id: Optional[str],
        text: Optional[str],
        source: str,
        scope_type: str = "user",
        scope_id: Optional[str] = None,
        team_ids: Optional[List[str]] = None,
        org_ids: Optional[List[str]] = None,
    ) -> int:
        """Scan text for any watchlist matches and emit alerts.
        Returns count of alerts created.
        """
        if not text or not user_id:
            return 0
        scan = text[: self._max_scan_chars]
        total_created = 0
        for wid, wl in self._applicable_watchlists(user_id, team_ids=team_ids, org_ids=org_ids):
            compiled = self._compiled.get(wid) or []
            for cr in compiled:
                m = cr.regex.search(scan)
                if not m:
                    continue
                # Dedup guard
                if self._db.recent_duplicate_exists(
                    user_id=str(user_id),
                    watchlist_id=str(wid),
                    pattern=str(cr.pattern_text),
                    source=str(source),
                    window_seconds=self._dedup_window_seconds,
                ):
                    continue
                snippet = self._snippet_around(scan, m.start(), m.end(), max_len=200)
                # Scope reflects the matched watchlist's scope
                alert = TopicAlert(
                    user_id=str(user_id),
                    scope_type=str(wl.scope_type or scope_type),
                    scope_id=str(wl.scope_id) if getattr(wl, 'scope_id', None) is not None else (scope_id or str(user_id)),
                    source=source,
                    watchlist_id=str(wid),
                    rule_category=cr.category,
                    rule_severity=cr.severity,
                    pattern=cr.pattern_text,
                    text_snippet=snippet,
                    metadata={"note": cr.note} if cr.note else None,
                )
                self._db.insert_alert(alert)
                # Notify if configured and severity threshold met
                try:
                    notifier = get_notification_service()
                    notifier.notify(alert)
                except Exception as _ne:
                    logger.debug(f"Topic monitoring notify skipped: {_ne}")
                total_created += 1
        return total_created


_service_singleton: Optional[TopicMonitoringService] = None


def get_topic_monitoring_service() -> TopicMonitoringService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = TopicMonitoringService()
    return _service_singleton


def _reset_topic_monitoring_service() -> None:
    """
    Testing helper: reset the cached singleton so the next access picks up
    fresh environment configuration (e.g., temp DB paths).
    """
    global _service_singleton
    _service_singleton = None
