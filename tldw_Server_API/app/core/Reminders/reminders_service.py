from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from tldw_Server_API.app.core.DB_Management.Collections_DB import (
    CollectionsDatabase,
    ReminderTaskRow,
)

MIN_SNOOZE_MINUTES = 1
MAX_SNOOZE_MINUTES = 10080


class RemindersService:
    """Domain service for user reminder task lifecycle operations."""

    def __init__(
        self,
        user_id: int | str,
        *,
        collections_db: CollectionsDatabase | None = None,
    ) -> None:
        self.user_id = int(user_id)
        self.collections = collections_db or CollectionsDatabase.for_user(self.user_id)

    def create_task(self, **kwargs: Any) -> ReminderTaskRow:
        task_id = self.collections.create_reminder_task(**kwargs)
        return self.collections.get_reminder_task(task_id)

    def list_tasks(self, *, include_disabled: bool = True) -> list[ReminderTaskRow]:
        return self.collections.list_reminder_tasks(include_disabled=include_disabled)

    def get_task(self, task_id: str) -> ReminderTaskRow:
        return self.collections.get_reminder_task(task_id)

    def update_task(self, task_id: str, patch: dict[str, Any]) -> ReminderTaskRow:
        return self.collections.update_reminder_task(task_id, patch)

    def delete_task(self, task_id: str) -> bool:
        return self.collections.delete_reminder_task(task_id)

    def snooze_notification(self, *, notification_id: int, minutes: int = 30) -> ReminderTaskRow:
        if minutes < MIN_SNOOZE_MINUTES or minutes > MAX_SNOOZE_MINUTES:
            raise ValueError(
                f"minutes must be between {MIN_SNOOZE_MINUTES} and {MAX_SNOOZE_MINUTES}"
            )

        source = self.collections.get_user_notification(notification_id)
        run_at = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
        task_id = self.collections.create_reminder_task(
            title=f"Snoozed: {source.title}",
            body=source.message,
            schedule_kind="one_time",
            run_at=run_at,
            cron=None,
            timezone="UTC",
            enabled=True,
            link_type=source.link_type,
            link_id=source.link_id,
            link_url=source.link_url,
        )
        return self.collections.get_reminder_task(task_id)
