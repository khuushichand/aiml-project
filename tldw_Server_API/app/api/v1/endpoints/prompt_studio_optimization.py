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
from tldw_Server_API.app.api.v1.schemas.prompt_studio_base import StandardResponse, ListResponse
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
    tags=["Prompt Studio (Experimental)"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not found"},
        429: {"description": "Rate limit exceeded"}
    }
)

########################################################################################################################
# Optimization CRUD Endpoints

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
                                    "early_stopping": true
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
                                "value": {"success": true, "data": {"id": 701, "status": "pending", "job_id": 9001}}
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
        # Validate project access
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Get project from prompt
        cursor.execute(
            "SELECT project_id FROM prompt_studio_prompts WHERE id = ?",
            (optimization_data.initial_prompt_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {optimization_data.initial_prompt_id} not found"
            )
        
        project_id = row[0]
        await require_project_write_access(project_id, user_context=user_context, db=db)
        
        # Create optimization record (aligned with schema)
        opt_cfg = optimization_data.optimization_config
        optimizer_type = opt_cfg.optimizer_type if hasattr(opt_cfg, "optimizer_type") else str(getattr(opt_cfg, "optimizer_type", "iterative"))
        max_iters = getattr(opt_cfg, "max_iterations", None)

        combined_config: Dict[str, Any] = json.loads(opt_cfg.model_dump_json()) if hasattr(opt_cfg, "model_dump_json") else (
            opt_cfg.dict() if hasattr(opt_cfg, "dict") else {}
        )
        # Include bootstrap_config if provided
        if optimization_data.bootstrap_config is not None:
            combined_config["bootstrap_config"] = (
                json.loads(optimization_data.bootstrap_config.model_dump_json())
                if hasattr(optimization_data.bootstrap_config, "model_dump_json")
                else optimization_data.bootstrap_config.dict()
            )

        cursor.execute(
            """
            INSERT INTO prompt_studio_optimizations (
                uuid, project_id, name, initial_prompt_id,
                optimizer_type, optimization_config, max_iterations, status, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"opt-{user_context['user_id']}-{datetime.utcnow().timestamp()}",
                project_id,
                optimization_data.name,
                optimization_data.initial_prompt_id,
                optimizer_type,
                json.dumps(combined_config),
                max_iters,
                "pending",
                db.client_id,
            ),
        )
        
        optimization_id = cursor.lastrowid
        conn.commit()
        
        # Create job for optimization
        job_manager = JobManager(db)
        job = job_manager.create_job(
            job_type=JobType.OPTIMIZATION,
            entity_id=optimization_id,
            payload={
                "optimization_id": optimization_id,
                "optimizer_type": optimizer_type,
                "test_case_ids": optimization_data.test_case_ids or [],
                "optimization_config": combined_config,
                "initial_prompt_id": optimization_data.initial_prompt_id,
                "project_id": project_id,
                "created_by": user_context.get("user_id"),
                "submitted_at": datetime.utcnow().isoformat(),
            },
            priority=5,
        )
        
        logger.info(f"User {user_context['user_id']} created optimization {optimization_id}")
        
        # Start optimization in background
        background_tasks.add_task(
            run_optimization_async,
            optimization_id,
            db,
        )
        
        return StandardResponse(
            success=True,
            data=OptimizationResponse(
                id=optimization_id,
                uuid=cursor.lastrowid,
                project_id=project_id,
                name=optimization_data.name,
                status="pending",
                job_id=job["id"]
            )
        )
        
    except DatabaseError as e:
        logger.error(f"Database error creating optimization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create optimization"
        )

@router.get("/list/{project_id}", response_model=ListResponse, openapi_extra={
    "responses": {"200": {"description": "Optimizations", "content": {"application/json": {"examples": {"list": {"summary": "Optimization list", "value": {"success": true, "data": [{"id": 701, "name": "Refine Summarizer", "status": "pending"}], "metadata": {"page": 1, "per_page": 20, "total": 1, "total_pages": 1}}}}}}}
})
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
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT * FROM prompt_studio_optimizations
            WHERE project_id = ? AND deleted = 0
        """
        params = [project_id]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor.execute(query, params)
        
        optimizations = []
        for row in cursor.fetchall():
            opt = db._row_to_dict(cursor, row)
            optimizations.append(OptimizationResponse(**opt))
        
        # Get total count
        count_query = """
            SELECT COUNT(*) FROM prompt_studio_optimizations
            WHERE project_id = ? AND deleted = 0
        """
        count_params = [project_id]
        
        if status:
            count_query += " AND status = ?"
            count_params.append(status)
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]
        
        return ListResponse(
            success=True,
            data=optimizations,
            metadata={
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing optimizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list optimizations"
        )

@router.get("/get/{optimization_id}", response_model=StandardResponse, openapi_extra={
    "responses": {"200": {"description": "Optimization details", "content": {"application/json": {"examples": {"get": {"summary": "Optimization", "value": {"success": true, "data": {"id": 701, "optimizer_type": "iterative", "status": "running"}}}}}}}}
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
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM prompt_studio_optimizations
            WHERE id = ? AND deleted = 0
        """, (optimization_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Optimization {optimization_id} not found"
            )
        
        optimization = db._row_to_dict(cursor, row)

        # Check project access
        await require_project_access(optimization["project_id"], user_context=user_context, db=db)
        
        # Parse JSON fields (aligned with schema)
        if isinstance(optimization.get("optimization_config"), str):
            try:
                optimization["optimization_config"] = json.loads(optimization["optimization_config"]) or {}
            except Exception:
                optimization["optimization_config"] = {}
        for k in ("initial_metrics", "final_metrics"):
            if isinstance(optimization.get(k), str):
                try:
                    optimization[k] = json.loads(optimization[k]) or {}
                except Exception:
                    optimization[k] = {}
        
        return StandardResponse(
            success=True,
            data=optimization
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting optimization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get optimization"
        )

@router.post("/cancel/{optimization_id}", response_model=StandardResponse, openapi_extra={
    "responses": {"200": {"description": "Cancelled", "content": {"application/json": {"examples": {"cancelled": {"value": {"success": true, "data": {"message": "Optimization cancelled"}}}}}}}, "400": {"description": "Invalid state"}, "404": {"description": "Not found"}}
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
        # Get optimization
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT project_id, status FROM prompt_studio_optimizations
            WHERE id = ? AND deleted = 0
        """, (optimization_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Optimization {optimization_id} not found"
            )
        
        project_id, status = row
        
        # Check access
        await require_project_write_access(project_id, user_context=user_context, db=db)
        
        # Check if can cancel
        if status in ["completed", "failed", "cancelled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel optimization with status: {status}"
            )
        
        # Cancel associated job
        job_manager = JobManager(db)
        cursor.execute("""
            SELECT id FROM prompt_studio_job_queue
            WHERE job_type = 'optimization' AND entity_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (optimization_id,))
        
        job_row = cursor.fetchone()
        if job_row:
            job_manager.cancel_job(job_row[0], reason or "User cancelled")
        
        # Update optimization status
        cursor.execute("""
            UPDATE prompt_studio_optimizations
            SET status = 'cancelled',
                error_message = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (reason or "Cancelled by user", optimization_id))
        
        conn.commit()
        
        logger.info(f"User {user_context['user_id']} cancelled optimization {optimization_id}")
        
        return StandardResponse(
            success=True,
            data={"message": "Optimization cancelled"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling optimization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel optimization"
        )

########################################################################################################################
# Optimization Strategy Endpoints

@router.get("/strategies", response_model=StandardResponse, openapi_extra={
    "responses": {"200": {"description": "Strategies", "content": {"application/json": {"examples": {"list": {"summary": "Available strategies", "value": {"success": true, "data": [{"name": "iterative", "display_name": "Iterative Refinement"}]}}}}}}}
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
                "description": "Comparison jobs created",
                "content": {
                    "application/json": {
                        "examples": {
                            "created": {
                                "summary": "Comparison started",
                                "value": {"success": true, "data": {"jobs": [{"id": 9002}, {"id": 9003}]}}
                            }
                        }
                    }
                }
            }
        }
    }
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
                                            "success": true,
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
        conn = db.get_connection()
        cursor = conn.cursor()

        # Optimization row
        cursor.execute(
            "SELECT * FROM prompt_studio_optimizations WHERE id = ?",
            (optimization_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Optimization not found")
        opt = db._row_to_dict(cursor, row)

        await require_project_access(opt["project_id"], user_context=user_context, db=db)

        # Latest job
        cursor.execute(
            """
            SELECT * FROM prompt_studio_job_queue
            WHERE job_type = 'optimization' AND entity_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (optimization_id,)
        )
        job_row = cursor.fetchone()
        job = db._row_to_dict(cursor, job_row) if job_row else None

        # Timeline (recent jobs)
        cursor.execute(
            """
            SELECT * FROM prompt_studio_job_queue
            WHERE job_type = 'optimization' AND entity_id = ?
            ORDER BY created_at ASC
            LIMIT 50
            """,
            (optimization_id,)
        )
        rows = cursor.fetchall()
        timeline = []
        for r in rows or []:
            j = db._row_to_dict(cursor, r)
            timeline.append({
                "job_id": j.get("id"),
                "status": j.get("status"),
                "created_at": j.get("created_at"),
                "started_at": j.get("started_at"),
                "completed_at": j.get("completed_at"),
            })

        # Parse JSON payloads
        import json as _json
        if job:
            for k in ("payload", "result"):
                if isinstance(job.get(k), str):
                    try:
                        job[k] = _json.loads(job[k])
                    except Exception:
                        pass

        return StandardResponse(
            success=True,
            data={
                "optimization": opt,
                "job": job,
                "progress": {
                    "iterations_completed": opt.get("iterations_completed"),
                    "max_iterations": opt.get("max_iterations"),
                    "status": opt.get("status")
                },
                "timeline": timeline
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching optimization history: {e}")
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
                         "content": {"application/json": {"examples": {"ok": {"value": {"success": true, "data": {"id": 1001}}}}}}
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
        conn = db.get_connection()
        cursor = conn.cursor()

        # Ownership check
        cursor.execute("SELECT project_id FROM prompt_studio_optimizations WHERE id = ?", (optimization_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Optimization not found")
        await require_project_write_access(row[0], user_context=user_context, db=db)

        cursor.execute(
            """
            INSERT INTO prompt_studio_optimization_iterations (
                optimization_id, iteration_number, prompt_variant, metrics, tokens_used, cost, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                optimization_id,
                payload.iteration_number,
                json.dumps(payload.prompt_variant) if payload.prompt_variant is not None else None,
                json.dumps(payload.metrics) if payload.metrics is not None else None,
                payload.tokens_used,
                payload.cost,
                payload.note,
            ),
        )
        iter_id = cursor.lastrowid
        conn.commit()

        return StandardResponse(success=True, data={"id": iter_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding iteration: {e}")
        raise HTTPException(status_code=500, detail="Failed to add iteration")


@router.get("/iterations/{optimization_id}", response_model=ListResponse,
            openapi_extra={
                "responses": {"200": {"description": "Iteration list", "content": {"application/json": {"examples": {"list": {"value": {"success": true, "data": [{"iteration_number": 1, "metrics": {"accuracy": 0.7}}], "metadata": {"page": 1, "per_page": 50, "total": 1, "total_pages": 1}}}}}}}
            })
async def list_optimization_iterations(
    optimization_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> ListResponse:
    """List persisted iterations for an optimization."""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        # Ownership check
        cursor.execute("SELECT project_id FROM prompt_studio_optimizations WHERE id = ?", (optimization_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Optimization not found")
        await require_project_access(row[0], user_context=user_context, db=db)

        offset = (page - 1) * per_page
        cursor.execute(
            """
            SELECT id, iteration_number, prompt_variant, metrics, tokens_used, cost, note, created_at
            FROM prompt_studio_optimization_iterations
            WHERE optimization_id = ?
            ORDER BY iteration_number ASC
            LIMIT ? OFFSET ?
            """,
            (optimization_id, per_page, offset),
        )
        rows = cursor.fetchall() or []
        items = []
        for r in rows:
            rec = db._row_to_dict(cursor, r)
            # Parse JSON fields
            for k in ("prompt_variant", "metrics"):
                if isinstance(rec.get(k), str):
                    try:
                        rec[k] = json.loads(rec[k])
                    except Exception:
                        pass
            items.append(rec)

        # Count
        cursor.execute(
            "SELECT COUNT(*) FROM prompt_studio_optimization_iterations WHERE optimization_id = ?",
            (optimization_id,),
        )
        total = cursor.fetchone()[0]
        return ListResponse(
            success=True,
            data=items,
            metadata={
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing iterations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list iterations")
async def compare_strategies(
    request: CompareStrategiesRequest,
    background_tasks: BackgroundTasks = None,
    _: bool = Depends(lambda: check_rate_limit("optimization")),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> StandardResponse:
    """
    Compare multiple optimization strategies.
    
    Args:
        prompt_id: Prompt to optimize
        test_case_ids: Test cases
        strategies: List of strategies to compare
        model_config: Model configuration
        background_tasks: Background task manager
        db: Database instance
        user_context: Current user context
        
    Returns:
        Comparison job details
    """
    try:
        # Validate prompt
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT project_id FROM prompt_studio_prompts WHERE id = ?",
            (request.prompt_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {request.prompt_id} not found"
            )
        
        project_id = row[0]
        await require_project_write_access(project_id, user_context=user_context, db=db)
        
        # Create optimizations for each strategy
        pending_jobs: List[Dict[str, Any]] = []
        
        for strategy in strategies:
            combined_config = {
                "optimizer_type": strategy,
                "max_iterations": 10,
                "model_configuration": request.model_configuration,
            }
            cursor.execute(
                """
                INSERT INTO prompt_studio_optimizations (
                    uuid, project_id, name, initial_prompt_id,
                    optimizer_type, optimization_config, max_iterations, status, client_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"compare-{strategy}-{datetime.utcnow().timestamp()}",
                    project_id,
                    f"Compare: {strategy}",
                    request.prompt_id,
                    strategy,
                    json.dumps(combined_config),
                    10,
                    "pending",
                    db.client_id,
                ),
            )
            
            pending_jobs.append({
                "id": cursor.lastrowid,
                "strategy": strategy,
                "config": combined_config,
                "test_case_ids": request.test_case_ids or [],
            })
        
        conn.commit()
        
        # Create jobs for each optimization
        job_manager = JobManager(db)
        jobs = []
        
        for item in pending_jobs:
            job = job_manager.create_job(
                job_type=JobType.OPTIMIZATION,
                entity_id=item["id"],
                payload={
                    "optimization_id": item["id"],
                    "optimizer_type": item["strategy"],
                    "test_case_ids": item["test_case_ids"],
                    "optimization_config": item["config"],
                    "initial_prompt_id": request.prompt_id,
                    "project_id": project_id,
                    "created_by": user_context.get("user_id"),
                    "submitted_at": datetime.utcnow().isoformat(),
                },
                priority=5
            )
            jobs.append(job)
        
        logger.info(f"User {user_context['user_id']} created strategy comparison")
        
        return StandardResponse(
            success=True,
            data={
                "optimization_ids": optimization_ids,
                "job_ids": [j["id"] for j in jobs],
                "strategies": strategies,
                "message": f"Comparing {len(strategies)} optimization strategies"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing strategies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare strategies"
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
        
        # Update status to failed
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE prompt_studio_optimizations
            SET status = 'failed',
                error_message = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (str(e), optimization_id))
        conn.commit()

async def require_project_access(project_id: int) -> bool:
    """Check if user has access to project."""
    # Placeholder - implement actual access control
    return True
