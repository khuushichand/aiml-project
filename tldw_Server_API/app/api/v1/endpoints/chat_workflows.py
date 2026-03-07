from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.API_Deps.chat_workflows_deps import (
    get_chat_workflows_db,
    get_chat_workflows_user,
)
from tldw_Server_API.app.api.v1.schemas.chat_workflows import (
    ChatWorkflowRunResponse,
    ChatWorkflowTemplateCreate,
    ChatWorkflowTemplateDraft,
    ChatWorkflowTemplateResponse,
    ChatWorkflowTemplateUpdate,
    ContinueChatResponse,
    GenerateDraftRequest,
    GenerateDraftResponse,
    StartRunRequest,
    SubmitAnswerRequest,
)
from tldw_Server_API.app.core.AuthNZ.permissions import (
    CHAT_WORKFLOWS_READ,
    CHAT_WORKFLOWS_RUN,
    CHAT_WORKFLOWS_WRITE,
)
from tldw_Server_API.app.core.Chat_Workflows.question_renderer import (
    ChatWorkflowQuestionRenderer,
)
from tldw_Server_API.app.core.Chat_Workflows.service import ChatWorkflowService
from tldw_Server_API.app.core.DB_Management.ChatWorkflows_DB import (
    ChatWorkflowsDatabase,
)


router = APIRouter(prefix="/api/v1/chat-workflows", tags=["chat-workflows"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_loads(value: str | None, *, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


async def _get_user_context(
    user_context: dict[str, Any] = Depends(get_chat_workflows_user),
) -> dict[str, Any]:
    return user_context


async def _get_db(
    db: ChatWorkflowsDatabase = Depends(get_chat_workflows_db),
) -> ChatWorkflowsDatabase:
    return db


async def _get_service(
    db: ChatWorkflowsDatabase = Depends(_get_db),
) -> ChatWorkflowService:
    return ChatWorkflowService(
        db=db,
        question_renderer=ChatWorkflowQuestionRenderer(),
    )


def _tenant_id_for(user_context: dict[str, Any]) -> str:
    tenant_id = user_context.get("tenant_id")
    return str(tenant_id) if tenant_id is not None else "default"


def _is_admin(user_context: dict[str, Any]) -> bool:
    return bool(user_context.get("is_admin", False))


def _require_template_access(
    template: dict[str, Any] | None,
    *,
    user_context: dict[str, Any],
) -> dict[str, Any]:
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if _is_admin(user_context):
        return template
    if str(template.get("tenant_id") or "default") != _tenant_id_for(user_context):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if str(template.get("user_id")) != str(user_context.get("user_id")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


def _require_run_access(
    run: dict[str, Any] | None,
    *,
    user_context: dict[str, Any],
) -> dict[str, Any]:
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if _is_admin(user_context):
        return run
    if str(run.get("tenant_id") or "default") != _tenant_id_for(user_context):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if str(run.get("user_id")) != str(user_context.get("user_id")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _db_call(db: ChatWorkflowsDatabase, method_name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(db, method_name, None)
    if not callable(method):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat workflows storage is unavailable",
        )
    return method(*args, **kwargs)


def _serialize_template(template: dict[str, Any]) -> dict[str, Any]:
    serialized_steps: list[dict[str, Any]] = []
    for step in sorted(template.get("steps", []), key=lambda row: int(row.get("step_index", 0))):
        serialized_steps.append(
            {
                "id": str(step.get("step_id") or step.get("id")),
                "step_index": int(step.get("step_index", 0)),
                "label": step.get("label"),
                "base_question": step.get("base_question"),
                "question_mode": step.get("question_mode", "stock"),
                "phrasing_instructions": step.get("phrasing_instructions"),
                "context_refs": _json_loads(step.get("context_refs_json"), default=[]),
            }
        )
    return {
        "id": int(template["id"]),
        "title": template["title"],
        "description": template.get("description"),
        "version": int(template.get("version", 1)),
        "status": template.get("status", "active"),
        "steps": serialized_steps,
        "created_at": template.get("created_at"),
        "updated_at": template.get("updated_at"),
    }


def _serialize_answer(answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "step_id": answer["step_id"],
        "step_index": int(answer["step_index"]),
        "displayed_question": answer["displayed_question"],
        "answer_text": answer["answer_text"],
        "question_generation_meta": _json_loads(
            answer.get("question_generation_meta_json"),
            default={},
        ),
        "answered_at": answer.get("answered_at"),
    }


async def _build_run_response(
    *,
    db: ChatWorkflowsDatabase,
    service: ChatWorkflowService,
    run: dict[str, Any],
) -> dict[str, Any]:
    answers = [_serialize_answer(answer) for answer in db.list_answers(run["run_id"])]
    current_question: str | None = None
    if run.get("status") == "active":
        current_step = await service.get_current_step(run["run_id"])
        if current_step is not None:
            current_question = current_step.get("displayed_question")

    return {
        "run_id": run["run_id"],
        "template_id": run.get("template_id"),
        "template_version": int(run.get("template_version", 1)),
        "status": run["status"],
        "current_step_index": int(run.get("current_step_index", 0)),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "canceled_at": run.get("canceled_at"),
        "free_chat_conversation_id": run.get("free_chat_conversation_id"),
        "selected_context_refs": _json_loads(run.get("selected_context_refs_json"), default=[]),
        "current_question": current_question,
        "answers": answers,
    }


@router.post(
    "/templates",
    response_model=ChatWorkflowTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_WRITE))],
)
async def create_template(
    payload: ChatWorkflowTemplateCreate,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
) -> dict[str, Any]:
    template_id = _db_call(
        db,
        "create_template",
        tenant_id=_tenant_id_for(user_context),
        user_id=str(user_context["user_id"]),
        title=payload.title,
        description=payload.description,
        version=payload.version,
    )
    _db_call(
        db,
        "replace_template_steps",
        template_id,
        [step.model_dump() for step in payload.steps],
    )
    return _serialize_template(_db_call(db, "get_template", template_id) or {})


@router.get(
    "/templates",
    response_model=list[ChatWorkflowTemplateResponse],
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_READ))],
)
async def list_templates(
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
) -> list[dict[str, Any]]:
    templates = _db_call(
        db,
        "list_templates",
        tenant_id=_tenant_id_for(user_context),
        user_id=str(user_context["user_id"]),
    )
    return [
        _serialize_template(
            _require_template_access(
                _db_call(db, "get_template", int(template["id"])),
                user_context=user_context,
            )
        )
        for template in templates
    ]


