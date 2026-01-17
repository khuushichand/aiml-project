"""Unit tests for IcalAdapter validation behavior."""

import pytest

from tldw_Server_API.app.core.File_Artifacts.adapters.ical_adapter import IcalAdapter


pytestmark = pytest.mark.unit
pytest.importorskip("icalendar", reason="icalendar not installed")


def test_ical_requires_timezone_for_naive_datetime() -> None:
    """Reject naive datetimes without an event or calendar timezone."""
    adapter = IcalAdapter()
    structured = {
        "calendar": {
            "prodid": "-//tldw//files//EN",
            "version": "2.0",
            "events": [
                {
                    "uid": "1",
                    "summary": "Meeting",
                    "start": "2026-01-01T10:00:00",
                }
            ],
        }
    }
    issues = adapter.validate(structured)
    assert any(issue.code == "event_timezone_required" for issue in issues)


def test_ical_accepts_timezone_with_naive_datetime() -> None:
    """Accept naive datetimes when a calendar timezone is provided."""
    adapter = IcalAdapter()
    structured = {
        "calendar": {
            "prodid": "-//tldw//files//EN",
            "version": "2.0",
            "timezone": "UTC",
            "events": [
                {
                    "uid": "1",
                    "summary": "Meeting",
                    "start": "2026-01-01T10:00:00",
                    "end": "2026-01-01T11:00:00",
                }
            ],
        }
    }
    issues = adapter.validate(structured)
    assert issues == []


def test_ical_rejects_invalid_timezone() -> None:
    """Reject invalid calendar timezones."""
    adapter = IcalAdapter()
    structured = {
        "calendar": {
            "prodid": "-//tldw//files//EN",
            "version": "2.0",
            "timezone": "Invalid/Zone",
            "events": [
                {
                    "uid": "1",
                    "summary": "Meeting",
                    "start": "2026-01-01T10:00:00",
                }
            ],
        }
    }
    issues = adapter.validate(structured)
    assert any(issue.code == "calendar_timezone_invalid" for issue in issues)


def test_ical_all_day_event_allowed() -> None:
    """Allow all-day events without timezone issues."""
    adapter = IcalAdapter()
    structured = {
        "calendar": {
            "prodid": "-//tldw//files//EN",
            "version": "2.0",
            "events": [
                {
                    "uid": "1",
                    "summary": "Holiday",
                    "start": "2026-01-01",
                    "end": "2026-01-02",
                }
            ],
        }
    }
    issues = adapter.validate(structured)
    assert issues == []
