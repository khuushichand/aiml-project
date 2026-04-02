from __future__ import annotations

from pathlib import Path

from tldw_Server_API.app.core.Evaluations.ms_g_eval import run_geval


def test_run_geval_save_false_does_not_write_results_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = run_geval(
        transcript="Source text for evaluation.",
        summary="Short summary.",
        api_key="test_api_key",
        api_name="openai",
        save=False,
    )

    assert result["average_score"] > 0
    assert not Path("geval_results.json").exists()
