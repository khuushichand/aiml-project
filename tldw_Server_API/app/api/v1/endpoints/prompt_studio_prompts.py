"""
Prompt Studio Prompts API (with versioning)

Manages prompts and their version history inside a project. Each update
creates a new immutable version to enable evaluation, comparison, and
reproducibility.

Key responsibilities
- Create/list/get prompts in a project
- Update prompts (create new version)
- View prompt version history
- Revert to a previous version (creates new version)

Security
- Read operations require project access
- Write operations require project write access
- Prompt length and content validated against SecurityConfig
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Header
from loguru import logger

# Local imports
from tldw_Server_API.app.api.v1.schemas.prompt_studio_base import (
    StandardResponse, ListResponse
)
from tldw_Server_API.app.api.v1.schemas.prompt_studio_project import (
    PromptCreate, PromptUpdate, PromptResponse, PromptVersion,
    SignatureCreate, SignatureUpdate, SignatureResponse,
    PromptGenerateRequest, PromptImproveRequest, ExampleGenerateRequest
)
from tldw_Server_API.app.api.v1.API_Deps.prompt_studio_deps import (
    get_prompt_studio_db, get_prompt_studio_user, require_project_access,
    require_project_write_access, check_rate_limit, get_security_config,
    PromptStudioDatabase, SecurityConfig
)
from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import (
    DatabaseError, InputError, ConflictError
)
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat

########################################################################################################################
# Router Setup

router = APIRouter(
    prefix="/api/v1/prompt-studio/prompts",
    tags=["prompt-studio"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not found"},
        429: {"description": "Rate limit exceeded"}
    }
)

########################################################################################################################
# Prompt CRUD Endpoints

# Compatibility: simple POST on base path returns prompt object directly
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_prompt_simple(
    prompt_data: PromptCreate,
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    security_config: SecurityConfig = Depends(get_security_config),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> Dict[str, Any]:
    resp = await create_prompt(prompt_data, db, security_config, user_context)  # type: ignore[arg-type]
    # Unwrap StandardResponse regardless of Pydantic/dict
    if hasattr(resp, "model_dump"):
        obj = resp.model_dump()
    else:
        obj = resp if isinstance(resp, dict) else {}
    data = obj.get("data", obj)
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return data

@router.post(
    "/create",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "basic": {
                            "summary": "Create a prompt",
                            "value": {
                                "project_id": 1,
                                "name": "Summarizer",
                                "system_prompt": "Summarize the content clearly.",
                                "user_prompt": "{{text}}"
                            }
                        }
                    }
                }
            }
        },
        "responses": {
            "201": {
                "description": "Prompt created",
                "content": {
                    "application/json": {
                        "examples": {
                            "created": {
                                "summary": "Prompt created response",
                                "value": {
                                    "success": True,
                                    "data": {
                                        "id": 12,
                                        "project_id": 1,
                                        "name": "Summarizer",
                                        "version_number": 1,
                                        "system_prompt": "Summarize the content clearly.",
                                        "user_prompt": "{{text}}",
                                        "created_at": "2024-09-20T10:00:00"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
)
async def create_prompt(
    prompt_data: PromptCreate,
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    security_config: SecurityConfig = Depends(get_security_config),
    user_context: Dict = Depends(get_prompt_studio_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")
) -> StandardResponse:
    """
    Create a new prompt in a project.

    Args:
        prompt_data: Prompt creation data
        db: Database instance
        security_config: Security configuration
        user_context: Current user context

    Returns:
        Created prompt details
    """
    try:
        # Validate prompt length
        if prompt_data.system_prompt and len(prompt_data.system_prompt) > security_config.max_prompt_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"System prompt exceeds maximum length of {security_config.max_prompt_length}"
            )

        if prompt_data.user_prompt and len(prompt_data.user_prompt) > security_config.max_prompt_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User prompt exceeds maximum length of {security_config.max_prompt_length}"
            )

        # Ensure write access to the project
        await require_project_write_access(prompt_data.project_id, user_context=user_context, db=db)

        few_shot_payload = None
        if prompt_data.few_shot_examples:
            few_shot_payload = [model_dump_compat(ex) for ex in prompt_data.few_shot_examples]

        modules_payload = None
        if prompt_data.modules_config:
            modules_payload = [model_dump_compat(mod) for mod in prompt_data.modules_config]

        # Idempotency: if provided, return existing prompt for this key
        user_id_str = str(user_context.get("user_id", "anonymous"))
        if idempotency_key:
            try:
                existing_id = db.lookup_idempotency("prompt", idempotency_key, user_id_str)
                if existing_id:
                    existing = db.get_prompt(existing_id)
                    if existing:
                        return StandardResponse(success=True, data=PromptResponse(**existing))
            except Exception:
                pass

        prompt_record = db.create_prompt(
            project_id=prompt_data.project_id,
            name=prompt_data.name,
            signature_id=prompt_data.signature_id,
            version_number=1,
            system_prompt=prompt_data.system_prompt,
            user_prompt=prompt_data.user_prompt,
            few_shot_examples=few_shot_payload,
            modules_config=modules_payload,
            parent_version_id=prompt_data.parent_version_id,
            change_description=prompt_data.change_description,
            client_id=user_context.get("client_id"),
        )

        if not prompt_record:
            raise DatabaseError("Prompt creation returned empty record")

        logger.info(f"User {user_context['user_id']} created prompt: {prompt_data.name} (project_id={prompt_data.project_id})")
        try:
            logger.info("Created prompt record: %s", prompt_record)
        except Exception:
            pass

        # Record idempotency mapping if provided
        if idempotency_key and prompt_record.get("id"):
            try:
                db.record_idempotency("prompt", idempotency_key, int(prompt_record["id"]), user_id_str)
            except Exception:
                pass

        return StandardResponse(
            success=True,
            data=PromptResponse(**prompt_record)
        )

    except ConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prompt with this name already exists in the project"
        )
    except DatabaseError as e:
        logger.error(f"Database error creating prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create prompt"
        )

@router.get(
    "/list/{project_id}",
    response_model=ListResponse,
    openapi_extra={
        "responses": {
            "200": {
                "description": "Prompts",
                "content": {
                    "application/json": {
                        "examples": {
                            "list": {
                                "summary": "Prompt list",
                                "value": {
                                    "success": True,
                                    "data": [
                                        {"id": 12, "name": "Summarizer", "version_number": 2}
                                    ],
                                    "metadata": {
                                        "page": 1,
                                        "per_page": 20,
                                        "total": 1,
                                        "total_pages": 1
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
)
async def list_prompts(
    project_id: int = Path(..., description="Project ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    include_deleted: bool = Query(False, description="Include deleted prompts"),
    _: bool = Depends(require_project_access),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db)
) -> ListResponse:
    """
    List prompts in a project.

    Args:
        project_id: Project ID
        page: Page number
        per_page: Items per page
        include_deleted: Include soft-deleted prompts
        db: Database instance

    Returns:
        Paginated list of prompts
    """
    try:
        result = db.list_prompts(
            project_id,
            page=page,
            per_page=per_page,
            include_deleted=include_deleted,
        )
        prompts = [PromptResponse(**prompt) for prompt in result.get("prompts", [])]

        return ListResponse(
            success=True,
            data=prompts,
            metadata=result.get("pagination", {}),
        )

    except DatabaseError as e:
        logger.error(f"Database error listing prompts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list prompts"
        )
    except InputError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Simple alias that mirrors the canonical list response shape
@router.get("", response_model=ListResponse)
async def list_prompts_simple(
    project_id: int = Query(..., description="Project ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    include_deleted: bool = Query(False, description="Include deleted prompts"),
    _: bool = Depends(require_project_access),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db)
) -> ListResponse:
    return await list_prompts(project_id, page, per_page, include_deleted, True, db)  # type: ignore[arg-type]

# Simple execute endpoint used by tests
@router.post("/execute")
async def execute_prompt_simple(
    payload: Dict[str, Any],
    db: PromptStudioDatabase = Depends(get_prompt_studio_db)
) -> Dict[str, Any]:
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio.prompt_executor import PromptExecutor
    executor = PromptExecutor(db)
    prompt_id = int(payload.get("prompt_id", 0))
    inputs = payload.get("inputs") or {}
    provider = payload.get("provider", "openai")
    model = payload.get("model", "gpt-3.5-turbo")
    # Support both async executor (normal) and sync mocks in tests
    maybe = executor.execute(prompt_id, inputs=inputs, provider=provider, model=model)
    try:
        import inspect as _inspect
        if _inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe  # test mocks may return plain dict
    except Exception:
        # Fallback to awaiting; if it fails, raise for better visibility
        result = await maybe  # type: ignore[func-returns-value]
    return {
        "output": result.get("raw_output") or result.get("parsed_output") or "",
        "tokens_used": result.get("tokens_used", 0),
        "execution_time": result.get("execution_time_ms", 0) / 1000.0
    }

@router.get("/get/{prompt_id}", response_model=StandardResponse, openapi_extra={
    "responses": {"200": {"description": "Prompt", "content": {"application/json": {"examples": {"get": {"summary": "Prompt details", "value": {"success": True, "data": {"id": 12, "name": "Summarizer", "version_number": 2}}}}}}}}
})
async def get_prompt(
    prompt_id: int = Path(..., description="Prompt ID"),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Get a specific prompt by ID.

    Args:
        prompt_id: Prompt ID
        db: Database instance

    Returns:
        Prompt details
    """
    try:
        prompt = db.get_prompt_with_project(prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {prompt_id} not found"
            )
        if prompt.get("project_user_id") != user_context["user_id"] and not user_context["is_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this prompt"
            )

        # Remove the extra field
        prompt.pop("project_user_id", None)

        return StandardResponse(
            success=True,
            data=PromptResponse(**prompt)
        )

    except DatabaseError as e:
        logger.error(f"Database error getting prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get prompt"
        )
    except InputError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put(
    "/update/{prompt_id}",
    response_model=StandardResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "revise": {
                            "summary": "Revise prompt (new version)",
                            "value": {
                                "system_prompt": "Summarize concisely.",
                                "change_description": "Tighten style"
                            }
                        }
                    }
                }
            }
        },
        "responses": {
            "200": {
                "description": "New prompt version created",
                "content": {
                    "application/json": {
                        "examples": {
                            "versioned": {
                                "summary": "New version response",
                                "value": {
                                    "success": True,
                                    "data": {
                                        "id": 13,
                                        "project_id": 1,
                                        "name": "Summarizer",
                                        "version_number": 2,
                                        "system_prompt": "Summarize concisely.",
                                        "created_at": "2024-09-21T10:00:00"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
)
async def update_prompt(
    prompt_id: int = Path(..., description="Prompt ID"),
    updates: PromptUpdate = ...,
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    security_config: SecurityConfig = Depends(get_security_config),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Update a prompt (creates a new version).

    Args:
        prompt_id: Prompt ID
        updates: Fields to update
        db: Database instance
        security_config: Security configuration
        user_context: Current user context

    Returns:
        New prompt version details
    """
    try:
        # Validate prompt lengths if provided
        if updates.system_prompt and len(updates.system_prompt) > security_config.max_prompt_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"System prompt exceeds maximum length of {security_config.max_prompt_length}"
            )

        if updates.user_prompt and len(updates.user_prompt) > security_config.max_prompt_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User prompt exceeds maximum length of {security_config.max_prompt_length}"
            )

        current_prompt = db.get_prompt_with_project(prompt_id)
        if not current_prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {prompt_id} not found"
            )
        if current_prompt.get("project_user_id") != user_context["user_id"] and not user_context["is_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this prompt"
            )

        # Create new version
        few_shot_payload = None
        if updates.few_shot_examples is not None:
            few_shot_payload = [model_dump_compat(ex) for ex in updates.few_shot_examples]

        modules_payload = None
        if updates.modules_config is not None:
            modules_payload = [model_dump_compat(mod) for mod in updates.modules_config]

        new_prompt = db.create_prompt_version(
            prompt_id,
            change_description=updates.change_description,
            name=updates.name,
            system_prompt=updates.system_prompt,
            user_prompt=updates.user_prompt,
            few_shot_examples=few_shot_payload,
            modules_config=modules_payload,
            client_id=user_context.get("client_id"),
        )

        logger.info(
            "User %s created version %s of prompt %s",
            user_context["user_id"],
            new_prompt.get("version_number"),
            prompt_id,
        )

        return StandardResponse(
            success=True,
            data=PromptResponse(**new_prompt)
        )

    except DatabaseError as e:
        logger.error(f"Database error updating prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update prompt"
        )
    except InputError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/history/{prompt_id}", response_model=StandardResponse, openapi_extra={
    "responses": {"200": {"description": "History", "content": {"application/json": {"examples": {"history": {"summary": "Versions", "value": {"success": True, "data": [{"id": 12, "version_number": 1}, {"id": 13, "version_number": 2}]}}}}}}}
})
async def get_prompt_history(
    prompt_id: int = Path(..., description="Prompt ID"),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Get version history for a prompt.

    Args:
        prompt_id: Prompt ID
        db: Database instance

    Returns:
        List of prompt versions
    """
    try:
        prompt = db.get_prompt(prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {prompt_id} not found"
            )
        project_id = prompt["project_id"]
        await require_project_access(project_id, user_context=user_context, db=db)

        versions = [
            PromptVersion(**version)
            for version in db.list_prompt_versions(project_id, prompt["name"])
        ]

        return StandardResponse(
            success=True,
            data=versions
        )

    except DatabaseError as e:
        logger.error(f"Database error getting prompt history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get prompt history"
        )
    except InputError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/revert/{prompt_id}/{version}", response_model=StandardResponse, openapi_extra={
    "responses": {"200": {"description": "Reverted", "content": {"application/json": {"examples": {"reverted": {"summary": "New version", "value": {"success": True, "data": {"id": 14, "version_number": 3}}}}}}}}
})
async def revert_prompt(
    prompt_id: int = Path(..., description="Current prompt ID"),
    version: int = Path(..., description="Version number to revert to"),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Revert a prompt to a previous version (creates a new version).

    Args:
        prompt_id: Current prompt ID
        version: Version number to revert to
        db: Database instance
        user_context: Current user context

    Returns:
        New prompt version details
    """
    try:
        current_prompt = db.get_prompt(prompt_id)
        if not current_prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {prompt_id} not found"
            )
        project_id = current_prompt["project_id"]
        await require_project_write_access(project_id, user_context=user_context, db=db)

        new_prompt = db.revert_prompt_to_version(
            prompt_id,
            version,
            client_id=user_context.get("client_id"),
        )

        logger.info(
            "User %s reverted prompt %s to version %s",
            user_context["user_id"],
            prompt_id,
            version,
        )

        return StandardResponse(
            success=True,
            data=PromptResponse(**new_prompt)
        )

    except DatabaseError as e:
        logger.error(f"Database error reverting prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revert prompt"
        )
    except InputError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
