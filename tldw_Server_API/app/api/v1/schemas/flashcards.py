import json
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DeckSchedulerSettings(BaseModel):
    new_steps_minutes: list[int] = Field(default_factory=lambda: [1, 10])
    relearn_steps_minutes: list[int] = Field(default_factory=lambda: [10])
    graduating_interval_days: int = 1
    easy_interval_days: int = 4
    easy_bonus: float = 1.3
    interval_modifier: float = 1.0
    max_interval_days: int = 36500
    leech_threshold: int = 8
    enable_fuzz: bool = False


class DeckCreate(BaseModel):
    name: str = Field(..., description="Deck name (unique)")
    description: Optional[str] = Field(None, description="Deck description")
    scheduler_settings: Optional[DeckSchedulerSettings] = None


class DeckUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scheduler_settings: Optional[DeckSchedulerSettings] = None
    expected_version: Optional[int] = Field(None, ge=1)


class Deck(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    deleted: bool
    client_id: str
    version: int
    scheduler_settings_json: Optional[str] = None
    scheduler_settings: DeckSchedulerSettings = Field(default_factory=DeckSchedulerSettings)

    @model_validator(mode="before")
    def _populate_scheduler_settings(cls, data):
        if not isinstance(data, dict):
            return data
        if data.get("scheduler_settings") is not None:
            return data
        raw = data.get("scheduler_settings_json")
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    data["scheduler_settings"] = parsed
            except Exception:
                data["scheduler_settings"] = DeckSchedulerSettings().model_dump()
        return data


class FlashcardReviewIntervalPreviews(BaseModel):
    again: str
    hard: str
    good: str
    easy: str


class FlashcardCreate(BaseModel):
    deck_id: Optional[int] = Field(None, description="Deck ID to assign the card to")
    front: str
    back: str
    notes: Optional[str] = None
    extra: Optional[str] = None
    is_cloze: Optional[bool] = False
    tags: Optional[list[str]] = Field(None, description="List of tags; stored as JSON array")
    source_ref_type: Optional[Literal['media', 'message', 'note', 'manual']] = 'manual'
    source_ref_id: Optional[str] = None
    model_type: Optional[Literal['basic','basic_reverse','cloze']] = None
    reverse: Optional[bool] = None


class Flashcard(BaseModel):
    uuid: UUID
    deck_id: Optional[int] = None
    deck_name: Optional[str] = None
    front: str
    back: str
    notes: Optional[str] = None
    extra: Optional[str] = None
    is_cloze: bool
    tags_json: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    source_ref_type: Optional[Literal['media', 'message', 'note', 'manual']] = None
    source_ref_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    ef: float
    interval_days: int
    repetitions: int
    lapses: int
    due_at: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    queue_state: Literal["new", "learning", "review", "relearning", "suspended"] = "new"
    step_index: Optional[int] = None
    suspended_reason: Optional[Literal["manual", "leech"]] = None
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    deleted: bool
    client_id: str
    version: int
    model_type: Literal['basic','basic_reverse','cloze']
    reverse: bool
    next_intervals: Optional[FlashcardReviewIntervalPreviews] = None

    @model_validator(mode="before")
    def _populate_tags(cls, data):
        if not isinstance(data, dict):
            return data
        if data.get("tags") is not None:
            return data
        tags_json = data.get("tags_json")
        if tags_json:
            try:
                parsed = json.loads(tags_json)
                if isinstance(parsed, list):
                    data["tags"] = [str(t) for t in parsed if t is not None]
                else:
                    data["tags"] = []
            except Exception:
                data["tags"] = []
        else:
            data["tags"] = []
        return data


class FlashcardListResponse(BaseModel):
    items: list[Flashcard]
    count: int
    total: int | None = None


class FlashcardReviewRequest(BaseModel):
    card_uuid: str
    rating: int = Field(..., ge=0, le=5, description="Anki 0-5 rating")
    answer_time_ms: Optional[int] = None


class FlashcardReviewResponse(BaseModel):
    uuid: UUID
    ef: float
    interval_days: int
    repetitions: int
    lapses: int
    due_at: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    last_modified: Optional[str] = None
    version: int
    queue_state: Literal["new", "learning", "review", "relearning", "suspended"]
    step_index: Optional[int] = None
    suspended_reason: Optional[Literal["manual", "leech"]] = None
    next_intervals: FlashcardReviewIntervalPreviews


class FlashcardNextReviewResponse(BaseModel):
    card: Optional[Flashcard] = None
    selection_reason: Optional[Literal["learning_due", "review_due", "new", "none"]] = None


class FlashcardGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Source text to generate flashcards from")
    num_cards: int = Field(10, ge=1, le=100, description="Requested number of generated cards")
    card_type: Literal['basic', 'basic_reverse', 'cloze'] = Field('basic')
    difficulty: Literal['easy', 'medium', 'hard', 'mixed'] = Field('mixed')
    focus_topics: list[str] = Field(default_factory=list)
    provider: Optional[str] = Field(None, description="Optional LLM provider override")
    model: Optional[str] = Field(None, description="Optional LLM model override")


class GeneratedFlashcard(BaseModel):
    front: str
    back: str
    tags: list[str] = Field(default_factory=list)
    model_type: Literal['basic', 'basic_reverse', 'cloze'] = Field('basic')
    notes: Optional[str] = None
    extra: Optional[str] = None


class FlashcardGenerateResponse(BaseModel):
    flashcards: list[GeneratedFlashcard] = Field(default_factory=list)
    count: int


class FlashcardDeckProgress(BaseModel):
    deck_id: int
    deck_name: str
    total: int
    new: int
    learning: int
    due: int
    mature: int


class FlashcardAnalyticsSummaryResponse(BaseModel):
    reviewed_today: int
    retention_rate_today: Optional[float] = None
    lapse_rate_today: Optional[float] = None
    avg_answer_time_ms_today: Optional[float] = None
    study_streak_days: int
    generated_at: str
    decks: list[FlashcardDeckProgress] = Field(default_factory=list)


class FlashcardUpdate(BaseModel):
    deck_id: Optional[int] = None
    front: Optional[str] = None
    back: Optional[str] = None
    notes: Optional[str] = None
    extra: Optional[str] = None
    is_cloze: Optional[bool] = None
    tags: Optional[list[str]] = None  # Optional: set/replace tags
    expected_version: Optional[int] = None
    model_type: Optional[Literal['basic','basic_reverse','cloze']] = None
    reverse: Optional[bool] = None


class FlashcardBulkUpdateItem(FlashcardUpdate):
    uuid: str


class FlashcardBulkUpdateError(BaseModel):
    code: Literal["validation_error", "not_found", "conflict"]
    message: str
    invalid_fields: list[str] = Field(default_factory=list)
    invalid_deck_ids: list[int] = Field(default_factory=list)


class FlashcardBulkUpdateResult(BaseModel):
    uuid: str
    status: Literal["updated", "validation_error", "not_found", "conflict"]
    flashcard: Optional[Flashcard] = None
    error: Optional[FlashcardBulkUpdateError] = None


class FlashcardBulkUpdateResponse(BaseModel):
    results: list[FlashcardBulkUpdateResult] = Field(default_factory=list)


class FlashcardAssetMetadata(BaseModel):
    asset_uuid: UUID
    reference: str
    markdown_snippet: str
    mime_type: str
    byte_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    original_filename: Optional[str] = None


class FlashcardResetSchedulingRequest(BaseModel):
    expected_version: int = Field(..., ge=1)


class StudyAssistantThreadSummary(BaseModel):
    id: int
    context_type: Literal["flashcard", "quiz_attempt_question"]
    flashcard_uuid: Optional[str] = None
    quiz_attempt_id: Optional[int] = None
    question_id: Optional[int] = None
    last_message_at: Optional[str] = None
    message_count: int = 0
    deleted: bool
    client_id: str
    version: int
    created_at: Optional[str] = None
    last_modified: Optional[str] = None


class StudyAssistantMessage(BaseModel):
    id: int
    thread_id: int
    role: Literal["user", "assistant"]
    action_type: Literal["explain", "mnemonic", "follow_up", "fact_check", "freeform"]
    input_modality: Literal["text", "voice_transcript"]
    content: str
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    provider: Optional[str] = None
    model: Optional[str] = None
    created_at: Optional[str] = None
    client_id: str

    @model_validator(mode="before")
    def _populate_json_fields(cls, data):
        if not isinstance(data, dict):
            return data

        for source_field, target_field in (
            ("structured_payload_json", "structured_payload"),
            ("context_snapshot_json", "context_snapshot"),
        ):
            if data.get(target_field) is not None:
                continue
            raw = data.get(source_field)
            if isinstance(raw, dict):
                data[target_field] = raw
                continue
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = {}
                data[target_field] = parsed if isinstance(parsed, dict) else {}

        if data.get("structured_payload") is None:
            data["structured_payload"] = {}
        if data.get("context_snapshot") is None:
            data["context_snapshot"] = {}
        return data


class StudyAssistantHistoryResponse(BaseModel):
    thread: StudyAssistantThreadSummary
    messages: list[StudyAssistantMessage] = Field(default_factory=list)


StudyAssistantAction = Literal["explain", "mnemonic", "follow_up", "fact_check", "freeform"]


class StudyAssistantFactCheckPayload(BaseModel):
    verdict: Literal["correct", "partially_correct", "incorrect"]
    corrections: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    next_prompt: str = Field(default="What part would you like to review next?")


class StudyAssistantRespondRequest(BaseModel):
    action: StudyAssistantAction
    message: Optional[str] = None
    input_modality: Literal["text", "voice_transcript"] = "text"
    provider: Optional[str] = None
    model: Optional[str] = None
    expected_thread_version: Optional[int] = Field(None, ge=1)


class StudyAssistantContextResponse(BaseModel):
    thread: StudyAssistantThreadSummary
    messages: list[StudyAssistantMessage] = Field(default_factory=list)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    available_actions: list[StudyAssistantAction] = Field(default_factory=list)


class StudyAssistantRespondResponse(BaseModel):
    thread: StudyAssistantThreadSummary
    user_message: StudyAssistantMessage
    assistant_message: StudyAssistantMessage
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)


