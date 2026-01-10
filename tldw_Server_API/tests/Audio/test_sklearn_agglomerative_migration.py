import pytest


def test_agglomerative_param_compatibility():


    """Ensure AgglomerativeClustering accepts 'metric' on newer sklearn or falls back to 'affinity'."""
    try:
        from sklearn.cluster import AgglomerativeClustering  # type: ignore
    except Exception:
        pytest.skip("scikit-learn not available")

    # Prefer new API (metric); if not supported, fall back to affinity
    ok = False
    try:
        _ = AgglomerativeClustering(n_clusters=2, linkage="average", metric="cosine")
        ok = True
    except TypeError:
        # Older sklearn: use affinity
        _ = AgglomerativeClustering(n_clusters=2, linkage="average", affinity="cosine")
        ok = True

    assert ok is True
