"""
Tests for CI/CD quality gating module.

Covers:
- GatingEvaluator with all-pass, stable-fail, unstable-fail, and mixed scenarios
- Exit codes (0 = pass, 1 = stable fail, 2 = unstable warning)
- lower_is_better logic for metrics like hallucination and latency
- YAML round-trip serialization via GatingConfig.to_yaml / from_yaml
- Default threshold values
- GatingEvaluationResult.to_dict() serialization
"""

import pytest

from tldw_Server_API.app.core.RAG.rag_service.quality_gating import (
    GatingConfig,
    GatingEvaluationResult,
    GatingEvaluator,
    GatingResult,
    MetricCategory,
    MetricResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_passing_metrics() -> dict[str, float]:
    """Return metric values that exceed every default threshold."""
    return {
        # Stable (higher is better)
        "precision": 0.95,
        "recall": 0.90,
        "mrr": 0.85,
        "ndcg": 0.88,
        # Unstable (higher is better except hallucination)
        "faithfulness": 0.80,
        "relevance": 0.75,
        "hallucination": 0.1,  # lower is better; 0.1 < 0.3 threshold -> pass
    }


# ---------------------------------------------------------------------------
# Test: Enum values
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEnums:
    """Sanity checks on enum members."""

    def test_metric_category_values(self):
        assert MetricCategory.STABLE.value == "stable"
        assert MetricCategory.UNSTABLE.value == "unstable"

    def test_gating_result_values(self):
        assert GatingResult.PASS.value == "pass"
        assert GatingResult.WARN.value == "warn"
        assert GatingResult.FAIL.value == "fail"


# ---------------------------------------------------------------------------
# Test: Default thresholds
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDefaultThresholds:
    """Verify the default GatingConfig ships with documented thresholds."""

    def test_stable_defaults(self):
        config = GatingConfig()
        assert config.stable == {
            "precision": 0.8,
            "recall": 0.8,
            "mrr": 0.8,
            "ndcg": 0.8,
        }

    def test_unstable_defaults(self):
        config = GatingConfig()
        assert config.unstable == {
            "faithfulness": 0.7,
            "relevance": 0.7,
            "hallucination": 0.3,
        }

    def test_lower_is_better_defaults(self):
        config = GatingConfig()
        assert "hallucination" in config.lower_is_better
        assert "latency_p99_ms" in config.lower_is_better


# ---------------------------------------------------------------------------
# Test: MetricResult model
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMetricResult:
    """Tests for the MetricResult frozen model."""

    def test_create_metric_result(self):
        mr = MetricResult(
            name="precision",
            value=0.85,
            threshold=0.8,
            category=MetricCategory.STABLE,
            result=GatingResult.PASS,
        )
        assert mr.name == "precision"
        assert mr.value == 0.85
        assert mr.threshold == 0.8
        assert mr.category == MetricCategory.STABLE
        assert mr.result == GatingResult.PASS

    def test_metric_result_is_frozen(self):
        mr = MetricResult(
            name="recall",
            value=0.9,
            threshold=0.8,
            category=MetricCategory.STABLE,
            result=GatingResult.PASS,
        )
        with pytest.raises(Exception):
            mr.value = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test: GatingEvaluator -- exit code scenarios
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGatingEvaluatorExitCodes:
    """Core gating logic: exit codes 0, 1, and 2."""

    def test_all_metrics_pass_exit_code_0(self):
        """When every metric meets its threshold the exit code is 0."""
        evaluator = GatingEvaluator()
        result = evaluator.evaluate(_all_passing_metrics())

        assert result.overall_result == GatingResult.PASS
        assert result.exit_code == 0
        assert "passed" in result.summary.lower()
        # Every individual metric should be PASS
        for m in result.metrics:
            assert m.result == GatingResult.PASS

    def test_stable_metric_fails_exit_code_1(self):
        """A stable metric below threshold triggers exit code 1."""
        evaluator = GatingEvaluator()
        metrics = _all_passing_metrics()
        metrics["precision"] = 0.5  # below 0.8 stable threshold

        result = evaluator.evaluate(metrics)

        assert result.overall_result == GatingResult.FAIL
        assert result.exit_code == 1
        assert "precision" in result.summary.lower()

        # Verify the individual metric was marked FAIL
        precision_metric = next(m for m in result.metrics if m.name == "precision")
        assert precision_metric.result == GatingResult.FAIL
        assert precision_metric.category == MetricCategory.STABLE

    def test_only_unstable_metric_fails_exit_code_2(self):
        """When only unstable metrics are below threshold the exit code is 2."""
        evaluator = GatingEvaluator()
        metrics = _all_passing_metrics()
        metrics["faithfulness"] = 0.4  # below 0.7 unstable threshold

        result = evaluator.evaluate(metrics)

        assert result.overall_result == GatingResult.WARN
        assert result.exit_code == 2
        assert "faithfulness" in result.summary.lower()

        faith_metric = next(m for m in result.metrics if m.name == "faithfulness")
        assert faith_metric.result == GatingResult.WARN
        assert faith_metric.category == MetricCategory.UNSTABLE

    def test_both_stable_and_unstable_fail_exit_code_1(self):
        """When both categories fail, stable failure (exit code 1) takes priority."""
        evaluator = GatingEvaluator()
        metrics = _all_passing_metrics()
        metrics["recall"] = 0.3       # stable fail
        metrics["relevance"] = 0.2    # unstable fail

        result = evaluator.evaluate(metrics)

        assert result.overall_result == GatingResult.FAIL
        assert result.exit_code == 1
        assert "recall" in result.summary.lower()

    def test_multiple_stable_failures_listed(self):
        """All failing stable metric names appear in the summary."""
        evaluator = GatingEvaluator()
        metrics = _all_passing_metrics()
        metrics["precision"] = 0.1
        metrics["mrr"] = 0.2

        result = evaluator.evaluate(metrics)

        assert result.exit_code == 1
        assert "precision" in result.summary.lower()
        assert "mrr" in result.summary.lower()


# ---------------------------------------------------------------------------
# Test: lower_is_better logic
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLowerIsBetter:
    """Metrics where lower values are better (hallucination, latency)."""

    def test_hallucination_below_threshold_passes(self):
        """Hallucination value below threshold -> pass."""
        evaluator = GatingEvaluator()
        metrics = _all_passing_metrics()
        metrics["hallucination"] = 0.1  # well below 0.3 threshold

        result = evaluator.evaluate(metrics)

        hall_metric = next(m for m in result.metrics if m.name == "hallucination")
        assert hall_metric.result == GatingResult.PASS

    def test_hallucination_equal_to_threshold_passes(self):
        """Hallucination value exactly at threshold -> pass (<=)."""
        evaluator = GatingEvaluator()
        metrics = _all_passing_metrics()
        metrics["hallucination"] = 0.3  # exactly at 0.3 threshold

        result = evaluator.evaluate(metrics)

        hall_metric = next(m for m in result.metrics if m.name == "hallucination")
        assert hall_metric.result == GatingResult.PASS

    def test_hallucination_above_threshold_warns(self):
        """Hallucination value above threshold -> warn (it is an unstable metric)."""
        evaluator = GatingEvaluator()
        metrics = _all_passing_metrics()
        metrics["hallucination"] = 0.5  # above 0.3 threshold

        result = evaluator.evaluate(metrics)

        hall_metric = next(m for m in result.metrics if m.name == "hallucination")
        assert hall_metric.result == GatingResult.WARN
        assert hall_metric.category == MetricCategory.UNSTABLE

    def test_lower_is_better_custom_stable_metric(self):
        """A custom stable metric marked lower_is_better fails when above threshold."""
        config = GatingConfig(
            stable={"latency_p99_ms": 500.0},
            unstable={},
            lower_is_better=["latency_p99_ms"],
        )
        evaluator = GatingEvaluator(config=config)

        # Latency too high -> fail
        result = evaluator.evaluate({"latency_p99_ms": 800.0})
        assert result.exit_code == 1

        lat_metric = next(m for m in result.metrics if m.name == "latency_p99_ms")
        assert lat_metric.result == GatingResult.FAIL

    def test_lower_is_better_custom_stable_metric_passes(self):
        """A custom stable metric marked lower_is_better passes when at or below threshold."""
        config = GatingConfig(
            stable={"latency_p99_ms": 500.0},
            unstable={},
            lower_is_better=["latency_p99_ms"],
        )
        evaluator = GatingEvaluator(config=config)

        result = evaluator.evaluate({"latency_p99_ms": 450.0})
        assert result.exit_code == 0

        lat_metric = next(m for m in result.metrics if m.name == "latency_p99_ms")
        assert lat_metric.result == GatingResult.PASS


# ---------------------------------------------------------------------------
# Test: YAML round-trip
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestYamlRoundTrip:
    """GatingConfig to_yaml -> from_yaml preserves all values."""

    def test_default_config_roundtrip(self, tmp_path):
        """Default config survives a YAML round-trip."""
        yaml_path = tmp_path / "gating.yaml"
        original = GatingConfig()

        original.to_yaml(yaml_path)
        loaded = GatingConfig.from_yaml(yaml_path)

        assert loaded.stable == original.stable
        assert loaded.unstable == original.unstable
        assert loaded.lower_is_better == original.lower_is_better

    def test_custom_config_roundtrip(self, tmp_path):
        """Custom config with non-default values survives a round-trip."""
        yaml_path = tmp_path / "custom_gating.yaml"
        original = GatingConfig(
            stable={"my_metric": 0.95, "other_metric": 0.5},
            unstable={"llm_score": 0.6},
            lower_is_better=["error_rate", "latency"],
        )

        original.to_yaml(yaml_path)
        loaded = GatingConfig.from_yaml(yaml_path)

        assert loaded.stable == {"my_metric": 0.95, "other_metric": 0.5}
        assert loaded.unstable == {"llm_score": 0.6}
        assert set(loaded.lower_is_better) == {"error_rate", "latency"}

    def test_from_yaml_file_not_found(self, tmp_path):
        """from_yaml raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            GatingConfig.from_yaml(tmp_path / "does_not_exist.yaml")

    def test_from_yaml_empty_file(self, tmp_path):
        """An empty YAML file returns a default GatingConfig."""
        yaml_path = tmp_path / "empty.yaml"
        yaml_path.write_text("")

        config = GatingConfig.from_yaml(yaml_path)

        # Should fall back to defaults
        assert isinstance(config, GatingConfig)

    def test_to_yaml_creates_parent_directories(self, tmp_path):
        """to_yaml creates intermediate directories when needed."""
        yaml_path = tmp_path / "nested" / "dir" / "gating.yaml"
        config = GatingConfig()

        config.to_yaml(yaml_path)

        assert yaml_path.exists()
        loaded = GatingConfig.from_yaml(yaml_path)
        assert loaded.stable == config.stable


# ---------------------------------------------------------------------------
# Test: GatingEvaluationResult.to_dict()
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestToDictSerialization:
    """GatingEvaluationResult.to_dict() returns proper plain-dict output."""

    def test_to_dict_all_pass(self):
        """to_dict for an all-pass evaluation."""
        evaluator = GatingEvaluator()
        result = evaluator.evaluate(_all_passing_metrics())
        d = result.to_dict()

        assert d["overall_result"] == "pass"
        assert d["exit_code"] == 0
        assert isinstance(d["metrics"], list)
        assert isinstance(d["summary"], str)

        # Each metric entry should have the right keys with string enum values
        for m in d["metrics"]:
            assert set(m.keys()) == {"name", "value", "threshold", "category", "result"}
            assert m["result"] == "pass"
            assert m["category"] in ("stable", "unstable")

    def test_to_dict_with_failures(self):
        """to_dict correctly represents failed and warned metrics."""
        evaluator = GatingEvaluator()
        metrics = _all_passing_metrics()
        metrics["recall"] = 0.1       # stable fail
        metrics["faithfulness"] = 0.2  # unstable warn

        result = evaluator.evaluate(metrics)
        d = result.to_dict()

        assert d["overall_result"] == "fail"
        assert d["exit_code"] == 1

        recall_entry = next(m for m in d["metrics"] if m["name"] == "recall")
        assert recall_entry["result"] == "fail"
        assert recall_entry["category"] == "stable"
        assert recall_entry["value"] == 0.1
        assert recall_entry["threshold"] == 0.8

        faith_entry = next(m for m in d["metrics"] if m["name"] == "faithfulness")
        assert faith_entry["result"] == "warn"
        assert faith_entry["category"] == "unstable"

    def test_to_dict_returns_plain_types(self):
        """Ensure to_dict produces only plain Python types (no Pydantic/Enum)."""
        evaluator = GatingEvaluator()
        result = evaluator.evaluate(_all_passing_metrics())
        d = result.to_dict()

        assert type(d["overall_result"]) is str
        assert type(d["exit_code"]) is int
        assert type(d["summary"]) is str
        for m in d["metrics"]:
            assert type(m["name"]) is str
            assert type(m["value"]) is float
            assert type(m["threshold"]) is float
            assert type(m["category"]) is str
            assert type(m["result"]) is str


# ---------------------------------------------------------------------------
# Test: GatingEvaluationResult model
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGatingEvaluationResultModel:
    """Tests for the GatingEvaluationResult frozen model."""

    def test_is_frozen(self):
        """GatingEvaluationResult should be immutable."""
        evaluator = GatingEvaluator()
        result = evaluator.evaluate(_all_passing_metrics())
        with pytest.raises(Exception):
            result.exit_code = 99  # type: ignore[misc]

    def test_empty_metrics_dict(self):
        """Evaluating an empty dict should pass (nothing to check)."""
        evaluator = GatingEvaluator()
        result = evaluator.evaluate({})

        assert result.exit_code == 0
        assert result.overall_result == GatingResult.PASS
        assert result.metrics == []

    def test_unknown_metrics_ignored(self):
        """Metrics not in the config are silently ignored."""
        evaluator = GatingEvaluator()
        result = evaluator.evaluate({"unknown_metric": 0.5})

        assert result.exit_code == 0
        assert len(result.metrics) == 0


# ---------------------------------------------------------------------------
# Test: Custom GatingConfig
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCustomConfig:
    """Evaluator with a non-default GatingConfig."""

    def test_custom_thresholds(self):
        """Custom thresholds are respected during evaluation."""
        config = GatingConfig(
            stable={"accuracy": 0.9},
            unstable={"coherence": 0.6},
            lower_is_better=[],
        )
        evaluator = GatingEvaluator(config=config)

        # accuracy passes, coherence fails
        result = evaluator.evaluate({"accuracy": 0.95, "coherence": 0.4})

        assert result.exit_code == 2  # only unstable failed
        assert result.overall_result == GatingResult.WARN

        acc = next(m for m in result.metrics if m.name == "accuracy")
        assert acc.result == GatingResult.PASS

        coh = next(m for m in result.metrics if m.name == "coherence")
        assert coh.result == GatingResult.WARN

    def test_evaluator_uses_defaults_when_no_config(self):
        """GatingEvaluator() without args uses default GatingConfig."""
        evaluator = GatingEvaluator()
        assert evaluator.config.stable == GatingConfig().stable

    def test_metric_at_exact_threshold_passes(self):
        """A higher-is-better metric exactly at threshold passes (>=)."""
        config = GatingConfig(
            stable={"precision": 0.8},
            unstable={},
            lower_is_better=[],
        )
        evaluator = GatingEvaluator(config=config)

        result = evaluator.evaluate({"precision": 0.8})

        assert result.exit_code == 0
        prec = next(m for m in result.metrics if m.name == "precision")
        assert prec.result == GatingResult.PASS

    def test_subset_of_metrics_provided(self):
        """Providing only some of the configured metrics evaluates only those."""
        evaluator = GatingEvaluator()
        # Only provide precision -- others are simply skipped
        result = evaluator.evaluate({"precision": 0.9})

        assert result.exit_code == 0
        assert len(result.metrics) == 1
        assert result.metrics[0].name == "precision"
