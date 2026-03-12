from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, is_single_user_principal


_BACKUP_DATASETS = {"media", "chacha", "prompts", "evaluations", "audit", "authnz"}
_PER_USER_BACKUP_DATASETS = _BACKUP_DATASETS - {"authnz"}
_PLATFORM_BACKUP_SCHEDULE_ROLES = {"owner", "super_admin"}
_WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass
class AdminBackupSchedulesService:
    """Service for authoritative backup schedule validation and derived semantics."""

    repo: Any | None

    def normalize_dataset(self, dataset: str) -> str:
        """Normalize and validate a schedule dataset identifier."""
        normalized = (dataset or "").strip().lower()
        if normalized not in _BACKUP_DATASETS:
            raise HTTPException(status_code=400, detail="unknown_dataset")
        return normalized

    def validate_target_rules(self, dataset: str, target_user_id: int | None) -> None:
        """Enforce dataset-specific target-user rules."""
        if dataset in _PER_USER_BACKUP_DATASETS and target_user_id is None:
            raise HTTPException(status_code=400, detail="target_user_required")
        if dataset == "authnz" and target_user_id is not None:
            raise HTTPException(status_code=400, detail="target_user_forbidden")

    def default_timezone(self, timezone_name: str | None) -> str:
        """Return the persisted schedule timezone, defaulting to UTC."""
        normalized = (timezone_name or "").strip()
        return normalized or "UTC"

    def requires_platform_admin(self, dataset: str) -> bool:
        """Return True when the dataset is platform-scoped."""
        return dataset == "authnz"

    def is_platform_admin(self, principal: AuthPrincipal) -> bool:
        """Return True when the principal may manage platform-level schedules."""
        if is_single_user_principal(principal):
            return True
        roles = {str(role).strip().lower() for role in (principal.roles or []) if role}
        return bool(roles & _PLATFORM_BACKUP_SCHEDULE_ROLES)

    def require_platform_admin(self, principal: AuthPrincipal) -> None:
        """Require platform-level schedule management rights."""
        if self.is_platform_admin(principal):
            return
        raise HTTPException(status_code=403, detail="platform_admin_required")

    def filter_visible_items(
        self,
        items: list[dict[str, Any]],
        *,
        principal: AuthPrincipal,
    ) -> list[dict[str, Any]]:
        """Filter schedule rows visible to the current principal."""
        if self.is_platform_admin(principal):
            return list(items)
        return [item for item in items if item.get("dataset") != "authnz"]

    def resolve_monthly_run_day(self, *, anchor_day_of_month: int, year: int, month: int) -> int:
        """Clamp a monthly anchor to the last valid day of the target month."""
        if anchor_day_of_month < 1:
            raise ValueError("anchor_day_of_month must be >= 1")
        return min(int(anchor_day_of_month), monthrange(year, month)[1])

    def derive_schedule_anchors(
        self,
        *,
        frequency: str,
        reference_time: datetime,
        current: Mapping[str, Any] | None = None,
    ) -> tuple[int | None, int | None]:
        """Derive persisted anchor fields for weekly/monthly schedules."""
        normalized = frequency.strip().lower()
        if normalized == "weekly":
            if current and current.get("anchor_day_of_week") is not None:
                return int(current["anchor_day_of_week"]), None
            return reference_time.weekday(), None
        if normalized == "monthly":
            if current and current.get("anchor_day_of_month") is not None:
                return None, int(current["anchor_day_of_month"])
            return None, reference_time.day
        return None, None

    def describe_schedule(self, item: Mapping[str, Any]) -> str:
        """Build human-readable schedule copy from stored schedule fields."""
        frequency = str(item.get("frequency") or "").strip().lower()
        time_of_day = str(item.get("time_of_day") or "00:00")
        timezone_name = str(item.get("timezone") or "UTC")
        if frequency == "weekly":
            weekday_idx = item.get("anchor_day_of_week")
            if isinstance(weekday_idx, int) and 0 <= weekday_idx <= 6:
                return f"Weekly on {_WEEKDAY_NAMES[weekday_idx]} at {time_of_day} {timezone_name}"
            return f"Weekly at {time_of_day} {timezone_name}"
        if frequency == "monthly":
            month_day = item.get("anchor_day_of_month")
            if isinstance(month_day, int):
                return f"Monthly on day {month_day} at {time_of_day} {timezone_name}"
            return f"Monthly at {time_of_day} {timezone_name}"
        return f"Daily at {time_of_day} {timezone_name}"

    def compute_next_run_at(
        self,
        item: Mapping[str, Any],
        *,
        from_time: datetime,
    ) -> str:
        """Compute the next fire slot in UTC based on schedule fields."""
        from datetime import timedelta

        timezone_name = self.default_timezone(str(item.get("timezone") or "UTC"))
        try:
            zone = ZoneInfo(timezone_name)
        except Exception:
            zone = dt_timezone.utc

        if from_time.tzinfo is None:
            from_time = from_time.replace(tzinfo=dt_timezone.utc)
        local_now = from_time.astimezone(zone)
        hour_str, minute_str = str(item.get("time_of_day") or "00:00").split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
        frequency = str(item.get("frequency") or "").strip().lower()

        if frequency == "daily":
            candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= local_now:
                candidate = candidate + timedelta(days=1)
            return candidate.astimezone(dt_timezone.utc).isoformat()

        if frequency == "weekly":
            target_weekday = int(item.get("anchor_day_of_week") or 0)
            delta_days = (target_weekday - local_now.weekday()) % 7
            candidate_date = local_now.date() + timedelta(days=delta_days)
            candidate = datetime(
                candidate_date.year,
                candidate_date.month,
                candidate_date.day,
                hour,
                minute,
                tzinfo=zone,
            )
            if candidate <= local_now:
                candidate = candidate + timedelta(days=7)
            return candidate.astimezone(dt_timezone.utc).isoformat()

        if frequency == "monthly":
            target_day = int(item.get("anchor_day_of_month") or 1)
            candidate_day = self.resolve_monthly_run_day(
                anchor_day_of_month=target_day,
                year=local_now.year,
                month=local_now.month,
            )
            candidate = datetime(
                local_now.year,
                local_now.month,
                candidate_day,
                hour,
                minute,
                tzinfo=zone,
            )
            if candidate <= local_now:
                if local_now.month == 12:
                    year = local_now.year + 1
                    month = 1
                else:
                    year = local_now.year
                    month = local_now.month + 1
                candidate_day = self.resolve_monthly_run_day(
                    anchor_day_of_month=target_day,
                    year=year,
                    month=month,
                )
                candidate = datetime(year, month, candidate_day, hour, minute, tzinfo=zone)
            return candidate.astimezone(dt_timezone.utc).isoformat()

        raise ValueError(f"Unsupported frequency: {frequency}")

    def _is_duplicate_active_target_error(self, exc: Exception) -> bool:
        message = str(exc).strip().lower()
        return any(
            token in message
            for token in (
                "idx_backup_schedules_target_scope_active",
                "backup_schedules.target_scope_key",
                "backup_schedules_target_scope_active",
                "unique constraint failed",
                "duplicate key value violates unique constraint",
            )
        )

    async def create_schedule(
        self,
        *,
        dataset: str,
        target_user_id: int | None,
        frequency: str,
        time_of_day: str,
        timezone_name: str | None,
        retention_count: int,
        principal_user_id: int | None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Create a schedule row with normalized defaults and derived anchors."""
        if self.repo is None:
            raise RuntimeError("Backup schedules repo is required")
        normalized_dataset = self.normalize_dataset(dataset)
        self.validate_target_rules(normalized_dataset, target_user_id)
        reference_time = now or datetime.now(dt_timezone.utc)
        anchor_day_of_week, anchor_day_of_month = self.derive_schedule_anchors(
            frequency=frequency,
            reference_time=reference_time,
        )
        effective_timezone = self.default_timezone(timezone_name)
        next_run_at = self.compute_next_run_at(
            {
                "frequency": frequency,
                "time_of_day": time_of_day,
                "timezone": effective_timezone,
                "anchor_day_of_week": anchor_day_of_week,
                "anchor_day_of_month": anchor_day_of_month,
            },
            from_time=reference_time,
        )
        try:
            return await self.repo.create_schedule(
                dataset=normalized_dataset,
                target_user_id=target_user_id,
                frequency=frequency,
                time_of_day=time_of_day,
                timezone=effective_timezone,
                anchor_day_of_week=anchor_day_of_week,
                anchor_day_of_month=anchor_day_of_month,
                retention_count=retention_count,
                created_by_user_id=principal_user_id,
                updated_by_user_id=principal_user_id,
                next_run_at=next_run_at,
            )
        except HTTPException:
            raise
        except Exception as exc:
            if self._is_duplicate_active_target_error(exc):
                raise HTTPException(status_code=409, detail="duplicate_active_schedule") from exc
            raise

    async def update_schedule(
        self,
        *,
        schedule_id: str,
        current: Mapping[str, Any],
        frequency: str | None,
        time_of_day: str | None,
        timezone_name: str | None,
        retention_count: int | None,
        principal_user_id: int | None,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Update a schedule row while preserving or deriving anchors as needed."""
        if self.repo is None:
            raise RuntimeError("Backup schedules repo is required")
        reference_time = now or datetime.now(dt_timezone.utc)
        next_frequency = frequency or str(current["frequency"])
        anchor_day_of_week, anchor_day_of_month = self.derive_schedule_anchors(
            frequency=next_frequency,
            reference_time=reference_time,
            current=current if next_frequency == str(current["frequency"]) else None,
        )
        effective_timezone = self.default_timezone(timezone_name) if timezone_name is not None else str(current.get("timezone") or "UTC")
        effective_time_of_day = time_of_day or str(current["time_of_day"])
        next_run_at = self.compute_next_run_at(
            {
                "frequency": next_frequency,
                "time_of_day": effective_time_of_day,
                "timezone": effective_timezone,
                "anchor_day_of_week": anchor_day_of_week,
                "anchor_day_of_month": anchor_day_of_month,
            },
            from_time=reference_time,
        )
        return await self.repo.update_schedule(
            schedule_id,
            frequency=frequency,
            time_of_day=time_of_day,
            timezone=effective_timezone if timezone_name is not None else None,
            anchor_day_of_week=anchor_day_of_week,
            anchor_day_of_month=anchor_day_of_month,
            retention_count=retention_count,
            updated_by_user_id=principal_user_id,
            next_run_at=next_run_at,
        )
