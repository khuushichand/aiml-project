import json
from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.Flashcards.scheduler_fsrs import (
    FsrsSettingsError,
    _load_fsrs_state,
    build_fsrs_next_interval_previews,
    bootstrap_fsrs_state,
    get_default_fsrs_settings,
    normalize_fsrs_settings,
    simulate_fsrs_review_transition,
)
from tldw_Server_API.app.core.Flashcards.scheduler_sm2 import parse_iso_datetime


def test_default_fsrs_settings_are_stable():
    settings = get_default_fsrs_settings()

    assert settings["target_retention"] == pytest.approx(0.9)
    assert settings["maximum_interval_days"] == 36500
    assert settings["enable_fuzz"] is False


def test_normalize_fsrs_settings_fills_defaults_and_validates_ranges():
    settings = normalize_fsrs_settings({"target_retention": 0.85})

    assert settings["target_retention"] == pytest.approx(0.85)
    assert settings["maximum_interval_days"] == 36500
    assert settings["enable_fuzz"] is False

    with pytest.raises(ValueError):
        normalize_fsrs_settings({"target_retention": 1.2})


def test_normalize_fsrs_settings_wraps_invalid_json_as_domain_error():
    with pytest.raises(FsrsSettingsError):
        normalize_fsrs_settings("{not-valid-json")


def test_load_fsrs_state_logs_and_bootstraps_when_json_is_corrupt():
    now = parse_iso_datetime("2026-03-13T00:00:00Z")
    card = {
        "uuid": "fsrs-card-corrupt",
        "interval_days": 12,
        "repetitions": 7,
        "lapses": 1,
        "last_reviewed_at": "2026-03-01T00:00:00Z",
        "due_at": "2026-03-13T00:00:00Z",
        "queue_state": "review",
        "scheduler_state_json": "{bad-json",
    }

    with patch("tldw_Server_API.app.core.Flashcards.scheduler_fsrs.logger.warning") as warning:
        state = _load_fsrs_state(card, now)

    warning.assert_called_once()
    assert state["stability"] > 0
    assert state["last_reviewed_at"] == "2026-03-01T00:00:00Z"


def test_bootstrap_fsrs_state_from_existing_card_snapshot():
    now = parse_iso_datetime("2026-03-13T00:00:00Z")
    card = {
        "interval_days": 12,
        "repetitions": 7,
        "lapses": 1,
        "last_reviewed_at": "2026-03-01T00:00:00Z",
        "due_at": "2026-03-13T00:00:00Z",
        "queue_state": "review",
    }

    state = bootstrap_fsrs_state(card, now=now)

    assert state["stability"] > 0
    assert 1.0 <= state["difficulty"] <= 10.0
    assert 0.0 < state["retrievability"] <= 1.0
    assert state["last_reviewed_at"] == "2026-03-01T00:00:00Z"


def test_simulate_fsrs_review_transition_returns_shared_compatibility_fields():
    now = parse_iso_datetime("2026-03-13T00:00:00Z")
    card = {
        "uuid": "fsrs-card-1",
        "queue_state": "review",
        "interval_days": 10,
        "repetitions": 5,
        "lapses": 0,
        "ef": 2.5,
        "last_reviewed_at": "2026-03-03T00:00:00Z",
        "due_at": "2026-03-13T00:00:00Z",
        "scheduler_state_json": "{}",
    }

    result = simulate_fsrs_review_transition(card, None, 3, now=now)

    assert result["queue_state"] == "review"
    assert result["interval_days"] >= 10
    assert result["repetitions"] == 6
    assert result["due_at"] == "2026-03-25T00:00:00.000Z"

    state = json.loads(result["scheduler_state_json"])
    assert state["stability"] >= 10.0
    assert state["difficulty"] >= 1.0


def test_build_fsrs_next_interval_previews_returns_all_ratings():
    now = parse_iso_datetime("2026-03-13T00:00:00Z")
    card = {
        "uuid": "fsrs-card-2",
        "queue_state": "review",
        "interval_days": 7,
        "repetitions": 3,
        "lapses": 0,
        "ef": 2.5,
        "last_reviewed_at": "2026-03-06T00:00:00Z",
        "due_at": "2026-03-13T00:00:00Z",
        "scheduler_state_json": "{}",
    }

    previews = build_fsrs_next_interval_previews(card, None, now=now)

    assert set(previews.keys()) == {"again", "hard", "good", "easy"}
    assert previews["again"] == "1 day"
    assert previews["hard"] == "8 days"
    assert previews["good"] == "11 days"
    assert previews["easy"] == "17 days"
