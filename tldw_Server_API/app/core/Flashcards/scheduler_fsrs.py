"""FSRS review-stage scheduling helpers for flashcards."""

import math
import copy
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from loguru import logger

from tldw_Server_API.app.core.Flashcards.scheduler_sm2 import (
    format_interval_label,
    parse_iso_datetime,
    to_iso_z,
)

DEFAULT_FSRS_SETTINGS: dict[str, Any] = {
    "target_retention": 0.9,
    "maximum_interval_days": 36500,
    "enable_fuzz": False,
}


class FsrsSettingsError(ValueError):
    """Raised when FSRS deck settings are invalid."""


def get_default_fsrs_settings() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_FSRS_SETTINGS)


def normalize_fsrs_settings(raw: Mapping[str, Any] | str | None) -> dict[str, Any]:
    if raw is None:
        source: dict[str, Any] = {}
    elif isinstance(raw, str):
        if not raw.strip():
            source = {}
        else:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise FsrsSettingsError("fsrs settings must be valid JSON") from exc
            if not isinstance(parsed, dict):
                raise FsrsSettingsError("fsrs settings must be a JSON object")
            source = parsed
    elif isinstance(raw, Mapping):
        source = dict(raw)
    else:
        raise FsrsSettingsError("fsrs settings must be a mapping or JSON string")

    settings = get_default_fsrs_settings()
    for key in settings:
        if key in source and source[key] is not None:
            settings[key] = source[key]

    try:
        settings["target_retention"] = float(settings["target_retention"])
    except (TypeError, ValueError) as exc:
        raise FsrsSettingsError("target_retention must be numeric") from exc

    try:
        settings["maximum_interval_days"] = int(settings["maximum_interval_days"])
    except (TypeError, ValueError) as exc:
        raise FsrsSettingsError("maximum_interval_days must be an integer") from exc

    settings["enable_fuzz"] = bool(settings.get("enable_fuzz"))

    if settings["target_retention"] <= 0 or settings["target_retention"] >= 1:
        raise FsrsSettingsError("target_retention must be between 0 and 1")
    if settings["maximum_interval_days"] < 1:
        raise FsrsSettingsError("maximum_interval_days must be >= 1")

    return settings


