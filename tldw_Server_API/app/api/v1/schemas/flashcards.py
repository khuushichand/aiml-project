from typing import List, Optional, Literal
from pydantic import BaseModel, Field


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
    tags: Optional[List[str]] = Field(None, description="List of tags; stored as JSON array")
    source_ref_type: Optional[Literal['media', 'message', 'note', 'manual']] = 'manual'
    source_ref_id: Optional[str] = None
    model_type: Optional[Literal['basic','basic_reverse','cloze']] = None
    reverse: Optional[bool] = None


class Flashcard(BaseModel):
    uuid: str
    deck_id: Optional[int] = None
    deck_name: Optional[str] = None
    front: str
    back: str
    notes: Optional[str] = None
    extra: Optional[str] = None
    is_cloze: bool
    tags_json: Optional[str] = None
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


class FlashcardListResponse(BaseModel):
    items: List[Flashcard]
    count: int
    total: int | None = None


class FlashcardReviewRequest(BaseModel):
    card_uuid: str
    rating: int = Field(..., ge=0, le=5, description="Anki 0-5 rating")
    answer_time_ms: Optional[int] = None


class FlashcardReviewResponse(BaseModel):
    uuid: str
    ef: float
    interval_days: int
    repetitions: int
    lapses: int
    due_at: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    last_modified: Optional[str] = None
    version: int


class FlashcardUpdate(BaseModel):
    deck_id: Optional[int] = None
    front: Optional[str] = None
    back: Optional[str] = None
    notes: Optional[str] = None
    extra: Optional[str] = None
    is_cloze: Optional[bool] = None
    tags: Optional[List[str]] = None  # Optional: set/replace tags
    expected_version: Optional[int] = None
    model_type: Optional[Literal['basic','basic_reverse','cloze']] = None
    reverse: Optional[bool] = None


class FlashcardTagsUpdate(BaseModel):
    tags: List[str]


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
