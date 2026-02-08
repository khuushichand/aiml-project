# evaluation_manager.py
# Manages evaluation runs for prompt testing

import asyncio
import os
import time
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from ....core.Chat.Chat_Deps import ChatConfigurationError
from ....core.Chat.chat_helpers import extract_response_content
from ....core.LLM_Calls.adapter_utils import (
    ensure_app_config,
    get_adapter_or_raise,
    normalize_provider,
    resolve_provider_api_key_from_config,
    resolve_provider_model,
    split_system_message,
)
from ....core.testing import is_test_mode
from .test_runner import TestRunner


class EvaluationManager:
    """Manages prompt evaluation runs and metrics calculation."""

    def __init__(self, db_manager):
        """
        Initialize evaluation manager.

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager

    @staticmethod
    def _call_adapter_text(
        *,
        provider: str,
        messages_payload: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        api_key: Optional[str],
        model: Optional[str],
        app_config: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        if is_test_mode() or os.getenv("PYTEST_CURRENT_TEST") is not None:
            # Avoid external calls in test mode; return a deterministic placeholder.
            for msg in messages_payload or []:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    return str(msg.get("content", ""))
            return ""
        provider_name = normalize_provider(provider)
        if not provider_name:
            raise ChatConfigurationError(provider=provider, message="LLM provider is required.")
        cfg = ensure_app_config(app_config)
        resolved_model = model or resolve_provider_model(provider_name, cfg)
        if not resolved_model:
            raise ChatConfigurationError(provider=provider_name, message="Model is required for provider.")
        system_message, cleaned_messages = split_system_message(messages_payload or [])
        request: dict[str, Any] = {
            "messages": cleaned_messages,
            "system_message": system_message,
            "model": resolved_model,
            "api_key": api_key or resolve_provider_api_key_from_config(provider_name, cfg),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "app_config": cfg,
        }
        response = get_adapter_or_raise(provider_name).chat(request, timeout=timeout)
        return extract_response_content(response) or str(response)

    async def run_evaluation_with_existing_record(
        self,
        *,
        evaluation_id: int,
        prompt_id: int,
        test_case_ids: list[int],
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        provider: str = "openai",
        api_key: Optional[str] = None,
        app_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute an evaluation against an existing DB record.

        This method powers both synchronous and background evaluation paths so
        scoring behavior remains consistent with optimizers via TestRunner.
        """
        prompt = self.db.get_prompt(prompt_id)
        if not prompt or prompt.get("deleted"):
            raise ValueError(f"Prompt {prompt_id} not found")

        if test_case_ids:
            test_cases = self.db.get_test_cases_by_ids(test_case_ids)
            if not test_cases:
                raise ValueError("No valid test cases provided for evaluation")
        else:
            test_cases = []

        evaluation_record = self.db.get_evaluation(evaluation_id)
        if not evaluation_record:
            raise ValueError(f"Evaluation {evaluation_id} not found")

        eval_uuid = evaluation_record.get("uuid")
        _log = logger.bind(
            ps_component="evaluation_manager",
            evaluation_id=evaluation_id,
            evaluation_uuid=eval_uuid,
            prompt_id=prompt_id,
            project_id=prompt.get("project_id"),
        )
        _log.info(
            "PS evaluation.exec.start test_cases={} model={} temperature={} max_tokens={} provider={}",
            len(test_case_ids),
            model,
            temperature,
            max_tokens,
            provider,
        )

        runner = TestRunner(self.db)

        # Keep compatibility with existing tests that monkeypatch
        # EvaluationManager._call_adapter_text by routing TestRunner adapter calls through it.
        def _runner_adapter_bridge(
            *,
            provider: str,
            model: Optional[str],
            messages_payload: list[dict[str, Any]],
            system_message: Optional[str],
            temperature: float,
            max_tokens: int,
            app_config: Optional[dict[str, Any]] = None,
            api_key_override: Optional[str] = None,
        ) -> str:
            payload = list(messages_payload or [])
            if system_message:
                payload = [{"role": "system", "content": system_message}] + payload
            return self._call_adapter_text(
                provider=provider,
                model=model,
                messages_payload=payload,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key_override,
                app_config=app_config,
            )

        runner._call_adapter = _runner_adapter_bridge  # type: ignore[method-assign]

        model_config = {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "app_config": app_config,
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        }

        results: list[dict[str, Any]] = []
        test_run_ids: list[int] = []
        t0 = time.perf_counter()
        for test_case in test_cases:
            test_id = int(test_case.get("id"))
            try:
                t_case0 = time.perf_counter()
                run_result = await runner.run_single_test(
                    prompt_id=prompt_id,
                    test_case_id=test_id,
                    model_config=model_config,
                )
                score = float((run_result.get("scores") or {}).get("aggregate_score", 0.0))
                passed = score >= 0.5
                run_id = run_result.get("id")
                if isinstance(run_id, int):
                    test_run_ids.append(run_id)

                results.append(
                    {
                        "test_case_id": test_id,
                        "inputs": run_result.get("inputs") or test_case.get("inputs") or {},
                        "expected": run_result.get("expected") or test_case.get("expected_outputs") or {},
                        "actual": run_result.get("actual") or {},
                        "score": score,
                        "passed": passed,
                    }
                )
                _log.debug(
                    "PS evaluation.exec.test_done test_case_id={} duration_ms={} score={} passed={}",
                    test_id,
                    int((time.perf_counter() - t_case0) * 1000),
                    round(score, 4),
                    passed,
                )
            except Exception as e:
                _log.error("PS evaluation.exec.test_error test_case_id={} error={}", test_id, e)
                results.append(
                    {
                        "test_case_id": test_id,
                        "inputs": test_case.get("inputs") or {},
                        "expected": test_case.get("expected_outputs") or {},
                        "actual": {"error": str(e)},
                        "score": 0.0,
                        "passed": False,
                    }
                )

        passed_count = sum(1 for r in results if bool(r.get("passed")))
        total = len(results)
        avg_score = (sum(float(r.get("score", 0.0)) for r in results) / total) if total else 0.0
        duration_ms = int((time.perf_counter() - t0) * 1000)

        aggregate_metrics = {
            "average_score": avg_score,
            "total_tests": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "pass_rate": (passed_count / total) if total else 0.0,
        }

        self.db.update_evaluation(
            evaluation_id,
            {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "test_run_ids": test_run_ids,
                "aggregate_metrics": aggregate_metrics,
            },
        )

        _log.info(
            "PS evaluation.exec.done total_tests={} passed={} avg_score={} duration_ms={}",
            total,
            passed_count,
            round(avg_score, 3),
            duration_ms,
        )

        return {
            "id": evaluation_id,
            "uuid": eval_uuid,
            "project_id": prompt.get("project_id"),
            "prompt_id": prompt_id,
            "model": model,
            "status": "completed",
            "results": results,
            "metrics": aggregate_metrics,
            "test_run_ids": test_run_ids,
        }

    async def run_evaluation_async(
        self,
        prompt_id: int,
        test_case_ids: list[int],
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        provider: str = "openai",
        api_key: Optional[str] = None,
        app_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Create and run an evaluation asynchronously."""
        prompt = self.db.get_prompt(prompt_id)
        if not prompt or prompt.get("deleted"):
            raise ValueError(f"Prompt {prompt_id} not found")

        evaluation_record = self.db.create_evaluation(
            prompt_id=prompt_id,
            project_id=prompt.get("project_id"),
            model_configs={
                "provider": provider,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            test_case_ids=test_case_ids,
            client_id=self.db.client_id,
        )
        eval_id = int(evaluation_record.get("id"))
        return await self.run_evaluation_with_existing_record(
            evaluation_id=eval_id,
            prompt_id=prompt_id,
            test_case_ids=test_case_ids,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            provider=provider,
            api_key=api_key,
            app_config=app_config,
        )

    def run_evaluation(
        self,
        prompt_id: int,
        test_case_ids: list[int],
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        provider: str = "openai",
        api_key: Optional[str] = None,
        app_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Run evaluation for a prompt against test cases.

        This sync wrapper is kept for compatibility with existing call sites.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            raise RuntimeError(
                "run_evaluation cannot be called from an active event loop. "
                "Use `await run_evaluation_async(...)` instead."
            )
        return asyncio.run(
            self.run_evaluation_async(
                prompt_id=prompt_id,
                test_case_ids=test_case_ids,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                provider=provider,
                api_key=api_key,
                app_config=app_config,
            )
        )

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        if isinstance(response, list) and response:
            if isinstance(response[0], str):
                return response[0]
            if isinstance(response[0], dict):
                return EvaluationManager._extract_response_text(response[0])
        if isinstance(response, dict):
            choices = response.get("choices")
            if isinstance(choices, list):
                for choice in choices:
                    if not isinstance(choice, dict):
                        continue
                    message = choice.get("message") or {}
                    content = message.get("content")
                    if isinstance(content, list):
                        parts = [part.get("text", "") for part in content if isinstance(part, dict)]
                        content = "".join(parts)
                    if isinstance(content, str):
                        return content
                    delta = choice.get("delta") or {}
                    delta_content = delta.get("content")
                    if isinstance(delta_content, list):
                        parts = [part.get("text", "") for part in delta_content if isinstance(part, dict)]
                        delta_content = "".join(parts)
                    if isinstance(delta_content, str):
                        return delta_content
            content = response.get("content")
            if isinstance(content, str):
                return content
        return str(response)

    def _calculate_score(self, expected: dict, actual: dict) -> float:
        """
        Calculate similarity score between expected and actual outputs.

        Args:
            expected: Expected output dictionary
            actual: Actual output dictionary

        Returns:
            Score between 0.0 and 1.0
        """
        if not expected:
            return 1.0  # No expected output means any output is valid

        # Simple implementation - can be enhanced with better similarity metrics
        expected_str = str(expected.get("response", "")).lower().strip()
        actual_str = str(actual.get("response", "")).lower().strip()

        if expected_str == actual_str:
            return 1.0
        elif expected_str in actual_str or actual_str in expected_str:
            return 0.5
        else:
            # Calculate word overlap
            expected_words = set(expected_str.split())
            actual_words = set(actual_str.split())

            if not expected_words:
                return 0.0

            overlap = len(expected_words & actual_words)
            return overlap / len(expected_words)

    def get_evaluation(self, eval_id: int) -> Optional[dict[str, Any]]:
        """
        Get evaluation details by ID.

        Args:
            eval_id: Evaluation ID

        Returns:
            Evaluation record or None
        """
        return self.db.get_evaluation(eval_id)

    def list_evaluations(
        self,
        project_id: Optional[int] = None,
        prompt_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> dict[str, Any]:
        """
        List evaluations with filtering.

        Args:
            project_id: Filter by project
            prompt_id: Filter by prompt
            status: Filter by status
            page: Page number
            per_page: Items per page

        Returns:
            Dictionary with evaluations and pagination
        """
        return self.db.list_evaluations(
            project_id=project_id,
            prompt_id=prompt_id,
            status=status,
            page=page,
            per_page=per_page,
        )

    def compare_evaluations(self, eval_ids: list[int]) -> dict[str, Any]:
        """
        Compare multiple evaluation runs.

        Args:
            eval_ids: List of evaluation IDs to compare

        Returns:
            Comparison results
        """
        evaluations = []
        for eval_id in eval_ids:
            eval_data = self.get_evaluation(eval_id)
            if eval_data:
                evaluations.append(eval_data)

        if not evaluations:
            return {"error": "No evaluations found"}

        # Compare metrics
        comparison = {
            "evaluations": evaluations,
            "metrics_comparison": {
                "average_scores": [
                    e.get("aggregate_metrics", {}).get("average_score", 0)
                    for e in evaluations
                ],
                "pass_rates": [
                    e.get("aggregate_metrics", {}).get("pass_rate", 0)
                    for e in evaluations
                ],
                "best_performer": max(
                    evaluations,
                    key=lambda e: e.get("aggregate_metrics", {}).get("average_score", 0)
                )["id"] if evaluations else None
            }
        }

        return comparison
