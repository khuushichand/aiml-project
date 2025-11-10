import numpy as np
import pytest


def test_agglomerative_metric_fallback(monkeypatch):
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    calls = []  # track constructor calls to verify fallback path

    class FakeAgglomerative:
        def __init__(self, *, n_clusters, linkage="average", metric=None, affinity=None):  # type: ignore[no-redef]
            """
            Initialize a FakeAgglomerative clustering stub used for tests.

            Parameters:
                n_clusters (int): Number of clusters to produce; stored on the instance as `self.n_clusters`.
                linkage (str): Linkage method (default "average"); accepted but not functionally used.
                metric: Must be None; providing a value raises TypeError instructing to use `affinity`.
                affinity: Accepted for compatibility but not used by the fake implementation.
            """
            calls.append({"metric": metric, "affinity": affinity})
            if metric is not None:
                raise TypeError("metric not supported in this fake; use affinity")
            self.n_clusters = n_clusters

        def fit_predict(self, embeddings):
            """
            Return deterministic cluster labels that cycle from 0 up to n_clusters - 1.

            Parameters:
                embeddings (Sequence): Collection of embedding vectors; only the number of items is used.

            Returns:
                np.ndarray: 1-D integer array of length len(embeddings) with labels in the range 0..max(1, int(self.n_clusters)) - 1.
            """
            n = len(embeddings)
            return np.array([i % max(1, int(self.n_clusters)) for i in range(n)], dtype=int)

    def fake_normalize(x, axis=1, norm="l2"):
        """
        No-op normalization used in tests; returns the input unchanged.

        Parameters:
            x: array-like
                Input array to "normalize".
            axis (int, optional):
                Axis along which normalization would be applied (ignored).
            norm (str, optional):
                Norm type that would be used (ignored).

        Returns:
            array-like: The same object passed in as `x`, unmodified.
        """
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
    # Verify fallback occurred: first attempt with metric, retry with affinity
    assert len(calls) >= 2, "Expected metric->affinity fallback to trigger two constructor calls"
    assert calls[0]["metric"] is not None, "First attempt should pass metric"
    assert calls[1]["metric"] is None and calls[1]["affinity"] is not None, "Fallback should use affinity"


def test_lazy_import_silero_vad_handles_hub_fail(monkeypatch):
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    # Reset global cache to ensure test isolation for VAD lazy import
    monkeypatch.setattr(dlib, "_silero_vad_model", None)
    monkeypatch.setattr(dlib, "_silero_vad_utils", None)

    monkeypatch.setattr(dlib, "_torch_available", lambda: True)

    class _FakeHub:
        def set_dir(self, path):
            """
            Set the directory path used by the hub loader.

            Parameters:
                path (str): Filesystem path to use as the hub directory.
            """
            self._dir = path

        def load(self, *args, **kwargs):
            """
            Simulate a failed hub model load.

            This function always raises a RuntimeError to emulate a failure when loading a model from the hub.

            Raises:
                RuntimeError: Always raised with the message "simulated hub load failure".
            """
            raise RuntimeError("simulated hub load failure")

    class _FakeTorch:
        def __init__(self):
            """
            Initialize a fake Torch wrapper that exposes a Hub instance for simulating torch.hub behavior.

            The instance attribute `hub` is set to a new `_FakeHub`, which can be used to simulate hub directory configuration and load failures in tests.
            """
            self.hub = _FakeHub()

    monkeypatch.setattr(dlib, "_lazy_import_torch", lambda: _FakeTorch())

    model, utils = dlib._lazy_import_silero_vad()
    assert model is None and utils is None
