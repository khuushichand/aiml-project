import os
import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.prompt_quality import PromptQualityScorer
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.program_evaluator import ProgramEvaluator


def test_score_to_bin_edges():
    # Bin size 0.5 => 0-0.49 -> 0, 0.5-0.99 -> 1, ..., 9.5-10 -> 19
    assert PromptQualityScorer.score_to_bin(0.0, 0.5) == 0
    assert PromptQualityScorer.score_to_bin(0.49, 0.5) == 0
    assert PromptQualityScorer.score_to_bin(0.5, 0.5) == 1
    assert PromptQualityScorer.score_to_bin(9.49, 0.5) == 18
    assert PromptQualityScorer.score_to_bin(9.5, 0.5) == 19
    assert PromptQualityScorer.score_to_bin(10.0, 0.5) == 20


def test_program_evaluator_heuristic_scoring_disabled_env(monkeypatch):
    # Ensure global flag is disabled
    monkeypatch.delenv("PROMPT_STUDIO_ENABLE_CODE_EVAL", raising=False)
    pe = ProgramEvaluator()
    # Heuristic should return positive for code-like text
    reward = pe.evaluate_text_output("""
def add(a,b):
    return a+b
if __name__ == '__main__':
    print(add(1,2))
""")
    assert reward > 0


def test_safe_constraint_eval():
    pe = ProgramEvaluator()
    names = {"x": 5, "y": 2}
    assert pe._safe_eval_constraint("x >= 0 and y < 10", names) is True
    assert pe._safe_eval_constraint("x + y == 7", names) is True
    # Disallow dangerous constructs
    assert pe._safe_eval_constraint("(__import__('os')).system('ls')", names) is False
