import os
import numpy as np
import pytest

from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import (
    decide_and_apply_l2,
)


@pytest.mark.unit
def test_base64_never_normalizes(monkeypatch):
     # Ensure env is unset to avoid influencing behavior
    monkeypatch.delenv("LLM_EMBEDDINGS_L2_NORMALIZE", raising=False)

    emb = [3.0, 4.0]
    arr, did_l2 = decide_and_apply_l2(emb, encoding_format="base64", embeddings_from_adapter=False)

    assert did_l2 is False
    # Norm remains as original (5.0)
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-6) == 5.0


@pytest.mark.unit
def test_numeric_default_normalizes_non_adapter(monkeypatch):
     monkeypatch.delenv("LLM_EMBEDDINGS_L2_NORMALIZE", raising=False)

    emb = [3.0, 4.0]
    arr, did_l2 = decide_and_apply_l2(emb, encoding_format="float", embeddings_from_adapter=False)

    assert did_l2 is True
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-6) == 1.0
    assert pytest.approx(arr[0], rel=0.0, abs=1e-6) == 0.6
    assert pytest.approx(arr[1], rel=0.0, abs=1e-6) == 0.8


@pytest.mark.unit
def test_adapter_vectors_preserved_by_default(monkeypatch):
     monkeypatch.delenv("LLM_EMBEDDINGS_L2_NORMALIZE", raising=False)

    emb = [3.0, 4.0]
    arr, did_l2 = decide_and_apply_l2(emb, encoding_format="float", embeddings_from_adapter=True)

    # Default behavior preserves adapter-provided vectors as-is
    assert did_l2 is False
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-6) == 5.0


@pytest.mark.unit
def test_adapter_vectors_normalize_when_env_truthy(monkeypatch):
     monkeypatch.setenv("LLM_EMBEDDINGS_L2_NORMALIZE", "true")

    emb = [3.0, 4.0]
    arr, did_l2 = decide_and_apply_l2(emb, encoding_format="float", embeddings_from_adapter=True)

    assert did_l2 is True
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-6) == 1.0


@pytest.mark.unit
def test_env_false_non_adapter_still_normalizes(monkeypatch):
     # Explicitly set false, which only disables L2 for adapter-supplied vectors
    monkeypatch.setenv("LLM_EMBEDDINGS_L2_NORMALIZE", "false")

    emb = [3.0, 4.0]
    arr, did_l2 = decide_and_apply_l2(emb, encoding_format="float", embeddings_from_adapter=False)

    assert did_l2 is True
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-6) == 1.0


@pytest.mark.unit
def test_error_during_norm_returns_original_and_logs(monkeypatch):
     # Force an error in np.linalg.norm to exercise error path
    original_norm = np.linalg.norm
    monkeypatch.setenv("LLM_EMBEDDINGS_L2_NORMALIZE", "true")

    def boom(_):

             raise RuntimeError("norm failed")

    monkeypatch.setattr(np.linalg, "norm", boom)

    emb = [1.0, 2.0, 2.0]
    arr, did_l2 = decide_and_apply_l2(emb, encoding_format="float", embeddings_from_adapter=False)

    # Should not have raised; should return original values (no L2 applied)
    assert did_l2 is False
    assert np.allclose(arr, np.asarray(emb, dtype=np.float32))


@pytest.mark.unit
def test_zero_vector_no_divide(monkeypatch):
     monkeypatch.delenv("LLM_EMBEDDINGS_L2_NORMALIZE", raising=False)
    emb = [0.0, 0.0, 0.0]
    arr, did_l2 = decide_and_apply_l2(emb, encoding_format="float", embeddings_from_adapter=False)

    # did_l2 reflects the policy decision (numeric → True), but vector remains unchanged
    assert did_l2 is True
    assert np.allclose(arr, np.asarray(emb, dtype=np.float32))
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-6) == 0.0


@pytest.mark.unit
def test_unknown_encoding_treated_as_numeric(monkeypatch):
     monkeypatch.delenv("LLM_EMBEDDINGS_L2_NORMALIZE", raising=False)
    emb = [3.0, 4.0]
    arr, did_l2 = decide_and_apply_l2(emb, encoding_format="xyz", embeddings_from_adapter=False)

    assert did_l2 is True
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-6) == 1.0


@pytest.mark.unit
def test_base64_ignores_env_truthy(monkeypatch):
     # Even if env requests normalization, base64 outputs are never normalized
    monkeypatch.setenv("LLM_EMBEDDINGS_L2_NORMALIZE", "1")
    emb = [3.0, 4.0]
    arr, did_l2 = decide_and_apply_l2(emb, encoding_format="base64", embeddings_from_adapter=False)

    assert did_l2 is False
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-6) == 5.0


@pytest.mark.unit
def test_mixed_batch_default_preserves_adapters(monkeypatch):
     # Default: non-adapter numeric → normalize; adapter numeric → preserve
    monkeypatch.delenv("LLM_EMBEDDINGS_L2_NORMALIZE", raising=False)

    e1 = [1.0, 2.0, 2.0]  # non-adapter
    e2 = [3.0, 4.0, 0.0]  # adapter

    a1, d1 = decide_and_apply_l2(e1, encoding_format="float", embeddings_from_adapter=False)
    a2, d2 = decide_and_apply_l2(e2, encoding_format="float", embeddings_from_adapter=True)

    assert d1 is True
    assert pytest.approx(np.linalg.norm(a1), rel=0.0, abs=1e-6) == 1.0

    assert d2 is False
    assert pytest.approx(np.linalg.norm(a2), rel=0.0, abs=1e-6) == np.linalg.norm(np.asarray(e2, dtype=np.float32))


@pytest.mark.unit
def test_mixed_batch_env_truthy_normalizes_all(monkeypatch):
     # Env truthy: both adapter and non-adapter numeric normalize
    monkeypatch.setenv("LLM_EMBEDDINGS_L2_NORMALIZE", "true")

    e1 = [1.0, 2.0, 2.0]
    e2 = [3.0, 4.0, 0.0]

    a1, d1 = decide_and_apply_l2(e1, encoding_format="float", embeddings_from_adapter=False)
    a2, d2 = decide_and_apply_l2(e2, encoding_format="float", embeddings_from_adapter=True)

    assert d1 is True and d2 is True
    assert pytest.approx(np.linalg.norm(a1), rel=0.0, abs=1e-6) == 1.0
    assert pytest.approx(np.linalg.norm(a2), rel=0.0, abs=1e-6) == 1.0


@pytest.mark.unit
def test_high_dim_non_adapter_normalizes_and_float32(monkeypatch):
     monkeypatch.delenv("LLM_EMBEDDINGS_L2_NORMALIZE", raising=False)
    vec = np.arange(1, 4097, dtype=np.float64)  # 4096-dim
    arr, did_l2 = decide_and_apply_l2(vec, encoding_format="float", embeddings_from_adapter=False)

    assert did_l2 is True
    assert arr.dtype == np.float32
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-5) == 1.0


@pytest.mark.unit
def test_high_dim_adapter_preserved_by_default(monkeypatch):
     monkeypatch.delenv("LLM_EMBEDDINGS_L2_NORMALIZE", raising=False)
    vec = np.arange(1, 4097, dtype=np.float64)
    original_norm = float(np.linalg.norm(vec.astype(np.float32)))
    arr, did_l2 = decide_and_apply_l2(vec, encoding_format="float", embeddings_from_adapter=True)

    assert did_l2 is False
    assert pytest.approx(np.linalg.norm(arr), rel=0.0, abs=1e-5) == original_norm
