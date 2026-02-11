"""Unit tests for EMAIL-M3-002 dual-read parity validation tooling."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "Helper_Scripts"
    / "checks"
    / "email_search_dual_read_parity.py"
)
_SPEC = importlib.util.spec_from_file_location("email_search_dual_read_parity", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
script = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = script
_SPEC.loader.exec_module(script)


def _thresholds() -> script.ParityThresholds:
    return script.ParityThresholds(
        min_precision=0.70,
        min_recall=0.70,
        min_jaccard=0.50,
        max_total_delta_ratio=0.40,
        min_pass_rate=0.95,
        max_query_errors=0,
        min_backfill_coverage=0.95,
    )


@pytest.mark.unit
def test_parse_query_mix_payload_supports_shared_and_split_queries() -> None:
    payload = [
        {"name": "shared", "query": "budget"},
        {
            "name": "split",
            "legacy_query": "alice@example.com",
            "normalized_query": "from:alice@example.com",
            "notes": "operator comparison",
        },
    ]

    cases = script._parse_query_mix_payload(payload)

    assert len(cases) == 2
    assert cases[0].legacy_query == "budget"
    assert cases[0].normalized_query == "budget"
    assert cases[1].legacy_query == "alice@example.com"
    assert cases[1].normalized_query == "from:alice@example.com"
    assert cases[1].notes == "operator comparison"


@pytest.mark.unit
def test_parse_query_mix_payload_rejects_missing_queries() -> None:
    with pytest.raises(ValueError, match="missing legacy query text"):
        script._parse_query_mix_payload([{"name": "broken"}])


@pytest.mark.unit
def test_build_auto_query_cases_extracts_phrase_and_terms() -> None:
    rows = [
        {
            "title": "Quarterly Budget Update",
            "content": "Budget planning for finance team and forecast details",
            "author": "alice@example.com",
        },
        {
            "title": "Incident Alert",
            "content": "Incident budget impact and mitigation plan",
            "author": "alerts@example.com",
        },
    ]

    cases = script._build_auto_query_cases(rows, query_count=6)
    queries = [case.legacy_query for case in cases]

    assert cases
    assert all(case.legacy_query == case.normalized_query for case in cases)
    assert any(query.startswith('"') and query.endswith('"') for query in queries)
    assert any("budget" in query.lower() for query in queries)


@pytest.mark.unit
def test_evaluate_case_metrics_passes_when_overlap_and_totals_match() -> None:
    metrics = script._evaluate_case_metrics(
        legacy_ids=[10, 20, 30],
        normalized_ids=[30, 10, 20],
        legacy_total=3,
        normalized_total=3,
        thresholds=_thresholds(),
        diff_limit=10,
    )

    assert metrics["overlap_count"] == 3
    assert metrics["precision"] == pytest.approx(1.0)
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["jaccard"] == pytest.approx(1.0)
    assert metrics["total_delta_ratio"] == pytest.approx(0.0)
    assert metrics["pass"] is True
    assert metrics["fail_reasons"] == []


@pytest.mark.unit
def test_evaluate_case_metrics_fails_when_total_delta_ratio_exceeds_threshold() -> None:
    metrics = script._evaluate_case_metrics(
        legacy_ids=[10],
        normalized_ids=[10],
        legacy_total=100,
        normalized_total=5,
        thresholds=_thresholds(),
        diff_limit=10,
    )

    assert metrics["pass"] is False
    assert "total_delta_ratio>0.40" in metrics["fail_reasons"]


@pytest.mark.unit
def test_build_gate_summary_fails_for_low_coverage_and_query_errors() -> None:
    results = [
        {"pass": True, "jaccard": 1.0, "precision": 1.0, "recall": 1.0},
        {"pass": False, "error": "InputError: bad query", "jaccard": 0.0, "precision": 0.0, "recall": 0.0},
    ]
    profile = {"normalized_to_legacy_coverage_ratio": 0.40}

    gate = script._build_gate_summary(
        query_results=results,
        profile=profile,
        thresholds=_thresholds(),
    )

    assert gate["gate_passed"] is False
    assert gate["error_queries"] == 1
    assert "coverage_ratio<0.95" in gate["gate_fail_reasons"]
    assert "query_errors>0" in gate["gate_fail_reasons"]