@router.get(
    "/templates/{template_id}",
    response_model=ChatWorkflowTemplateResponse,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_READ))],
)
async def get_template(
    template_id: int,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
) -> dict[str, Any]:
    template = _require_template_access(_db_call(db, "get_template", template_id), user_context=user_context)
    return _serialize_template(template)


@router.put(
    "/templates/{template_id}",
    response_model=ChatWorkflowTemplateResponse,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_WRITE))],
)
async def update_template(
    template_id: int,
    payload: ChatWorkflowTemplateUpdate,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
) -> dict[str, Any]:
    existing = _require_template_access(_db_call(db, "get_template", template_id), user_context=user_context)
    content_changed = any(
        value is not None
        for value in (payload.title, payload.description, payload.steps)
    )
    version = int(existing.get("version", 1)) + 1 if content_changed else None
    _db_call(
        db,
        "update_template",
        template_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        version=version,
    )
    if payload.steps is not None:
        _db_call(
            db,
            "replace_template_steps",
            template_id,
            [step.model_dump() for step in payload.steps],
        )
    updated = _require_template_access(_db_call(db, "get_template", template_id), user_context=user_context)
    return _serialize_template(updated)


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_WRITE))],
)
async def delete_template(
    template_id: int,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
) -> Response:
    _require_template_access(_db_call(db, "get_template", template_id), user_context=user_context)
    _db_call(db, "delete_template", template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/generate-draft",
    response_model=GenerateDraftResponse,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_WRITE))],
)
async def generate_draft(
    payload: GenerateDraftRequest,
    service: ChatWorkflowService = Depends(_get_service),
) -> dict[str, Any]:
    try:
        draft = service.generate_draft(
            goal=payload.goal,
            base_question=payload.base_question,
            desired_step_count=payload.desired_step_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"template_draft": ChatWorkflowTemplateDraft.model_validate(draft)}


