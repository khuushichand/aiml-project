import json
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DeckCreate(BaseModel):
    name: str = Field(..., description="Deck name (unique)")
    description: Optional[str] = Field(None, description="Deck description")


class Deck(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    deleted: bool
    client_id: str
    version: int


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
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    deleted: bool
    client_id: str
    version: int
    model_type: Literal['basic','basic_reverse','cloze']
    reverse: bool

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


class FlashcardResetSchedulingRequest(BaseModel):
    expected_version: int = Field(..., ge=1)


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
