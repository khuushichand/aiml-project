from __future__ import annotations

from datetime import timezone

from tldw_Server_API.app.services.admin_system_service import _parse_date_param


def test_parse_date_param_date_only_returns_utc_aware_datetime():
    parsed = _parse_date_param("2026-02-01", "start")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def test_parse_date_param_naive_datetime_returns_utc_aware_datetime():
    parsed = _parse_date_param("2026-02-01T12:30:00", "start")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def test_parse_date_param_offset_datetime_is_normalized_to_utc():
    parsed = _parse_date_param("2026-02-01T12:30:00-05:00", "start")
    assert parsed is not None
    assert parsed.hour == 17
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
