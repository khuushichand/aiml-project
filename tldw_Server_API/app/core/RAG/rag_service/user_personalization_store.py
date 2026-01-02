"""
Per-user lightweight personalization store for RAG.

- Stores doc-level priors and implicit interactions (click/expand/copy)
  under Databases/user_databases/<user_id>/rag_personalization.json
- Provides a simple boosting function to adjust document scores.

This avoids cross-tenant leakage by isolating data per user.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.exceptions import UnsafeUserPathError


@dataclass
class Prior:
    score: float
    last_updated: float
    corpus: Optional[str] = None


_DEFAULT_USER_ID = "anon"
_SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _empty_store() -> Dict[str, Any]:
    return {"priors": {}, "events": {}, "pairs": {}}


def _normalize_user_id(raw_user_id: Optional[str]) -> str:
    raw = str(raw_user_id or _DEFAULT_USER_ID).strip()
    if not raw:
        return _DEFAULT_USER_ID
    if _SAFE_USER_ID_RE.fullmatch(raw):
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"u_{digest}"


def _resolve_path(path: Path) -> Path:
    """Expand and resolve a path without requiring it to exist."""
    expanded = path.expanduser()
    try:
        return expanded.resolve(strict=False)
    except TypeError:
        # Python < 3.6 doesn't support strict parameter
        return expanded.resolve()


def _get_user_base_dir() -> Path:
    base = _resolve_path(Path("Databases/user_databases"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _safe_user_dir(user_id: str) -> Path:
    base = _get_user_base_dir()
    candidate = _resolve_path(base / user_id)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise UnsafeUserPathError("Unsafe user_id path for personalization store") from exc
    return candidate


class UserPersonalizationStore:
    def __init__(self, user_id: Optional[str]) -> None:
        self.user_id = _normalize_user_id(user_id)
        base = _safe_user_dir(self.user_id)
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / "rag_personalization.json"
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._data = data
                else:
                    self._data = _empty_store()
            else:
                self._data = _empty_store()
            self._data.setdefault("priors", {})
            self._data.setdefault("events", {})
            self._data.setdefault("pairs", {})
        except Exception as e:
            logger.debug(f"Failed loading personalization data: {e}")
            self._data = _empty_store()

    def _save(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f)
        except Exception as e:
            logger.debug(f"Failed saving personalization: {e}")

    def record_event(
        self,
        *,
        event_type: str,
        doc_id: Optional[str],
        corpus: Optional[str] = None,
        impression: Optional[List[str]] = None,
    ) -> None:
        now = time.time()
        # Count events
        evt = self._data.setdefault("events", {})
        evt[event_type] = int(evt.get(event_type, 0)) + 1
        # Update priors modestly
        if doc_id:
            priors: Dict[str, Dict[str, float]] = self._data.setdefault("priors", {})
            cur = priors.get(doc_id) or {"score": 0.0, "last_updated": 0.0, "corpus": corpus}
            cur["score"] = min(5.0, float(cur.get("score", 0.0)) + (0.1 if event_type == "expand" else 0.2))
            cur["last_updated"] = now
            if corpus:
                cur["corpus"] = corpus
            priors[doc_id] = cur
        # Pairwise updates: clicked doc wins over docs ranked above but not clicked
        if event_type in {"click", "copy"} and doc_id and impression:
            pairs: Dict[str, int] = self._data.setdefault("pairs", {})
            for other in impression:
                if other == doc_id:
                    break  # only compare with items above in the list
                key = f"{doc_id}|{other}"
                pairs[key] = int(pairs.get(key, 0)) + 1
        self._save()

    def get_prior(self, doc_id: str) -> float:
        try:
            p = self._data.get("priors", {}).get(doc_id)
            if not p:
                return 0.0
            # Simple recency decay (half-life ~ 7 days)
            half_life_days = float(os.getenv("RAG_PERSONALIZATION_HALF_LIFE_DAYS", "7"))
            dt = max(0.0, time.time() - float(p.get("last_updated", 0.0)))
            decay = pow(0.5, dt / (half_life_days * 86400.0)) if half_life_days > 0 else 1.0
            return float(p.get("score", 0.0)) * float(decay)
        except Exception:
            return 0.0

    def boost_documents(self, documents: List[Any], *, corpus: Optional[str] = None) -> List[Any]:
        # Adjust scores by a bounded additive boost based on priors
        try:
            weight = float(os.getenv("RAG_PERSONALIZATION_WEIGHT", "0.1"))
        except Exception:
            weight = 0.1
        boosted = []
        for d in documents:
            try:
                did = getattr(d, "id", None) or (isinstance(d, dict) and d.get("id"))
                base = float(getattr(d, "score", 0.0) if hasattr(d, "score") else (d.get("score", 0.0) if isinstance(d, dict) else 0.0))
                prior = self.get_prior(str(did))
                new_score = base + (weight * prior)
                if hasattr(d, "score"):
                    d.score = new_score
                elif isinstance(d, dict):
                    d["score"] = new_score
                boosted.append(d)
            except Exception:
                boosted.append(d)
        # Keep ordering by updated score
        try:
            boosted.sort(key=lambda x: getattr(x, "score", x.get("score", 0.0) if isinstance(x, dict) else 0.0), reverse=True)
        except Exception:
            pass
        return boosted
