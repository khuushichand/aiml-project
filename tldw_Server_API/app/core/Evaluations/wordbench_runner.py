"""
WordBench Runner - Specialized runner for next token prediction analysis.

This module provides functionality to run WordBench evaluations,
capturing and analyzing next token predictions and their probabilities.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
from tldw_Server_API.app.core.Evaluations.benchmark_utils import NextTokenCapture
from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_local_llm
from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
from tldw_Server_API.app.core.config import load_and_log_configs

logger = logger


class WordBenchRunner:
    """Runner for WordBench next token prediction analysis."""

    def __init__(self, api_name: str = "openai", api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize WordBench runner.

        Args:
            api_name: Name of the API to use (openai, local-llm, etc.)
            api_key: API key if required
            model: Optional model override for adapter-backed providers
        """
        self.api_name = api_name
        self.api_key = api_key
        self.model = model
        self.capture = NextTokenCapture(top_k=10)

    async def analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """Analyze a single prompt for next token predictions.

        Args:
            prompt: The input prompt to analyze

        Returns:
            Dict containing token predictions and analysis
        """
        try:
            # Format request for logprob capture
            request = self.capture.format_request(prompt)

            # Call the appropriate API
            if self.api_name == "openai":
                response = await self._call_openai(request)
            elif self.api_name.startswith("local"):
                response = await self._call_local_llm(request)
            else:
                raise ValueError(f"Unsupported API: {self.api_name}")

            # Parse logprobs from response
            logprobs_data = self.capture.parse_logprobs(response)

            # Analyze the distribution
            analysis = self.capture.analyze_distribution(logprobs_data)

            return {
                "prompt": prompt,
                "logprobs": logprobs_data,
                "analysis": analysis,
                "display": self.capture.format_display(prompt, logprobs_data, analysis)
            }

        except Exception as e:
            logger.error(f"Error analyzing prompt '{prompt}': {e}")
            return {
                "prompt": prompt,
                "error": str(e),
                "logprobs": None,
                "analysis": None
            }

    async def _call_openai(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call OpenAI API with logprob request.

        Note: OpenAI's newer models may not support logprobs directly.
        This uses the adapter-backed chat completions path with logprobs enabled.
        """
        adapter = get_registry().get_adapter("openai")
        if adapter is None:
            raise ChatConfigurationError(provider="openai", message="OpenAI adapter unavailable.")

        cfg = load_and_log_configs() or {}
        cfg_model = (cfg.get("openai_api") or {}).get("model")
        model = self.model or cfg_model or "gpt-4o-mini"

        logprobs_val = request.get("logprobs")
        top_logprobs = None
        if isinstance(logprobs_val, int):
            top_logprobs = logprobs_val

        response = await adapter.achat(
            {
                "messages": [{"role": "user", "content": request["prompt"]}],
                "model": model,
                "api_key": self.api_key,
                "temperature": request.get("temperature"),
                "max_tokens": request.get("max_tokens"),
                "logprobs": bool(top_logprobs),
                "top_logprobs": top_logprobs,
                "stream": False,
            }
        )

        return response

    async def _call_local_llm(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call local LLM with logprob request.

        This assumes the local LLM supports logprob return.
        """
        # Format for local LLM that supports logprobs
        response = await asyncio.to_thread(
            chat_with_local_llm,
            request["prompt"],
            "",  # No system message
            "",  # No API endpoint override
            model_name="",  # Use default
            temperature=request["temperature"],
            max_tokens=request["max_tokens"],
            custom_prompt_input="",
            stream=False,
            logprobs=request.get("logprobs", 0)  # Request logprobs
        )

        return response

    async def run_benchmark(self, prompts: List[str],
                           output_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run WordBench on a list of prompts.

        Args:
            prompts: List of prompts to analyze
            output_file: Optional file to save results

        Returns:
            List of analysis results
        """
        results = []

        for prompt in prompts:
            logger.info(f"Analyzing prompt: {prompt}")
            result = await self.analyze_prompt(prompt)
            results.append(result)

            # Print display format if successful
            if "display" in result and result["display"]:
                print("\n" + result["display"] + "\n")

        # Save results if requested
        if output_file:
            self._save_results(results, output_file)

        return results

    def _save_results(self, results: List[Dict[str, Any]], output_file: str):
        """Save results to file.

        Args:
            results: List of analysis results
            output_file: Path to output file
        """
        # Prepare data for JSON serialization
        output_data = {
            "benchmark": "wordbench",
            "api": self.api_name,
            "num_prompts": len(results),
            "results": []
        }

        for result in results:
            # Extract serializable data
            result_data = {
                "prompt": result["prompt"],
                "error": result.get("error"),
                "generated_token": result.get("logprobs", {}).get("generated_token") if result.get("logprobs") else None,
                "top_tokens": result.get("logprobs", {}).get("top_tokens") if result.get("logprobs") else None,
                "analysis": result.get("analysis")
            }
            output_data["results"].append(result_data)

        # Save to file
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Results saved to {output_file}")

    @staticmethod
    def load_prompts_from_file(file_path: str) -> List[str]:
        """Load prompts from a text file.

        Args:
            file_path: Path to file containing prompts (one per line)

        Returns:
            List of prompts
        """
        prompts = []
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip comments
                    prompts.append(line)
        return prompts

    @staticmethod
    def compare_distributions(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare token distributions across multiple prompts.

        Args:
            results: List of analysis results

        Returns:
            Comparison analysis
        """
        comparison = {
            "total_prompts": len(results),
            "avg_entropy": 0.0,
            "avg_top_probability": 0.0,
            "concentration_distribution": {"high": 0, "medium": 0, "low": 0},
            "most_uncertain_prompt": None,
            "most_certain_prompt": None
        }

        valid_results = [r for r in results if r.get("analysis") and not r.get("error")]

        if not valid_results:
            return comparison

        entropies = []
        top_probs = []

        for result in valid_results:
            analysis = result["analysis"]
            entropies.append(analysis["entropy"])
            top_probs.append(analysis["top_probability"])
            comparison["concentration_distribution"][analysis["concentration"]] += 1

        comparison["avg_entropy"] = sum(entropies) / len(entropies)
        comparison["avg_top_probability"] = sum(top_probs) / len(top_probs)

        # Find most/least certain prompts
        if entropies:
            max_entropy_idx = entropies.index(max(entropies))
            min_entropy_idx = entropies.index(min(entropies))

            comparison["most_uncertain_prompt"] = {
                "prompt": valid_results[max_entropy_idx]["prompt"],
                "entropy": entropies[max_entropy_idx],
                "top_token": valid_results[max_entropy_idx]["analysis"]["top_token"]
            }

            comparison["most_certain_prompt"] = {
                "prompt": valid_results[min_entropy_idx]["prompt"],
                "entropy": entropies[min_entropy_idx],
                "top_token": valid_results[min_entropy_idx]["analysis"]["top_token"]
            }

        return comparison


async def main():
    """Example usage of WordBench."""
    # Example prompts
    prompts = [
        "The sky is",
        "I am on my way to",
        "Once upon a time",
        "The capital of France is",
        "Water freezes at"
    ]

    # Create runner
    runner = WordBenchRunner(api_name="openai")

    # Run benchmark
    results = await runner.run_benchmark(prompts, output_file="wordbench_results.json")

    # Compare distributions
    comparison = WordBenchRunner.compare_distributions(results)
    print("\nComparison Analysis:")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
