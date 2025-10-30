"""
mcts_optimizer.py
Full MCTS optimizer for Prompt Studio (tree search, UCT, contextual generation,
optional feedback refinement, and WS progress broadcasts).
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import math
from loguru import logger

from .prompt_executor import PromptExecutor
from .test_runner import TestRunner
from .optimization_engine import MetricType
from .prompt_quality import PromptQualityScorer
from .prompt_decomposer import PromptDecomposer
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.event_broadcaster import (
    EventBroadcaster,
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
    def __init__(self, db: PromptStudioDatabase, test_runner: TestRunner):
        self.db = db
        self.test_runner = test_runner
        self.executor = PromptExecutor(db)
        self.scorer = PromptQualityScorer(executor=self.executor)
        self.decomposer = PromptDecomposer()
        # Simple in-memory caches (bounded by usage patterns)
        self._rephrase_cache: Dict[Tuple[str, str], str] = {}
        self._eval_cache: Dict[str, float] = {}
        try:
            from .optimization_strategies import IterativeRefinementOptimizer  # noqa: WPS433
            self._refiner_cls = IterativeRefinementOptimizer
        except Exception:  # pragma: no cover
            self._refiner_cls = None

    class _Node:
        __slots__ = (
            "parent",
            "children",
            "children_by_bin",
            "segment_index",
            "system_text",
            "q_sum",
            "n_visits",
            "score_bin",
        )

        def __init__(self, *, parent: Optional["MCTSOptimizer._Node"], segment_index: int, system_text: str, score_bin: Optional[int] = None):
            self.parent = parent
            self.children: List["MCTSOptimizer._Node"] = []
            self.children_by_bin: Dict[int, "MCTSOptimizer._Node"] = {}
            self.segment_index = segment_index
            self.system_text = system_text
            self.q_sum = 0.0
            self.n_visits = 0
            self.score_bin = score_bin if score_bin is not None else -1

        def uct(self, *, exploration_c: float) -> float:
            if self.n_visits == 0:
                return float("inf")
            parent_visits = self.parent.n_visits if self.parent is not None else max(1, self.n_visits)
            exploitation = self.q_sum / max(1, self.n_visits)
            exploration = exploration_c * math.sqrt(math.log(max(1, parent_visits)) / self.n_visits)
            return exploitation + exploration

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
        params = strategy_params or {}
        n_sims = int(params.get("mcts_simulations") or max_iterations or 20)
        early_no_improve = int(params.get("early_stop_no_improve") or 5)
        min_quality = float(params.get("min_quality") or 0.0)
        exploration_c = float(params.get("mcts_exploration_c") or 1.4)
        max_depth = int(params.get("mcts_max_depth") or 4)
        k_candidates = int(params.get("prompt_candidates_per_node") or 3)
        score_bin_size = float(params.get("score_dedup_bin") or 0.1)
        token_budget = int(params.get("token_budget") or 0)  # 0 => unlimited
        scorer_model = params.get("scorer_model")
        feedback_enabled = bool(params.get("feedback_enabled", True))
        feedback_threshold = float(params.get("feedback_threshold", 6.0))
        feedback_max_retries = int(params.get("feedback_max_retries", 2))

        # Configure scorer
        if scorer_model:
            try:
                self.scorer.set_model(str(scorer_model))
            except Exception:
                pass

        # Token accounting
        self._tokens_spent = 0
        def _add_tokens(n: int):
            try:
                self._tokens_spent += int(n or 0)
            except Exception:
                pass
        self.scorer.set_token_callback(_add_tokens)

        logger.info(
            "MCTS starting: prompt=%s sims=%s depth=%s c=%.2f",
            initial_prompt_id,
            n_sims,
            max_depth,
            exploration_c,
        )

        base_prompt = self._get_prompt(initial_prompt_id)
        base_system = (base_prompt.get("system_prompt") or "").strip()
        base_user = base_prompt.get("user_prompt") or ""
        segments = self.decomposer.decompose_text(base_system + ("\n\n" + base_user if base_user else ""))

        root = self._Node(parent=None, segment_index=0, system_text=base_system, score_bin=None)

        # Baseline evaluation
        best_prompt_id = initial_prompt_id
        best_score = await self._evaluate_prompt(initial_prompt_id, test_case_ids, model_config, target_metric)
        initial_score = best_score

        iteration_history: List[Dict[str, Any]] = []
        no_improve_streak = 0

        broadcaster = None
        if ws_connection_manager is not None and optimization_id is not None:
            broadcaster = EventBroadcaster(ws_connection_manager, self.db)

        for sim in range(1, n_sims + 1):
            if token_budget and self._tokens_spent >= token_budget:
                logger.info("MCTS token budget exhausted: %s >= %s", self._tokens_spent, token_budget)
                break
            # Selection & Expansion
            path: List[MCTSOptimizer._Node] = [root]
            node = root
            while True:
                depth = node.segment_index
                if depth >= len(segments) or depth >= max_depth:
                    break
                if len(node.children) < k_candidates:
                    child = await self._expand_node(
                        node,
                        segment=segments[depth],
                        base_user=base_user,
                        k_candidates=k_candidates,
                        score_bin_size=score_bin_size,
                        min_quality=min_quality,
                    )
                    if child is not None:
                        node = child
                        path.append(node)
                        continue
                if node.children:
                    node = max(node.children, key=lambda ch: ch.uct(exploration_c=exploration_c))
                    path.append(node)
                    continue
                break

            # Simulation/Evaluation at leaf
            eval_system = node.system_text
            score, prompt_id = await self._evaluate_with_feedback(
                base_prompt=base_prompt,
                system_text=eval_system,
                user_text=base_user,
                test_case_ids=test_case_ids,
                model_config=model_config,
                target_metric=target_metric,
                feedback_enabled=feedback_enabled,
                feedback_threshold=feedback_threshold,
                feedback_max_retries=feedback_max_retries,
            )

            # Backpropagate
            for p in path:
                p.n_visits += 1
                p.q_sum += float(score)

            # Update best and record
            iteration_history.append({
                "simulation": sim,
                "prompt_id": prompt_id,
                "score": score,
                "improvement": score - best_score,
            })
            if score > best_score:
                best_score = score
                best_prompt_id = prompt_id
                no_improve_streak = 0
            else:
                no_improve_streak += 1
                if no_improve_streak >= early_no_improve:
                    logger.info("MCTS early stop: no improvement for %s sims", early_no_improve)
                    break

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

        return {
            "initial_prompt_id": initial_prompt_id,
            "optimized_prompt_id": best_prompt_id,
            "initial_score": initial_score,
            "final_score": best_score,
            "improvement": best_score - initial_score,
            "iterations": len(iteration_history),
            "iteration_history": iteration_history,
            "strategy": "MCTS",
        }

    async def _expand_node(
        self,
        node: "MCTSOptimizer._Node",
        *,
        segment: str,
        base_user: str,
        k_candidates: int,
        score_bin_size: float,
        min_quality: float,
    ) -> Optional["MCTSOptimizer._Node"]:
        candidates = await self._propose_candidates(node.system_text, segment, k_candidates)
        if not candidates:
            return None
        best_existing: Optional[MCTSOptimizer._Node] = None
        best_existing_score = -1.0
        for cand_system in candidates:
            q = await self.scorer.score_prompt_async(system_text=cand_system, user_text=base_user)
            if q < min_quality:
                continue
            bin_idx = PromptQualityScorer.score_to_bin(q, score_bin_size)
            if bin_idx in node.children_by_bin:
                ch = node.children_by_bin[bin_idx]
                if q > best_existing_score:
                    best_existing = ch
                    best_existing_score = q
                continue
            child = self._Node(parent=node, segment_index=node.segment_index + 1, system_text=cand_system, score_bin=bin_idx)
            node.children.append(child)
            node.children_by_bin[bin_idx] = child
            return child
        return best_existing

    async def _propose_candidates(self, system_so_far: str, segment_text: str, k: int) -> List[str]:
        proposals: List[str] = []
        improved = await self._rephrase_segment(system_so_far, segment_text)
        if improved:
            proposals.append(improved)
        suffix = "\n\nEnsure outputs strictly follow the required format and constraints."
        proposals.append((system_so_far + suffix).strip())
        suffix2 = "\n\nBefore responding, validate that all required fields are present."
        proposals.append((system_so_far + suffix2).strip())
        seen = set()
        uniq: List[str] = []
        for p in proposals:
            if p not in seen:
                uniq.append(p)
                seen.add(p)
            if len(uniq) >= k:
                break
        return uniq

    async def _rephrase_segment(self, system_text: str, segment_text: str) -> Optional[str]:
        if not system_text or not segment_text:
            return None
        cache_key = (system_text, segment_text)
        if cache_key in self._rephrase_cache:
            return self._rephrase_cache[cache_key]
        prompt = (
            "You are improving a system prompt for an assistant.\n"
            "Focus on the following segment, enhancing clarity, specificity, and constraint adherence,"
            " without changing the overall intent. Return the full revised system prompt.\n\n"
            f"Current system prompt:\n{system_text}\n\nSegment to improve:\n{segment_text}\n\n"
            "Revised system prompt:"
        )
        try:
            result = await self.executor._call_llm(
                provider="openai",
                model="gpt-3.5-turbo",
                prompt=prompt,
                parameters={"temperature": 0.5, "max_tokens": 600},
            )
            content = (result or {}).get("content", "").strip()
            try:
                self._tokens_spent += int((result or {}).get("tokens", 0) or 0)
            except Exception:
                pass
            if content:
                self._rephrase_cache[cache_key] = content
            return content or None
        except Exception:
            return None

    async def _evaluate_with_feedback(
        self,
        *,
        base_prompt: Dict[str, Any],
        system_text: str,
        user_text: str,
        test_case_ids: List[int],
        model_config: Dict[str, Any],
        target_metric: MetricType,
        feedback_enabled: bool,
        feedback_threshold: float,
        feedback_max_retries: int,
    ) -> Tuple[float, int]:
        # Caching by content to reduce repeated evaluations
        eval_cache_key = self._make_eval_cache_key(system_text, user_text, model_config, test_case_ids)
        cached = self._eval_cache.get(eval_cache_key)
        prompt_id = self._create_ephemeral_prompt_version(
            base_prompt=base_prompt,
            system_text=system_text,
            user_text=user_text,
        )
        if cached is not None:
            score = cached
        else:
            score = await self._evaluate_prompt(prompt_id, test_case_ids, model_config, target_metric)
            self._eval_cache[eval_cache_key] = score
        scaled = score * 10.0
        if not feedback_enabled or scaled >= feedback_threshold or not self._refiner_cls:
            return score, prompt_id
        refiner = self._refiner_cls(self.db, self.test_runner)
        best_score = score
        best_prompt_id = prompt_id
        for _ in range(max(0, feedback_max_retries)):
            try:
                result = await refiner.optimize(
                    prompt_id=best_prompt_id,
                    test_case_ids=test_case_ids,
                    model_config=model_config,
                    max_iterations=1,
                )
                cand_id = int(result.get("optimized_prompt_id", best_prompt_id))
                cand_score = await self._evaluate_prompt(cand_id, test_case_ids, model_config, target_metric)
                if cand_score > best_score:
                    best_score = cand_score
                    best_prompt_id = cand_id
                if best_score * 10.0 >= feedback_threshold:
                    break
            except Exception:
                break
        return best_score, best_prompt_id

    def _create_ephemeral_prompt_version(self, *, base_prompt: Dict[str, Any], system_text: str, user_text: str) -> int:
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
                base_prompt["project_id"],
                base_prompt.get("signature_id"),
                f"{base_prompt['name']} (MCTS)",
                system_text,
                user_text,
                (base_prompt.get("version_number") or 0) + 1,
                base_prompt.get("id"),
                self.db.client_id,
            ),
        )
        new_id = int(cursor.lastrowid)
        conn.commit()
        return new_id

    async def _evaluate_prompt(
        self,
        prompt_id: int,
        test_case_ids: List[int],
        model_config: Dict[str, Any],
        target_metric: MetricType,
    ) -> float:
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
                score = result["scores"].get(metric_key)
                if score is None:
                    score = result["scores"].get("aggregate_score", 0.0)
                scores.append(float(score))
        return sum(scores) / len(scores) if scores else 0.0

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
            logger.debug(f"mcts: rephrase failed: {e}")
            return None

    def _get_prompt(self, prompt_id: int) -> Dict[str, Any]:
        p = self.db.get_prompt(prompt_id)
        if not p:
            raise ValueError(f"Prompt {prompt_id} not found")
        return p

    @staticmethod
    def _make_eval_cache_key(system_text: str, user_text: str, model_config: Dict[str, Any], test_case_ids: List[int]) -> str:
        import hashlib, json
        h = hashlib.sha256()
        h.update(system_text.encode("utf-8", errors="ignore"))
        h.update(b"\0")
        h.update(user_text.encode("utf-8", errors="ignore"))
        h.update(b"\0")
        try:
            model_key = json.dumps(model_config, sort_keys=True, separators=(",", ":"))
        except Exception:
            model_key = str(model_config)
        h.update(model_key.encode("utf-8", errors="ignore"))
        h.update(b"\0")
        h.update(
            (",".join(str(int(x)) for x in sorted(test_case_ids or []))).encode("utf-8")
        )
        return h.hexdigest()
