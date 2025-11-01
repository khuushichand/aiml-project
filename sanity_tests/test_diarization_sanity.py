import numpy as np
import pytest


def test_agglomerative_metric_fallback(monkeypatch):
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    class FakeAgglomerative:
        def __init__(self, *, n_clusters, linkage="average", metric=None, affinity=None):  # type: ignore[no-redef]
            if metric is not None:
                raise TypeError("metric not supported in this fake; use affinity")
            self.n_clusters = n_clusters

        def fit_predict(self, embeddings):
            n = len(embeddings)
            return np.array([i % max(1, int(self.n_clusters)) for i in range(n)], dtype=int)

    def fake_normalize(x, axis=1, norm="l2"):
        return x

    fake_bundle = {
        "SpectralClustering": None,
        "AgglomerativeClustering": FakeAgglomerative,
        "normalize": fake_normalize,
        "silhouette_score": lambda X, labels, metric="cosine": 0.0,
        "cosine_similarity": lambda A, B: np.zeros((len(A), len(B))),
    }

    monkeypatch.setattr(dlib, "_lazy_import_sklearn", lambda: fake_bundle)

    svc = dlib.DiarizationService(config={"clustering_method": dlib.ClusteringMethod.AGGLOMERATIVE.value})
    embeddings = np.random.randn(4, 3).astype(np.float32)
    labels = svc._cluster_speakers(embeddings, num_speakers=2)

    assert isinstance(labels, np.ndarray)
    assert labels.shape[0] == embeddings.shape[0]
    assert set(labels.tolist()).issubset({0, 1})


def test_lazy_import_silero_vad_handles_hub_fail(monkeypatch):
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    monkeypatch.setattr(dlib, "_torch_available", lambda: True)

    class _FakeHub:
        def set_dir(self, path):
            self._dir = path

        def load(self, *args, **kwargs):
            raise RuntimeError("simulated hub load failure")

    class _FakeTorch:
        def __init__(self):
            self.hub = _FakeHub()

    monkeypatch.setattr(dlib, "_lazy_import_torch", lambda: _FakeTorch())

    model, utils = dlib._lazy_import_silero_vad()
    assert model is None and utils is None

