import os
import pytest

from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.mcts_optimizer import MCTSOptimizer
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.prompt_quality import PromptQualityScorer
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.optimization_engine import MetricType
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.test_runner import TestRunner


@pytest.fixture
def temp_ps_db(tmp_path) -> PromptStudioDatabase:
    os.environ.setdefault("TEST_MODE", "true")
    return PromptStudioDatabase(str(tmp_path / "ps_mcts_unit.db"), client_id="mcts-unit")


def _seed_prompt_and_tests(db: PromptStudioDatabase, n_tests: int = 2):
    proj = db.create_project("MCTS-Unit", "desc")
    pid = int(proj["id"]) if isinstance(proj, dict) else int(proj)
    p = db.create_prompt(
        project_id=pid,
        name="Base-MCTS",
        system_prompt="Base system",
        user_prompt="Answer {q}",
        version_number=1,
    )
    t_ids = []
    for i in range(n_tests):
        tc = db.create_test_case(
            project_id=pid,
            name=f"TC-{i}",
            inputs={"q": f"q-{i}"},
            expected_outputs={"response": f"a-{i}"},
            is_golden=False,
        )
        t_ids.append(int(tc["id"]))
    return int(p["id"]), t_ids


def test_uct_selection_behavior():
    parent = MCTSOptimizer._Node.__new__(MCTSOptimizer._Node)  # bypass __init__ signature
    parent.parent = None
    parent.segment_index = 0
    parent.system_text = ""
    parent.q_sum = 0.0
    parent.n_visits = 10
    parent.children = []
    parent.children_by_bin = {}
    parent.score_bin = -1

    # Two children with different q/n - ensure UCT favors higher exploitation when visits equal
    def _mk(q_sum, n_vis):
        ch = MCTSOptimizer._Node.__new__(MCTSOptimizer._Node)
        ch.parent = parent
        ch.segment_index = 1
        ch.system_text = "x"
        ch.q_sum = q_sum
        ch.n_visits = n_vis
        ch.children = []
        ch.children_by_bin = {}
        ch.score_bin = 0
        return ch

    a = _mk(9.0, 3)   # avg = 3.0
    b = _mk(4.0, 2)   # avg = 2.0
    parent.children = [a, b]

    # With same exploration_c, child 'a' should have higher UCT
    ua = a.uct(exploration_c=1.4)
    ub = b.uct(exploration_c=1.4)
    assert ua > ub


@pytest.mark.asyncio
async def test_node_dedup_by_score_bins(monkeypatch, temp_ps_db):
    prompt_id, test_ids = _seed_prompt_and_tests(temp_ps_db)
    mcts = MCTSOptimizer(temp_ps_db, TestRunner(temp_ps_db))
    mcts._counters = {}

    # Force candidate proposals to two items mapped into same score bin
    async def fake_props(system_so_far, segment_text, k):
        return [system_so_far + " A", system_so_far + " B"]

    monkeypatch.setattr(mcts, "_propose_candidates", fake_props)

    # Map scores so both fall in same bin for bin_size=0.5
    async def fake_score_prompt_async(*, system_text: str, user_text: str) -> float:
        return 0.74 if system_text.endswith("A") else 0.76

    monkeypatch.setattr(PromptQualityScorer, "score_prompt_async", fake_score_prompt_async, raising=False)

    node = MCTSOptimizer._Node(parent=None, segment_index=0, system_text="S0")
    child = await mcts._expand_node(
        node,
        segment="seg",
        base_user="user",
        k_candidates=2,
        score_bin_size=0.5,
        min_quality=0.0,
    )

    # Only one child created; dedup counter incremented
    assert isinstance(child, MCTSOptimizer._Node)
    assert len(node.children) == 1
    assert mcts._counters.get("prune_dedup", 0) >= 1


@pytest.mark.asyncio
async def test_token_budget_cutoff(monkeypatch, temp_ps_db):
    prompt_id, test_ids = _seed_prompt_and_tests(temp_ps_db)
    mcts = MCTSOptimizer(temp_ps_db, TestRunner(temp_ps_db))

    # Enable token callback in scorer by configuring a scorer_model and monkeypatching executor
    mcts.scorer.set_model("gpt-3.5-turbo")
    class _Exec:
        async def _call_llm(self, **kwargs):
            return {"content": "5", "tokens": 50}
    mcts.scorer.set_executor(_Exec())

    # Decomposer: single segment to allow one expansion
    monkeypatch.setattr(mcts.decomposer, "decompose_text", lambda _: ["seg"])  # type: ignore[attr-defined]
    # _propose_candidates: one child
    monkeypatch.setattr(mcts, "_propose_candidates", lambda sys, seg, k: [sys + " X"])  # type: ignore[misc]
    # Evaluator: constant score
    async def fake_eval(*args, **kwargs):
        return {"success": True, "scores": {"aggregate_score": 0.1}}
    monkeypatch.setattr(TestRunner, "run_single_test", fake_eval)

    res = await mcts.optimize(
        initial_prompt_id=prompt_id,
        test_case_ids=test_ids,
        model_config={"model": "dummy"},
        max_iterations=50,
        target_metric=MetricType.ACCURACY,
        strategy_params={
            "mcts_simulations": 50,
            "token_budget": 40,  # smaller than fake tokens per scorer call
            "mcts_max_depth": 2,
        },
    )
    # Should stop early due to token budget before exhausting all sims
    assert res["iterations"] < 50


@pytest.mark.asyncio
async def test_early_stop_no_improve(monkeypatch, temp_ps_db):
    prompt_id, test_ids = _seed_prompt_and_tests(temp_ps_db)
    mcts = MCTSOptimizer(temp_ps_db, TestRunner(temp_ps_db))

    # Single segment, constant candidates and constant evaluation equals baseline
    monkeypatch.setattr(mcts.decomposer, "decompose_text", lambda _: ["seg1"])  # type: ignore[attr-defined]
    monkeypatch.setattr(mcts, "_propose_candidates", lambda sys, seg, k: [sys + " X"])  # type: ignore[misc]

    async def fake_eval_prompt(self, prompt_id: int, test_case_ids, model_config, target_metric):
        return 0.5  # constant
    monkeypatch.setattr(MCTSOptimizer, "_evaluate_prompt", fake_eval_prompt)

    res = await mcts.optimize(
        initial_prompt_id=prompt_id,
        test_case_ids=test_ids,
        model_config={"model": "dummy"},
        max_iterations=100,
        target_metric=MetricType.ACCURACY,
        strategy_params={"mcts_simulations": 100, "early_stop_no_improve": 2, "mcts_max_depth": 2},
    )
    # Expect iterations equal to early_stop_no_improve before break
    assert res["iterations"] == 2
