"""Agent Orchestration API endpoints.

Provides project/task management, run dispatch, and reviewer gate.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Agent_Orchestration.models import TaskStatus
from tldw_Server_API.app.core.Agent_Orchestration.orchestration_service import (
    get_orchestration_db,
)

router = APIRouter(prefix="/agent-orchestration", tags=["agent-orchestration"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., description="Project name")
    description: str = Field(default="", description="Project description")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str = ""
    user_id: int = 0
    created_at: str = ""
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    task_summary: dict[str, Any] | None = None


class TaskCreateRequest(BaseModel):
    title: str = Field(..., description="Task title")
    description: str = Field(default="", description="Task description")
    agent_type: str | None = Field(default=None, description="Agent type to use for this task")
    dependency_id: int | None = Field(default=None, description="Task ID this depends on")
    reviewer_agent_type: str | None = Field(default=None, description="Agent type for review gate")
    max_review_attempts: int = Field(default=3, ge=1, le=10, description="Max review attempts before triage")
    success_criteria: str = Field(default="", description="Success criteria for the task")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: int
    project_id: int
    title: str
    description: str = ""
    status: str = "todo"
    agent_type: str | None = None
    dependency_id: int | None = None
    reviewer_agent_type: str | None = None
    max_review_attempts: int = 3
    review_count: int = 0
    success_criteria: str = ""
    user_id: int = 0
    created_at: str = ""
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    runs: list[dict[str, Any]] | None = None


class RunDispatchRequest(BaseModel):
    agent_type: str | None = Field(default=None, description="Override agent type for this run")
    cwd: str = Field(default=".", description="Working directory for the ACP session")


class ReviewRequest(BaseModel):
    approved: bool = Field(..., description="Whether the review is approved")
    feedback: str = Field(default="", description="Review feedback")


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_token_scope("any", require_if_present=True, endpoint_id="agent_orchestration.projects.manage"))],
)
async def create_project(
    payload: ProjectCreateRequest,
    user: User = Depends(get_request_user),
) -> ProjectResponse:
    """Create a new agent project."""
    db = get_orchestration_db(int(user.id))
    project = db.create_project(
        name=payload.name,
        description=payload.description,
        metadata=payload.metadata,
    )
    return ProjectResponse(**project.to_dict())


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    dependencies=[Depends(require_token_scope("any", require_if_present=True, endpoint_id="agent_orchestration.projects.read"))],
)
async def list_projects(
    user: User = Depends(get_request_user),
) -> list[ProjectResponse]:
    """List all projects for the current user."""
    db = get_orchestration_db(int(user.id))
    projects = db.list_projects()
    results = []
    for p in projects:
        summary = db.get_project_summary(p.id)
        d = p.to_dict()
        d["task_summary"] = summary
        results.append(ProjectResponse(**d))
    return results


@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_token_scope("any", require_if_present=True, endpoint_id="agent_orchestration.projects.read"))],
)
async def get_project(
    project_id: int,
    user: User = Depends(get_request_user),
) -> ProjectResponse:
    """Get a project by ID."""
    db = get_orchestration_db(int(user.id))
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    summary = db.get_project_summary(project_id)
    d = project.to_dict()
    d["task_summary"] = summary
    return ProjectResponse(**d)


@router.delete(
    "/projects/{project_id}",
    dependencies=[Depends(require_token_scope("any", require_if_present=True, endpoint_id="agent_orchestration.projects.manage"))],
)
async def delete_project(
    project_id: int,
    user: User = Depends(get_request_user),
) -> dict[str, Any]:
    """Delete a project and all associated tasks/runs."""
    db = get_orchestration_db(int(user.id))
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete_project(project_id)
    return {"deleted": True, "project_id": project_id}


# ---------------------------------------------------------------------------
# Task endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_token_scope("any", require_if_present=True, endpoint_id="agent_orchestration.tasks.manage"))],
)
async def create_task(
    project_id: int,
    payload: TaskCreateRequest,
    user: User = Depends(get_request_user),
) -> TaskResponse:
    """Create a new task in a project."""
    db = get_orchestration_db(int(user.id))
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        task = db.create_task(
            project_id=project_id,
            title=payload.title,
            description=payload.description,
            agent_type=payload.agent_type,
            dependency_id=payload.dependency_id,
            reviewer_agent_type=payload.reviewer_agent_type,
            max_review_attempts=payload.max_review_attempts,
            success_criteria=payload.success_criteria,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        err_msg = str(exc).lower()
        if "cycle" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaskResponse(**task.to_dict())


@router.get(
    "/projects/{project_id}/tasks",
    response_model=list[TaskResponse],
    dependencies=[Depends(require_token_scope("any", require_if_present=True, endpoint_id="agent_orchestration.tasks.read"))],
)
async def list_tasks(
    project_id: int,
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(get_request_user),
) -> list[TaskResponse]:
    """List tasks in a project with optional status filter."""
    db = get_orchestration_db(int(user.id))
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    task_status = None
    if status_filter:
        try:
            task_status = TaskStatus(status_filter)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")
    tasks = db.list_tasks(project_id, status=task_status)
    return [TaskResponse(**t.to_dict()) for t in tasks]


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_token_scope("any", require_if_present=True, endpoint_id="agent_orchestration.tasks.read"))],
)
async def get_task(
    task_id: int,
    user: User = Depends(get_request_user),
) -> TaskResponse:
    """Get task detail including run history."""
    db = get_orchestration_db(int(user.id))
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    runs = db.list_runs(task_id)
    d = task.to_dict()
    d["runs"] = [r.to_dict() for r in runs]
    return TaskResponse(**d)


# ---------------------------------------------------------------------------
# Run dispatch
# ---------------------------------------------------------------------------


@router.post(
    "/tasks/{task_id}/run",
    dependencies=[Depends(require_token_scope("any", require_if_present=True, endpoint_id="agent_orchestration.tasks.manage"))],
)
async def dispatch_run(
    task_id: int,
    payload: RunDispatchRequest,
    user: User = Depends(get_request_user),
) -> dict[str, Any]:
    """Dispatch a task run to an ACP agent.

    Creates an ACP session, sends the task description as the initial prompt,
    and tracks the run.
    """
    db = get_orchestration_db(int(user.id))
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check dependency
    dep_ready = db.check_dependency_ready(task_id)
    if not dep_ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task dependency {task.dependency_id} is not complete",
        )

    # Transition to in_progress
    try:
        db.transition_task(task_id, TaskStatus.IN_PROGRESS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Create ACP session with quota check, session-store registration, and audit
    session_id: str | None = None
    agent_type = payload.agent_type or task.agent_type
    try:
        from tldw_Server_API.app.core.Agent_Client_Protocol.runner_client import get_runner_client
        from tldw_Server_API.app.services.admin_acp_sessions_service import get_acp_session_store

        # Quota check
        store = await get_acp_session_store()
        quota_error = await store.check_session_quota(int(user.id))
        if quota_error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_error,
            )

        client = await get_runner_client()
        session_id = await client.create_session(
            payload.cwd,
            agent_type=agent_type,
            user_id=user.id,
        )

        # Register in session store
        try:
            await store.register_session(
                session_id=session_id,
                user_id=int(user.id),
                agent_type=agent_type or "custom",
                name=f"orchestration-task-{task_id}",
                cwd=payload.cwd,
            )
        except Exception as reg_exc:
            logger.warning("Failed to register orchestration ACP session {}: {}", session_id, reg_exc)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create ACP session for task {}: {}", task_id, exc)
        # Create a failed run record
        run = db.create_run(task_id, agent_type=agent_type)
        db.fail_run(run.id, error=str(exc))
        db.transition_task(task_id, TaskStatus.TRIAGE)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create ACP session: {exc}",
        ) from exc

    # Create run record
    run = db.create_run(
        task_id,
        agent_type=payload.agent_type or task.agent_type,
        session_id=session_id,
    )

    # Send initial prompt with task description
    prompt_text = f"Task: {task.title}\n\n{task.description}"
    if task.success_criteria:
        prompt_text += f"\n\nSuccess Criteria: {task.success_criteria}"

    try:
        result = await client.prompt(
            session_id,
            [{"role": "user", "content": prompt_text}],
        )
        stop_reason = result.get("stopReason", "")
        db.complete_run(
            run.id,
            result_summary=stop_reason,
            token_usage=result.get("usage", {}),
        )
        # Transition to review if reviewer is configured, else complete
        if task.reviewer_agent_type:
            db.transition_task(task_id, TaskStatus.REVIEW)
        else:
            db.transition_task(task_id, TaskStatus.COMPLETE)

    except Exception as exc:
        logger.error("ACP prompt failed for task {}: {}", task_id, exc)
        db.fail_run(run.id, error=str(exc))
        db.transition_task(task_id, TaskStatus.TRIAGE)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ACP prompt failed: {exc}",
        ) from exc

    # Refetch task to get post-transition status
    updated_task = db.get_task(task_id)
    return {
        "task_id": task_id,
        "run_id": run.id,
        "session_id": session_id,
        "status": updated_task.status.value if updated_task else "unknown",
    }


# ---------------------------------------------------------------------------
# Review gate
# ---------------------------------------------------------------------------


@router.post(
    "/tasks/{task_id}/review",
    response_model=TaskResponse,
    dependencies=[Depends(require_token_scope("any", require_if_present=True, endpoint_id="agent_orchestration.tasks.manage"))],
)
async def submit_review(
    task_id: int,
    payload: ReviewRequest,
    user: User = Depends(get_request_user),
) -> TaskResponse:
    """Submit a review result for a task.

    Approved → complete. Rejected → back to in_progress or triage (after max attempts).
    """
    db = get_orchestration_db(int(user.id))
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        updated = db.submit_review(task_id, payload.approved, payload.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaskResponse(**updated.to_dict())
