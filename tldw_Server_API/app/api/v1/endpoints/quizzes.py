from typing import Any, Optional

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
    QuizImportError,
    QuizImportItemResult,
    QuizImportRequest,
    QuizImportResponse,
    QuizListResponse,
    QuizResponse,
    QuizUpdate,
)
from tldw_Server_API.app.api.v1.schemas.flashcards import (
    StudyAssistantContextResponse,
    StudyAssistantRespondRequest,
    StudyAssistantRespondResponse,
)
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
)
from tldw_Server_API.app.core.Flashcards.study_assistant import (
    build_quiz_attempt_question_context,
    generate_study_assistant_reply,
)
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.quiz_generator import (
    QuizProvenanceValidationError,
    generate_quiz_from_sources,
)

router = APIRouter(prefix="/quizzes", tags=["quizzes"])
QUIZ_EXPORT_FORMAT = "tldw.quiz.export.v1"


def _build_assistant_context_snapshot(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "context_type": context.get("context_type"),
        "attempt": context.get("attempt"),
        "question": context.get("question"),
    }


def _default_study_assistant_message(action: str, context: dict[str, Any]) -> str:
    question_text = str((context.get("question") or {}).get("question_text") or "this question").strip()
    return {
        "explain": f"Explain why I missed this question: {question_text}",
        "mnemonic": f"Give me a mnemonic for this question: {question_text}",
        "follow_up": f"I have a follow-up about this question: {question_text}",
        "fact_check": f"Fact-check my explanation of this question: {question_text}",
        "freeform": f"Help me review this question: {question_text}",
    }.get(action, f"Help me review this question: {question_text}")


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


