# mcts_optimizer.py
# Minimal MCTS-style optimizer skeleton for Prompt Studio (MVP)

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from loguru import logger

from .prompt_executor import PromptExecutor
from .test_runner import TestRunner
from .optimization_engine import MetricType
from .prompt_quality import PromptQualityScorer
from .prompt_decomposer import PromptDecomposer
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.event_broadcaster import (
    EventBroadcaster, EventType,
)
try:
    # Optional: shared WS connection manager if WS endpoints loaded
    from tldw_Server_API.app.api.v1.endpoints.prompt_studio_websocket import (
        connection_manager as ws_connection_manager,
    )
except Exception:  # pragma: no cover - optional in minimal builds
    ws_connection_manager = None
from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase


class MCTSOptimizer:
    """Lightweight, MVP optimizer that approximates MCTS-style exploration.

    This version focuses on iterative candidate generation with cheap scoring and
    selection of best variants. It intentionally avoids a full tree structure to
    keep the first integration minimal and safe, while preserving the external
    interface needed by OptimizationEngine.
    """

    def __init__(self, db: PromptStudioDatabase, test_runner: TestRunner):
        self.db = db
        self.test_runner = test_runner
        self.executor = PromptExecutor(db)
        self.scorer = PromptQualityScorer()
        self.decomposer = PromptDecomposer()

    async def optimize(
        self,
        *,
        initial_prompt_id: int,
        optimization_id: Optional[int] = None,
        test_case_ids: List[int],
        model_config: Dict[str, Any],
        max_iterations: int = 20,
        target_metric: MetricType = MetricType.ACCURACY,
        strategy_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a simplified MCTS-like optimization loop.

        Args:
            initial_prompt_id: Starting prompt ID
            test_case_ids: Test cases for evaluation
            model_config: Model configuration for execution
            max_iterations: Used as fallback for number of simulations
            target_metric: Metric to optimize (unused in MVP except for parity)
            strategy_params: Optional knobs for the search

        Returns:
            Result summary compatible with OptimizationEngine._update_optimization_results
        """
        params = strategy_params or {}
        n_sims = int(params.get("mcts_simulations") or max_iterations or 20)
        early_no_improve = int(params.get("early_stop_no_improve") or 5)
        min_quality = float(params.get("min_quality") or 0.0)

        logger.info(
            "MCTS(MVP) starting: prompt=%s sims=%s target_metric=%s",
            initial_prompt_id,
            n_sims,
            getattr(target_metric, "value", str(target_metric)),
        )

        # Evaluate baseline
        best_prompt_id = initial_prompt_id
        best_score = await self._evaluate_prompt(
            initial_prompt_id, test_case_ids, model_config, target_metric
        )
        initial_score = best_score

        iteration_history: List[Dict[str, Any]] = []
        no_improve_streak = 0

        broadcaster = None
        if ws_connection_manager is not None and optimization_id is not None:
            broadcaster = EventBroadcaster(ws_connection_manager, self.db)

        for sim in range(1, n_sims + 1):
            try:
                candidate_prompt_id = await self._create_prompt_variant(best_prompt_id)
            except Exception as e:  # defensive, continue search
                logger.debug(f"mcts(mvp): variant creation failed in sim {sim}: {e}")
                continue

            # Cheap quality check to avoid bad variants before evaluation
            try:
                cand = self._get_prompt(candidate_prompt_id)
                q = self.scorer.score_prompt(
                    system_text=cand.get("system_prompt") or "",
                    user_text=cand.get("user_prompt") or "",
                )
                if q < min_quality:
                    logger.debug(
                        "mcts(mvp): pruned low-quality variant (score=%.2f < %.2f)",
                        q,
                        min_quality,
                    )
                    # Broadcast pruned event
                    if broadcaster:
                        try:
                            await broadcaster.broadcast_optimization_iteration(
                                optimization_id=optimization_id,
                                iteration=sim,
                                max_iterations=n_sims,
                                current_metric=float(q) / 10.0,
                                best_metric=float(best_score),
                                extra={"event": "pruned_low_quality"},
                            )
                        except Exception:
                            pass
                    continue
            except Exception:
                # If scorer fails, continue without pruning
                pass

            score = await self._evaluate_prompt(
                candidate_prompt_id, test_case_ids, model_config, target_metric
            )

            iteration_history.append(
                {
                    "simulation": sim,
                    "prompt_id": candidate_prompt_id,
                    "score": score,
                    "improvement": score - best_score,
                }
            )

            if score > best_score:
                best_score = score
                best_prompt_id = candidate_prompt_id
                no_improve_streak = 0
            else:
                no_improve_streak += 1
                if no_improve_streak >= early_no_improve:
                    logger.info(
                        "MCTS(MVP) early stop at sim %s (no improvement for %s)",
                        sim,
                        early_no_improve,
                    )
                    break

            # Broadcast progress (best so far)
            if broadcaster:
                try:
                    await broadcaster.broadcast_optimization_iteration(
                        optimization_id=optimization_id,
                        iteration=sim,
                        max_iterations=n_sims,
                        current_metric=float(score),
                        best_metric=float(best_score),
                    )
                except Exception:
                    pass

        results = {
            "initial_prompt_id": initial_prompt_id,
            "optimized_prompt_id": best_prompt_id,
            "initial_score": initial_score,
            "final_score": best_score,
            "improvement": best_score - initial_score,
            "iterations": len(iteration_history),
            "iteration_history": iteration_history,
            "strategy": "MCTS",
        }
        return results

    async def _evaluate_prompt(
        self,
        prompt_id: int,
        test_case_ids: List[int],
        model_config: Dict[str, Any],
        target_metric: MetricType,
    ) -> float:
        """Evaluate prompt against test cases; return target metric or aggregate.

        MVP uses the TestRunner aggregate score and maps to [0..1]. If a specific
        MetricType is supplied that is not available, fall back to aggregate.
        """
        scores: List[float] = []
        metric_key = getattr(target_metric, "value", str(target_metric))

        for tc_id in test_case_ids:
            result = await self.test_runner.run_single_test(
                prompt_id=prompt_id,
                test_case_id=tc_id,
                model_config=model_config,
                metrics=[target_metric] if hasattr(target_metric, "value") else None,
            )
            if result.get("success") and "scores" in result:
                # Prefer named metric, otherwise aggregate_score
                score = result["scores"].get(metric_key)
                if score is None:
                    score = result["scores"].get("aggregate_score", 0.0)
                scores.append(float(score))

        return sum(scores) / len(scores) if scores else 0.0

    async def _create_prompt_variant(self, base_prompt_id: int) -> int:
        """Create a minor variant of the prompt by tweaking system instructions.

        MVP strategy: append a small clarity/formatting nudge or rephrase via LLM.
        """
        prompt = self._get_prompt(base_prompt_id)
        system = (prompt.get("system_prompt") or "").strip()
        user = prompt.get("user_prompt")

        # Try a light LLM rephrase of the system prompt; fall back to heuristic append
        new_system = await self._rephrase_instruction(system)
        if not new_system:
            suffix = "\n\nBe explicit, validate outputs, and adhere to constraints."
            new_system = (system + suffix).strip()

        # Insert as a new version/variant
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO prompt_studio_prompts (
                uuid, project_id, signature_id, name, system_prompt,
                user_prompt, version_number, parent_version_id, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"mcts-{datetime.utcnow().timestamp()}",
                prompt["project_id"],
                prompt.get("signature_id"),
                f"{prompt['name']} (MCTS)",
                new_system,
                user,
                (prompt.get("version_number") or 0) + 1,
                base_prompt_id,
                self.db.client_id,
            ),
        )
        new_prompt_id = cursor.lastrowid
        conn.commit()
        return int(new_prompt_id)

    async def _rephrase_instruction(self, instruction: str) -> Optional[str]:
        if not instruction:
            return None
        prompt = (
            "Rephrase these system instructions to be clearer and more precise, "
            "keeping the same intent.\n\n" + instruction + "\n\nRephrased:"
        )
        try:
            result = await self.executor._call_llm(
                provider="openai",
                model="gpt-3.5-turbo",
                prompt=prompt,
                parameters={"temperature": 0.5, "max_tokens": 300},
            )
            return (result or {}).get("content", "").strip() or None
        except Exception as e:
            logger.debug(f"mcts(mvp): rephrase failed: {e}")
            return None

    def _get_prompt(self, prompt_id: int) -> Dict[str, Any]:
        p = self.db.get_prompt(prompt_id)
        if not p:
            raise ValueError(f"Prompt {prompt_id} not found")
        return p
