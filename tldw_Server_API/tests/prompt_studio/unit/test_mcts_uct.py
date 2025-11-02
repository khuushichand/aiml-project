import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.mcts_optimizer import MCTSOptimizer


pytestmark = pytest.mark.unit


class _DummyDB:
    client_id = "test"


class _DummyRunner:
    pass


def test_uct_exploration_constant_affects_selection():
    # Build bare nodes without running optimizer logic
    parent = MCTSOptimizer._Node(parent=None, segment_index=0, system_text="root")
    # Manually set parent visits to a realistic value to stabilize log term
    parent.n_visits = 120

    # Two children with different visit counts and slight exploitation difference
    # A: higher exploitation, more visits
    child_a = MCTSOptimizer._Node(parent=parent, segment_index=1, system_text="A")
    child_a.n_visits = 100
    child_a.q_sum = 81.0  # exploitation = 0.81

    # B: slightly lower exploitation, fewer visits (more exploration incentive)
    child_b = MCTSOptimizer._Node(parent=parent, segment_index=1, system_text="B")
    child_b.n_visits = 10
    child_b.q_sum = 8.0  # exploitation = 0.8

    # With a very small exploration constant, exploitation dominates => pick A
    c_small = 0.01
    uct_a_small = child_a.uct(exploration_c=c_small)
    uct_b_small = child_b.uct(exploration_c=c_small)
    assert uct_a_small > uct_b_small, "With small c, higher exploitation should be preferred"

    # With a larger exploration constant, low-visit child gets boosted => pick B
    c_large = 0.5
    uct_a_large = child_a.uct(exploration_c=c_large)
    uct_b_large = child_b.uct(exploration_c=c_large)
    assert uct_b_large > uct_a_large, "With large c, exploration bonus should prefer low-visit child"
