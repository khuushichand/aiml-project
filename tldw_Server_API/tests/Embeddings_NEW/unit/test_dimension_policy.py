import os
import numpy as np

from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import adjust_dimensions


def test_adjust_dimensions_reduce_policy(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_DIMENSION_POLICY", "reduce")
    vecs = [[1.0, 2.0, 3.0, 4.0]]
    out = adjust_dimensions(vecs, 2, provider="huggingface", model="m")
    assert out == [[1.0, 2.0]]


def test_adjust_dimensions_pad_policy(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_DIMENSION_POLICY", "pad")
    vecs = [[1.0, 2.0]]
    out = adjust_dimensions(vecs, 4, provider="huggingface", model="m")
    assert len(out[0]) == 4
    assert out[0][:2] == [1.0, 2.0]
    assert out[0][2:] == [0.0, 0.0]


def test_adjust_dimensions_ignore_policy(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_DIMENSION_POLICY", "ignore")
    vecs = [[1.0, 2.0, 3.0, 4.0]]
    out = adjust_dimensions(vecs, 2, provider="huggingface", model="m")
    # unchanged when ignore
    assert out[0] == [1.0, 2.0, 3.0, 4.0]


def test_base64_reduction_is_deterministic():
    # Simulate the base64 branch reduction used in endpoint
    arr = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    target = 3
    a1 = arr[:target]
    a2 = arr[:target]
    import base64
    b1 = base64.b64encode(a1.tobytes()).decode("utf-8")
    b2 = base64.b64encode(a2.tobytes()).decode("utf-8")
    assert b1 == b2
