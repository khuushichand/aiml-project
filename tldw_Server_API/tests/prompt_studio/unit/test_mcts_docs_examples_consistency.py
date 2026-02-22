import json
from pathlib import Path


EXAMPLES_DIR = (
    Path(__file__).resolve().parents[4]
    / "Docs"
    / "Examples"
    / "PromptStudio"
    / "mcts"
)


def _load_json(name: str) -> dict:
    path = EXAMPLES_DIR / name
    assert path.exists(), f"Missing example file: {path}"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_mcts_examples_directory_contains_required_assets():
    required = {
        "README.md",
        "create_optimization_mcts.json",
        "websocket_optimization_iteration_event.json",
        "optimization_history_response.json",
        "ROLL_OUT_NOTES.md",
    }
    existing = {p.name for p in EXAMPLES_DIR.iterdir() if p.is_file()}
    assert required.issubset(existing)


def test_create_optimization_example_matches_mcts_contract():
    payload = _load_json("create_optimization_mcts.json")
    assert payload["optimization_config"]["optimizer_type"] == "mcts"
    strategy = payload["optimization_config"]["strategy_params"]
    required = {
        "mcts_simulations",
        "mcts_max_depth",
        "mcts_exploration_c",
        "prompt_candidates_per_node",
        "score_dedup_bin",
        "token_budget",
        "early_stop_no_improve",
        "ws_throttle_every",
        "trace_top_k",
    }
    assert required.issubset(set(strategy.keys()))


def test_websocket_iteration_example_matches_payload_shape():
    event = _load_json("websocket_optimization_iteration_event.json")
    assert event["type"] == "optimization_iteration"
    data = event["data"]
    required = {
        "optimization_id",
        "iteration",
        "max_iterations",
        "current_metric",
        "best_metric",
        "progress",
        "strategy",
        "sim_index",
        "depth",
        "reward",
        "best_reward",
        "token_spend_so_far",
        "trace_summary",
    }
    assert required.issubset(set(data.keys()))
    assert int(data["iteration"]) == int(data["sim_index"])
    assert set(data["trace_summary"].keys()) >= {"prompt_id", "system_hash"}


def test_optimization_history_example_matches_endpoint_shape():
    payload = _load_json("optimization_history_response.json")
    assert payload["success"] is True
    data = payload["data"]
    assert set(data.keys()) >= {"optimization", "job", "progress", "timeline"}
    assert set(data["progress"].keys()) >= {"iterations_completed", "max_iterations", "status"}
    assert isinstance(data["timeline"], list)
