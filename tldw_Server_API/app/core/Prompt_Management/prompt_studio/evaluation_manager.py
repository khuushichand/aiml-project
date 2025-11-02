# evaluation_manager.py
# Manages evaluation runs for prompt testing

from datetime import datetime
import time
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.Chat.chat_orchestrator import chat_api_call

class EvaluationManager:
    """Manages prompt evaluation runs and metrics calculation."""

    def __init__(self, db_manager):
        """
        Initialize evaluation manager.

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager

    def run_evaluation(
        self,
        prompt_id: int,
        test_case_ids: List[int],
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
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
            formatted_user_prompt = prompt.get("user_prompt", "")
            for key, value in inputs.items():
                formatted_user_prompt = formatted_user_prompt.replace(f"{{{key}}}", str(value))

            # Call LLM
            try:
                t_case0 = time.perf_counter()
                response = chat_api_call(
                    api_endpoint="openai",
                    model=model,
                    messages_payload=[
                        {"role": "system", "content": prompt.get("system_prompt")},
                        {"role": "user", "content": formatted_user_prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                actual_output = response[0] if response else ""
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

    def _calculate_score(self, expected: Dict, actual: Dict) -> float:
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

    def get_evaluation(self, eval_id: int) -> Optional[Dict[str, Any]]:
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
    ) -> Dict[str, Any]:
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

    def compare_evaluations(self, eval_ids: List[int]) -> Dict[str, Any]:
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
