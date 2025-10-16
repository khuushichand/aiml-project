# test_runner.py
# Runs test cases against prompts

import json
import asyncio
import time
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.Chat.Chat_Functions import chat_api_call

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
                messages=[
                    {"role": "system", "content": prompt.get("system_prompt")},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            actual_output = {"response": response[0] if response else ""}
            
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
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

        return {
            "id": stored_run.get("id"),
            "test_case_id": stored_run.get("test_case_id", test_case_id),
            "prompt_id": stored_run.get("prompt_id", prompt_id),
            "inputs": stored_run.get("inputs", inputs),
            "expected": stored_run.get("expected_outputs", expected),
            "actual": stored_run.get("outputs", actual_output),
            "model": stored_run.get("model_name", model),
        }
    
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
            
            return processed_results
        else:
            # Run tests sequentially
            results = []
            for test_id in test_case_ids:
                try:
                    result = await self.run_test_case(
                        prompt_id, test_id, model, temperature, max_tokens
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Test case {test_id} failed: {e}")
                    results.append({
                        "test_case_id": test_id,
                        "error": str(e)
                    })
            
            return results
