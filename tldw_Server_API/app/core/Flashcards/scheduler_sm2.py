import copy
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

QUEUE_STATES = ("new", "learning", "review", "relearning", "suspended")
SUSPENDED_REASONS = ("manual", "leech")
MATURE_INTERVAL_DAYS = 21

DEFAULT_SCHEDULER_SETTINGS: dict[str, Any] = {
    "new_steps_minutes": [1, 10],
    "relearn_steps_minutes": [10],
    "graduating_interval_days": 1,
    "easy_interval_days": 4,
    "easy_bonus": 1.3,
    "interval_modifier": 1.0,
    "max_interval_days": 36500,
    "leech_threshold": 8,
    "enable_fuzz": False,
}


class SchedulerSettingsError(ValueError):
    """Raised when deck scheduler settings are invalid."""


def get_default_scheduler_settings() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_SCHEDULER_SETTINGS)


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def normalize_scheduler_settings(raw: Mapping[str, Any] | str | None) -> dict[str, Any]:
    source: dict[str, Any]
    if raw is None:
        source = {}
    elif isinstance(raw, str):
        if not raw.strip():
            source = {}
        else:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise SchedulerSettingsError("scheduler_settings must be a JSON object")
            source = parsed
    elif isinstance(raw, Mapping):
        source = dict(raw)
    else:
        raise SchedulerSettingsError("scheduler_settings must be a mapping or JSON string")

    settings = get_default_scheduler_settings()
    for key in settings:
        if key in source and source[key] is not None:
            settings[key] = source[key]

    for key in ("new_steps_minutes", "relearn_steps_minutes"):
        steps = settings.get(key)
        if not isinstance(steps, list):
            raise SchedulerSettingsError(f"{key} must be a list of positive integers")
        normalized_steps: list[int] = []
        for step in steps:
            try:
                minutes = int(step)
            except (TypeError, ValueError) as exc:
                raise SchedulerSettingsError(f"{key} must contain integers") from exc
            if minutes <= 0:
                raise SchedulerSettingsError(f"{key} values must be positive")
            normalized_steps.append(minutes)
        if len(normalized_steps) > 8:
            raise SchedulerSettingsError(f"{key} cannot contain more than 8 entries")
        settings[key] = normalized_steps

    int_fields = (
        "graduating_interval_days",
        "easy_interval_days",
        "max_interval_days",
        "leech_threshold",
    )
    for key in int_fields:
        try:
            settings[key] = int(settings[key])
        except (TypeError, ValueError) as exc:
            raise SchedulerSettingsError(f"{key} must be an integer") from exc

    float_fields = ("easy_bonus", "interval_modifier")
    for key in float_fields:
        try:
            settings[key] = float(settings[key])
        except (TypeError, ValueError) as exc:
            raise SchedulerSettingsError(f"{key} must be numeric") from exc

    settings["enable_fuzz"] = bool(settings.get("enable_fuzz"))

    if settings["graduating_interval_days"] < 1:
        raise SchedulerSettingsError("graduating_interval_days must be >= 1")
    if settings["easy_interval_days"] < settings["graduating_interval_days"]:
        raise SchedulerSettingsError("easy_interval_days must be >= graduating_interval_days")
    if settings["easy_bonus"] < 1.0:
        raise SchedulerSettingsError("easy_bonus must be >= 1.0")
    if settings["interval_modifier"] <= 0:
        raise SchedulerSettingsError("interval_modifier must be > 0")
    if settings["max_interval_days"] < settings["graduating_interval_days"]:
        raise SchedulerSettingsError("max_interval_days must be >= graduating_interval_days")
    if settings["leech_threshold"] < 1:
        raise SchedulerSettingsError("leech_threshold must be >= 1")

    return settings


def scheduler_settings_to_json(raw: Mapping[str, Any] | str | None) -> str:
    return json.dumps(normalize_scheduler_settings(raw), sort_keys=True)


def coerce_queue_state(card: Mapping[str, Any]) -> str:
    queue_state = str(card.get("queue_state") or "").strip().lower()
    if queue_state in QUEUE_STATES:
        return queue_state
    last_reviewed = card.get("last_reviewed_at")
    repetitions = int(card.get("repetitions") or 0)
    if not last_reviewed:
        return "new"
    if repetitions in (1, 2):
        return "learning"
    return "review"


def format_interval_label(*, next_due_at: datetime | None, now: datetime) -> str:
    if next_due_at is None:
        return "suspended"
    delta_seconds = max(0.0, (next_due_at - now).total_seconds())
    total_minutes = max(1, int(math.ceil(delta_seconds / 60.0)))
    if total_minutes < 60:
        return f"{total_minutes} min"
    if total_minutes < 24 * 60:
        total_hours = int(math.ceil(total_minutes / 60.0))
        return f"{total_hours} hr" if total_hours == 1 else f"{total_hours} hr"
    total_days = int(math.ceil(total_minutes / (24 * 60)))
    if total_days == 1:
        return "1 day"
    if total_days < 30:
        return f"{total_days} days"
    if total_days < 365:
        return f"{max(1, round(total_days / 30))} mo"
    return f"{(total_days / 365):.1f} yr"