@router.post("/import/json", response_model=QuizImportResponse)
def import_quizzes_json(
    payload: QuizImportRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """Import quizzes from the JSON export format."""
    if payload.export_format and payload.export_format != QUIZ_EXPORT_FORMAT:
        raise HTTPException(status_code=400, detail="Unsupported quiz export format")

    imported_quizzes = 0
    failed_quizzes = 0
    imported_questions = 0
    failed_questions = 0
    items: list[QuizImportItemResult] = []
    errors: list[QuizImportError] = []

    for source_index, entry in enumerate(payload.quizzes):
        quiz_name = entry.quiz.name
        try:
            quiz_id = db.create_quiz(**entry.quiz.model_dump())
            imported_quizzes += 1
        except CharactersRAGDBError as exc:
            failed_quizzes += 1
            errors.append(
                QuizImportError(
                    source_index=source_index,
                    quiz_name=quiz_name,
                    error=f"Failed to create quiz: {exc}",
                )
            )
            continue

        entry_imported_questions = 0
        entry_failed_questions = 0
        sorted_questions = sorted(entry.questions, key=lambda question: question.order_index)

        for question_index, question in enumerate(sorted_questions):
            try:
                db.create_question(
                    quiz_id=quiz_id,
                    **question.model_dump(),
                )
                imported_questions += 1
                entry_imported_questions += 1
            except CharactersRAGDBError as exc:
                failed_questions += 1
                entry_failed_questions += 1
                errors.append(
                    QuizImportError(
                        source_index=source_index,
                        quiz_name=quiz_name,
                        question_index=question_index,
                        error=f"Failed to create question: {exc}",
                    )
                )

        items.append(
            QuizImportItemResult(
                source_index=source_index,
                quiz_id=quiz_id,
                imported_questions=entry_imported_questions,
                failed_questions=entry_failed_questions,
            )
        )

    return QuizImportResponse(
        imported_quizzes=imported_quizzes,
        failed_quizzes=failed_quizzes,
        imported_questions=imported_questions,
        failed_questions=failed_questions,
        items=items,
        errors=errors,
    )


@router.get("/{quiz_id:int}", response_model=QuizResponse)
def get_quiz(quiz_id: int, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    """Get a quiz by ID."""
    quiz = db.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


@router.patch("/{quiz_id:int}", response_model=QuizResponse)
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


@router.delete("/{quiz_id:int}")
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
    "/{quiz_id:int}/questions",
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


@router.post("/{quiz_id:int}/questions", response_model=QuestionAdminResponse)
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


@router.patch("/{quiz_id:int}/questions/{question_id:int}", response_model=QuestionAdminResponse)
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


@router.delete("/{quiz_id:int}/questions/{question_id:int}")
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


@router.post("/{quiz_id:int}/attempts", response_model=AttemptResponse, response_model_exclude_none=True)
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


@router.put("/attempts/{attempt_id:int}", response_model=AttemptResponse, response_model_exclude_none=True)
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


@router.get("/attempts/{attempt_id:int}", response_model=AttemptResponse, response_model_exclude_none=True)
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


@router.get(
    "/attempts/{attempt_id:int}/questions/{question_id:int}/assistant",
    response_model=StudyAssistantContextResponse,
)
def get_quiz_attempt_question_assistant(
    attempt_id: int,
    question_id: int,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    try:
        context = build_quiz_attempt_question_context(db, attempt_id, question_id)
        return {
            "thread": context["thread"],
            "messages": context["history"],
            "context_snapshot": _build_assistant_context_snapshot(context),
            "available_actions": context["available_actions"],
        }
    except ConflictError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharactersRAGDBError as exc:
        logger.error(f"Failed to fetch quiz question assistant context: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch study assistant context") from exc


@router.post(
    "/attempts/{attempt_id:int}/questions/{question_id:int}/assistant/respond",
    response_model=StudyAssistantRespondResponse,
)
async def respond_quiz_attempt_question_assistant(
    attempt_id: int,
    question_id: int,
    payload: StudyAssistantRespondRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    try:
        context = build_quiz_attempt_question_context(db, attempt_id, question_id)
        thread = context["thread"]
        if payload.expected_thread_version is not None and int(thread["version"]) != int(payload.expected_thread_version):
            raise HTTPException(status_code=409, detail="Study assistant thread version mismatch")

        user_content = str(payload.message or "").strip() or _default_study_assistant_message(payload.action, context)
        reply = await generate_study_assistant_reply(
            action=payload.action,
            context=context,
            message=user_content,
            provider=payload.provider,
            model=payload.model,
        )
        context_snapshot = _build_assistant_context_snapshot(context)
        user_message = db.append_study_assistant_message(
            thread_id=int(thread["id"]),
            role="user",
            action_type=payload.action,
            input_modality=payload.input_modality,
            content=user_content,
            structured_payload={"action": payload.action},
            context_snapshot=context_snapshot,
            provider=payload.provider,
            model=payload.model,
        )
        assistant_message = db.append_study_assistant_message(
            thread_id=int(thread["id"]),
            role="assistant",
            action_type=payload.action,
            input_modality="text",
            content=str(reply.get("assistant_text") or "").strip(),
            structured_payload=reply.get("structured_payload") or {},
            context_snapshot=context_snapshot,
            provider=str(reply.get("provider") or payload.provider or "default"),
            model=reply.get("model") or payload.model,
        )
        updated_thread = db.get_study_assistant_thread(int(thread["id"]))
        if not updated_thread:
            raise HTTPException(status_code=404, detail="Study assistant thread not found after update")
        return {
            "thread": updated_thread,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "structured_payload": reply.get("structured_payload") or {},
            "context_snapshot": context_snapshot,
        }
    except HTTPException:
        raise
    except ConflictError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharactersRAGDBError as exc:
        logger.error(f"Failed to respond with quiz question assistant: {exc}")
        raise HTTPException(status_code=500, detail="Failed to generate study assistant response") from exc
    except (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.error(f"Unexpected quiz question assistant failure: {exc}")
        raise HTTPException(status_code=500, detail="Failed to generate study assistant response") from exc


@router.post("/generate", response_model=QuizGenerateResponse)
async def generate_quiz(
    request: QuizGenerateRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    media_db: MediaDatabase = Depends(get_media_db_for_user),
):
    """Generate a quiz from mixed sources using AI."""
    try:
        if request.sources:
            sources = [source.model_dump(mode="json") for source in request.sources]
        elif request.media_id is not None:
            sources = [{"source_type": "media", "source_id": str(request.media_id)}]
        else:
            raise ValueError("Either media_id or sources must be provided")

        return await generate_quiz_from_sources(
            db=db,
            media_db=media_db,
            sources=sources,
            num_questions=request.num_questions,
            question_types=request.question_types,
            difficulty=request.difficulty,
            focus_topics=request.focus_topics,
            model=request.model,
            workspace_tag=request.workspace_tag,
        )
    except QuizProvenanceValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except CharactersRAGDBError as e:
        logger.error(f"Failed to generate quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate quiz") from e
