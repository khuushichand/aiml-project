from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import re

from tldw_Server_API.app.core.File_Artifacts.adapters.base import ExportResult, ValidationIssue


class IcalAdapter:
    file_type = "ical"
    export_formats = {"ics"}

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        calendar = payload.get("calendar")
        if not isinstance(calendar, dict):
            raise ValueError("calendar_required")
        prodid = calendar.get("prodid") or "-//tldw//files//EN"
        version = calendar.get("version") or "2.0"
        calendar_timezone = calendar.get("timezone")
        if calendar_timezone is not None and not isinstance(calendar_timezone, str):
            raise ValueError("calendar_timezone_invalid")
        events = calendar.get("events")
        if events is None:
            events = []
        if not isinstance(events, list):
            raise ValueError("events_must_be_list")
        return {
            "calendar": {
                "prodid": str(prodid),
                "version": str(version),
                "timezone": calendar_timezone,
                "events": events,
            }
        }

    def validate(self, structured: Dict[str, Any]) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        calendar = structured.get("calendar")
        if not isinstance(calendar, dict):
            return [ValidationIssue(code="calendar_required", message="calendar must be an object", path="calendar")]
        events = calendar.get("events")
        if not isinstance(events, list):
            issues.append(ValidationIssue(code="events_required", message="events must be a list", path="calendar.events"))
            return issues
        calendar_tz = calendar.get("timezone")
        if calendar_tz is not None and not isinstance(calendar_tz, str):
            issues.append(
                ValidationIssue(code="calendar_timezone_invalid", message="calendar timezone must be a string", path="calendar.timezone")
            )
            return issues
        if calendar_tz and not self._timezone_valid(calendar_tz):
            issues.append(
                ValidationIssue(code="calendar_timezone_invalid", message="calendar timezone must be a valid IANA timezone", path="calendar.timezone")
            )
            return issues
        for idx, event in enumerate(events):
            if not isinstance(event, dict):
                issues.append(ValidationIssue(code="event_invalid", message="event must be an object", path=f"calendar.events[{idx}]"))
                continue
            for field in ("uid", "summary", "start"):
                if not event.get(field):
                    issues.append(
                        ValidationIssue(
                            code="event_missing_field",
                            message=f"event missing {field}",
                            path=f"calendar.events[{idx}].{field}",
                        )
                    )
            event_tz = event.get("timezone") or calendar_tz
            start_dt, start_issues = self._parse_event_datetime(
                event.get("start"),
                event_tz,
                path=f"calendar.events[{idx}].start",
            )
            issues.extend(start_issues)
            end_dt, end_issues = self._parse_event_datetime(
                event.get("end"),
                event_tz,
                path=f"calendar.events[{idx}].end",
            )
            issues.extend(end_issues)
            if start_dt and end_dt:
                if isinstance(start_dt, date) != isinstance(end_dt, date):
                    issues.append(
                        ValidationIssue(
                            code="event_date_type_mismatch",
                            message="start and end must both be date or datetime",
                            path=f"calendar.events[{idx}]",
                        )
                    )
                elif end_dt < start_dt:
                    issues.append(
                        ValidationIssue(
                            code="event_end_before_start",
                            message="event end must be after start",
                            path=f"calendar.events[{idx}].end",
                        )
                    )
        if issues:
            return issues
        try:
            _ = self._build_calendar(structured)
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    code="icalendar_validation_failed",
                    message=str(exc),
                    path="calendar",
                )
            )
        return issues

    def export(self, structured: Dict[str, Any], *, format: str) -> ExportResult:
        if format != "ics":
            raise ValueError("unsupported_format")
        cal = self._build_calendar(structured)
        data = cal.to_ical()
        return ExportResult(status="ready", content_type="text/calendar", bytes_len=len(data), content=data)

    @staticmethod
    def _timezone_valid(tzid: str) -> bool:
        try:
            ZoneInfo(tzid)
            return True
        except Exception:
            return False

    @staticmethod
    def _is_date_only(raw: str) -> bool:
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", raw))

    def _parse_event_datetime(
        self,
        raw: Any,
        tzid: Optional[str],
        *,
        path: str,
    ) -> Tuple[datetime | date | None, List[ValidationIssue]]:
        issues: List[ValidationIssue] = []
        if raw is None:
            return None, issues
        if not isinstance(raw, str):
            issues.append(ValidationIssue(code="event_datetime_invalid", message="value must be a string", path=path))
            return None, issues
        candidate = raw.strip()
        if self._is_date_only(candidate):
            try:
                return datetime.strptime(candidate, "%Y-%m-%d").date(), issues
            except ValueError:
                issues.append(ValidationIssue(code="event_date_invalid", message="date must be YYYY-MM-DD", path=path))
                return None, issues

        try:
            from dateutil.parser import isoparse
        except Exception as exc:
            issues.append(ValidationIssue(code="datetime_parser_unavailable", message=str(exc), path=path))
            return None, issues

        try:
            dt = isoparse(candidate)
        except Exception:
            issues.append(ValidationIssue(code="event_datetime_invalid", message="datetime must be ISO8601", path=path))
            return None, issues

        if dt.tzinfo is None:
            if not tzid:
                issues.append(
                    ValidationIssue(
                        code="event_timezone_required",
                        message="timezone required for datetime values",
                        path=path,
                    )
                )
                return None, issues
            try:
                tzinfo = ZoneInfo(tzid)
            except Exception:
                issues.append(
                    ValidationIssue(
                        code="event_timezone_invalid",
                        message="timezone must be a valid IANA timezone",
                        path=path,
                    )
                )
                return None, issues
            dt = dt.replace(tzinfo=tzinfo)
        else:
            if tzid:
                tz_key = getattr(dt.tzinfo, "key", None)
                if tz_key != tzid:
                    issues.append(
                        ValidationIssue(
                            code="event_timezone_mismatch",
                            message="datetime timezone does not match event timezone",
                            path=path,
                        )
                    )
                    return None, issues
        return dt, issues

    def _build_calendar(self, structured: Dict[str, Any]):
        try:
            from icalendar import Calendar, Event
        except Exception as exc:
            raise ValueError("icalendar_library_unavailable") from exc

        calendar = structured.get("calendar") or {}
        cal = Calendar()
        cal.add("prodid", calendar.get("prodid") or "-//tldw//files//EN")
        cal.add("version", calendar.get("version") or "2.0")
        calendar_tz = calendar.get("timezone")
        for event in calendar.get("events") or []:
            if not isinstance(event, dict):
                continue
            event_tz = event.get("timezone") or calendar_tz
            start_dt, start_issues = self._parse_event_datetime(event.get("start"), event_tz, path="calendar.events.start")
            if start_issues or not start_dt:
                raise ValueError("event_start_invalid")
            end_dt, end_issues = self._parse_event_datetime(event.get("end"), event_tz, path="calendar.events.end")
            if end_issues:
                raise ValueError("event_end_invalid")

            ical_event = Event()
            ical_event.add("uid", event.get("uid"))
            ical_event.add("summary", event.get("summary"))
            ical_event.add("dtstart", start_dt)
            if end_dt is not None:
                ical_event.add("dtend", end_dt)
            if event.get("description"):
                ical_event.add("description", event.get("description"))
            if event.get("location"):
                ical_event.add("location", event.get("location"))
            cal.add_component(ical_event)
        return cal
