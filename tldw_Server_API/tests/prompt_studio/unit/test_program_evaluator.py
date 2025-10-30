import os
import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.program_evaluator import ProgramEvaluator


def test_forbidden_imports_detected():
    pe = ProgramEvaluator()
    code = """
    ```python
    import requests
    print('hello')
    ```
    """
    # Force enabled to test validator path
    os.environ["PROMPT_STUDIO_ENABLE_CODE_EVAL"] = "true"
    res = pe.evaluate(project_id=None, db=None, llm_output=code, spec={})
    assert res.success is False
    assert "Forbidden" in (res.error or "")


def test_runner_python_path_enabled_vs_disabled(tmp_path):
    # When enabled, reward should reflect metric_var from globals; when disabled, use heuristic
    pe = ProgramEvaluator()
    code = """
    ```python
    val = 2.5
    print('done')
    ```
    """
    spec = {"runner": "python", "objective": "maximize", "metric_var": "val"}
    # Enabled
    os.environ["PROMPT_STUDIO_ENABLE_CODE_EVAL"] = "true"
    r_on = pe.evaluate(project_id=None, db=None, llm_output=code, spec=spec)
    # reward = 10*(1 - 1/(1+2.5)) ~= 7.142 => score 0.714 in TestRunner
    assert r_on.success is True
    assert r_on.reward > 5.0
    # Disabled -> Heuristic fallback (no sandbox)
    os.environ["PROMPT_STUDIO_ENABLE_CODE_EVAL"] = "false"
    r_off = pe.evaluate(project_id=None, db=None, llm_output=code, spec=spec)
    assert r_off.success is True
    assert r_off.reward <= r_on.reward


def test_program_evaluator_timeout(monkeypatch):
    pe = ProgramEvaluator()
    os.environ["PROMPT_STUDIO_ENABLE_CODE_EVAL"] = "true"
    # Shorten wall time for test
    monkeypatch.setattr(ProgramEvaluator, "WALL_TIME_SEC", 0.1, raising=False)
    code = """
    ```python
    import time
    time.sleep(2)
    ```
    """
    res = pe.evaluate(project_id=None, db=None, llm_output=code, spec={})
    assert res.success is False
    # stderr may include 'timeout'
    assert "stderr" in res.metrics