def _finalize_review_interval_days(
    days: float,
    *,
    settings: Mapping[str, Any],
    card_uuid: str | None = None,
    queue_state: str = "review",
) -> int:
    adjusted = max(1.0, float(days) * float(settings["interval_modifier"]))
    adjusted = min(adjusted, float(settings["max_interval_days"]))
    if settings.get("enable_fuzz") and queue_state == "review":
        seed = hashlib.sha256(f"{card_uuid or ''}:{adjusted:.4f}".encode("utf-8")).hexdigest()
        raw = int(seed[:8], 16) / 0xFFFFFFFF
        span = max(1.0, min(3.0, adjusted * 0.05))
        adjusted += (raw * 2.0 - 1.0) * span
    return max(1, min(int(round(adjusted)), int(settings["max_interval_days"])))


def _hard_step_delay_minutes(current_step: int, next_step: int | None) -> int:
    if next_step is None:
        return max(current_step + 1, int(math.ceil(current_step * 1.5)))
    return max(current_step + 1, int(math.ceil((current_step + next_step) / 2.0)))


def _apply_learning_transition(
    *,
    card: Mapping[str, Any],
    rating: int,
    steps_minutes: list[int],
    settings: Mapping[str, Any],
    queue_state: str,
    now: datetime,
) -> dict[str, Any]:
    result = {
        "queue_state": queue_state,
        "step_index": None,
        "suspended_reason": None,
        "ef": max(1.3, float(card.get("ef") or 2.5)),
        "interval_days": max(0, int(card.get("interval_days") or 0)),
        "repetitions": max(0, int(card.get("repetitions") or 0)),
        "lapses": max(0, int(card.get("lapses") or 0)),
        "due_at": None,
        "last_reviewed_at": to_iso_z(now),
        "was_lapse": False,
    }

    if not steps_minutes:
        interval_days = (
            int(settings["easy_interval_days"])
            if rating == 5
            else max(1, result["interval_days"] or int(settings["graduating_interval_days"]))
        )
        next_due_at = now + timedelta(days=interval_days)
        result.update(
            {
                "queue_state": "review",
                "step_index": None,
                "interval_days": interval_days,
                "repetitions": max(1, result["repetitions"] or 1),
                "due_at": to_iso_z(next_due_at),
                "next_due_dt": next_due_at,
            }
        )
        return result

    current_index = min(max(0, int(card.get("step_index") or 0)), len(steps_minutes) - 1)
    current_step = int(steps_minutes[current_index])
    next_step = int(steps_minutes[current_index + 1]) if current_index + 1 < len(steps_minutes) else None

    if rating == 0:
        next_due_at = now + timedelta(minutes=int(steps_minutes[0]))
        result.update(
            {
                "queue_state": queue_state,
                "step_index": 0,
                "interval_days": 0,
                "due_at": to_iso_z(next_due_at),
                "next_due_dt": next_due_at,
            }
        )
        return result

    if rating == 2:
        next_due_at = now + timedelta(minutes=_hard_step_delay_minutes(current_step, next_step))
        result.update(
            {
                "queue_state": queue_state,
                "step_index": current_index,
                "interval_days": max(0, result["interval_days"]),
                "repetitions": max(1, result["repetitions"]),
                "due_at": to_iso_z(next_due_at),
                "next_due_dt": next_due_at,
            }
        )
        return result

    if rating == 3 and next_step is not None:
        next_due_at = now + timedelta(minutes=next_step)
        result.update(
            {
                "queue_state": queue_state,
                "step_index": current_index + 1,
                "interval_days": max(0, result["interval_days"]),
                "repetitions": max(1, result["repetitions"]),
                "due_at": to_iso_z(next_due_at),
                "next_due_dt": next_due_at,
            }
        )
        return result

    interval_days = (
        int(settings["easy_interval_days"])
        if rating == 5
        else (
            int(settings["graduating_interval_days"])
            if queue_state == "learning"
            else max(1, result["interval_days"] or int(settings["graduating_interval_days"]))
        )
    )
    next_due_at = now + timedelta(days=interval_days)
    result.update(
        {
            "queue_state": "review",
            "step_index": None,
            "interval_days": interval_days,
            "repetitions": max(1, result["repetitions"] or 1),
            "due_at": to_iso_z(next_due_at),
            "next_due_dt": next_due_at,
        }
    )
    return result


