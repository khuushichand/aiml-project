# unified_evaluation_service.py - Unified evaluation service combining all evaluation capabilities
"""
Unified evaluation service that combines OpenAI-compatible evaluation framework
with tldw-specific evaluation features.

This service provides:
- OpenAI Evals compatible evaluation management
- G-Eval, RAG, and response quality evaluations
- Dataset management
- Run management with async processing
- Webhook notifications
- Advanced metrics and monitoring
"""

import asyncio
import json
import time
from contextlib import suppress
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from loguru import logger

# Import database components
from tldw_Server_API.app.core.DB_Management.DB_Manager import (
    create_evaluations_database as _create_evals_db,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

# Import evaluation engines
from tldw_Server_API.app.core.Evaluations.rag_evaluator import RAGEvaluator
from tldw_Server_API.app.core.Evaluations.response_quality_evaluator import ResponseQualityEvaluator

# Import support services
from tldw_Server_API.app.core.Evaluations.metrics_advanced import advanced_metrics
from tldw_Server_API.app.core.Evaluations.user_rate_limiter import user_rate_limiter, UserTier
from tldw_Server_API.app.core.Evaluations.circuit_breaker import CircuitBreaker
from tldw_Server_API.app.core.Evaluations.audit_adapter import (
    log_evaluation_created,
    log_evaluation_updated,
    log_evaluation_deleted,
    log_run_started,
    log_run_cancelled,
    log_dataset_created,
    log_dataset_deleted,
)
from tldw_Server_API.app.core.Evaluations.webhook_manager import WebhookEvent


class EvaluationType(str, Enum):
    """Supported evaluation types"""
    MODEL_GRADED = "model_graded"
    EXACT_MATCH = "exact_match"
    INCLUDES = "includes"
    GEVAL = "geval"
    RAG = "rag"
    RESPONSE_QUALITY = "response_quality"
    PROPOSITION_EXTRACTION = "proposition_extraction"
    QA3 = "qa3"
    OCR = "ocr"
    LABEL_CHOICE = "label_choice"
    NLI_FACTCHECK = "nli_factcheck"
    CUSTOM = "custom"


class UnifiedEvaluationService:
    """
    Unified service for all evaluation operations.

    Combines OpenAI-compatible evaluation framework with tldw-specific features
    into a single, cohesive service.
    """

    def __init__(
        self,
        db_path: str = str(DatabasePaths.get_evaluations_db_path(DatabasePaths.get_single_user_id())),
        *,
        enable_webhooks: bool = True,
        enable_caching: bool = True
    ):
        """
        Initialize the unified evaluation service.

        Args:
            db_path: Path to the evaluations database
            enable_webhooks: Toggle webhook delivery for evaluation lifecycle events
            enable_caching: Toggle optional caching layers (reserved for future use)
        """
        # Feature flags
        self.enable_webhooks = enable_webhooks
        self.enable_caching = enable_caching

        # Lifecycle flag
        self._initialized = False

        # Initialize database (allow override via env for tests)
        import os as _os
        _override_db = _os.getenv("EVALUATIONS_TEST_DB_PATH")
        effective_db_path = _override_db or db_path
        # Use backend-aware factory so Postgres content backend is honored
        self.db = _create_evals_db(db_path=effective_db_path)

        # Initialize evaluation runner for async processing (lazy import)
        from tldw_Server_API.app.core.Evaluations.eval_runner import EvaluationRunner
        self.runner = EvaluationRunner(effective_db_path)

        # Initialize evaluation engines (lazy loading)
        self._rag_evaluator = None
        self._quality_evaluator = None
        self._ocr_evaluator = None

        # Initialize circuit breaker for resilience
        from tldw_Server_API.app.core.Evaluations.circuit_breaker import CircuitBreakerConfig
        self.circuit_breaker = CircuitBreaker(
            name="evaluation_service",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60.0,
                expected_exception=Exception
            )
        )

        # Audit logger shim for backward compatibility in tests
        class _AuditShim:
            def evaluation_created(self, *, user_id: str, eval_id: str, name: str, eval_type: str) -> None:
                try:
                    log_evaluation_created(user_id=user_id, eval_id=eval_id, name=name, eval_type=eval_type)
                except Exception:
                    pass

            def evaluation_updated(self, *, user_id: str, eval_id: str, updates: Dict[str, Any]) -> None:
                try:
                    log_evaluation_updated(user_id=user_id, eval_id=eval_id, updates=updates)
                except Exception:
                    pass

            def evaluation_deleted(self, *, user_id: str, eval_id: str) -> None:
                try:
                    log_evaluation_deleted(user_id=user_id, eval_id=eval_id)
                except Exception:
                    pass

            def run_started(self, *, user_id: str, run_id: str, eval_id: str, target_model: str) -> None:
                try:
                    log_run_started(user_id=user_id, run_id=run_id, eval_id=eval_id, target_model=target_model)
                except Exception:
                    pass

            def run_cancelled(self, *, user_id: str, run_id: str) -> None:
                try:
                    log_run_cancelled(user_id=user_id, run_id=run_id)
                except Exception:
                    pass

            def dataset_created(self, *, user_id: str, dataset_id: str, name: str, samples: int) -> None:
                try:
                    log_dataset_created(user_id=user_id, dataset_id=dataset_id, name=name, samples=samples)
                except Exception:
                    pass

            def dataset_deleted(self, *, user_id: str, dataset_id: str) -> None:
                try:
                    log_dataset_deleted(user_id=user_id, dataset_id=dataset_id)
                except Exception:
                    pass

        self.audit_logger = _AuditShim()

        # Initialize per-service webhook manager bound to this DB
        try:
            from tldw_Server_API.app.core.Evaluations.webhook_manager import WebhookManager
            self.webhook_manager = WebhookManager(db_path=effective_db_path)
        except Exception:
            self.webhook_manager = None

        logger.info("Unified Evaluation Service initialized")

    async def initialize(self) -> None:
        """Async initializer to align with test fixtures and future setup steps."""
        if self._initialized:
            return

        # Placeholder for future async setup (e.g., warming caches, migrations)
        self._initialized = True
        logger.debug("Unified Evaluation Service async initialization complete")

    async def shutdown(self) -> None:
        """Gracefully shut down background activity and release resources."""
        if not self._initialized:
            return

        runner_shutdown = getattr(self.runner, "shutdown", None)
        if callable(runner_shutdown):
            try:
                result = runner_shutdown()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.warning(f"Evaluation runner shutdown encountered an error: {exc}")
        else:
            # Fallback: cancel any tracked tasks directly
            tasks_map = getattr(self.runner, "running_tasks", None)
            if isinstance(tasks_map, dict):
                for task in list(tasks_map.values()):
                    if not task or task.done():
                        continue
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                tasks_map.clear()

        self._initialized = False
        logger.debug("Unified Evaluation Service shutdown complete")

    # ============= Lazy Initialization =============

    def get_rag_evaluator(self) -> RAGEvaluator:
        """Get or create RAG evaluator instance"""
        if self._rag_evaluator is None:
            self._rag_evaluator = RAGEvaluator()
        return self._rag_evaluator

    def get_quality_evaluator(self) -> ResponseQualityEvaluator:
        """Get or create quality evaluator instance"""
        if self._quality_evaluator is None:
            self._quality_evaluator = ResponseQualityEvaluator()
        return self._quality_evaluator

    def get_ocr_evaluator(self):
        """Get or create OCR evaluator instance"""
        if self._ocr_evaluator is None:
            from tldw_Server_API.app.core.Evaluations.ocr_evaluator import OCREvaluator
            self._ocr_evaluator = OCREvaluator()
        return self._ocr_evaluator

    # ============= Evaluation Management =============

    async def create_evaluation(
        self,
        name: str,
        eval_type: str,
        eval_spec: Dict[str, Any],
        description: Optional[str] = None,
        dataset_id: Optional[str] = None,
        dataset: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None,
        created_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Create a new evaluation definition.

        Supports both OpenAI-style evaluation definitions and tldw-specific types.

        Args:
            name: Unique evaluation name
            eval_type: Type of evaluation (see EvaluationType enum)
            eval_spec: Evaluation specification
            description: Optional description
            dataset_id: ID of existing dataset
            dataset: Inline dataset (creates new dataset if provided)
            metadata: Optional metadata
            created_by: User/system creating the evaluation

        Returns:
            Created evaluation object
        """
        try:
            # If inline dataset provided, create it first
            if dataset and not dataset_id:
                dataset_id = self.db.create_dataset(
                    name=f"{name}_dataset",
                    samples=dataset,
                    description=f"Dataset for {name}",
                    created_by=created_by
                )

            # Create evaluation
            eval_id = self.db.create_evaluation(
                name=name,
                description=description,
                eval_type=eval_type,
                eval_spec=eval_spec,
                dataset_id=dataset_id,
                created_by=created_by,
                metadata=metadata
            )

            # Unified audit
            log_evaluation_created(user_id=created_by, eval_id=eval_id, name=name, eval_type=eval_type)

            # Get and return created evaluation
            evaluation = self.db.get_evaluation(eval_id)
            if not evaluation:
                raise ValueError("Failed to retrieve created evaluation")

            return evaluation

        except Exception as e:
            logger.error(f"Failed to create evaluation: {e}")
            raise

    async def list_evaluations(
        self,
        limit: int = 20,
        after: Optional[str] = None,
        eval_type: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Tuple[List[Dict], bool]:
        """
        List evaluations with pagination and filtering.

        Args:
            limit: Maximum number of results
            after: Cursor for pagination
            eval_type: Filter by evaluation type
            created_by: Filter by creator

        Returns:
            Tuple of (evaluations list, has_more flag)
        """
        try:
            return self.db.list_evaluations(
                limit=limit,
                after=after,
                eval_type=eval_type,
                created_by=created_by
            )
        except Exception as e:
            logger.error(f"Failed to list evaluations: {e}")
            raise

    async def get_evaluation(self, eval_id: str) -> Optional[Dict[str, Any]]:
        """Get evaluation by ID"""
        try:
            return self.db.get_evaluation(eval_id)
        except Exception as e:
            logger.error(f"Failed to get evaluation {eval_id}: {e}")
            raise

    async def update_evaluation(
        self,
        eval_id: str,
        updates: Dict[str, Any],
        updated_by: str = "system"
    ) -> Optional[Dict[str, Any]]:
        """Update evaluation definition and return the updated record.

        The underlying DB method returns a boolean. For API correctness and
        caller convenience, fetch and return the updated evaluation object
        when the update succeeds, or None if not found/updated.
        """
        try:
            success = self.db.update_evaluation(eval_id, updates)

            if not success:
                return None

            # Audit on success
            try:
                log_evaluation_updated(user_id=updated_by, eval_id=eval_id, updates=updates)
            except Exception:
                # Best-effort audit logging should not break the flow
                pass

            # Return the updated evaluation
            updated = self.db.get_evaluation(eval_id)
            return updated

        except Exception as e:
            logger.error(f"Failed to update evaluation {eval_id}: {e}")
            raise

    async def delete_evaluation(
        self,
        eval_id: str,
        deleted_by: str = "system"
    ) -> bool:
        """Soft delete an evaluation"""
        try:
            success = self.db.delete_evaluation(eval_id)

            if success:
                log_evaluation_deleted(user_id=deleted_by, eval_id=eval_id)

            return success

        except Exception as e:
            logger.error(f"Failed to delete evaluation {eval_id}: {e}")
            raise

    # ============= Run Management =============

    async def create_run(
        self,
        eval_id: str,
        target_model: str,
        config: Optional[Dict] = None,
        dataset_override: Optional[Dict] = None,
        webhook_url: Optional[str] = None,
        created_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Create and start an evaluation run.

        Args:
            eval_id: ID of evaluation to run
            target_model: Model to evaluate
            config: Run configuration
            dataset_override: Optional dataset override
            webhook_url: Optional webhook for notifications
            created_by: User creating the run

        Returns:
            Run object with status and ID
        """
        try:
            # Get evaluation
            evaluation = await self.get_evaluation(eval_id)
            if not evaluation:
                raise ValueError(f"Evaluation {eval_id} not found")

            # Create run record
            run_id = self.db.create_run(
                eval_id=eval_id,
                target_model=target_model,
                config=config or {},
                webhook_url=webhook_url
            )

            # Send webhook for run started
            if webhook_url and self.enable_webhooks:
                from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
                await webhook_manager.send_webhook(
                    user_id=created_by,
                    event=WebhookEvent.EVALUATION_STARTED,
                    evaluation_id=run_id,
                    data={
                        "eval_id": eval_id,
                        "target_model": target_model,
                        "eval_type": evaluation["eval_type"]
                    }
                )

            # Prepare evaluation config
            eval_config = {
                "eval_type": evaluation["eval_type"],
                "eval_spec": evaluation["eval_spec"],
                "dataset_id": evaluation.get("dataset_id"),
                "dataset_override": dataset_override,
                "config": config or {},
                "webhook_url": webhook_url
            }

            # Start async evaluation
            asyncio.create_task(
                self._run_evaluation_async(
                    run_id=run_id,
                    eval_id=eval_id,
                    eval_config=eval_config,
                    created_by=created_by
                )
            )

            # Unified audit
            log_run_started(user_id=created_by, run_id=run_id, eval_id=eval_id, target_model=target_model)

            # Return run info
            run = self.db.get_run(run_id)
            return run

        except Exception as e:
            logger.error(f"Failed to create run: {e}")
            raise

    async def _run_evaluation_async(
        self,
        run_id: str,
        eval_id: str,
        eval_config: Dict,
        created_by: str
    ):
        """Run evaluation asynchronously"""
        try:
            # Run evaluation with circuit breaker protection
            await self.circuit_breaker.call(
                self.runner.run_evaluation,
                run_id=run_id,
                eval_id=eval_id,
                eval_config=eval_config,
                background=False
            )

            # Send completion webhook
            if eval_config.get("webhook_url") and self.enable_webhooks and getattr(self, "webhook_manager", None):
                run = self.db.get_run(run_id)
                await self.webhook_manager.send_webhook(
                    user_id=created_by,
                    event=WebhookEvent.EVALUATION_COMPLETED,
                    evaluation_id=run_id,
                    data={
                        "run_id": run_id,
                        "status": run["status"],
                        "results": run.get("results")
                    }
                )

        except Exception as e:
            logger.error(f"Evaluation run {run_id} failed: {e}")

            # Update run status
            self.db.update_run_status(run_id, "failed", error_message=str(e))

            # Send failure webhook
            if eval_config.get("webhook_url") and self.enable_webhooks and getattr(self, "webhook_manager", None):
                await self.webhook_manager.send_webhook(
                    user_id=created_by,
                    event=WebhookEvent.EVALUATION_FAILED,
                    evaluation_id=run_id,
                    data={"error": str(e)}
                )

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run by ID"""
        try:
            return self.db.get_run(run_id)
        except Exception as e:
            logger.error(f"Failed to get run {run_id}: {e}")
            raise

    async def list_runs(
        self,
        eval_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        after: Optional[str] = None
    ) -> Tuple[List[Dict], bool]:
        """List runs with filtering"""
        try:
            runs, has_more = self.db.list_runs(
                eval_id=eval_id,
                status=status,
                limit=limit,
                after=after,
                return_has_more=True,
            )
            return runs, has_more
        except Exception as e:
            logger.error(f"Failed to list runs: {e}")
            raise

    async def cancel_run(self, run_id: str, cancelled_by: str = "system") -> bool:
        """Cancel a running evaluation"""
        try:
            # Try to cancel via runner
            success = self.runner.cancel_run(run_id)

            if not success:
                # Update status directly if not in runner
                self.db.update_run_status(run_id, "cancelled")

            log_run_cancelled(user_id=cancelled_by, run_id=run_id)

            return True

        except Exception as e:
            logger.error(f"Failed to cancel run {run_id}: {e}")
            raise

    # ============= Specialized Evaluations =============

    async def evaluate_geval(
        self,
        source_text: str,
        summary: str,
        metrics: Optional[List[str]] = None,
        api_name: str = "openai",
        api_key: Optional[str] = None,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Run G-Eval summarization evaluation.

        Args:
            source_text: Original text
            summary: Summary to evaluate
            metrics: Metrics to compute (default: all)
            api_name: LLM API to use
            api_key: Optional API key
            user_id: User running evaluation

        Returns:
            Evaluation results with metrics
        """
        try:
            start_time = time.time()

            # Track metrics
            # Lazy import to avoid heavy chat stack at module import time
            from tldw_Server_API.app.core.Evaluations.ms_g_eval import run_geval

            if advanced_metrics.enabled:
                with advanced_metrics.track_sli_request("/evaluations/geval"):
                    result = await asyncio.to_thread(
                        run_geval,
                        transcript=source_text,
                        summary=summary,
                        api_key=api_key,
                        api_name=api_name,
                        save=False
                    )
            else:
                result = await asyncio.to_thread(
                    run_geval,
                    transcript=source_text,
                    summary=summary,
                    api_key=api_key,
                    api_name=api_name,
                    save=False
                )

            # Parse and structure results
            evaluation_time = time.time() - start_time

            # Store in database
            eval_id = await self._store_evaluation_result(
                evaluation_type="geval",
                input_data={
                    "source_text": source_text[:1000],  # Truncate for storage
                    "summary": summary[:500]
                },
                results=result,
                metadata={
                    "api_name": api_name,
                    "evaluation_time": evaluation_time,
                    "user_id": user_id
                }
            )

            # Emit webhook for completion (await in TEST_MODE for deterministic tests)
            if self.enable_webhooks:
                try:
                    import os as _os, asyncio as _asyncio
                    from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
                    # Normalize single-user id to fixed numeric id when appropriate
                    effective_user_id = user_id
                    if user_id == "single_user":
                        try:
                            from tldw_Server_API.app.core.config import settings as _app_settings
                            effective_user_id = str(_app_settings.get("SINGLE_USER_FIXED_ID", "1"))
                        except Exception:
                            effective_user_id = "1"
                    if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
                        await webhook_manager.send_webhook(
                            user_id=effective_user_id,
                            event=WebhookEvent.EVALUATION_COMPLETED,
                            evaluation_id=eval_id,
                            data={
                                "evaluation_type": "geval",
                                "average_score": result.get("average_score", 0.0),
                                "processing_time": evaluation_time
                            }
                        )
                    else:
                        _asyncio.create_task(webhook_manager.send_webhook(
                            user_id=effective_user_id,
                            event=WebhookEvent.EVALUATION_COMPLETED,
                            evaluation_id=eval_id,
                            data={
                                "evaluation_type": "geval",
                                "average_score": result.get("average_score", 0.0),
                                "processing_time": evaluation_time
                            }
                        ))
                except Exception:
                    # Never fail the evaluation due to webhook issues
                    pass

            return {
                "evaluation_id": eval_id,
                "results": result,
                "evaluation_time": evaluation_time
            }

        except Exception as e:
            logger.error(f"G-Eval evaluation failed: {e}")
            raise

    async def evaluate_rag(
        self,
        query: str,
        contexts: List[str],
        response: str,
        ground_truth: Optional[str] = None,
        metrics: Optional[List[str]] = None,
        api_name: str = "openai",
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Run RAG system evaluation.

        Args:
            query: User query
            contexts: Retrieved contexts
            response: Generated response
            ground_truth: Optional expected answer
            metrics: Metrics to compute
            api_name: LLM API to use
            user_id: User running evaluation

        Returns:
            Evaluation results with metrics
        """
        try:
            start_time = time.time()

            # Run evaluation
            results = await self.get_rag_evaluator().evaluate(
                query=query,
                contexts=contexts,
                response=response,
                ground_truth=ground_truth,
                metrics=metrics,
                api_name=api_name
            )

            evaluation_time = time.time() - start_time

            # Store in database
            eval_id = await self._store_evaluation_result(
                evaluation_type="rag",
                input_data={
                    "query": query,
                    "num_contexts": len(contexts),
                    "response_length": len(response)
                },
                results=results,
                metadata={
                    "api_name": api_name,
                    "evaluation_time": evaluation_time,
                    "user_id": user_id
                }
            )

            # Emit webhook for completion (await in TEST_MODE for deterministic tests)
            if self.enable_webhooks:
                try:
                    import os as _os, asyncio as _asyncio
                    from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
                    effective_user_id = user_id
                    if user_id == "single_user":
                        try:
                            from tldw_Server_API.app.core.config import settings as _app_settings
                            effective_user_id = str(_app_settings.get("SINGLE_USER_FIXED_ID", "1"))
                        except Exception:
                            effective_user_id = "1"
                    if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
                        await webhook_manager.send_webhook(
                            user_id=effective_user_id,
                            event=WebhookEvent.EVALUATION_COMPLETED,
                            evaluation_id=eval_id,
                            data={
                                "evaluation_type": "rag",
                                "overall_score": results.get("overall_score", 0.0),
                                "processing_time": evaluation_time
                            }
                        )
                    else:
                        _asyncio.create_task(webhook_manager.send_webhook(
                            user_id=effective_user_id,
                            event=WebhookEvent.EVALUATION_COMPLETED,
                            evaluation_id=eval_id,
                            data={
                                "evaluation_type": "rag",
                                "overall_score": results.get("overall_score", 0.0),
                                "processing_time": evaluation_time
                            }
                        ))
                except Exception:
                    pass

            return {
                "evaluation_id": eval_id,
                "results": results,
                "evaluation_time": evaluation_time
            }

        except Exception as e:
            logger.error(f"RAG evaluation failed: {e}")
            raise

    async def evaluate_response_quality(
        self,
        prompt: str,
        response: str,
        expected_format: Optional[str] = None,
        custom_criteria: Optional[Dict] = None,
        api_name: str = "openai",
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Evaluate response quality.

        Args:
            prompt: Original prompt
            response: Generated response
            expected_format: Expected response format
            custom_criteria: Custom evaluation criteria
            api_name: LLM API to use
            user_id: User running evaluation

        Returns:
            Evaluation results with quality metrics
        """
        try:
            start_time = time.time()

            # Run evaluation
            results = await self.get_quality_evaluator().evaluate(
                prompt=prompt,
                response=response,
                expected_format=expected_format,
                custom_criteria=custom_criteria,
                api_name=api_name
            )

            evaluation_time = time.time() - start_time

            # Store in database
            eval_id = await self._store_evaluation_result(
                evaluation_type="response_quality",
                input_data={
                    "prompt": prompt[:500],
                    "response_length": len(response),
                    "expected_format": expected_format
                },
                results=results,
                metadata={
                    "api_name": api_name,
                    "evaluation_time": evaluation_time,
                    "user_id": user_id
                }
            )

            # Emit webhook for completion (await in TEST_MODE for deterministic tests)
            if self.enable_webhooks:
                try:
                    import os as _os, asyncio as _asyncio
                    from tldw_Server_API.app.core.Evaluations.webhook_manager import webhook_manager, WebhookEvent
                    effective_user_id = user_id
                    if user_id == "single_user":
                        try:
                            from tldw_Server_API.app.core.config import settings as _app_settings
                            effective_user_id = str(_app_settings.get("SINGLE_USER_FIXED_ID", "1"))
                        except Exception:
                            effective_user_id = "1"
                    if _os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes"):
                        await webhook_manager.send_webhook(
                            user_id=effective_user_id,
                            event=WebhookEvent.EVALUATION_COMPLETED,
                            evaluation_id=eval_id,
                            data={
                                "evaluation_type": "response_quality",
                                "overall_quality": results.get("overall_quality", 0.0),
                                "processing_time": evaluation_time
                            }
                        )
                    else:
                        _asyncio.create_task(webhook_manager.send_webhook(
                            user_id=effective_user_id,
                            event=WebhookEvent.EVALUATION_COMPLETED,
                            evaluation_id=eval_id,
                            data={
                                "evaluation_type": "response_quality",
                                "overall_quality": results.get("overall_quality", 0.0),
                                "processing_time": evaluation_time
                            }
                        ))
                except Exception:
                    pass

            return {
                "evaluation_id": eval_id,
                "results": results,
                "evaluation_time": evaluation_time
            }

        except Exception as e:
            logger.error(f"Response quality evaluation failed: {e}")
            raise

    async def evaluate_ocr(
        self,
        items: List[Dict[str, Any]],
        ocr_options: Optional[Dict[str, Any]] = None,
        metrics: Optional[List[str]] = None,
        thresholds: Optional[Dict[str, float]] = None,
        user_id: str = "system",
    ) -> Dict[str, Any]:
        """Evaluate OCR effectiveness for provided documents.

        Each item supports keys: id, pdf_path|pdf_bytes|extracted_text, ground_truth_text
        """
        try:
            start_time = time.time()

            results = await self.get_ocr_evaluator().evaluate(
                items=items,
                metrics=metrics,
                ocr_options=ocr_options,
                thresholds=thresholds,
            )

            evaluation_time = time.time() - start_time

            eval_id = await self._store_evaluation_result(
                evaluation_type="ocr",
                input_data={
                    "count": len(items),
                    "metrics": metrics or ["cer", "wer", "coverage", "page_coverage"],
                    "thresholds": thresholds or {},
                },
                results=results,
                metadata={
                    "evaluation_time": evaluation_time,
                    "user_id": user_id,
                },
            )

            return {
                "evaluation_id": eval_id,
                "results": results,
                "evaluation_time": evaluation_time,
            }
        except Exception as e:
            logger.error(f"OCR evaluation failed: {e}")
            raise

    async def evaluate_qa3(
        self,
        items: List[Dict[str, Any]],
        allowed_labels: Optional[List[str]] = None,
        label_mapping: Optional[Dict[str, str]] = None,
        generate_predictions: bool = False,
        api_name: str = "openai",
        temperature: float = 0.0,
        max_tokens: int = 3,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """Evaluate tri-label QA accuracy and PRF per label.

        If generate_predictions is True, uses LLM to produce predictions.
        Otherwise expects 'prediction' on each item.
        """
        allowed = [l.upper() for l in (allowed_labels or ["SUPPORTED","REFUTED","NEI"])]

        def norm_label(x: Optional[str]) -> Optional[str]:
            if x is None:
                return None
            s = str(x).strip()
            if label_mapping and s in label_mapping:
                s = label_mapping[s]
            s = s.upper()
            # normalize common variants
            aliases = {
                "TRUE": "SUPPORTED",
                "FALSE": "REFUTED",
                "NOT_ENTAILED": "NEI",
                "NOT_ENTAILMENT": "NEI",
            }
            s = aliases.get(s, s)
            return s

        def parse_prediction(text: str) -> Optional[str]:
            t = (text or "").upper()
            for lab in allowed:
                if lab in t:
                    return lab
            # try exact tokenization
            for lab in allowed:
                if t.strip() == lab:
                    return lab
            return None

        # Prompt builder
        def build_prompt(q: str, allowed_str: str, ctx: Optional[str]) -> str:
            p = (
                "You are a strict grader. Read the question and answer with exactly one token from the set.\n"
                f"Allowed labels: {allowed_str}. Respond with only one of these labels.\n\n"
            )
            if ctx:
                p += f"Context (optional):\n{ctx}\n\n"
            p += f"Question:\n{q}\n\nAnswer (one token):"
            return p

        # LLM call helper
        import tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib as sgl
        def call_llm(prompt: str) -> str:
            try:
                # use analyze(api_name, input_data, custom_prompt_arg, api_key, system_message, temp, streaming=False, recursive_summarization=False, chunked_summarization=False)
                result = sgl.analyze(api_name, prompt, None, None, "You output one token only.", temperature, False, False, False, None)
                if isinstance(result, tuple) and result:
                    return str(result[0])
                return str(result)
            except Exception as e:
                logger.error(f"LLM call failed in QA3: {e}")
                return ""

        # Compute predictions
        results = []
        for it in items:
            q = it.get("question", "")
            gold = norm_label(it.get("label"))
            pred = norm_label(it.get("prediction"))
            if generate_predictions or not pred:
                prompt = build_prompt(q, ", ".join(allowed), it.get("context"))
                raw = call_llm(prompt)
                parsed = parse_prediction(raw) or "NEI"
                pred = parsed
                results.append({"id": it.get("id"), "question": q, "gold": gold, "pred": pred, "raw": raw})
            else:
                results.append({"id": it.get("id"), "question": q, "gold": gold, "pred": pred})

        # Metrics
        cm: Dict[str, Dict[str, int]] = {g: {p: 0 for p in allowed} for g in allowed}
        total = 0
        correct = 0
        for r in results:
            g = r.get("gold") or "NEI"
            p = r.get("pred") or "NEI"
            if g not in cm:
                cm[g] = {lab: 0 for lab in allowed}
            if p not in cm[g]:
                for lab in cm:
                    cm[lab][p] = cm[lab].get(p, 0)
            cm[g][p] = cm[g].get(p, 0) + 1
            total += 1
            if g == p:
                correct += 1

        accuracy = (correct / total) if total else 0.0
        per_label = {}
        macro_f1 = 0.0
        for lab in allowed:
            tp = cm.get(lab, {}).get(lab, 0)
            fp = sum(cm[g].get(lab, 0) for g in cm if g != lab)
            fn = sum(cm[lab].get(p, 0) for p in cm[lab] if p != lab) if lab in cm else 0
            prec = tp / (tp + fp) if (tp + fp) else 0.0
            rec = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
            per_label[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": sum(cm.get(lab, {}).values())}
            macro_f1 += f1
        macro_f1 = macro_f1 / len(allowed) if allowed else 0.0

        # Pack results
        payload = {
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "per_label": per_label,
            "confusion_matrix": cm,
            "results": results,
        }

        # Store
        eval_id = await self._store_evaluation_result(
            evaluation_type="qa3",
            input_data={"count": len(items), "generate": generate_predictions, "allowed_labels": allowed},
            results=payload,
            metadata={"user_id": user_id}
        )

        return {"evaluation_id": eval_id, "results": payload}

    async def evaluate_propositions(
        self,
        extracted: List[str],
        reference: List[str],
        method: str = "semantic",
        threshold: float = 0.7,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """Evaluate proposition extraction against a reference set."""
        try:
            from tldw_Server_API.app.core.Chunking.utils.proposition_eval import evaluate_propositions as eval_props
            start = time.time()
            result = eval_props(extracted=extracted, reference=reference, method=method, threshold=threshold)
            evaluation_time = time.time() - start

            # Structure results as a dict
            results = {
                "metrics": {
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1": result.f1,
                    "claim_density_per_100_tokens": result.claim_density_per_100_tokens,
                    "avg_prop_len_tokens": result.avg_prop_len_tokens,
                    "dedup_rate": result.dedup_rate,
                },
                "counts": {
                    "matched": result.matched,
                    "total_extracted": result.total_extracted,
                    "total_reference": result.total_reference,
                },
                "details": result.details,
            }

            # Store result
            eval_id = await self._store_evaluation_result(
                evaluation_type="proposition_extraction",
                input_data={
                    "method": method,
                    "threshold": threshold,
                    "extracted_size": len(extracted),
                    "reference_size": len(reference),
                },
                results=results,
                metadata={
                    "user_id": user_id,
                    "evaluation_time": evaluation_time
                }
            )

            return {
                "evaluation_id": eval_id,
                "results": results,
                "evaluation_time": evaluation_time
            }

        except Exception as e:
            logger.error(f"Proposition evaluation failed: {e}")
            raise

    # ============= Dataset Management =============

    async def create_dataset(
        self,
        name: str,
        samples: List[Dict],
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        created_by: str = "system"
    ) -> str:
        """Create a new dataset"""
        try:
            dataset_id = self.db.create_dataset(
                name=name,
                description=description,
                samples=samples,
                created_by=created_by,
                metadata=metadata
            )

            log_dataset_created(user_id=created_by, dataset_id=dataset_id, name=name, samples=len(samples))

            return dataset_id

        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            raise

    async def list_datasets(
        self,
        limit: int = 20,
        after: Optional[str] = None,
        offset: int = 0
    ) -> Tuple[List[Dict], bool]:
        """List datasets with pagination"""
        try:
            return self.db.list_datasets(limit=limit, after=after, offset=offset)
        except Exception as e:
            logger.error(f"Failed to list datasets: {e}")
            raise

    async def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get dataset by ID"""
        try:
            return self.db.get_dataset(dataset_id)
        except Exception as e:
            logger.error(f"Failed to get dataset {dataset_id}: {e}")
            raise

    async def delete_dataset(
        self,
        dataset_id: str,
        deleted_by: str = "system"
    ) -> bool:
        """Delete a dataset"""
        try:
            success = self.db.delete_dataset(dataset_id)

            if success:
                log_dataset_deleted(user_id=deleted_by, dataset_id=dataset_id)

            return success

        except Exception as e:
            logger.error(f"Failed to delete dataset {dataset_id}: {e}")
            raise

    async def get_evaluation_history(
        self,
        user_id: str,
        evaluation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get evaluation history for a user.

        Args:
            user_id: User identifier
            evaluation_type: Optional filter by evaluation type
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of evaluation records
        """
        try:
            # Build filter criteria
            filters = {"user_id": user_id}

            if evaluation_type:
                filters["type"] = evaluation_type

            if start_date:
                filters["created_after"] = start_date.isoformat()

            if end_date:
                filters["created_before"] = end_date.isoformat()

            # Query database - list_evaluations only accepts limit, after, and eval_type
            # We need to filter results manually since the DB method doesn't support all filters
            evaluations, _ = self.db.list_evaluations(
                limit=limit + offset,  # Get more results to handle offset manually
                eval_type=evaluation_type,
                created_by=user_id
            )

            # Manual filtering for user_id and date ranges since DB method doesn't support these
            filtered_evaluations = []
            for eval in evaluations:
                # Filter by user_id if present in the record
                if user_id and eval.get("user_id") != user_id:
                    continue

                # Filter by date range if specified
                if start_date or end_date:
                    created_at_str = eval.get("created_at")
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                            if start_date and created_at < start_date:
                                continue
                            if end_date and created_at > end_date:
                                continue
                        except Exception as dt_err:
                            logger.debug(f"Failed to parse evaluation created_at timestamp: value={created_at_str}, error={dt_err}")

                filtered_evaluations.append(eval)

            # Apply offset and limit manually
            evaluations = filtered_evaluations[offset:offset + limit]

            return evaluations

        except Exception as e:
            logger.error(f"Failed to get evaluation history: {e}")
            raise

    async def count_evaluations(
        self,
        user_id: str,
        evaluation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """
        Count evaluations matching criteria.

        Args:
            user_id: User identifier
            evaluation_type: Optional filter by evaluation type
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Total count of matching evaluations
        """
        try:
            # Build filter criteria
            filters = {"user_id": user_id}

            if evaluation_type:
                filters["type"] = evaluation_type

            if start_date:
                filters["created_after"] = start_date.isoformat()

            if end_date:
                filters["created_before"] = end_date.isoformat()

            # Get count from database - since DB doesn't have count_evaluations, count manually
            # Get all evaluations and count them with filters
            evaluations, _ = self.db.list_evaluations(
                limit=10000,  # Large limit to get all
                eval_type=evaluation_type,
                created_by=user_id
            )

            # Manual filtering and counting
            count = 0
            for eval in evaluations:
                # Filter by user_id if present in the record
                if user_id and eval.get("user_id") != user_id:
                    continue

                # Filter by date range if specified
                if start_date or end_date:
                    created_at_str = eval.get("created_at")
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                            if start_date and created_at < start_date:
                                continue
                            if end_date and created_at > end_date:
                                continue
                        except Exception as dt_err:
                            logger.debug(f"Failed to parse evaluation created_at timestamp: value={created_at_str}, error={dt_err}")

                count += 1

            return count

        except Exception as e:
            logger.error(f"Failed to count evaluations: {e}")
            raise

    # ============= Helper Methods =============

    async def _store_evaluation_result(
        self,
        evaluation_type: str,
        input_data: Dict,
        results: Any,
        metadata: Dict
    ) -> str:
        """Store evaluation result in database using unified approach"""
        try:
            # Generate evaluation ID
            eval_id = f"eval_{evaluation_type}_{int(time.time() * 1000)}"

            # Store using unified method if available
            if hasattr(self.db, 'store_unified_evaluation'):
                success = self.db.store_unified_evaluation(
                    evaluation_id=eval_id,
                    name=f"{evaluation_type}_{int(time.time())}",
                    evaluation_type=evaluation_type,
                    input_data=input_data,
                    results=results if isinstance(results, dict) else {"result": results},
                    status="completed",
                    user_id=metadata.get("user_id", "system"),
                    metadata=metadata,
                    embedding_provider=metadata.get("embedding_provider"),
                    embedding_model=metadata.get("embedding_model")
                )
                if success:
                    logger.info(f"Stored evaluation {eval_id} in unified table")
                    return eval_id

            # Fallback to standard approach
            eval_id = self.db.create_evaluation(
                name=f"{evaluation_type}_{int(time.time())}",
                eval_type=evaluation_type,
                eval_spec={"type": evaluation_type, "input": input_data},
                created_by=metadata.get("user_id", "system"),
                metadata=metadata
            )

            # Create and complete a run with results
            run_id = self.db.create_run(
                eval_id=eval_id,
                target_model=metadata.get("api_name", "unknown"),
                config={}
            )

            # Update run with results
            self.db.update_run_status(run_id, "completed")
            self.db.update_run_progress(run_id, {"results": results})

            return eval_id

        except Exception as e:
            logger.error(f"Failed to store evaluation result: {e}")
            return f"temp_{int(time.time())}"

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get evaluation metrics summary"""
        try:
            if advanced_metrics.enabled:
                return advanced_metrics.get_summary()
            return {"metrics_enabled": False}
        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            # Do not expose internal error details to external clients
            return {"error": "Failed to collect metrics"}

    async def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        try:
            # Check database connectivity with a lightweight probe
            db_healthy = False
            try:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    _ = cur.fetchone()
                    db_healthy = True
            except Exception as db_err:
                logger.error(f"DB health probe failed: {db_err}")

            # Check circuit breaker
            from tldw_Server_API.app.core.Evaluations.circuit_breaker import CircuitState
            cb_healthy = self.circuit_breaker.state != CircuitState.OPEN

            return {
                "status": "healthy" if (db_healthy and cb_healthy) else "degraded",
                "database": "connected" if db_healthy else "disconnected",
                "circuit_breaker": "closed" if cb_healthy else "open",
                "uptime": time.time(),
                "version": "1.0.0"
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Singleton instance
_service_instance = None
_service_instances_lock = None

# LRU cache for per-user services to bound memory in long-lived servers
try:
    from collections import OrderedDict
except Exception:  # pragma: no cover - stdlib guard
    OrderedDict = dict  # type: ignore

_MAX_SERVICE_INSTANCES = 128
_service_instances_by_user: "OrderedDict[int, UnifiedEvaluationService]" = OrderedDict()  # type: ignore[name-defined]


def get_unified_evaluation_service(db_path: Optional[str] = None) -> UnifiedEvaluationService:
    """
    Get or create the unified evaluation service singleton.

    Args:
        db_path: Optional database path override

    Returns:
        UnifiedEvaluationService instance
    """
    global _service_instance

    if _service_instance is None:
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths as _DP
        _default_path = str(_DP.get_evaluations_db_path(_DP.get_single_user_id()))
        _service_instance = UnifiedEvaluationService(db_path or _default_path)

    return _service_instance


def get_unified_evaluation_service_for_user(user_id: int) -> UnifiedEvaluationService:
    """Get or create a per-user unified evaluation service bound to that user's DB."""
    # Lazy init lock to avoid import-time issues
    global _service_instances_lock
    if _service_instances_lock is None:
        import threading as _threading
        _service_instances_lock = _threading.Lock()

    with _service_instances_lock:
        # Return existing and mark as recently used
        if user_id in _service_instances_by_user:
            svc = _service_instances_by_user.pop(user_id)
            # If tests override the DB via env, ensure the cached instance matches
            try:
                import os as _os
                override_path = _os.getenv("EVALUATIONS_TEST_DB_PATH")
                if override_path and getattr(getattr(svc, "db", None), "db_path", None) != override_path:
                    # Replace with a new instance bound to the override path
                    svc = UnifiedEvaluationService(db_path=override_path)
            except Exception:
                pass
            _service_instances_by_user[user_id] = svc
            return svc

        # Create new service for this user
        db_path = str(DatabasePaths.get_evaluations_db_path(user_id))
        svc = UnifiedEvaluationService(db_path=db_path)
        _service_instances_by_user[user_id] = svc

        # Evict least-recently-used if over capacity
        if hasattr(_service_instances_by_user, "popitem") and len(_service_instances_by_user) > _MAX_SERVICE_INSTANCES:  # type: ignore[attr-defined]
            try:
                old_user_id, old_svc = _service_instances_by_user.popitem(last=False)  # type: ignore[arg-type]
                # Best effort shutdown without blocking
                try:
                    import asyncio as _aio
                    if hasattr(old_svc, "shutdown"):
                        _aio.create_task(old_svc.shutdown())
                except Exception:
                    pass
            except Exception:
                pass
        return svc
