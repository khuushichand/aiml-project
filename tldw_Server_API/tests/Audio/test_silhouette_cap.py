import numpy as np


def test_silhouette_estimation_capped(monkeypatch):


     """Ensure _estimate_num_speakers does not try more than max_speakers on large inputs."""
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    attempts = []

    class _FakeSpectral:
        def __init__(self, n_clusters, affinity=None, assign_labels=None, random_state=None):
                     attempts.append(int(n_clusters))

        def fit_predict(self, embeddings):

                     n = max(2, attempts[-1])
            # Return a simple repeating pattern of labels in [0..n-1]
            idxs = np.arange(len(embeddings)) % n
            return idxs

    def _fake_silhouette_score(embeddings, labels, metric=None):

             return 0.5

    def _fake_lazy_import_sklearn():

             return {
            "SpectralClustering": _FakeSpectral,
            "silhouette_score": _fake_silhouette_score,
        }

    monkeypatch.setattr(dlib, "_lazy_import_sklearn", _fake_lazy_import_sklearn)

    svc = dlib.DiarizationService(config={
        "max_speakers": 5,
    })

    embeddings = np.zeros((100, 8), dtype=float)  # large number of segments
    _ = svc._estimate_num_speakers(embeddings)

    assert attempts, "No attempts recorded"
    assert max(attempts) <= 5, f"Tried {max(attempts)} speakers when max_speakers=5"
    # Should attempt exactly 2..5
    assert attempts == [2, 3, 4, 5]
