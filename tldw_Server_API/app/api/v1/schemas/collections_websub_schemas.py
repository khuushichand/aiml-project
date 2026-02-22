from __future__ import annotations

from pydantic import BaseModel

from tldw_Server_API.app.api.v1.schemas._compat import Field


class WebSubSubscribeRequest(BaseModel):
    lease_seconds: int | None = Field(
        default=None,
        description="Requested lease in seconds. If omitted, the server default (WEBSUB_DEFAULT_LEASE_SECONDS or 864000) is used.",
    )


class WebSubSubscriptionResponse(BaseModel):
    id: int
    source_id: int
    hub_url: str
    topic_url: str
    state: str
    lease_seconds: int | None = None
    verified_at: str | None = None
    expires_at: str | None = None
    last_push_at: str | None = None
    created_at: str | None = None


class WebSubUnsubscribeResponse(BaseModel):
    message: str
    state: str
