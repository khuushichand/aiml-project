from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.schemas.quizzes import (
    AttemptListResponse,
    AttemptResponse,
    AttemptSubmitRequest,
    QuestionAdminResponse,
    QuestionCreate,
    QuestionListResponse,
    QuestionUpdate,
    QuizCreate,
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizListResponse,
    QuizResponse,
    QuizUpdate,
)
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
)
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.quiz_generator import generate_quiz_from_media

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get("", response_model=QuizListResponse)
def list_quizzes(
    q: Optional[str] = None,
    media_id: Optional[int] = None,
    workspace_tag: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """List quizzes with pagination and optional filters."""
    try:
        return db.list_quizzes(q=q, media_id=media_id, workspace_tag=workspace_tag, limit=limit, offset=offset)
    except CharactersRAGDBError as e:
        logger.error(f"Failed to list quizzes: {e}")
        raise HTTPException(status_code=500, detail="Failed to list quizzes") from e


@router.post("", response_model=QuizResponse)
def create_quiz(payload: QuizCreate, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    """Create a new quiz."""
    try:
        quiz_id = db.create_quiz(**payload.model_dump())
        quiz = db.get_quiz(quiz_id)
        if not quiz:
            raise HTTPException(status_code=500, detail="Failed to load created quiz")
        return quiz
    except CharactersRAGDBError as e:
        logger.error(f"Failed to create quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to create quiz") from e


@router.get("/{quiz_id}", response_model=QuizResponse)
def get_quiz(quiz_id: int, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    """Get a quiz by ID."""
    quiz = db.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


@router.patch("/{quiz_id}", response_model=QuizResponse)
def update_quiz(
    quiz_id: int,
    updates: QuizUpdate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """Update a quiz."""
    try:
        ok = db.update_quiz(quiz_id, updates.model_dump(exclude_unset=True))
        if not ok:
            raise HTTPException(status_code=404, detail="Quiz not found")
        quiz = db.get_quiz(quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        return quiz
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"Failed to update quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to update quiz") from e


@router.delete("/{quiz_id}")
def delete_quiz(
    quiz_id: int,
    expected_version: Optional[int] = None,
    hard: bool = False,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """Delete a quiz."""
    try:
        ok = db.delete_quiz(quiz_id, expected_version=expected_version, hard_delete=hard)
        if not ok:
            raise HTTPException(status_code=404, detail="Quiz not found")
        return {"status": "deleted"}
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"Failed to delete quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete quiz") from e


@router.get(
    "/{quiz_id}/questions",
    response_model=QuestionListResponse,
    response_model_exclude_none=True,
)
def list_questions(
    quiz_id: int,
    q: Optional[str] = None,
    include_answers: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """List all questions for a quiz (use include_answers=true for Manage/Edit flows)."""
    try:
        return db.list_questions(quiz_id, q=q, include_answers=include_answers, limit=limit, offset=offset)
    except CharactersRAGDBError as e:
        logger.error(f"Failed to list questions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list questions") from e


@router.post("/{quiz_id}/questions", response_model=QuestionAdminResponse)
def create_question(
    quiz_id: int,
    question: QuestionCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """Add a question to a quiz."""
    try:
        question_id = db.create_question(quiz_id=quiz_id, **question.model_dump())
        item = db.get_question(question_id)
        if not item:
            raise HTTPException(status_code=500, detail="Failed to load created question")
        return item
    except ConflictError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"Failed to create question: {e}")
        raise HTTPException(status_code=500, detail="Failed to create question") from e


@router.patch("/{quiz_id}/questions/{question_id}", response_model=QuestionAdminResponse)
def update_question(
    quiz_id: int,
    question_id: int,
    updates: QuestionUpdate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """Update a question."""
    try:
        ok = db.update_question(question_id, updates.model_dump(exclude_unset=True))
        if not ok:
            raise HTTPException(status_code=404, detail="Question not found")
        item = db.get_question(question_id)
        if not item:
            raise HTTPException(status_code=404, detail="Question not found")
        return item
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"Failed to update question: {e}")
        raise HTTPException(status_code=500, detail="Failed to update question") from e


@router.delete("/{quiz_id}/questions/{question_id}")
def delete_question(
    quiz_id: int,
    question_id: int,
    expected_version: Optional[int] = None,
    hard: bool = False,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """Delete a question."""
    try:
        ok = db.delete_question(question_id, expected_version=expected_version, hard_delete=hard)
        if not ok:
            raise HTTPException(status_code=404, detail="Question not found")
        return {"status": "deleted"}
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"Failed to delete question: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete question") from e


@router.post("/{quiz_id}/attempts", response_model=AttemptResponse, response_model_exclude_none=True)
def start_attempt(
    quiz_id: int,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """Start a new quiz attempt."""
    try:
        return db.start_attempt(quiz_id)
    except ConflictError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"Failed to start attempt: {e}")
        raise HTTPException(status_code=500, detail="Failed to start attempt") from e


@router.put("/attempts/{attempt_id}", response_model=AttemptResponse, response_model_exclude_none=True)
def submit_attempt(
    attempt_id: int,
    submission: AttemptSubmitRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """Submit answers for an attempt."""
    try:
        return db.submit_attempt(attempt_id, [a.model_dump() for a in submission.answers])
    except ConflictError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"Failed to submit attempt: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit attempt") from e


@router.get("/attempts", response_model=AttemptListResponse, response_model_exclude_none=True)
def list_attempts(
    quiz_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """List quiz attempts."""
    try:
        return db.list_attempts(quiz_id=quiz_id, limit=limit, offset=offset)
    except CharactersRAGDBError as e:
        logger.error(f"Failed to list attempts: {e}")
        raise HTTPException(status_code=500, detail="Failed to list attempts") from e


@router.get("/attempts/{attempt_id}", response_model=AttemptResponse, response_model_exclude_none=True)
def get_attempt(
    attempt_id: int,
    include_questions: bool = False,
    include_answers: bool = False,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """Get attempt details."""
    attempt = db.get_attempt(attempt_id, include_questions=include_questions, include_answers=include_answers)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


@router.post("/generate", response_model=QuizGenerateResponse)
async def generate_quiz(
    request: QuizGenerateRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    media_db: MediaDatabase = Depends(get_media_db_for_user),
):
    """Generate a quiz from media content using AI."""
    try:
        return await generate_quiz_from_media(
            db=db,
            media_db=media_db,
            media_id=request.media_id,
            num_questions=request.num_questions,
            question_types=request.question_types,
            difficulty=request.difficulty,
            focus_topics=request.focus_topics,
            model=request.model,
            workspace_tag=request.workspace_tag,
        )
    except ConflictError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"Failed to generate quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate quiz") from e
