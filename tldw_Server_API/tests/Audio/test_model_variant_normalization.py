import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.model_utils import (
    normalize_model_and_variant,
    ALLOWED_PARAKEET_VARIANTS,
)


@pytest.mark.unit
def test_parakeet_combined_sets_variant_when_no_override():
    m, v = normalize_model_and_variant(
        raw_model="parakeet-onnx",
        current_model="parakeet",
        current_variant="standard",
        variant_override=None,
    )
    assert m == "parakeet"
    assert v == "onnx"


@pytest.mark.unit
def test_parakeet_override_wins_over_combined_suffix():
    m, v = normalize_model_and_variant(
        raw_model="parakeet-mlx",
        current_model="parakeet",
        current_variant="standard",
        variant_override="onnx",
    )
    assert m == "parakeet"
    assert v == "onnx"


@pytest.mark.unit
def test_whisper_hyphenated_collapses_to_base():
    m, v = normalize_model_and_variant(
        raw_model="whisper-1",
        current_model="parakeet",
        current_variant="standard",
        variant_override=None,
    )
    assert m == "whisper"
    # variant remains unchanged for non-parakeet
    assert v == "standard"


@pytest.mark.unit
def test_canary_hyphenated_collapses_to_base():
    m, v = normalize_model_and_variant(
        raw_model="canary-1b",
        current_model="parakeet",
        current_variant="onnx",
        variant_override=None,
    )
    assert m == "canary"
    assert v == "onnx"


@pytest.mark.unit
def test_unknown_parakeet_suffix_does_not_set_invalid_variant():
    m, v = normalize_model_and_variant(
        raw_model="parakeet-fast",
        current_model="parakeet",
        current_variant="standard",
        variant_override=None,
    )
    assert m == "parakeet"
    assert v in ALLOWED_PARAKEET_VARIANTS
    assert v != "fast"
