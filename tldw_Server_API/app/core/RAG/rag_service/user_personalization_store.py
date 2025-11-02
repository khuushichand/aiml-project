"""
Per-user lightweight personalization store for RAG.

- Stores doc-level priors and implicit interactions (click/expand/copy)
  under Databases/user_databases/<user_id>/rag_personalization.json
- Provides a simple boosting function to adjust document scores.

This avoids cross-tenant leakage by isolating data per user.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class Prior:
    score: float
    last_updated: float
    corpus: Optional[str] = None


class UserPersonalizationStore:
    def __init__(self, user_id: Optional[str]) -> None:
        self.user_id = (user_id or "anon").strip()
        base = Path("Databases/user_databases") / self.user_id
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / "rag_personalization.json"
        self._data: Dict[str, any] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {"priors": {}, "events": {}, "pairs": {}}
        except Exception:
            self._data = {"priors": {}, "events": {}, "pairs": {}}

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

    def boost_documents(self, documents: List[any], *, corpus: Optional[str] = None) -> List[any]:
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