@router.post(
    "/runs",
    response_model=ChatWorkflowRunResponse,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_RUN))],
)
async def start_run(
    payload: StartRunRequest,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
    service: ChatWorkflowService = Depends(_get_service),
) -> dict[str, Any]:
    template: dict[str, Any]
    source_mode: str
    if payload.template_id is not None:
        template = _require_template_access(
            _db_call(db, "get_template", payload.template_id),
            user_context=user_context,
        )
        source_mode = "template"
    else:
        template = payload.template_draft.model_dump() if payload.template_draft is not None else {}
        source_mode = "generated_snapshot"

    try:
        created_run = service.start_run(
            tenant_id=_tenant_id_for(user_context),
            user_id=str(user_context["user_id"]),
            template=template,
            source_mode=source_mode,
            selected_context_refs=payload.selected_context_refs,
            question_renderer_model=payload.question_renderer_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    run = _require_run_access(_db_call(db, "get_run", created_run["run_id"]), user_context=user_context)
    return await _build_run_response(db=db, service=service, run=run)


@router.get(
    "/runs/{run_id}",
    response_model=ChatWorkflowRunResponse,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_READ))],
)
async def get_run(
    run_id: str,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
    service: ChatWorkflowService = Depends(_get_service),
) -> dict[str, Any]:
    run = _require_run_access(_db_call(db, "get_run", run_id), user_context=user_context)
    return await _build_run_response(db=db, service=service, run=run)


@router.get(
    "/runs/{run_id}/transcript",
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_READ))],
)
async def get_run_transcript(
    run_id: str,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
    service: ChatWorkflowService = Depends(_get_service),
) -> dict[str, Any]:
    run = _require_run_access(_db_call(db, "get_run", run_id), user_context=user_context)
    messages: list[dict[str, Any]] = []
    for answer in db.list_answers(run_id):
        messages.append(
            {
                "role": "assistant",
                "content": answer["displayed_question"],
                "step_index": int(answer["step_index"]),
            }
        )
        messages.append(
            {
                "role": "user",
                "content": answer["answer_text"],
                "step_index": int(answer["step_index"]),
            }
        )

    if run.get("status") == "active":
        current_step = await service.get_current_step(run_id)
        if current_step is not None:
            messages.append(
                {
                    "role": "assistant",
                    "content": current_step["displayed_question"],
                    "step_index": int(current_step["step_index"]),
                }
            )

    return {"run_id": run_id, "messages": messages}


@router.post(
    "/runs/{run_id}/answer",
    response_model=ChatWorkflowRunResponse,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_RUN))],
)
async def answer_run_step(
    run_id: str,
    payload: SubmitAnswerRequest,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
    service: ChatWorkflowService = Depends(_get_service),
) -> dict[str, Any]:
    run = _require_run_access(_db_call(db, "get_run", run_id), user_context=user_context)
    if run.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active runs can accept answers",
        )

    try:
        await service.record_answer(
            run_id=run_id,
            step_index=payload.step_index,
            answer_text=payload.answer_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    updated_run = _require_run_access(_db_call(db, "get_run", run_id), user_context=user_context)
    return await _build_run_response(db=db, service=service, run=updated_run)


@router.post(
    "/runs/{run_id}/cancel",
    response_model=ChatWorkflowRunResponse,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_RUN))],
)
async def cancel_run(
    run_id: str,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
    service: ChatWorkflowService = Depends(_get_service),
) -> dict[str, Any]:
    run = _require_run_access(_db_call(db, "get_run", run_id), user_context=user_context)
    if run.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed runs cannot be canceled",
        )
    if run.get("status") != "canceled":
        _db_call(
            db,
            "update_run",
            run_id,
            status="canceled",
            canceled_at=_utcnow_iso(),
        )
        _db_call(db, "append_event", run_id, "run_canceled", {"status": "canceled"})

    updated_run = _require_run_access(_db_call(db, "get_run", run_id), user_context=user_context)
    return await _build_run_response(db=db, service=service, run=updated_run)


@router.post(
    "/runs/{run_id}/continue-chat",
    response_model=ContinueChatResponse,
    dependencies=[Depends(auth_deps.require_permissions(CHAT_WORKFLOWS_RUN))],
)
async def continue_chat(
    run_id: str,
    user_context: dict[str, Any] = Depends(_get_user_context),
    db: ChatWorkflowsDatabase = Depends(_get_db),
) -> dict[str, Any]:
    run = _require_run_access(_db_call(db, "get_run", run_id), user_context=user_context)
    if run.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow must be completed before continuing to free chat",
        )

    conversation_id = run.get("free_chat_conversation_id")
    if not conversation_id:
        conversation_id = str(uuid4())
        _db_call(db, "update_run", run_id, free_chat_conversation_id=conversation_id)
        _db_call(
            db,
            "append_event",
            run_id,
            "continued_to_free_chat",
            {"conversation_id": conversation_id},
        )

    return {"conversation_id": conversation_id}