def bootstrap_fsrs_state(
    card: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    interval_days = max(1, int(card.get("interval_days") or 1))
    repetitions = max(0, int(card.get("repetitions") or 0))
    lapses = max(0, int(card.get("lapses") or 0))
    due_at = parse_iso_datetime(str(card.get("due_at") or "")) if card.get("due_at") else None
    last_reviewed_at = str(card.get("last_reviewed_at") or "") or None

    if due_at is None:
        retrievability = 0.9
    elif current_time <= due_at:
        retrievability = 0.95
    else:
        overdue_days = max(0.0, (current_time - due_at).total_seconds() / 86400.0)
        retrievability = max(0.3, min(0.95, 1.0 - (overdue_days / max(interval_days, 1)) * 0.4))

    stability = max(1.0, float(interval_days) * max(0.75, 1.0 - lapses * 0.05))
    difficulty = min(10.0, max(1.0, 5.0 + lapses * 0.35 - min(repetitions, 10) * 0.1))

    return {
        "stability": round(stability, 4),
        "difficulty": round(difficulty, 4),
        "retrievability": round(retrievability, 4),
        "last_reviewed_at": last_reviewed_at,
    }


def _load_fsrs_state(card: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    raw = card.get("scheduler_state_json")
    if isinstance(raw, Mapping):
        parsed = dict(raw)
    elif isinstance(raw, str) and raw.strip():
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "Invalid FSRS scheduler_state_json for flashcard {}. Rebootstrapping state.",
                card.get("uuid") or "<unknown>",
            )
            loaded = {}
        parsed = dict(loaded) if isinstance(loaded, dict) else {}
    else:
        parsed = {}

    if not parsed:
        return bootstrap_fsrs_state(card, now=now)

    merged = bootstrap_fsrs_state(card, now=now)
    for key in ("stability", "difficulty", "retrievability", "last_reviewed_at"):
        if key in parsed and parsed[key] is not None:
            merged[key] = parsed[key]
    return merged


def _determine_interval_days(interval_days: int, repetitions: int) -> int:
    return max(1, interval_days + min(4, max(2, 7 - repetitions)))


def simulate_fsrs_review_transition(
    card: Mapping[str, Any],
    settings: Mapping[str, Any] | str | None,
    rating: int,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    normalized_settings = normalize_fsrs_settings(settings)
    state = _load_fsrs_state(card, current_time)

    interval_days = max(1, int(card.get("interval_days") or 1))
    repetitions = max(0, int(card.get("repetitions") or 0))
    lapses = max(0, int(card.get("lapses") or 0))
    ef = float(card.get("ef") or 2.5)

    result = {
        "queue_state": "review",
        "step_index": None,
        "suspended_reason": None,
        "ef": ef,
        "interval_days": interval_days,
        "repetitions": repetitions,
        "lapses": lapses,
        "due_at": None,
        "last_reviewed_at": to_iso_z(current_time),
        "was_lapse": False,
        "next_due_dt": None,
        "scheduler_state_json": "{}",
    }

    if rating == 0:
        next_interval = 1
        next_state = {
            "stability": round(max(1.0, float(state["stability"]) * 0.5), 4),
            "difficulty": round(min(10.0, float(state["difficulty"]) + 0.35), 4),
            "retrievability": 0.3,
            "last_reviewed_at": result["last_reviewed_at"],
        }
        result["lapses"] = lapses + 1
        result["repetitions"] = max(0, repetitions - 1)
        result["was_lapse"] = True
    elif rating == 2:
        next_interval = min(
            int(normalized_settings["maximum_interval_days"]),
            interval_days + 1,
        )
        next_state = {
            "stability": round(max(float(state["stability"]), next_interval * 0.95), 4),
            "difficulty": round(max(1.0, float(state["difficulty"]) - 0.05), 4),
            "retrievability": round(max(0.75, float(normalized_settings["target_retention"]) - 0.05), 4),
            "last_reviewed_at": result["last_reviewed_at"],
        }
        result["repetitions"] = repetitions + 1
    elif rating == 5:
        good_interval = _determine_interval_days(interval_days, repetitions)
        next_interval = min(
            int(normalized_settings["maximum_interval_days"]),
            int(math.ceil(good_interval * 1.5)),
        )
        next_state = {
            "stability": round(max(float(state["stability"]), next_interval * 1.05), 4),
            "difficulty": round(max(1.0, float(state["difficulty"]) - 0.2), 4),
            "retrievability": round(min(0.99, float(normalized_settings["target_retention"]) + 0.05), 4),
            "last_reviewed_at": result["last_reviewed_at"],
        }
        result["repetitions"] = repetitions + 1
    else:
        next_interval = min(
            int(normalized_settings["maximum_interval_days"]),
            _determine_interval_days(interval_days, repetitions),
        )
        next_state = {
            "stability": round(max(float(state["stability"]), next_interval * float(normalized_settings["target_retention"])), 4),
            "difficulty": round(max(1.0, float(state["difficulty"]) - 0.1), 4),
            "retrievability": round(float(normalized_settings["target_retention"]), 4),
            "last_reviewed_at": result["last_reviewed_at"],
        }
        result["repetitions"] = repetitions + 1

    next_due_at = current_time + timedelta(days=next_interval)
    result["interval_days"] = next_interval
    result["due_at"] = to_iso_z(next_due_at)
    result["next_due_dt"] = next_due_at
    result["scheduler_state_json"] = json.dumps(next_state, sort_keys=True)
    return result


def build_fsrs_next_interval_previews(
    card: Mapping[str, Any],
    settings: Mapping[str, Any] | str | None,
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    current_time = now or datetime.now(timezone.utc)
    previews: dict[str, str] = {}
    for label, rating in (("again", 0), ("hard", 2), ("good", 3), ("easy", 5)):
        simulated = simulate_fsrs_review_transition(card, settings, rating, now=current_time)
        previews[label] = format_interval_label(
            next_due_at=simulated.get("next_due_dt"),
            now=current_time,
        )
    return previews
