from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    MULTI_SELECT = "multi_select"
    MATCHING = "matching"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"


AnswerValue = int | str | list[int] | dict[str, str]


class SourceCitation(BaseModel):
    label: Optional[str] = None
    quote: Optional[str] = None
    media_id: Optional[int] = Field(None, ge=1)
    chunk_id: Optional[str] = None
    timestamp_seconds: Optional[float] = Field(None, ge=0)
    source_url: Optional[str] = None


class QuizCreate(BaseModel):
    name: str = Field(..., description="Quiz name")
    description: Optional[str] = Field(None, description="Optional quiz description")
    workspace_tag: Optional[str] = Field(None, description="Optional workspace tag (e.g., 'workspace:<slug-or-id>')")
    media_id: Optional[int] = Field(None, description="Source media ID for AI-generated quizzes")
    time_limit_seconds: Optional[int] = Field(None, ge=1, description="Optional time limit in seconds")
    passing_score: Optional[int] = Field(None, ge=0, le=100, description="Passing score percentage")


class QuizUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    description: Optional[str] = None
    workspace_tag: Optional[str] = None
    media_id: Optional[int] = None
    time_limit_seconds: Optional[int] = Field(None, ge=1)
    passing_score: Optional[int] = Field(None, ge=0, le=100)
    expected_version: Optional[int] = None


class QuizResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    workspace_tag: Optional[str] = None
    media_id: Optional[int] = None
    total_questions: int
    time_limit_seconds: Optional[int] = None
    passing_score: Optional[int] = None
    deleted: bool
    client_id: str
    version: int
    created_at: Optional[str] = None
    last_modified: Optional[str] = None


class QuizListResponse(BaseModel):
    items: list[QuizResponse]
    count: int


class QuestionCreate(BaseModel):
    question_type: QuestionType
    question_text: str
    options: Optional[list[str]] = Field(None, description="Multiple choice options")
    correct_answer: AnswerValue
    explanation: Optional[str] = None
    hint: Optional[str] = None
    hint_penalty_points: int = Field(0, ge=0)
    source_citations: Optional[list[SourceCitation]] = None
    points: int = Field(1, ge=0)
    order_index: int = 0
    tags: Optional[list[str]] = None


class QuestionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_type: Optional[QuestionType] = None
    question_text: Optional[str] = None
    options: Optional[list[str]] = None
    correct_answer: Optional[AnswerValue] = None
    explanation: Optional[str] = None
    hint: Optional[str] = None
    hint_penalty_points: Optional[int] = Field(None, ge=0)
    source_citations: Optional[list[SourceCitation]] = None
    points: Optional[int] = Field(None, ge=0)
    order_index: Optional[int] = None
    tags: Optional[list[str]] = None
    expected_version: Optional[int] = None


class QuestionPublicResponse(BaseModel):
    id: int
    quiz_id: int
    question_type: QuestionType
    question_text: str
    options: Optional[list[str]] = None
    hint: Optional[str] = None
    hint_penalty_points: int = Field(0, ge=0)
    source_citations: Optional[list[SourceCitation]] = None
    points: int
    order_index: int
    tags: Optional[list[str]] = None
    deleted: bool
    client_id: str
    version: int
    created_at: Optional[str] = None
    last_modified: Optional[str] = None


class QuestionAdminResponse(QuestionPublicResponse):
    correct_answer: Optional[AnswerValue] = None
    explanation: Optional[str] = None


class QuestionListResponse(BaseModel):
    items: list[QuestionPublicResponse | QuestionAdminResponse]
    count: int


class QuizAnswerInput(BaseModel):
    question_id: int
    user_answer: AnswerValue
    hint_used: Optional[bool] = None
    time_spent_ms: Optional[int] = None


class AttemptSubmitRequest(BaseModel):
    answers: list[QuizAnswerInput]


class AttemptAnswer(BaseModel):
    question_id: int
    user_answer: AnswerValue
    is_correct: bool
    correct_answer: Optional[AnswerValue] = None
    explanation: Optional[str] = None
    hint_used: Optional[bool] = None
    hint_penalty_points: Optional[int] = Field(None, ge=0)
    source_citations: Optional[list[SourceCitation]] = None
    points_awarded: Optional[int] = None
    time_spent_ms: Optional[int] = None


class AttemptResponse(BaseModel):
    id: int
    quiz_id: int
    started_at: str
    completed_at: Optional[str] = None
    score: Optional[int] = None
    total_possible: int
    time_spent_seconds: Optional[int] = None
    answers: list[AttemptAnswer] = Field(default_factory=list)
    questions: Optional[list[QuestionPublicResponse]] = None


class AttemptListResponse(BaseModel):
    items: list[AttemptResponse]
    count: int


class QuizGenerateRequest(BaseModel):
    media_id: int
    num_questions: int = Field(10, ge=1, le=100)
    question_types: Optional[list[QuestionType]] = None
    difficulty: str = Field("mixed", description="easy, medium, hard, mixed")
    focus_topics: Optional[list[str]] = None
    model: Optional[str] = None
    workspace_tag: Optional[str] = Field(None, description="Optional workspace tag (e.g., 'workspace:<slug-or-id>')")


class QuizGenerateResponse(BaseModel):
    quiz: QuizResponse
    questions: list[QuestionAdminResponse]


class QuizImportQuestion(BaseModel):
    question_type: QuestionType
    question_text: str
    options: Optional[list[str]] = None
    correct_answer: AnswerValue
    explanation: Optional[str] = None
    hint: Optional[str] = None
    hint_penalty_points: int = Field(0, ge=0)
    source_citations: Optional[list[SourceCitation]] = None
    points: int = Field(1, ge=0)
    order_index: int = Field(0, ge=0)
    tags: Optional[list[str]] = None


class QuizImportQuiz(BaseModel):
    name: str
    description: Optional[str] = None
    workspace_tag: Optional[str] = None
    media_id: Optional[int] = None
    time_limit_seconds: Optional[int] = Field(None, ge=1)
    passing_score: Optional[int] = Field(None, ge=0, le=100)


class QuizImportEntry(BaseModel):
    quiz: QuizImportQuiz
    questions: list[QuizImportQuestion] = Field(default_factory=list)


class QuizImportRequest(BaseModel):
    export_format: Optional[str] = Field(
        default=None,
        description="Expected export format marker, e.g. tldw.quiz.export.v1",
    )
    quizzes: list[QuizImportEntry]


class QuizImportItemResult(BaseModel):
    source_index: int = Field(..., ge=0, description="Index of the input quiz entry")
    quiz_id: int
    imported_questions: int = Field(..., ge=0)
    failed_questions: int = Field(..., ge=0)


class QuizImportError(BaseModel):
    source_index: int = Field(..., ge=0)
    quiz_name: Optional[str] = None
    question_index: Optional[int] = Field(default=None, ge=0)
    error: str


class QuizImportResponse(BaseModel):
    imported_quizzes: int = Field(..., ge=0)
    failed_quizzes: int = Field(..., ge=0)
    imported_questions: int = Field(..., ge=0)
    failed_questions: int = Field(..., ge=0)
    items: list[QuizImportItemResult] = Field(default_factory=list)
    errors: list[QuizImportError] = Field(default_factory=list)
