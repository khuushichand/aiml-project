# prompt_studio_evaluations.py
# Evaluation endpoints for Prompt Studio

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
import uuid
import json
from datetime import datetime
import asyncio
from loguru import logger

from ....core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from ....core.Prompt_Management.prompt_studio.test_runner import TestRunner
from ....core.Prompt_Management.prompt_studio.evaluation_metrics import EvaluationMetrics
from ....core.Prompt_Management.prompt_studio.evaluation_manager import EvaluationManager
from ..API_Deps.prompt_studio_deps import get_prompt_studio_db, get_prompt_studio_user
from ..schemas.prompt_studio_schemas import (
    EvaluationCreate,
    EvaluationResponse,
    EvaluationList,
    EvaluationUpdate,
    EvaluationMetrics,
    EvaluationConfig,
)

router = APIRouter(prefix="/api/v1/prompt-studio")

@router.post("/evaluations", response_model=EvaluationResponse)
async def create_evaluation(
    evaluation: EvaluationCreate,
    background_tasks: BackgroundTasks,
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> EvaluationResponse:
    """
    Create a new evaluation for a prompt.
    
    Args:
        evaluation: Evaluation configuration
        background_tasks: FastAPI background tasks
        db: Database instance
        user_context: Current user context
        
    Returns:
        Created evaluation response
    """
    try:
        # Normalize config
        cfg: Optional[EvaluationConfig] = evaluation.config
        model_name = (cfg.model_name if cfg and cfg.model_name else "gpt-3.5-turbo")
        temperature = (cfg.temperature if cfg and cfg.temperature is not None else 0.7)
        max_tokens = (cfg.max_tokens if cfg and cfg.max_tokens is not None else 1000)

        # Use EvaluationManager for sync path; for async we create a record and update later
        eval_manager = EvaluationManager(db)

        if getattr(evaluation, 'run_async', False):
            # Create a pending evaluation record tied to this request
            eval_uuid = str(uuid.uuid4())
            conn = db.get_connection()
            cursor = conn.cursor()
            model_configs = json.dumps({
                "model_name": model_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
            })
            cursor.execute(
                """
                INSERT INTO prompt_studio_evaluations (
                    uuid, project_id, prompt_id, name, description,
                    test_case_ids, model_configs, status, client_id, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL)
                """,
                (
                    eval_uuid,
                    evaluation.project_id,
                    evaluation.prompt_id,
                    evaluation.name or "Evaluation",
                    evaluation.description or "",
                    json.dumps(evaluation.test_case_ids or []),
                    model_configs,
                    user_context.get("client_id", "api"),
                ),
            )
            eval_id = cursor.lastrowid
            conn.commit()

            # Defer execution which will update this record to running/completed
            background_tasks.add_task(
                run_evaluation_async,
                evaluation_id=eval_id,
                db=db,
            )

            return EvaluationResponse(
                id=eval_id,
                uuid=eval_uuid,
                project_id=evaluation.project_id,
                prompt_id=evaluation.prompt_id,
                name=evaluation.name or "Evaluation",
                description=evaluation.description or "",
                status="pending",
                created_at=datetime.now().isoformat(),
            )
        else:
            # Run synchronously and return results
            result = eval_manager.run_evaluation(
                prompt_id=evaluation.prompt_id,
                test_case_ids=evaluation.test_case_ids or [],
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return EvaluationResponse(
                id=result["id"],
                uuid=result["uuid"],
                project_id=evaluation.project_id,
                prompt_id=result["prompt_id"],
                name=evaluation.name or "Evaluation",
                description=evaluation.description or "",
                status=result["status"],
                created_at=datetime.now().isoformat(),
                metrics=result.get("metrics"),
            )
        
    except Exception as e:
        logger.error(f"Failed to create evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/evaluations", response_model=List[EvaluationResponse])
async def list_evaluations(
    project_id: int = Query(..., description="Project ID"),
    prompt_id: Optional[int] = Query(None, description="Filter by prompt ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> List[EvaluationResponse]:
    """
    List evaluations for a project.
    
    Args:
        project_id: Project ID
        prompt_id: Optional prompt ID filter
        limit: Maximum results
        offset: Pagination offset
        db: Database instance
        user_context: Current user context
        
    Returns:
        List of evaluations
    """
    try:
        # Use EvaluationManager to list evaluations
        eval_manager = EvaluationManager(db)
        
        # Calculate page from offset
        page = (offset // limit) + 1 if limit > 0 else 1
        
        result = eval_manager.list_evaluations(
            project_id=project_id,
            prompt_id=prompt_id,
            page=page,
            per_page=limit
        )
        
        # Convert to response format
        evaluations = []
        for eval_data in result.get("evaluations", []):
            evaluations.append(EvaluationResponse(
                id=eval_data["id"],
                uuid=eval_data.get("uuid", ""),
                project_id=project_id,  # Add project_id since it might not be in the result
                prompt_id=eval_data["prompt_id"],
                name=eval_data.get("prompt_name", "Evaluation"),
                description="",  # Not returned by manager
                status=eval_data.get("status", "pending"),
                created_at=eval_data.get("created_at", ""),
                completed_at=eval_data.get("completed_at"),
                metrics=eval_data.get("aggregate_metrics")
            ))
        
        return evaluations
        
    except Exception as e:
        logger.error(f"Failed to list evaluations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/evaluations/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: int,
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> EvaluationResponse:
    """
    Get a specific evaluation.
    
    Args:
        evaluation_id: Evaluation ID
        db: Database instance
        user_context: Current user context
        
    Returns:
        Evaluation details
    """
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, uuid, project_id, prompt_id, name, description,
                   status, created_at, completed_at, aggregate_metrics
            FROM prompt_studio_evaluations
            WHERE id = ?
        """, (evaluation_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        
        eval_dict = db.row_to_dict(row, cursor)
        
        return EvaluationResponse(
            id=eval_dict["id"],
            uuid=eval_dict["uuid"],
            project_id=eval_dict["project_id"],
            prompt_id=eval_dict["prompt_id"],
            name=eval_dict.get("name", ""),
            description=eval_dict.get("description", ""),
            status=eval_dict.get("status", "pending"),
            created_at=eval_dict.get("created_at", ""),
            completed_at=eval_dict.get("completed_at"),
            metrics=json.loads(eval_dict["aggregate_metrics"]) if eval_dict.get("aggregate_metrics") else {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/evaluations/{evaluation_id}")
async def delete_evaluation(
    evaluation_id: int,
    db: PromptStudioDatabase = Depends(get_prompt_studio_db),
    user_context: Dict = Depends(get_prompt_studio_user)
) -> Dict[str, str]:
    """
    Delete an evaluation (soft delete).
    
    Args:
        evaluation_id: Evaluation ID
        db: Database instance
        user_context: Current user context
        
    Returns:
        Success message
    """
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Soft delete
        cursor.execute("""
            UPDATE prompt_studio_evaluations
            SET deleted = 1, deleted_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), evaluation_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        
        conn.commit()
        
        return {"message": f"Evaluation {evaluation_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

########################################################################################################################
# Background Task Health

# Minimal in-memory ping registry for background tasks health checks
_BG_PINGS: Dict[str, Dict[str, Any]] = {}


async def _complete_ping(ping_id: str):
    try:
        # Yield to event loop briefly to simulate background work
        await asyncio.sleep(0.01)
        _BG_PINGS[ping_id]["status"] = "completed"
        _BG_PINGS[ping_id]["completed_at"] = datetime.now().isoformat()
    except Exception:
        _BG_PINGS[ping_id]["status"] = "failed"


@router.post("/background/ping")
async def background_ping(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Schedule a trivial background task to verify background execution works."""
    pid = str(uuid.uuid4())
    _BG_PINGS[pid] = {"id": pid, "status": "processing", "created_at": datetime.now().isoformat()}
    background_tasks.add_task(_complete_ping, pid)
    return _BG_PINGS[pid]


@router.get("/background/pings/{ping_id}")
async def get_ping_status(ping_id: str) -> Dict[str, Any]:
    if ping_id not in _BG_PINGS:
        raise HTTPException(status_code=404, detail="Ping not found")
    return _BG_PINGS[ping_id]

async def run_evaluation_async(evaluation_id: int, db: PromptStudioDatabase):
    """
    Execute an evaluation and update the existing record.

    Best-effort: computes simple metrics; tolerates missing LLM credentials by
    marking failures while still completing the record.
    """
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio.evaluation_manager import EvaluationManager
    from tldw_Server_API.app.core.Chat.Chat_Functions import chat_api_call
    import json as _json

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        # Load the evaluation record
        cursor.execute(
            """
            SELECT id, project_id, prompt_id, test_case_ids, model_configs
            FROM prompt_studio_evaluations
            WHERE id = ?
            """,
            (evaluation_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Evaluation not found")

        # Move to running
        cursor.execute(
            """
            UPDATE prompt_studio_evaluations
            SET status = 'running', started_at = ?
            WHERE id = ?
            """,
            (datetime.now().isoformat(), evaluation_id),
        )
        conn.commit()

        _id, project_id, prompt_id, tc_ids_json, model_cfg_json = row
        try:
            test_case_ids = _json.loads(tc_ids_json) if tc_ids_json else []
        except Exception:
            test_case_ids = []
        try:
            cfg = _json.loads(model_cfg_json) if model_cfg_json else {}
        except Exception:
            cfg = {}
        model_name = cfg.get("model_name") or cfg.get("model") or "gpt-3.5-turbo"
        temperature = cfg.get("temperature", 0.7)
        max_tokens = cfg.get("max_tokens", 1000)

        # Fetch prompt
        cursor.execute(
            """
            SELECT system_prompt, user_prompt, name
            FROM prompt_studio_prompts
            WHERE id = ? AND deleted = 0
            """,
            (prompt_id,),
        )
        prompt_row = cursor.fetchone()
        if not prompt_row:
            raise RuntimeError(f"Prompt {prompt_id} not found")
        system_prompt, user_prompt, prompt_name = prompt_row
        system_prompt = system_prompt or ""
        user_prompt = user_prompt or ""

        # Fetch test cases
        if not test_case_ids:
            results = []
        else:
            placeholders = ",".join("?" * len(test_case_ids))
            cursor.execute(
                f"""
                SELECT id, inputs, expected_outputs
                FROM prompt_studio_test_cases
                WHERE id IN ({placeholders}) AND deleted = 0
                """,
                test_case_ids,
            )
            tc_rows = cursor.fetchall()

            results = []
            total_score = 0.0
            for tc in tc_rows:
                tc_id, inputs_json, expected_json = tc
                try:
                    inputs = _json.loads(inputs_json) if inputs_json else {}
                except Exception:
                    inputs = {}
                try:
                    expected = _json.loads(expected_json) if expected_json else {}
                except Exception:
                    expected = {}

                # Format user prompt with inputs
                formatted_user_prompt = user_prompt
                try:
                    for k, v in (inputs or {}).items():
                        formatted_user_prompt = formatted_user_prompt.replace(f"{{{k}}}", str(v))
                except Exception:
                    pass

                # LLM call best-effort
                actual_output = ""
                error = None
                try:
                    resp = chat_api_call(
                        api_endpoint="openai",
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": formatted_user_prompt},
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if isinstance(resp, list) and resp:
                        actual_output = resp[0]
                except Exception as e:
                    error = str(e)

                # Score: simple exact/contains match on 'response' field
                def _score(exp: dict, act: dict) -> float:
                    if not exp:
                        return 1.0
                    exp_str = str(exp.get("response", "")).lower().strip()
                    act_str = str(act.get("response", "")).lower().strip()
                    if exp_str == act_str:
                        return 1.0
                    if exp_str and act_str and (exp_str in act_str or act_str in exp_str):
                        return 0.5
                    if not exp_str:
                        return 0.0
                    exp_words = set(exp_str.split())
                    act_words = set(act_str.split())
                    if not exp_words:
                        return 0.0
                    overlap = len(exp_words & act_words)
                    return overlap / max(1, len(exp_words))

                actual = {"response": actual_output} if not error else {"error": error}
                score = _score(expected, {"response": actual_output}) if not error else 0.0
                total_score += score
                results.append(
                    {
                        "test_case_id": tc_id,
                        "inputs": inputs,
                        "expected": expected,
                        "actual": actual,
                        "score": score,
                        "passed": score >= 0.5,
                    }
                )

        passed = sum(1 for r in results if r.get("passed"))
        total = len(results)
        aggregate_metrics = {
            "average_score": (sum(r.get("score", 0.0) for r in results) / total) if total else 0.0,
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": (passed / total) if total else 0.0,
        }

        # Update evaluation to completed with metrics
        cursor.execute(
            """
            UPDATE prompt_studio_evaluations
            SET status = 'completed',
                completed_at = ?,
                aggregate_metrics = ?,
                test_run_ids = ?
            WHERE id = ?
            """,
            (
                datetime.now().isoformat(),
                _json.dumps(aggregate_metrics),
                _json.dumps([r["test_case_id"] for r in results]) if results else _json.dumps([]),
                evaluation_id,
            ),
        )
        conn.commit()

    except Exception as e:
        logger.error(f"Failed to run async evaluation: {e}")
        try:
            cursor.execute(
                """
                UPDATE prompt_studio_evaluations
                SET status = 'failed', error_message = ?
                WHERE id = ?
                """,
                (str(e), evaluation_id),
            )
            conn.commit()
        except Exception:
            pass
