# evaluation_manager.py
# Manages evaluation runs for prompt testing

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
        """
        Run evaluation for a prompt against test cases.

        Args:
            prompt_id: ID of the prompt to evaluate
            test_case_ids: List of test case IDs to run
            model: LLM model to use
            temperature: Temperature setting
            max_tokens: Maximum tokens for response

        Returns:
            Evaluation results with metrics
        """
        prompt = self.db.get_prompt(prompt_id)
        if not prompt or prompt.get("deleted"):
            raise ValueError(f"Prompt {prompt_id} not found")

        test_cases = self.db.get_test_cases_by_ids(test_case_ids)
        if not test_cases:
            raise ValueError("No valid test cases provided for evaluation")

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

        eval_id = evaluation_record.get("id")
        eval_uuid = evaluation_record.get("uuid")
        _log = logger.bind(ps_component="evaluation_manager", evaluation_id=eval_id, evaluation_uuid=eval_uuid, prompt_id=prompt_id, project_id=prompt.get("project_id"))
        _log.info(
            "PS evaluation.sync.start test_cases={} model={} temperature={} max_tokens={}",
            len(test_case_ids),
            model,
            temperature,
            max_tokens,
        )

        # Run each test case
        results = []
        total_score = 0
        t0 = time.perf_counter()

        for test_case in test_cases:
            test_id = test_case.get("id")
            inputs = test_case.get("inputs") or {}
            expected = test_case.get("expected_outputs") or {}

            # Format prompt with inputs
            formatted_user_prompt = prompt.get("user_prompt") or ""
            for key, value in inputs.items():
                formatted_user_prompt = formatted_user_prompt.replace(f"{{{key}}}", str(value))

            # Call LLM
            try:
                t_case0 = time.perf_counter()
                messages_payload = []
                system_prompt = prompt.get("system_prompt")
                if system_prompt:
                    messages_payload.append({"role": "system", "content": system_prompt})
                messages_payload.append({"role": "user", "content": formatted_user_prompt})

                response = self._call_adapter_text(
                    provider=provider,
                    model=model,
                    messages_payload=messages_payload,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=api_key,
                    app_config=app_config,
                )

                actual_output = self._extract_response_text(response)
                _log.debug(
                    "PS evaluation.sync.test_done test_case_id={} duration_ms={}",
                    test_id,
                    int((time.perf_counter() - t_case0) * 1000),
                )

                # Simple scoring - exact match = 1.0, partial match = 0.5, no match = 0.0
                score = self._calculate_score(expected, {"response": actual_output})
                total_score += score

                results.append({
                    "test_case_id": test_id,
                    "inputs": inputs,
                    "expected": expected,
                    "actual": {"response": actual_output},
                    "score": score,
                    "passed": score >= 0.5
                })

            except Exception as e:
                _log.error("PS evaluation.sync.test_error test_case_id={} error={}", test_id, e)
                results.append({
                    "test_case_id": test_id,
                    "inputs": inputs,
                    "expected": expected,
                    "actual": {"error": str(e)},
                    "score": 0.0,
                    "passed": False
                })

        # Calculate metrics
        avg_score = total_score / len(results) if results else 0.0
        passed_count = sum(1 for r in results if r["passed"])
        duration_ms = int((time.perf_counter() - t0) * 1000)

        aggregate_metrics = {
            "average_score": avg_score,
            "total_tests": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "pass_rate": passed_count / len(results) if results else 0.0
        }

        # Update evaluation record
        self.db.update_evaluation(
            eval_id,
            {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "test_run_ids": [r["test_case_id"] for r in results],
                "aggregate_metrics": aggregate_metrics,
            },
        )

        _log.info(
            "PS evaluation.sync.done total_tests={} passed={} avg_score={} duration_ms={}",
            len(results),
            passed_count,
            round(avg_score, 3),
            duration_ms,
        )

        return {
            "id": eval_id,
            "uuid": eval_uuid,
            "project_id": prompt.get("project_id"),
            "prompt_id": prompt_id,
            "model": model,
            "status": "completed",
            "results": results,
            "metrics": aggregate_metrics
        }

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