class FlashcardTagsUpdate(BaseModel):
    tags: list[str]


class FlashcardQuery(BaseModel):
    deck_id: Optional[int] = None
    tag: Optional[str] = None
    due_status: Optional[Literal['new', 'learning', 'due', 'all']] = 'all'
    q: Optional[str] = None
    limit: Optional[int] = Field(100, ge=1, le=1000)
    offset: Optional[int] = Field(0, ge=0)
    order_by: Optional[Literal['due_at', 'created_at']] = 'due_at'


class FlashcardsImportRequest(BaseModel):
    content: str = Field(..., description="TSV content: Deck, Front, Back, Tags, Notes per line")
    delimiter: Optional[str] = Field('\t', description="Field delimiter; default tab")
    has_header: Optional[bool] = Field(False, description="Whether the first line is a header")


class StructuredQaImportPreviewRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Labeled Q&A content for preview parsing")


class StructuredQaImportPreviewDraft(BaseModel):
    front: str
    back: str
    line_start: int
    line_end: int
    notes: Optional[str] = None
    extra: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class StructuredQaImportPreviewError(BaseModel):
    line: Optional[int] = None
    error: str


class StructuredQaImportPreviewResponse(BaseModel):
    drafts: list[StructuredQaImportPreviewDraft] = Field(default_factory=list)
    errors: list[StructuredQaImportPreviewError] = Field(default_factory=list)
    detected_format: Literal["qa_labels"] = "qa_labels"
    skipped_blocks: int = 0
