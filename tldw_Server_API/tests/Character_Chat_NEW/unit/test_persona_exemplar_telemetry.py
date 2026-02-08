"""Unit tests for persona exemplar telemetry metrics."""

import pytest

from tldw_Server_API.app.core.Character_Chat.modules.persona_exemplar_telemetry import (
    compute_persona_exemplar_telemetry,
)


@pytest.mark.unit
def test_persona_telemetry_computes_overlap_metrics():
    telemetry = compute_persona_exemplar_telemetry(
        output_text="Stay calm and answer directly with facts.",
        selected_exemplars=[
            {"text": "Stay calm, answer directly, and pivot to facts."},
            {"text": "Keep your tone measured in press settings."},
        ],
    )

    assert 0.0 <= telemetry["ioo"] <= 1.0
    assert 0.0 <= telemetry["ior"] <= 1.0
    assert 0.0 <= telemetry["lcs"] <= 1.0
    assert telemetry["ioo"] > 0.0
    assert telemetry["ior"] > 0.0


@pytest.mark.unit
def test_persona_telemetry_handles_empty_inputs():
    telemetry = compute_persona_exemplar_telemetry(
        output_text="",
        selected_exemplars=[],
    )

    assert telemetry == {
        "ioo": 0.0,
        "ior": 0.0,
        "lcs": 0.0,
        "safety_flags": [],
    }


@pytest.mark.unit
def test_persona_telemetry_flags_high_copy_ratio_for_long_output():
    exemplar_text = "calm direct factual response"
    long_output = " ".join(["calm", "direct", "factual", "response"] * 50)  # 200 tokens
    telemetry = compute_persona_exemplar_telemetry(
        output_text=long_output,
        selected_exemplars=[{"text": exemplar_text}],
    )

    assert telemetry["ioo"] > 0.4
    assert "ioo_high" in telemetry["safety_flags"]


@pytest.mark.unit
def test_persona_telemetry_flags_refusal_language():
    telemetry = compute_persona_exemplar_telemetry(
        output_text="I cannot assist with that request.",
        selected_exemplars=[{"text": "Keep responses concise."}],
    )

    assert "refusal_detected" in telemetry["safety_flags"]
