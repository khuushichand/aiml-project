import pytest

from tldw_Server_API.app.core.Evaluations.eval_runner import EvaluationRunner


@pytest.mark.asyncio
async def test_eval_summarization_parses_geval_dict(monkeypatch, tmp_path):
    runner = EvaluationRunner(db_path=str(tmp_path / "evals.db"))

    def mock_run_geval(*args, **kwargs):
        assert kwargs.get("api_name") == "openai"
        assert kwargs.get("api_key") is None
        return {
            "metrics": {
                "coherence": 4.0,
                "fluency": 3.0,
            }
        }

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Evaluations.eval_runner.run_geval",
        mock_run_geval,
    )

    sample = {"input": {"source_text": "source", "summary": "summary"}}
    eval_spec = {
        "metrics": ["coherence", "fluency"],
        "threshold": 0.7,
        "evaluator_model": "openai",
    }

    result = await runner._eval_summarization(sample, eval_spec, {}, "sample_000001")
    assert result["scores"]["coherence"] == pytest.approx(0.8)
    assert result["scores"]["fluency"] == pytest.approx(1.0)
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_eval_rag_parses_metric_dicts(tmp_path):
    runner = EvaluationRunner(db_path=str(tmp_path / "evals.db"))

    class _FakeRagEval:
        async def evaluate(self, **kwargs):
            return {
                "metrics": {
                    "relevance": {"score": 0.9},
                    "faithfulness": {"score": 0.8},
                }
            }

    runner._rag_evaluator = _FakeRagEval()  # type: ignore

    sample = {
        "input": {"query": "q", "contexts": ["c"], "response": "r"},
        "expected": {"answer": "a"},
    }
    eval_spec = {"metrics": ["relevance", "faithfulness"], "threshold": 0.7}

    result = await runner._eval_rag(sample, eval_spec, {}, "sample_000002")
    assert result["scores"]["relevance"] == pytest.approx(0.9)
    assert result["scores"]["faithfulness"] == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_eval_response_quality_parses_metric_dicts(tmp_path):
    runner = EvaluationRunner(db_path=str(tmp_path / "evals.db"))

    class _FakeQualityEval:
        async def evaluate(self, **kwargs):
            return {
                "metrics": {
                    "relevance": {"score": 0.9},
                    "clarity": {"score": 0.8},
                },
                "overall_quality": 0.85,
                "format_compliance": True,
            }

    runner._quality_evaluator = _FakeQualityEval()  # type: ignore

    sample = {"input": {"prompt": "p", "response": "r"}}
    eval_spec = {"metrics": ["relevance", "clarity"], "threshold": 0.7}

    result = await runner._eval_response_quality(sample, eval_spec, {}, "sample_000003")
    assert result["scores"]["relevance"] == pytest.approx(0.9)
    assert result["scores"]["clarity"] == pytest.approx(0.8)
    assert result["scores"]["overall_quality"] == pytest.approx(0.85)
