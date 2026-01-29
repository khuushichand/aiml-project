from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"


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
    items: List[QuizResponse]
    count: int


class QuestionCreate(BaseModel):
    question_type: QuestionType
    question_text: str
    options: Optional[List[str]] = Field(None, description="Multiple choice options")
    correct_answer: int | str
    explanation: Optional[str] = None
    points: int = Field(1, ge=0)
    order_index: int = 0
    tags: Optional[List[str]] = None


class QuestionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_type: Optional[QuestionType] = None
    question_text: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[int | str] = None
    explanation: Optional[str] = None
    points: Optional[int] = Field(None, ge=0)
    order_index: Optional[int] = None
    tags: Optional[List[str]] = None
    expected_version: Optional[int] = None


class QuestionPublicResponse(BaseModel):
    id: int
    quiz_id: int
    question_type: QuestionType
    question_text: str
    options: Optional[List[str]] = None
    points: int
    order_index: int
    tags: Optional[List[str]] = None
    deleted: bool
    client_id: str
    version: int
    created_at: Optional[str] = None
    last_modified: Optional[str] = None


class QuestionAdminResponse(QuestionPublicResponse):
    correct_answer: Optional[int | str] = None
    explanation: Optional[str] = None


class QuestionListResponse(BaseModel):
    items: List[QuestionPublicResponse | QuestionAdminResponse]
    count: int


class QuizAnswerInput(BaseModel):
    question_id: int
    user_answer: int | str
    time_spent_ms: Optional[int] = None


class AttemptSubmitRequest(BaseModel):
    answers: List[QuizAnswerInput]


class AttemptAnswer(BaseModel):
    question_id: int
    user_answer: int | str
    is_correct: bool
    correct_answer: Optional[int | str] = None
    explanation: Optional[str] = None
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
    answers: List[AttemptAnswer] = Field(default_factory=list)
    questions: Optional[List[QuestionPublicResponse]] = None


class AttemptListResponse(BaseModel):
    items: List[AttemptResponse]
    count: int


class QuizGenerateRequest(BaseModel):
    media_id: int
    num_questions: int = Field(10, ge=1, le=100)
    question_types: Optional[List[QuestionType]] = None
    difficulty: str = Field("mixed", description="easy, medium, hard, mixed")
    focus_topics: Optional[List[str]] = None
    model: Optional[str] = None
    workspace_tag: Optional[str] = Field(None, description="Optional workspace tag (e.g., 'workspace:<slug-or-id>')")


class QuizGenerateResponse(BaseModel):
    quiz: QuizResponse
    questions: List[QuestionAdminResponse]
