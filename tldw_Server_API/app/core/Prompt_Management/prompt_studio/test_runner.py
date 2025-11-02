# test_runner.py
# Runs test cases against prompts

import json
import asyncio
import time
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.Chat.chat_orchestrator import chat_api_call
from .program_evaluator import ProgramEvaluator

class TestRunner:
    """Runs test cases against prompts using LLM."""

    def __init__(self, db_manager):
        """
        Initialize test runner.

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager

    async def run_test_case(
        self,
        prompt_id: int,
        test_case_id: int,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        Run a single test case against a prompt.

        Args:
            prompt_id: ID of the prompt
            test_case_id: ID of the test case
            model: LLM model to use
            temperature: Temperature setting
            max_tokens: Maximum tokens

        Returns:
            Test run result
        """
        start_time = time.time()
        _log = logger.bind(ps_component="test_runner", prompt_id=prompt_id, test_case_id=test_case_id, model=model)
        _log.info("PS testrun.start temperature={} max_tokens={}", temperature, max_tokens)
        prompt = self.db.get_prompt(prompt_id)
        if not prompt or prompt.get("deleted"):
            raise ValueError(f"Prompt {prompt_id} not found")

        test_case = self.db.get_test_case(test_case_id)
        if not test_case:
            raise ValueError(f"Test case {test_case_id} not found")

        inputs = test_case.get("inputs") or {}
        expected = test_case.get("expected_outputs") or {}

        # Format prompt with inputs
        user_prompt = prompt.get("user_prompt", "")
        for key, value in inputs.items():
            user_prompt = user_prompt.replace(f"{{{key}}}", str(value))

        # Call LLM
        try:
            response = await asyncio.to_thread(
                chat_api_call,
                api_endpoint="openai",
                model=model,
                messages_payload=[
                    {"role": "system", "content": prompt.get("system_prompt")},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )

            actual_output = {"response": response[0] if response else ""}
            _log.info("PS testrun.llm.done time_ms={}", int((time.time() - start_time) * 1000))

        except Exception as e:
            _log.error("PS testrun.llm.error error={} time_ms={}", e, int((time.time() - start_time) * 1000))
            actual_output = {"error": str(e)}

        execution_time_ms = int((time.time() - start_time) * 1000)
        tokens_used = None

        stored_run = self.db.create_test_run(
            project_id=prompt.get("project_id") or test_case.get("project_id"),
            prompt_id=prompt_id,
            test_case_id=test_case_id,
            model_name=model,
            model_params={"temperature": temperature, "max_tokens": max_tokens},
            inputs=inputs,
            outputs=actual_output,
            expected_outputs=expected,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            client_id=self.db.client_id,
        )
        _log.info("PS testrun.persisted id={} exec_ms={}", stored_run.get("id"), execution_time_ms)

        return {
            "id": stored_run.get("id"),
            "test_case_id": stored_run.get("test_case_id", test_case_id),
            "prompt_id": stored_run.get("prompt_id", prompt_id),
            "inputs": stored_run.get("inputs", inputs),
            "expected": stored_run.get("expected_outputs", expected),
            "actual": stored_run.get("outputs", actual_output),
            "model": stored_run.get("model_name", model),
        }

    async def run_single_test(
        self,
        *,
        prompt_id: int,
        test_case_id: int,
        model_config: Dict[str, Any],
        metrics: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Compatibility wrapper used by optimizers.

        Executes a single test case using model_config and returns a dict that
        includes a simple 'scores' map for downstream selection logic.
        """
        params = (model_config or {}).get("parameters", {})
        model = (model_config or {}).get("model", "gpt-3.5-turbo")
        temperature = float(params.get("temperature", 0.7)) if params is not None else 0.7
        max_tokens = int(params.get("max_tokens", 1000)) if params is not None else 1000

        _log = logger.bind(ps_component="test_runner", prompt_id=prompt_id, test_case_id=test_case_id, model=model)
        _log.info("PS single_test.start temperature={} max_tokens={}", temperature, max_tokens)
        t0 = time.perf_counter()
        result = await self.run_test_case(
            prompt_id=prompt_id,
            test_case_id=test_case_id,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Determine if this is a program test case and if evaluator is enabled
        try:
            test_case = self.db.get_test_case(test_case_id)
        except Exception:
            test_case = None

        runner_hint = None
        if isinstance(test_case, dict):
            runner_hint = (
                (test_case.get("expected_outputs") or {}).get("runner")
                or (test_case.get("expected_outputs") or {}).get("_runner")
                or (test_case.get("inputs") or {}).get("runner")
                or (test_case.get("inputs") or {}).get("_runner")
            )

        if str(runner_hint or "").lower() == "python":
            # Sandboxed program evaluator (feature-gated per project)
            pe = ProgramEvaluator()
            try:
                project_id = (self.db.get_prompt(prompt_id) or {}).get("project_id")
            except Exception:
                project_id = None
            eval_res = pe.evaluate(
                project_id=project_id,
                db=self.db,
                llm_output=result.get("actual", {}).get("response", ""),
                spec=(self.db.get_test_case(test_case_id) or {}).get("expected_outputs") or {},
            )
            reward = eval_res.reward
            score = max(0.0, min(1.0, reward / 10.0))
            _log.info("PS single_test.code_eval reward={} score={}", round(reward, 3), round(score, 3))
        else:
            # Provide a basic aggregate score based on expected vs actual overlap
            expected = result.get("expected", {}) or {}
            actual = result.get("actual", {}) or {}
            exp = str(expected.get("response", "")).lower()
            act = str(actual.get("response", "")).lower()
            if not exp and not act:
                score = 0.0
            elif exp == act:
                score = 1.0
            elif exp and act and (exp in act or act in exp):
                score = 0.5
            else:
                # very rough token overlap
                ew = set(exp.split())
                aw = set(act.split())
                score = (len(ew & aw) / max(1, len(ew))) if ew else 0.0

        result = dict(result)
        result["success"] = True
        result["scores"] = {"aggregate_score": float(score)}
        _log.info(
            "PS single_test.done aggregate_score={} duration_ms={}",
            round(float(score), 3),
            int((time.perf_counter() - t0) * 1000),
        )
        return result

    async def run_multiple_tests(
        self,
        prompt_id: int,
        test_case_ids: List[int],
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        parallel: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Run multiple test cases.

        Args:
            prompt_id: ID of the prompt
            test_case_ids: List of test case IDs
            model: LLM model to use
            temperature: Temperature setting
            max_tokens: Maximum tokens
            parallel: Run tests in parallel

        Returns:
            List of test run results
        """
        if parallel:
            # Run tests concurrently
            _log = logger.bind(ps_component="test_runner", prompt_id=prompt_id, total_tests=len(test_case_ids))
            _log.info("PS testrun.multi.start mode=parallel total_tests={}", len(test_case_ids))
            tasks = [
                self.run_test_case(prompt_id, test_id, model, temperature, max_tokens)
                for test_id in test_case_ids
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Test case {test_case_ids[i]} failed: {result}")
                    processed_results.append({
                        "test_case_id": test_case_ids[i],
                        "error": str(result)
                    })
                else:
                    processed_results.append(result)

            _log.info("PS testrun.multi.done mode=parallel ok={} failed={}", sum(1 for r in processed_results if not isinstance(r, dict) or not r.get("error")), sum(1 for r in processed_results if isinstance(r, dict) and r.get("error")))
            return processed_results
        else:
            # Run tests sequentially
            results = []
            _log = logger.bind(ps_component="test_runner", prompt_id=prompt_id, total_tests=len(test_case_ids))
            _log.info("PS testrun.multi.start mode=sequential total_tests={}", len(test_case_ids))
            for test_id in test_case_ids:
                try:
                    result = await self.run_test_case(
                        prompt_id, test_id, model, temperature, max_tokens
                    )
                    results.append(result)
                except Exception as e:
                    _log.error("PS testrun.multi.error test_case_id={} error={}", test_id, e)
                    results.append({
                        "test_case_id": test_id,
                        "error": str(e)
                    })
            ok = sum(1 for r in results if isinstance(r, dict) and not r.get("error"))
            failed = sum(1 for r in results if isinstance(r, dict) and r.get("error"))
            _log.info("PS testrun.multi.done mode=sequential ok={} failed={}", ok, failed)
            return results
