from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class KnowledgeSaveRequest(BaseModel):
    conversation_id: str = Field(..., description="Conversation to backlink")
    message_id: Optional[str] = Field(None, description="Optional message ID to backlink")
    snippet: str = Field(..., min_length=1, description="Snippet content to save")
    tags: Optional[List[str]] = Field(None, description="Optional tags to attach as keywords")
    make_flashcard: bool = Field(False, description="If true, also create a flashcard from the snippet")
    export_to: Literal["none", "notion", "wiki"] = Field(
        "none",
        description="Optional export target; disabled unless chat connectors v2 is enabled"
    )

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        cleaned = []
        seen = set()
        for v in value:
            if v is None:
                continue
            s = str(v).strip()
            if not s:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(s)
        return cleaned or None


class KnowledgeSaveResponse(BaseModel):
    note_id: str
    flashcard_id: Optional[str] = None
    conversation_id: str
    message_id: Optional[str] = None
    export_status: Literal["not_requested", "skipped_disabled", "queued", "completed"] = "not_requested"
    export_job_id: Optional[str] = None
