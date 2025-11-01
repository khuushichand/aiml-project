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
from .types_common import MetricType
from .prompt_quality import PromptQualityScorer
from .prompt_decomposer import PromptDecomposer
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.event_broadcaster import (
    EventBroadcaster,
    EventType,
)
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.monitoring import (
    prompt_studio_metrics,
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
        ws_throttle_every = int(params.get("ws_throttle_every") or max(1, int(n_sims // 50) or 1))
        trace_top_k = int(params.get("trace_top_k") or 3)
        # Debugging/observability of decisions
        import os as _os
        debug_decisions = str(_os.getenv("PROMPT_STUDIO_MCTS_DEBUG_DECISIONS", "false")).lower() in {"1", "true", "yes", "on"}

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
        nodes_created = 0
        edges_created = 0
        parent_ids: set = set()
        t_start = datetime.utcnow()

        # Error/observability counters
        self._counters = {
            "prune_low_quality": 0,
            "prune_dedup": 0,
            "scorer_failures": 0,
            "evaluator_timeouts": 0,
        }
        # Collect top scored candidates per depth when debugging
        self._debug_top_by_depth: Dict[int, List[Dict[str, Any]]] = {} if debug_decisions else None

        broadcaster = None
        if ws_connection_manager is not None and optimization_id is not None:
            broadcaster = EventBroadcaster(ws_connection_manager, self.db)
            try:
                await broadcaster.broadcast_event(
                    event_type=EventType.OPTIMIZATION_STARTED,
                    data={
                        "optimization_id": optimization_id,
                        "strategy": "mcts",
                        "max_iterations": n_sims,
                    },
                    project_id=base_prompt.get("project_id"),
                )
            except Exception:
                pass

        best_eval_system: Optional[str] = None
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
                        nodes_created += 1
                        edges_created += 1
                        try:
                            parent_ids.add(id(node.parent))
                        except Exception:
                            pass
                        continue
                if node.children:
                    # Log selection decision (UCT) for observability
                    try:
                        if debug_decisions:
                            scored_children = [
                                (ch, ch.uct(exploration_c=exploration_c)) for ch in node.children
                            ]
                            chosen, chosen_uct = max(scored_children, key=lambda p: p[1])
                            logger.debug(
                                "mcts.select depth=%s chose_child_bin=%s uct=%.4f",
                                node.segment_index,
                                getattr(chosen, "score_bin", None),
                                float(chosen_uct),
                            )
                            node = chosen
                        else:
                            node = max(node.children, key=lambda ch: ch.uct(exploration_c=exploration_c))
                    except Exception:
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
                optimization_id=optimization_id,
            )

            # Backpropagate
            for p in path:
                p.n_visits += 1
                p.q_sum += float(score)

            # Update best and record
            # Compact system trace info
            import hashlib
            sys_hash = hashlib.sha256((eval_system or "").encode("utf-8", errors="ignore")).hexdigest()
            sys_preview = (eval_system or "")[:160]
            iter_entry = {
                "simulation": sim,
                "prompt_id": prompt_id,
                "score": score,
                "improvement": score - best_score,
                "system_hash": sys_hash,
                "system_preview": sys_preview,
            }
            iteration_history.append(iter_entry)
            improved = score > best_score
            if improved:
                best_score = score
                best_prompt_id = prompt_id
                no_improve_streak = 0
                best_eval_system = eval_system
            else:
                no_improve_streak += 1
                if no_improve_streak >= early_no_improve:
                    logger.info("MCTS early stop: no improvement for %s sims", early_no_improve)
                    break

            # Throttled WS + per-iteration persistence
            do_broadcast = (
                (sim == 1)
                or (sim == n_sims)
                or improved
                or (sim % ws_throttle_every == 0)
            )
            if broadcaster and do_broadcast:
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

            # Persist iteration record (throttled similarly to WS)
            if optimization_id is not None and do_broadcast:
                try:
                    self.db.record_optimization_iteration(
                        optimization_id,
                        iteration_number=sim,
                        prompt_variant={
                            "prompt_id": prompt_id,
                            "system_hash": sys_hash,
                            "system_preview": sys_preview,
                        },
                        metrics={
                            "score": float(score),
                            "best_metric": float(best_score),
                        },
                        tokens_used=int(self._tokens_spent),
                        note="mcts-iteration",
                    )
                except Exception:
                    pass

            # Cancellation check (if status changed to cancelled)
            if optimization_id is not None:
                try:
                    current = self.db.get_optimization(optimization_id)
                    if current and str(current.get("status")).lower() == "cancelled":
                        logger.info("MCTS detected cancellation; exiting loop")
                        break
                except Exception:
                    pass

        duration_ms = (datetime.utcnow() - t_start).total_seconds() * 1000.0
        parents_used = len(parent_ids) or 1
        avg_branching = float(edges_created) / float(parents_used)

        # Record metrics and error counters
        try:
            prompt_studio_metrics.record_mcts_summary(
                sims_total=len(iteration_history),
                tree_nodes=nodes_created,
                avg_branching=avg_branching,
                best_reward=float(best_score),
                tokens_spent=self._tokens_spent,
                duration_ms=duration_ms,
            )
        except Exception:
            pass
        # Emit error counters
        try:
            for key, val in (self._counters or {}).items():
                if not val:
                    continue
                # Map internal keys to error labels
                label = {
                    "prune_low_quality": "prune_low_quality",
                    "prune_dedup": "prune_dedup",
                    "scorer_failures": "scorer_failure",
                    "evaluator_timeouts": "evaluator_timeout",
                }.get(key, key)
                prompt_studio_metrics.record_mcts_error(error=label, count=int(val))
        except Exception:
            pass

        if broadcaster:
            try:
                await broadcaster.broadcast_event(
                    event_type=EventType.OPTIMIZATION_COMPLETED,
                    data={
                        "optimization_id": optimization_id,
                        "strategy": "mcts",
                        "iterations": len(iteration_history),
                        "final_score": float(best_score),
                        "tokens_spent": int(self._tokens_spent),
                    },
                    project_id=base_prompt.get("project_id"),
                )
            except Exception:
                pass

        # Build compact final trace: best path + top-K candidates
        top_candidates = sorted(iteration_history, key=lambda e: e.get("score", 0.0), reverse=True)[: max(1, trace_top_k)]
        final_trace = {
            "best_path": {
                "prompt_id": best_prompt_id,
                "system_hash": (top_candidates[0]["system_hash"] if top_candidates else None),
                "system_preview": (top_candidates[0]["system_preview"] if top_candidates else None),
                "depth": None,  # unknown without tracking full path; kept for schema stability
            },
            "top_candidates": [
                {
                    "simulation": tc.get("simulation"),
                    "prompt_id": tc.get("prompt_id"),
                    "score": tc.get("score"),
                    "system_hash": tc.get("system_hash"),
                    "system_preview": tc.get("system_preview"),
                }
                for tc in top_candidates
            ],
            "sims_total": len(iteration_history),
        }
        if debug_decisions and isinstance(self._debug_top_by_depth, dict):
            final_trace["debug_top_scores_by_depth"] = self._debug_top_by_depth

        result = {
            "initial_prompt_id": initial_prompt_id,
            "optimized_prompt_id": best_prompt_id,
            "initial_score": initial_score,
            "final_score": best_score,
            "improvement": best_score - initial_score,
            "iterations": len(iteration_history),
            "iteration_history": iteration_history,
            "strategy": "MCTS",
            "total_tokens": self._tokens_spent,
            "duration_ms": duration_ms,
            # Extra metrics/traces for engine to persist
            "final_metrics": {
                "score": float(best_score),
                "best_reward": float(best_score),
                "tree_nodes": nodes_created,
                "avg_branching": avg_branching,
                "tokens_spent": int(self._tokens_spent),
                "duration_ms": duration_ms,
                "trace": final_trace,
                "errors": dict(self._counters or {}),
                "applied_params": {
                    "mcts_max_depth": max_depth,
                    "prompt_candidates_per_node": k_candidates,
                    "mcts_exploration_c": exploration_c,
                },
            },
        }

        # Reset counters holder
        self._counters = None
        return result

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
        # Support both async and sync monkeypatching for _propose_candidates in tests
        try:
            maybe = self._propose_candidates(node.system_text, segment, k_candidates)
            if hasattr(maybe, "__await__") or hasattr(maybe, "__aiter__"):
                candidates = await maybe  # type: ignore[assignment]
            else:
                candidates = maybe  # type: ignore[assignment]
        except TypeError:
            # Fallback to direct await if attribute detection failed
            candidates = await self._propose_candidates(node.system_text, segment, k_candidates)
        if not candidates:
            return None
        best_existing: Optional[MCTSOptimizer._Node] = None
        best_existing_score = -1.0
        new_child: Optional[MCTSOptimizer._Node] = None
        scored: List[Tuple[str, float, int]] = []
        for cand_system in candidates:
            # DB-backed scorer cache (optional)
            try:
                key = "scorer:" + self.scorer._cache_key(cand_system, base_user)
                cached = self._db_cache_get(key)
            except Exception:
                cached = None
            if cached is not None:
                q = float(cached)
            else:
                try:
                    q = await self.scorer.score_prompt_async(system_text=cand_system, user_text=base_user)
                except Exception:
                    q = 0.0
                    try:
                        if hasattr(self, "_counters") and isinstance(self._counters, dict):
                            self._counters["scorer_failures"] = self._counters.get("scorer_failures", 0) + 1
                    except Exception:
                        pass
                try:
                    self._db_cache_set(key, q, ttl_sec=1800)
                except Exception:
                    pass
            try:
                bin_idx = PromptQualityScorer.score_to_bin(q, score_bin_size)
                scored.append((cand_system, q, bin_idx))
            except Exception:
                bin_idx = PromptQualityScorer.score_to_bin(q, score_bin_size)
            if q < min_quality:
                try:
                    if hasattr(self, "_counters") and isinstance(self._counters, dict):
                        self._counters["prune_low_quality"] = self._counters.get("prune_low_quality", 0) + 1
                except Exception:
                    pass
                continue
            if bin_idx in node.children_by_bin:
                ch = node.children_by_bin[bin_idx]
                if q > best_existing_score:
                    best_existing = ch
                    best_existing_score = q
                try:
                    if hasattr(self, "_counters") and isinstance(self._counters, dict):
                        self._counters["prune_dedup"] = self._counters.get("prune_dedup", 0) + 1
                except Exception:
                    pass
                continue
            # Create at most one child per expansion
            if new_child is None:
                child = self._Node(parent=node, segment_index=node.segment_index + 1, system_text=cand_system, score_bin=bin_idx)
                node.children.append(child)
                node.children_by_bin[bin_idx] = child
                new_child = child
            # Debug: record top scored candidates for this depth
            try:
                if isinstance(self._debug_top_by_depth, dict):
                    depth = node.segment_index
                    top = sorted(scored, key=lambda t: t[1], reverse=True)[:3]
                    self._debug_top_by_depth[depth] = [
                        {"score": float(s[1]), "bin": int(s[2]), "system_preview": (s[0] or "")[:160]}
                        for s in top
                    ]
            except Exception:
                pass
        # If no child added, still capture debug top scored at this depth
        try:
            if isinstance(self._debug_top_by_depth, dict) and scored:
                depth = node.segment_index
                top = sorted(scored, key=lambda t: t[1], reverse=True)[:3]
                self._debug_top_by_depth[depth] = [
                    {"score": float(s[1]), "bin": int(s[2]), "system_preview": (s[0] or "")[:160]}
                    for s in top
                ]
        except Exception:
            pass
        return new_child or best_existing

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
        # DB cache
        try:
            db_key = "rephrase:" + self._hash_pair(system_text, segment_text)
            cached = self._db_cache_get(db_key)
            if isinstance(cached, str) and cached:
                self._rephrase_cache[cache_key] = cached
                return cached
        except Exception:
            pass
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
                try:
                    self._db_cache_set(db_key, content, ttl_sec=3600)
                except Exception:
                    pass
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
        optimization_id: Optional[int] = None,
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
            # DB cache (rollout)
            db_key = "eval:" + eval_cache_key
            try:
                cached_db = self._db_cache_get(db_key)
            except Exception:
                cached_db = None
            if cached_db is not None:
                score = float(cached_db)
            else:
                score = await self._evaluate_prompt(prompt_id, test_case_ids, model_config, target_metric)
                self._eval_cache[eval_cache_key] = score
                try:
                    self._db_cache_set(db_key, score, ttl_sec=3600)
                except Exception:
                    pass
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
                    optimization_id=optimization_id,
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
        # Compute next version number for the same prompt name within the project to avoid collisions
        new_name = f"{base_prompt['name']} (MCTS)"
        try:
            cursor.execute(
                """
                SELECT COALESCE(MAX(version_number), 0)
                FROM prompt_studio_prompts
                WHERE project_id = ? AND name = ?
                """,
                (base_prompt["project_id"], new_name),
            )
            row = cursor.fetchone()
            next_version = int(row[0]) + 1 if row and row[0] is not None else (int(base_prompt.get("version_number") or 0) + 1)
        except Exception:
            next_version = (base_prompt.get("version_number") or 0) + 1
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
                new_name,
                system_text,
                user_text,
                next_version,
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
            try:
                result = await self.test_runner.run_single_test(
                    prompt_id=prompt_id,
                    test_case_id=tc_id,
                    model_config=model_config,
                    metrics=[target_metric] if hasattr(target_metric, "value") else None,
                )
            except Exception as e:
                # Count timeouts; keep conservative by substring match
                msg = str(e).lower()
                if "timeout" in msg or "timed out" in msg:
                    try:
                        if hasattr(self, "_counters") and isinstance(self._counters, dict):
                            self._counters["evaluator_timeouts"] = self._counters.get("evaluator_timeouts", 0) + 1
                    except Exception:
                        pass
                continue
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

    # --- Simple DB-backed cache via sync_log ---
    def _db_cache_get(self, key: str) -> Optional[Any]:
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT payload, timestamp FROM sync_log WHERE entity = ? AND entity_uuid = ? ORDER BY timestamp DESC LIMIT 1",
                ("prompt_studio_cache", key),
            )
            row = cursor.fetchone()
            if not row:
                return None
            payload_raw = row[0]
            import json, datetime
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else self.db._row_to_dict(cursor, row)
            data = payload if isinstance(payload, dict) else {}
            expires = data.get("expires_at")
            if expires:
                try:
                    if datetime.datetime.fromisoformat(expires) < datetime.datetime.utcnow():
                        return None
                except Exception:
                    pass
            return data.get("value")
        except Exception:
            return None

    def _db_cache_set(self, key: str, value: Any, *, ttl_sec: int = 3600) -> None:
        try:
            import json, datetime, uuid
            expires_at = (datetime.datetime.utcnow() + datetime.timedelta(seconds=int(ttl_sec))).isoformat()
            payload = {"value": value, "expires_at": expires_at}
            self.db._log_sync_event(
                entity="prompt_studio_cache",
                entity_uuid=key,
                operation="set",
                payload=payload,
            )
        except Exception:
            pass

    @staticmethod
    def _hash_pair(a: str, b: str) -> str:
        import hashlib
        h = hashlib.sha256()
        h.update(a.encode("utf-8", errors="ignore"))
        h.update(b"\0")
        h.update(b.encode("utf-8", errors="ignore"))
        return h.hexdigest()
