from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from datetime import datetime, timezone, timedelta
import re


def _to_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val if isinstance(x, (str, int, float))]
    return [str(val)]


def _normalize_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        fl = payload.get("filters")
        if isinstance(fl, list):
            return [f for f in fl if isinstance(f, dict)]
        return []
    if isinstance(payload, list):
        return [f for f in payload if isinstance(f, dict)]
    return []


def normalize_filters(payload: Any) -> List[Dict[str, Any]]:
    """Return a normalized list of filters sorted by priority desc then index."""
    raw = _normalize_payload(payload)
    out: List[Dict[str, Any]] = []
    for f in raw:
        t = str(f.get("type") or "").lower()
        a = str(f.get("action") or "").lower()
        if t not in {"keyword", "author", "date_range", "regex", "all"}:
            continue
        if a not in {"include", "exclude", "flag"}:
            continue
        val = f.get("value") if isinstance(f.get("value"), dict) else {}
        try:
            pr = int(f.get("priority")) if f.get("priority") is not None else 0
        except Exception:
            pr = 0
        active = f.get("is_active")
        if active is None:
            active = True
        out.append({
            "type": t,
            "action": a,
            "value": val,
            "priority": pr,
            "is_active": bool(active),
            "id": f.get("id"),
        })
    # Sort by priority desc, stable for input order
    out.sort(key=lambda x: int(x.get("priority") or 0), reverse=True)
    return out


def _get_text_fields(candidate: Dict[str, Any], names: Sequence[str]) -> List[str]:
    vals: List[str] = []
    for n in names:
        v = candidate.get(n)
        if v is None:
            continue
        try:
            s = str(v)
        except Exception:
            continue
        if s:
            vals.append(s)
    return vals


def _match_keyword(value: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    keywords = [k.lower() for k in _to_list(value.get("keywords")) if str(k).strip()]
    if not keywords:
        return False
    fields = value.get("fields")
    field_names = [str(x) for x in fields] if isinstance(fields, list) else ["title", "summary", "content", "author"]
    haystack = "\n".join(_get_text_fields(candidate, field_names)).lower()
    if not haystack:
        return False
    mode = str(value.get("match") or "any").lower()
    if mode == "all":
        return all(k in haystack for k in keywords)
    return any(k in haystack for k in keywords)


def _match_author(value: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    names = [k.lower() for k in _to_list(value.get("names")) if str(k).strip()]
    if not names:
        return False
    author = str(candidate.get("author") or "").lower()
    if not author:
        return False
    mode = str(value.get("match") or "any").lower()
    if mode == "all":
        return all(n in author for n in names)
    return any(n in author for n in names)


def _compile_regex(pattern: str, flags: Optional[str]) -> Optional[re.Pattern[str]]:
    if not pattern:
        return None
    f = 0
    if isinstance(flags, str):
        if "i" in flags.lower():
            f |= re.IGNORECASE
        if "m" in flags.lower():
            f |= re.MULTILINE
        if "s" in flags.lower():
            f |= re.DOTALL
    try:
        return re.compile(pattern, f)
    except Exception:
        return None


def _match_regex(value: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    pattern = value.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return False
    flags = value.get("flags")
    rx = _compile_regex(pattern, flags)
    if rx is None:
        return False
    field = value.get("field")
    if isinstance(field, str) and field:
        hay = str(candidate.get(field) or "")
        return bool(rx.search(hay))
    # Search across common fields
    for name in ("title", "summary", "content", "author"):
        hay = str(candidate.get(name) or "")
        if rx.search(hay):
            return True
    return False


def _parse_iso(dt: str) -> Optional[datetime]:
    text = (dt or "").strip()
    if not text:
        return None
    # Try fromisoformat with Z support
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        d = datetime.fromisoformat(text)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        pass
    # Fallback email.utils
    try:
        from email.utils import parsedate_to_datetime

        d = parsedate_to_datetime(dt)
        if d is None:
            return None
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def _match_date_range(value: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    max_age_days = value.get("max_age_days")
    if not isinstance(max_age_days, int):
        try:
            max_age_days = int(max_age_days)
        except Exception:
            return False
    pub = candidate.get("published_at")
    if not pub:
        return False
    dt = _parse_iso(str(pub))
    if not dt:
        return False
    try:
        delta = datetime.now(timezone.utc) - dt
        return delta <= timedelta(days=max_age_days)
    except Exception:
        return False


def _match_all(_: Dict[str, Any], __: Dict[str, Any]) -> bool:
    return True


def evaluate_filters(filters: List[Dict[str, Any]], candidate: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
    """Return (decision, meta) where decision in {include, exclude, flag, None}.

    Applies active filters in priority order, short-circuiting on first match.
    Meta includes a stable key for tallying.
    """
    for idx, f in enumerate(filters):
        if not f.get("is_active", True):
            continue
        t = f.get("type")
        val = f.get("value") or {}
        matched = False
        if t == "keyword":
            matched = _match_keyword(val, candidate)
        elif t == "author":
            matched = _match_author(val, candidate)
        elif t == "regex":
            matched = _match_regex(val, candidate)
        elif t == "date_range":
            matched = _match_date_range(val, candidate)
        elif t == "all":
            matched = _match_all(val, candidate)
        if matched:
            fid = f.get("id")
            key = f"id:{fid}" if fid is not None else f"idx:{idx}"
            return f.get("action"), {"key": key}
    return None, {}
