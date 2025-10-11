"""
Prompt Studio Optimizations API

Creates and manages optimization jobs that iterate on prompts using
defined strategies (e.g., iterative refinement, hyperparameter tuning,
genetic algorithms). Integrates with the job queue and background
workers to run safely and asynchronously.

Key responsibilities
- Create optimization jobs against a prompt and test cases
- List/get/cancel optimizations
- Enumerate available optimization strategies
- Compare multiple strategies by spawning multiple jobs

Security
- Read operations require project access
- Write operations require project write access
- Rate limits applied to optimization creation and comparisons
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, BackgroundTasks
import json
from datetime import datetime
from loguru import logger

# Local imports
from tldw_Server_API.app.api.v1.schemas.prompt_studio_base import (
    StandardResponse,
    ListResponse,
    PaginationMetadata,
)
from tldw_Server_API.app.api.v1.schemas.prompt_studio_optimization import (
    OptimizationCreate, OptimizationResponse,
    OptimizationConfig
)
from tldw_Server_API.app.api.v1.schemas.prompt_studio_optimization_requests import (
    CompareStrategiesRequest
)
from tldw_Server_API.app.api.v1.API_Deps.prompt_studio_deps import (
    get_prompt_studio_db, get_prompt_studio_user, require_project_access, require_project_write_access,
    check_rate_limit, get_security_config, PromptStudioDatabase, SecurityConfig
)
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.optimization_engine import OptimizationEngine
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_manager import JobManager, JobType
from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import DatabaseError

########################################################################################################################
# Router Setup

router = APIRouter(
    prefix="/api/v1/prompt-studio/optimizations",
    tags=["prompt-studio"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not found"},
        429: {"description": "Rate limit exceeded"}
    }
)

########################################################################################################################
# Optimization CRUD Endpoints

# Compatibility: base POST returns job info directly
@router.post("")
async def create_optimization_simple(
    payload: Dict[str, Any],
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> Dict[str, Any]:
    # Minimal creation: create a job with provided payload
    prompt_id = int(payload.get("prompt_id") or payload.get("initial_prompt_id") or 0)
    job_manager = JobManager(db)
    job = job_manager.create_job(
        job_type=JobType.OPTIMIZATION,
        entity_id=prompt_id if prompt_id else 0,
        payload={"prompt_id": prompt_id, "config": payload.get("config", {})},
        priority=5,
    )
    return {"id": job.get("id"), "status": job.get("status", "pending")}

@router.post(
    "/create",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "iterative": {
                            "summary": "Create optimization job",
                            "value": {
                                "project_id": 1,
                                "initial_prompt_id": 12,
                                "optimization_config": {
                                    "optimizer_type": "iterative",
                                    "max_iterations": 20,
                                    "target_metric": "accuracy",
                                    "early_stopping": True
                                },
                                "test_case_ids": [1, 2, 3],
                                "name": "Refine Summarizer"
                            }
                        }
                    }
                }
            }
        },
        "responses": {
            "201": {
                "description": "Optimization created",
                "content": {
                    "application/json": {
                        "examples": {
                            "created": {
                                "summary": "Created optimization",
                                "value": {"success": True, "data": {"id": 701, "status": "pending", "job_id": 9001}}
                            }
                        }
                    }
                }
            }
        }
    }
)
async def create_optimization(
    optimization_data: OptimizationCreate,
    background_tasks: BackgroundTasks,
    _: bool = Depends(lambda: check_rate_limit("optimization")),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    security_config: SecurityConfig = Depends(get_security_config),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Create and start a new optimization.
    
    Args:
        optimization_data: Optimization configuration
        background_tasks: Background task manager
        db: Database instance
        security_config: Security configuration
        user_context: Current user context
        
    Returns:
        Created optimization details
    """
    try:
        prompt_row = db.get_prompt_with_project(
            optimization_data.initial_prompt_id,
            include_deleted=False,
        )
        if not prompt_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {optimization_data.initial_prompt_id} not found",
            )

        project_id = prompt_row["project_id"]
        await require_project_write_access(project_id, user_context=user_context, db=db)

        opt_cfg = optimization_data.optimization_config
        optimizer_type = opt_cfg.optimizer_type
        max_iters = opt_cfg.max_iterations

        combined_config: Dict[str, Any] = (
            json.loads(opt_cfg.model_dump_json())
            if hasattr(opt_cfg, "model_dump_json")
            else opt_cfg.dict()
        )
        if optimization_data.bootstrap_config is not None:
            combined_config["bootstrap_config"] = (
                json.loads(optimization_data.bootstrap_config.model_dump_json())
                if hasattr(optimization_data.bootstrap_config, "model_dump_json")
                else optimization_data.bootstrap_config.dict()
            )

        bootstrap_samples = (
            getattr(optimization_data.bootstrap_config, "num_samples", None)
            if optimization_data.bootstrap_config is not None
            else None
        )

        optimization_record = db.create_optimization(
            project_id=project_id,
            name=optimization_data.name,
            initial_prompt_id=optimization_data.initial_prompt_id,
            optimizer_type=optimizer_type,
            optimization_config=combined_config,
            max_iterations=max_iters,
            bootstrap_samples=bootstrap_samples,
            status="pending",
            client_id=db.client_id,
        )

        job_manager = JobManager(db)
        job = job_manager.create_job(
            job_type=JobType.OPTIMIZATION,
            entity_id=optimization_record["id"],
            payload={
                "optimization_id": optimization_record["id"],
                "optimizer_type": optimizer_type,
                "test_case_ids": optimization_data.test_case_ids or [],
                "optimization_config": combined_config,
                "initial_prompt_id": optimization_data.initial_prompt_id,
                "project_id": project_id,
                "created_by": user_context.get("user_id"),
                "submitted_at": datetime.utcnow().isoformat(),
            },
            project_id=project_id,
            priority=5,
        )

        logger.info(
            "User %s created optimization %s",
            user_context.get("user_id"),
            optimization_record.get("id"),
        )

        background_tasks.add_task(
            run_optimization_async,
            optimization_record["id"],
            db,
        )

        response_payload = {
            "optimization": OptimizationResponse(**optimization_record),
            "job_id": job["id"],
        }

        return StandardResponse(success=True, data=response_payload)

    except DatabaseError as exc:
        logger.error(f"Database error creating optimization: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create optimization",
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - safety
        logger.error(f"Unexpected error creating optimization: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create optimization",
        )

@router.get(
    "/list/{project_id}",
    response_model=ListResponse,
    openapi_extra={
        "responses": {
            "200": {
                "description": "Optimizations",
                "content": {
                    "application/json": {
                        "examples": {
                            "list": {
                                "summary": "Optimization list",
                                "value": {
                                    "success": True,
                                    "data": [
                                        {"id": 701, "name": "Refine Summarizer", "status": "pending"}
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
async def list_optimizations(
    project_id: int = Path(..., description="Project ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    _: bool = Depends(require_project_access),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db)
) -> ListResponse:
    """
    List optimizations for a project.
    
    Args:
        project_id: Project ID
        page: Page number
        per_page: Items per page
        status: Optional status filter
        db: Database instance
        
    Returns:
        Paginated list of optimizations
    """
    try:
        result = db.list_optimizations(
            project_id=project_id,
            status=status,
            page=page,
            per_page=per_page,
        )

        optimizations = [
            OptimizationResponse(**record)
            for record in result.get("optimizations", [])
        ]
        metadata = PaginationMetadata(**result.get("pagination", {}))

        return ListResponse(success=True, data=optimizations, metadata=metadata)

    except DatabaseError as exc:
        logger.error(f"Database error listing optimizations: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list optimizations",
        )
    except Exception as exc:
        logger.error(f"Unexpected error listing optimizations: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list optimizations",
        )

@router.get("/get/{optimization_id}", response_model=StandardResponse, openapi_extra={
    "responses": {"200": {"description": "Optimization details", "content": {"application/json": {"examples": {"get": {"summary": "Optimization", "value": {"success": True, "data": {"id": 701, "optimizer_type": "iterative", "status": "running"}}}}}}}}
})
async def get_optimization(
    optimization_id: int = Path(..., description="Optimization ID"),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Get optimization details.
    
    Args:
        optimization_id: Optimization ID
        db: Database instance
        
    Returns:
        Optimization details
    """
    try:
        optimization = db.get_optimization(optimization_id)
        if not optimization or optimization.get("deleted"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Optimization {optimization_id} not found",
            )

        await require_project_access(
            optimization.get("project_id"),
            user_context=user_context,
            db=db,
        )

        return StandardResponse(
            success=True,
            data=OptimizationResponse(**optimization),
        )

    except DatabaseError as exc:
        logger.error(f"Database error fetching optimization {optimization_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get optimization",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error getting optimization {optimization_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get optimization",
        )

# Compatibility: GET job status by job_id returning direct job data
@router.get("/{job_id}")
async def get_optimization_job_status(job_id: str, db: PromptStudioDatabase = Depends(get_prompt_studio_db)) -> Dict[str, Any]:
    jm = JobManager(db)
    job = jm.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/cancel/{optimization_id}", response_model=StandardResponse, openapi_extra={
    "responses": {"200": {"description": "Cancelled", "content": {"application/json": {"examples": {"cancelled": {"value": {"success": True, "data": {"message": "Optimization cancelled"}}}}}}}, "400": {"description": "Invalid state"}, "404": {"description": "Not found"}}
})
async def cancel_optimization(
    optimization_id: int = Path(..., description="Optimization ID"),
    reason: str = Body(None, description="Cancellation reason"),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Cancel a running optimization.
    
    Args:
        optimization_id: Optimization ID
        reason: Optional cancellation reason
        db: Database instance
        user_context: Current user context
        
    Returns:
        Success response
    """
    try:
        optimization = db.get_optimization(optimization_id)
        if not optimization or optimization.get("deleted"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Optimization {optimization_id} not found",
            )

        project_id = optimization.get("project_id")
        await require_project_write_access(project_id, user_context=user_context, db=db)

        status_value = optimization.get("status")
        if status_value in {"completed", "failed", "cancelled"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel optimization with status: {status_value}",
            )

        job_manager = JobManager(db)
        latest_job = db.get_latest_job_for_entity(
            JobType.OPTIMIZATION.value,
            optimization_id,
        )
        if latest_job:
            job_manager.cancel_job(latest_job["id"], reason or "User cancelled")

        db.set_optimization_status(
            optimization_id,
            "cancelled",
            error_message=reason or "Cancelled by user",
            mark_completed=True,
        )

        logger.info(
            "User %s cancelled optimization %s",
            user_context.get("user_id"),
            optimization_id,
        )

        return StandardResponse(
            success=True,
            data={"message": "Optimization cancelled"},
        )

    except DatabaseError as exc:
        logger.error(f"Database error cancelling optimization {optimization_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel optimization",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error cancelling optimization {optimization_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel optimization",
        )

########################################################################################################################
# Optimization Strategy Endpoints

@router.get("/strategies", response_model=StandardResponse, openapi_extra={
    "responses": {"200": {"description": "Strategies", "content": {"application/json": {"examples": {"list": {"summary": "Available strategies", "value": {"success": True, "data": [{"name": "iterative", "display_name": "Iterative Refinement"}]}}}}}}}
})
async def get_optimization_strategies() -> StandardResponse:
    """
    Get available optimization strategies.
    
    Returns:
        List of available strategies with descriptions
    """
    strategies = [
        {
            "name": "mipro",
            "display_name": "MIPRO",
            "description": "Multi-Instruction Prompt Optimization - iteratively refines instructions",
            "parameters": {
                "target_metric": "Metric to optimize (accuracy, f1_score, etc.)",
                "min_improvement": "Minimum improvement to continue (0.01-0.1)"
            }
        },
        {
            "name": "bootstrap",
            "display_name": "Bootstrap Few-Shot",
            "description": "Automatically selects best examples for few-shot learning",
            "parameters": {
                "num_examples": "Number of examples to include (1-10)",
                "selection_strategy": "How to select examples (best, diverse, random)"
            }
        },
        {
            "name": "iterative",
            "display_name": "Iterative Refinement",
            "description": "Analyzes errors and iteratively refines the prompt",
            "parameters": {}
        },
        {
            "name": "hyperparameter",
            "display_name": "Hyperparameter Tuning",
            "description": "Optimizes model parameters like temperature and max_tokens",
            "parameters": {
                "params_to_optimize": "List of parameters to tune",
                "search_method": "Search method (bayesian, grid, random)"
            }
        },
        {
            "name": "genetic",
            "display_name": "Genetic Algorithm",
            "description": "Evolves prompts using genetic algorithm techniques",
            "parameters": {
                "population_size": "Population size (5-20)",
                "mutation_rate": "Mutation probability (0.05-0.2)"
            }
        }
    ]
    
    return StandardResponse(
        success=True,
        data=strategies
    )

@router.get("/history/{optimization_id}", response_model=StandardResponse,
            openapi_extra={
                "responses": {
                    "200": {
                        "description": "Optimization history and progress",
                        "content": {
                            "application/json": {
                                "examples": {
                                    "history": {
                                        "summary": "Recent job and progress",
                                        "value": {
                                            "success": True,
                                            "data": {
                                                "optimization": {"id": 701, "status": "running", "iterations_completed": 3, "max_iterations": 20},
                                                "job": {"id": 9001, "status": "processing"},
                                                "progress": {"iterations_completed": 3, "max_iterations": 20, "status": "running"},
                                                "timeline": [
                                                    {"event": "queued", "job_id": 9001, "at": "2024-09-21T10:00:00"},
                                                    {"event": "processing", "job_id": 9001, "at": "2024-09-21T10:00:05"}
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            })
async def get_optimization_history(
    optimization_id: int = Path(..., description="Optimization ID"),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Fetch optimization status and recent job history for UI progress.
    
    Returns the optimization row, latest job entry (if any), and
    lightweight progress fields.
    """
    try:
        optimization = db.get_optimization(optimization_id)
        if not optimization or optimization.get("deleted"):
            raise HTTPException(status_code=404, detail="Optimization not found")

        await require_project_access(
            optimization.get("project_id"),
            user_context=user_context,
            db=db,
        )

        job = db.get_latest_job_for_entity(
            JobType.OPTIMIZATION.value,
            optimization_id,
        )
        timeline_records = db.list_jobs_for_entity(
            JobType.OPTIMIZATION.value,
            optimization_id,
            limit=50,
            ascending=True,
        )

        timeline = [
            {
                "job_id": entry.get("id"),
                "status": entry.get("status"),
                "created_at": entry.get("created_at"),
                "started_at": entry.get("started_at"),
                "completed_at": entry.get("completed_at"),
            }
            for entry in timeline_records
        ]

        return StandardResponse(
            success=True,
            data={
                "optimization": OptimizationResponse(**optimization),
                "job": job,
                "progress": {
                    "iterations_completed": optimization.get("iterations_completed"),
                    "max_iterations": optimization.get("max_iterations"),
                    "status": optimization.get("status"),
                },
                "timeline": timeline,
            },
        )
    except DatabaseError as exc:
        logger.error(f"Database error fetching optimization history {optimization_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch optimization history")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error fetching optimization history {optimization_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch optimization history")

########################################################################################################################
# Iteration Events (persisted)

from pydantic import BaseModel, Field

class OptimizationIterationCreate(BaseModel):
    iteration_number: int = Field(..., ge=1, description="Iteration number starting at 1")
    prompt_variant: Optional[Dict[str, Any]] = Field(None, description="Prompt variant used")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Metrics for this iteration")
    tokens_used: Optional[int] = Field(None, ge=0)
    cost: Optional[float] = Field(None, ge=0.0)
    note: Optional[str] = Field(None, max_length=1000)


@router.post("/iterations/{optimization_id}", response_model=StandardResponse,
             openapi_extra={
                 "requestBody": {
                     "content": {
                         "application/json": {
                             "examples": {
                                 "iteration": {
                                     "summary": "Record iteration",
                                     "value": {
                                         "iteration_number": 4,
                                         "metrics": {"accuracy": 0.82},
                                         "tokens_used": 1400,
                                         "cost": 0.08
                                     }
                                 }
                             }
                         }
                     }
                 },
                 "responses": {
                     "200": {
                         "description": "Iteration persisted",
                         "content": {"application/json": {"examples": {"ok": {"value": {"success": True, "data": {"id": 1001}}}}}}
                     }
                 }
             })
async def add_optimization_iteration(
    optimization_id: int,
    payload: OptimizationIterationCreate,
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """Persist a single optimization iteration event."""
    try:
        optimization = db.get_optimization(optimization_id)
        if not optimization or optimization.get("deleted"):
            raise HTTPException(status_code=404, detail="Optimization not found")

        await require_project_write_access(
            optimization.get("project_id"),
            user_context=user_context,
            db=db,
        )

        record = db.record_optimization_iteration(
            optimization_id,
            iteration_number=payload.iteration_number,
            prompt_variant=payload.prompt_variant,
            metrics=payload.metrics,
            tokens_used=payload.tokens_used,
            cost=payload.cost,
            note=payload.note,
        )

        return StandardResponse(success=True, data=record)
    except DatabaseError as exc:
        logger.error(f"Database error recording iteration for optimization {optimization_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to add iteration")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error adding iteration: {exc}")
        raise HTTPException(status_code=500, detail="Failed to add iteration")


@router.get(
    "/iterations/{optimization_id}",
    response_model=ListResponse,
    openapi_extra={
        "responses": {
            "200": {
                "description": "Iteration list",
                "content": {
                    "application/json": {
                        "examples": {
                            "list": {
                                "value": {
                                    "success": True,
                                    "data": [
                                        {"iteration_number": 1, "metrics": {"accuracy": 0.7}}
                                    ],
                                    "metadata": {
                                        "page": 1,
                                        "per_page": 50,
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
async def list_optimization_iterations(
    optimization_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> ListResponse:
    """List persisted iterations for an optimization."""
    try:
        optimization = db.get_optimization(optimization_id)
        if not optimization or optimization.get("deleted"):
            raise HTTPException(status_code=404, detail="Optimization not found")

        await require_project_access(
            optimization.get("project_id"),
            user_context=user_context,
            db=db,
        )

        result = db.list_optimization_iterations(
            optimization_id,
            page=page,
            per_page=per_page,
        )

        metadata = PaginationMetadata(**result.get("pagination", {}))
        return ListResponse(
            success=True,
            data=result.get("iterations", []),
            metadata=metadata,
        )
    except DatabaseError as exc:
        logger.error(f"Database error listing optimization iterations for {optimization_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list iterations")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error listing iterations: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list iterations")
@router.post(
    "/compare",
    response_model=StandardResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "compare": {
                            "summary": "Compare optimization strategies",
                            "value": {
                                "prompt_id": 12,
                                "test_case_ids": [1, 2, 3],
                                "strategies": ["iterative", "bayesian"],
                                "model_configuration": {"model_name": "gpt-4o-mini", "temperature": 0.3}
                            }
                        }
                    }
                }
            }
        },
        "responses": {
            "200": {
                "description": "Comparison jobs created"
            }
        }
    }
)
async def compare_strategies(
    request: CompareStrategiesRequest,
    background_tasks: BackgroundTasks = None,
    _: bool = Depends(lambda: check_rate_limit("optimization")),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Compare multiple optimization strategies.
    
    Returns:
        Comparison job details
    """
    try:
        prompt_row = db.get_prompt_with_project(request.prompt_id, include_deleted=False)
        if not prompt_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {request.prompt_id} not found",
            )

        project_id = prompt_row["project_id"]
        await require_project_write_access(project_id, user_context=user_context, db=db)

        job_manager = JobManager(db)
        optimization_ids: List[int] = []
        job_ids: List[int] = []

        strategies = request.strategies or []
        for strategy in strategies:
            combined_config = {
                "optimizer_type": strategy,
                "max_iterations": 10,
                "model_configuration": request.model_configuration,
            }

            optimization_record = db.create_optimization(
                project_id=project_id,
                name=f"Compare: {strategy}",
                initial_prompt_id=request.prompt_id,
                optimizer_type=strategy,
                optimization_config=combined_config,
                max_iterations=10,
                status="pending",
                client_id=db.client_id,
            )
            optimization_ids.append(optimization_record["id"])

            job = job_manager.create_job(
                job_type=JobType.OPTIMIZATION,
                entity_id=optimization_record["id"],
                payload={
                    "optimization_id": optimization_record["id"],
                    "optimizer_type": strategy,
                    "test_case_ids": request.test_case_ids or [],
                    "optimization_config": combined_config,
                    "initial_prompt_id": request.prompt_id,
                    "project_id": project_id,
                    "created_by": user_context.get("user_id"),
                    "submitted_at": datetime.utcnow().isoformat(),
                },
                project_id=project_id,
                priority=5,
            )
            job_ids.append(job["id"])

        logger.info(
            "User %s created strategy comparison for prompt %s",
            user_context.get("user_id"),
            request.prompt_id,
        )

        return StandardResponse(
            success=True,
            data={
                "optimization_ids": optimization_ids,
                "job_ids": job_ids,
                "strategies": strategies,
                "message": f"Comparing {len(strategies)} optimization strategies",
            },
        )

    except DatabaseError as exc:
        logger.error(f"Database error comparing strategies: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare strategies",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error comparing strategies: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare strategies",
        )

########################################################################################################################
# Helper Functions

import json
from datetime import datetime

async def run_optimization_async(optimization_id: int, db: PromptStudioDatabase):
    """
    Run optimization asynchronously.
    
    Args:
        optimization_id: Optimization ID
        db: Database instance
    """
    try:
        engine = OptimizationEngine(db)
        await engine.optimize(optimization_id)
    except Exception as e:
        logger.error(f"Async optimization failed: {e}")
        
        db.set_optimization_status(
            optimization_id,
            "failed",
            error_message=str(e),
            mark_completed=True,
        )

async def require_project_access(project_id: int) -> bool:
    """Check if user has access to project."""
    # Placeholder - implement actual access control
    return True
