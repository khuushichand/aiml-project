from click.testing import CliRunner

from tldw_Server_API.cli.evals_cli import main


def test_unified_cli_help_includes_benchmark_group():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "benchmark" in result.output


def test_unified_cli_has_list_benchmarks_alias():
    result = CliRunner().invoke(main, ["list-benchmarks", "--help"])
    assert result.exit_code == 0


def test_benchmark_run_command_executes(monkeypatch):
    called = {"loaded": False}

    class _Cfg:
        evaluation_type = "bullshit_detection"

    class _Registry:
        def get(self, name):
            return _Cfg() if name == "bullshit_benchmark" else None

        def create_evaluator(self, name):
            if name != "bullshit_benchmark":
                return None

            class _Eval:
                def format_for_custom_metric(self, item):
                    return {
                        "name": "m",
                        "description": "d",
                        "evaluation_prompt": "{question}",
                        "input_data": {"question": item["question"]},
                        "scoring_criteria": {"k": "v"},
                    }

            return _Eval()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Evaluations.cli.benchmark_cli.get_registry",
        lambda: _Registry(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Evaluations.cli.benchmark_cli.load_benchmark_dataset",
        lambda name, source=None, limit=None, **kwargs: (
            called.__setitem__("loaded", True)
            or [{"id": "q1", "question": "q", "nonsensical_element": "n", "domain": "d"}]
        ),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Evaluations.cli.benchmark_cli.run_async_safely",
        lambda coro: [{"score": 1.0, "explanation": "ok"}],
    )

    result = CliRunner().invoke(
        main,
        ["benchmark", "run", "bullshit_benchmark", "--limit", "1"],
    )
    assert result.exit_code == 0
    assert called["loaded"] is True
