import numpy as np
import pytest


def test_overlap_detection_fields_via_mock_similarity(monkeypatch):


    """Verify is_overlapping, primary_confidence, and secondary_speakers are set using a mocked similarity matrix."""
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    svc = dlib.DiarizationService(config={
        "detect_overlapping_speech": True,
        "overlap_confidence_threshold": 0.7,
    })

    # Build dummy segments and labels for three items with two speakers (labels 0 and 1)
    segments = [
        {"start": 0.0, "end": 1.0},  # primary=0, low confidence
        {"start": 1.0, "end": 2.0},  # primary=1, high confidence
        {"start": 2.0, "end": 3.0},  # primary=1, low confidence
    ]
    primary_labels = np.array([0, 1, 1])
    # Embeddings are not used directly by our mocked cosine_similarity; shape must align with len(segments)
    embeddings = np.zeros((3, 4), dtype=float)

    # Prepare a mocked similarity matrix (3 segments x 2 clusters sorted by unique labels [0,1])
    # Rows: segment -> [sim_to_label0, sim_to_label1]
    sim = np.array([
        [0.50, 0.80],  # segment 0: low primary(0.5) < 0.7 => overlapping, secondary=label1 0.80
        [0.20, 0.90],  # segment 1: high primary(0.9) => not overlapping
        [0.40, 0.60],  # segment 2: low primary(0.6) < 0.7 => overlapping, secondary=label0 0.40
    ])

    def _fake_lazy_import_sklearn():

        return {
            "cosine_similarity": lambda X, Y: sim,
        }

    monkeypatch.setattr(dlib, "_lazy_import_sklearn", _fake_lazy_import_sklearn)

    out = svc._detect_overlapping_speech(segments, embeddings, primary_labels)

    # segment 0 overlapping
    assert out[0].get("is_overlapping") is True
    assert out[0].get("primary_confidence") == pytest.approx(0.50)
    assert out[0].get("secondary_speakers")[0]["speaker_id"] == 1
    assert out[0].get("secondary_speakers")[0]["confidence"] == pytest.approx(0.80)

    # segment 1 not overlapping
    assert out[1].get("is_overlapping") is False
    assert out[1].get("primary_confidence") == pytest.approx(0.90)
    assert "secondary_speakers" not in out[1] or not out[1]["secondary_speakers"]

    # segment 2 overlapping with secondary 0
    assert out[2].get("is_overlapping") is True
    assert out[2].get("primary_confidence") == pytest.approx(0.60)
    assert out[2].get("secondary_speakers")[0]["speaker_id"] == 0
    assert out[2].get("secondary_speakers")[0]["confidence"] == pytest.approx(0.40)