def simulate_review_transition(
    card: Mapping[str, Any],
    settings: Mapping[str, Any] | str | None,
    rating: int,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    normalized_settings = normalize_scheduler_settings(settings)
    queue_state = coerce_queue_state(card)
    card_uuid = str(card.get("uuid") or "")
    ef = max(1.3, float(card.get("ef") or 2.5))
    interval_days = max(0, int(card.get("interval_days") or 0))
    repetitions = max(0, int(card.get("repetitions") or 0))
    lapses = max(0, int(card.get("lapses") or 0))
    previous_due_at_iso = card.get("due_at")
    previous_due_at = parse_iso_datetime(previous_due_at_iso)

    if queue_state == "new":
        return _apply_learning_transition(
            card={**card, "step_index": 0},
            rating=rating,
            steps_minutes=list(normalized_settings["new_steps_minutes"]),
            settings=normalized_settings,
            queue_state="learning",
            now=current_time,
        )

    if queue_state in ("learning", "relearning"):
        step_minutes = (
            list(normalized_settings["new_steps_minutes"])
            if queue_state == "learning"
            else list(normalized_settings["relearn_steps_minutes"])
        )
        return _apply_learning_transition(
            card=card,
            rating=rating,
            steps_minutes=step_minutes,
            settings=normalized_settings,
            queue_state=queue_state,
            now=current_time,
        )

    current_interval = max(1, interval_days or int(normalized_settings["graduating_interval_days"]))
    overdue_days = 0.0
    if previous_due_at is not None and current_time > previous_due_at:
        overdue_days = min(
            (current_time - previous_due_at).total_seconds() / 86400.0,
            current_interval * 0.5,
        )
    interval_base = max(1.0, current_interval + overdue_days)

    result = {
        "queue_state": "review",
        "step_index": None,
        "suspended_reason": None,
        "ef": ef,
        "interval_days": current_interval,
        "repetitions": repetitions,
        "lapses": lapses,
        "due_at": None,
        "last_reviewed_at": to_iso_z(current_time),
        "was_lapse": False,
        "next_due_dt": None,
    }

    if rating == 0:
        result["was_lapse"] = True
        result["lapses"] = lapses + 1
        result["ef"] = max(1.3, ef - 0.2)
        result["repetitions"] = max(0, repetitions - 1)
        reduced_interval = max(1, int(round(current_interval * 0.3)))
        result["interval_days"] = reduced_interval
        if result["lapses"] >= int(normalized_settings["leech_threshold"]):
            result.update(
                {
                    "queue_state": "suspended",
                    "step_index": None,
                    "suspended_reason": "leech",
                    "due_at": None,
                    "next_due_dt": None,
                }
            )
            return result

        relearn_steps = list(normalized_settings["relearn_steps_minutes"])
        if relearn_steps:
            next_due_at = current_time + timedelta(minutes=int(relearn_steps[0]))
            result.update(
                {
                    "queue_state": "relearning",
                    "step_index": 0,
                    "due_at": to_iso_z(next_due_at),
                    "next_due_dt": next_due_at,
                }
            )
            return result

        next_due_at = current_time + timedelta(days=1)
        result.update(
            {
                "queue_state": "review",
                "step_index": None,
                "interval_days": 1,
                "due_at": to_iso_z(next_due_at),
                "next_due_dt": next_due_at,
            }
        )
        return result

    if rating == 2:
        result["ef"] = max(1.3, ef - 0.15)
        next_interval_days = _finalize_review_interval_days(
            max(current_interval + 1, interval_base * max(1.15, min(ef - 0.15, 1.4))),
            settings=normalized_settings,
            card_uuid=card_uuid or None,
        )
        next_due_at = current_time + timedelta(days=next_interval_days)
        result.update(
            {
                "queue_state": "review",
                "interval_days": next_interval_days,
                "repetitions": repetitions + 1,
                "due_at": to_iso_z(next_due_at),
                "next_due_dt": next_due_at,
            }
        )
        return result

    if rating == 5:
        result["ef"] = min(3.5, ef + 0.05)
        interval_seed = max(float(normalized_settings["easy_interval_days"]), interval_base)
        next_interval_days = _finalize_review_interval_days(
            interval_seed * max(ef, 1.3) * float(normalized_settings["easy_bonus"]),
            settings=normalized_settings,
            card_uuid=card_uuid or None,
        )
        next_due_at = current_time + timedelta(days=next_interval_days)
        result.update(
            {
                "queue_state": "review",
                "interval_days": next_interval_days,
                "repetitions": repetitions + 1,
                "due_at": to_iso_z(next_due_at),
                "next_due_dt": next_due_at,
            }
        )
        return result

    next_interval_days = _finalize_review_interval_days(
        max(float(normalized_settings["graduating_interval_days"]), interval_base * max(ef, 1.3)),
        settings=normalized_settings,
        card_uuid=card_uuid or None,
    )
    next_due_at = current_time + timedelta(days=next_interval_days)
    result.update(
        {
            "queue_state": "review",
            "interval_days": next_interval_days,
            "repetitions": repetitions + 1,
            "due_at": to_iso_z(next_due_at),
            "next_due_dt": next_due_at,
        }
    )
    return result


def build_next_interval_previews(
    card: Mapping[str, Any],
    settings: Mapping[str, Any] | str | None,
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    current_time = now or datetime.now(timezone.utc)
    previews: dict[str, str] = {}
    for label, rating in (("again", 0), ("hard", 2), ("good", 3), ("easy", 5)):
        simulated = simulate_review_transition(card, settings, rating, now=current_time)
        previews[label] = format_interval_label(
            next_due_at=simulated.get("next_due_dt"),
            now=current_time,
        )
    return previews
