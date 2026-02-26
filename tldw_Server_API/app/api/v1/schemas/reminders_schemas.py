from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReminderScheduleKind = Literal["one_time", "recurring"]


class ReminderTaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    body: str | None = None
    schedule_kind: ReminderScheduleKind
    run_at: str | None = None
    cron: str | None = None
    timezone: str | None = None
    link_type: str | None = None
    link_id: str | None = None
    link_url: str | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def _validate_schedule_fields(self) -> "ReminderTaskCreateRequest":
        if self.schedule_kind == "one_time":
            if not self.run_at:
                raise ValueError("run_at is required for one_time schedules")
            return self

        if not self.cron:
            raise ValueError("cron is required for recurring schedules")
        if not self.timezone:
            raise ValueError("timezone is required for recurring schedules")
        return self
