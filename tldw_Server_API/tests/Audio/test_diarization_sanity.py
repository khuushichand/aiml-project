import numpy as np
import pytest


def test_agglomerative_metric_fallback(monkeypatch):
    # Import module under test
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    # Build a fake sklearn bundle where AgglomerativeClustering rejects 'metric'
    class FakeAgglomerative:
        def __init__(self, *, n_clusters, linkage="average", metric=None, affinity=None):  # type: ignore[no-redef]
            # Simulate newer API that errors if unexpected kwarg is supplied
            """
            Initialize a fake agglomerative clustering instance used in tests.

            Parameters:
                n_clusters (int): Number of clusters to produce.
                linkage (str): Linkage criterion to use (default "average").
                metric: Unsupported parameter retained to simulate newer sklearn API; must be None.
                affinity: Affinity/distance measure to use.

            Raises:
                TypeError: If `metric` is not None - this fake implementation rejects the `metric` keyword to force fallback behavior in callers.
            """
            if metric is not None:
                # force fallback path
                raise TypeError("metric not supported in this fake; use affinity")
            # accept affinity
            self.n_clusters = n_clusters
            self.linkage = linkage
            self.affinity = affinity

        def fit_predict(self, embeddings):
            # Simple round-robin cluster assignment
            """
            Assigns cluster labels to the provided embeddings in a round-robin fashion.

            Parameters:
                embeddings (Sequence): Iterable of embedding vectors whose length determines the number of samples to label.

            Returns:
                numpy.ndarray: 1-D integer array of length equal to the number of embeddings containing cluster labels in the range [0, n_clusters-1]. The effective number of clusters is int(self.n_clusters) coerced to at least 1.
            """
            n = len(embeddings)
            return np.array([i % max(1, int(self.n_clusters)) for i in range(n)], dtype=int)

    def fake_normalize(x, axis=1, norm="l2"):
        """
        No-op placeholder normalization used for testing; returns the input unchanged.

        Parameters:
            x: Array-like input to "normalize". Accepted for compatibility; not modified.
            axis (int): Ignored; present to match the normalization API.
            norm (str): Ignored; present to match the normalization API.

        Returns:
            The same object passed as `x`, unmodified.
        """
        return x

    fake_bundle = {
        "SpectralClustering": None,  # not used in this test
        "AgglomerativeClustering": FakeAgglomerative,
        "normalize": fake_normalize,
        "silhouette_score": lambda X, labels, metric="cosine": 0.0,  # not used
        "cosine_similarity": lambda A, B: np.zeros((len(A), len(B))),  # not used here
    }

    # Ensure our fake bundle is used by the diarization code
    monkeypatch.setattr(dlib, "_lazy_import_sklearn", lambda: fake_bundle)

    # Create service and set method to agglomerative
    svc = dlib.DiarizationService(config={"clustering_method": dlib.ClusteringMethod.AGGLOMERATIVE.value})

    # Small embedding set
    embeddings = np.random.randn(4, 3).astype(np.float32)

    # Call clustering with explicit number of speakers to skip estimation
    labels = svc._cluster_speakers(embeddings, num_speakers=2)

    assert isinstance(labels, np.ndarray)
    assert labels.shape[0] == embeddings.shape[0]
    # Only 0/1 labels expected from our fake
    assert set(labels.tolist()).issubset({0, 1})


def test_lazy_import_silero_vad_handles_hub_fail(monkeypatch):
    # Import module under test
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    # Force torch to be considered available
    monkeypatch.setattr(dlib, "_torch_available", lambda: True)

    # Provide a fake torch with hub API. set_dir should not crash; load should raise.
    class _FakeHub:
        def set_dir(self, path):
            # accept any path
            """
            Set the internal directory path used by this instance.

            Parameters:
                path (str | os.PathLike): File-system path to assign as the instance's directory.
            """
            self._dir = path

        def load(self, *args, **kwargs):
            # Simulate network/cache failure
            """
            Simulate a hub loading failure by raising a RuntimeError.

            All arguments are ignored; this method always raises a RuntimeError with the message "simulated hub load failure".

            Raises:
                RuntimeError: Indicates the simulated hub load failure.
            """
            raise RuntimeError("simulated hub load failure")

    class _FakeTorch:
        def __init__(self):
            """
            Initialize the fake hub container.

            Creates and assigns a `_FakeHub` instance to the `hub` attribute for use in tests that simulate torch.hub behavior.
            """
            self.hub = _FakeHub()

    monkeypatch.setattr(dlib, "_lazy_import_torch", lambda: _FakeTorch())

    # Call the lazy loader; it should catch the exception and return (None, None)
    model, utils = dlib._lazy_import_silero_vad()
    assert model is None and utils is None


def test_cluster_speakers_with_real_sklearn():
    # Skip if sklearn is not actually installed in the environment
    sklearn = pytest.importorskip("sklearn")

    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    # Create a service configured to use agglomerative clustering
    svc = dlib.DiarizationService(config={"clustering_method": dlib.ClusteringMethod.AGGLOMERATIVE.value})

    # Create synthetic embeddings and request 2 speakers explicitly to avoid estimation path
    rng = np.random.default_rng(0)
    embeddings = rng.normal(size=(10, 5)).astype(np.float32)

    labels = svc._cluster_speakers(embeddings, num_speakers=2)

    assert isinstance(labels, np.ndarray)
    assert labels.shape[0] == embeddings.shape[0]
    # We only requested 2 clusters; labels should reflect that
    assert set(labels.tolist()).issubset({0, 1})


def test_detect_speech_fallback_full_span(monkeypatch):
    # Verify _detect_speech falls back to a full-span region when VAD load fails
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    # Ensure VAD loader fails
    monkeypatch.setattr(dlib, "_lazy_import_silero_vad", lambda: (None, None))

    svc = dlib.DiarizationService()
    # 16k samples at 16kHz => 1.0 second
    waveform = np.zeros(16000, dtype=np.float32)
    segments = svc._detect_speech(waveform, sample_rate=16000, streaming=False)
    assert isinstance(segments, list) and len(segments) == 1
    seg = segments[0]
    assert pytest.approx(seg['start'], rel=1e-6, abs=1e-6) == 0.0
    assert pytest.approx(seg['end'], rel=1e-6, abs=1e-6) == 1.0


def test_overlap_detection_label_mapping(monkeypatch):
    """Ensure overlap detection maps label -> center index correctly when labels are {2,4}."""
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    # Fake sklearn bundle that returns a fixed similarity matrix, regardless of inputs
    def fake_cosine_similarity(A, B):  # shapes: (2, d), (2, d)
        # unique_labels sorted -> [2, 4]; rows correspond to segments 0,1
        # row0 (primary label 2): sims -> [0.65 (label 2), 0.90 (label 4)]
        # row1 (primary label 4): sims -> [0.10 (label 2), 0.95 (label 4)]
        """
        Fake cosine similarity that returns a predefined 2×2 similarity matrix for two segments.

        Parameters:
            A (numpy.ndarray): Embeddings for two segments, shape (2, d). Only shape is considered.
            B (numpy.ndarray): Embeddings for two segments, shape (2, d). Only shape is considered.

        Returns:
            numpy.ndarray: A 2×2 float32 similarity matrix where rows correspond to primary labels [2, 4]
            and columns correspond to labels [2, 4]. Matrix values are:
            [[0.65, 0.90],
             [0.10, 0.95]]
        """
        return np.array([[0.65, 0.90], [0.10, 0.95]], dtype=np.float32)

    fake_bundle = {
        "cosine_similarity": fake_cosine_similarity,
    }
    monkeypatch.setattr(dlib, "_lazy_import_sklearn", lambda: fake_bundle)

    svc = dlib.DiarizationService()
    # Two segments with non-contiguous labels
    primary_labels = np.array([2, 4], dtype=int)
    # Embeddings shape matched to rows; content irrelevant due to fake cosine_similarity
    embeddings = np.zeros((2, 3), dtype=np.float32)
    segments = [
        {"start": 0.0, "end": 1.0},
        {"start": 1.0, "end": 2.0},
    ]

    out = svc._detect_overlapping_speech(segments, embeddings, primary_labels)
    assert out is segments  # in-place mutation expected

    # Segment 0: primary label 2 => primary_index 0 => confidence 0.65 < 0.7 → overlap
    assert segments[0]["is_overlapping"] is True
    assert pytest.approx(segments[0]["primary_confidence"], rel=1e-6) == 0.65
    assert segments[0]["secondary_speakers"][0]["speaker_id"] == 4
    assert pytest.approx(segments[0]["secondary_speakers"][0]["confidence"], rel=1e-6) == 0.90

    # Segment 1: primary label 4 => primary_index 1 => confidence 0.95 >= 0.7 → no overlap
    assert segments[1]["is_overlapping"] is False
    assert pytest.approx(segments[1]["primary_confidence"], rel=1e-6) == 0.95


@pytest.mark.asyncio
async def test_streaming_diarizer_persists_without_soundfile(tmp_path, monkeypatch):
    """Simulate missing 'soundfile' and verify WAV is still written via fallback."""
    import builtins
    import wave

    # Patch imports: make 'soundfile' unavailable
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        """
        Simulates imports but forces a simulated ImportError for the "soundfile" module.

        Parameters:
            name (str): Name of the module to import.
            *args: Positional arguments forwarded to the real import function.
            **kwargs: Keyword arguments forwarded to the real import function.

        Returns:
            The object returned by the real import call for the specified module.

        Raises:
            ImportError: If `name` is "soundfile", raises a simulated ImportError.
        """
        if name == "soundfile":
            raise ImportError("simulated absence of soundfile")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Stub diarization service to avoid heavy deps and still allow finalize() path
    class _StubDiarizationService:
        def __init__(self, *args, **kwargs):
            """
            Initialize the instance and mark it as available.

            Sets the instance attribute `is_available` to True.
            """
            self.is_available = True

        def diarize(self, audio_path, transcription_segments=None, num_speakers=None):
            # pass through segments with a dummy speaker
            """
            Assign all provided transcription segments to a single dummy speaker and return the segments and speaker list.

            Parameters:
                audio_path (str): Path to the audio file (not used by this implementation).
                transcription_segments (list[dict], optional): Sequence of segment dictionaries to pass through. Each returned segment will include `speaker_id` and `speaker_label`.
                num_speakers (int, optional): Ignored by this implementation.

            Returns:
                dict: A mapping with keys:
                    - "segments": list of segment dicts (each original segment augmented with `speaker_id`: 0 and `speaker_label`: "SPEAKER_0").
                    - "speakers": list containing a single speaker dict `{"speaker_id": 0, "speaker_label": "SPEAKER_0"}`.
            """
            segments = []
            for seg in transcription_segments or []:
                segments.append({**seg, "speaker_id": 0, "speaker_label": "SPEAKER_0"})
            return {"segments": segments, "speakers": [{"speaker_id": 0, "speaker_label": "SPEAKER_0"}]}

    # Patch in the stub service
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified as unified

    monkeypatch.setattr(
        unified,
        "DiarizationService",
        _StubDiarizationService,
        raising=False,
    )

    # Import the class under test
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        StreamingDiarizer,
    )

    diarizer = StreamingDiarizer(
        sample_rate=16000,
        store_audio=True,
        storage_dir=str(tmp_path),
    )
    ready = await diarizer.ensure_ready()
    assert ready is True

    # Provide some audio; label one segment to accumulate audio
    audio = np.random.uniform(-0.5, 0.5, size=(16000,)).astype(np.float32)
    meta = {"segment_id": 1, "segment_start": 0.0, "segment_end": 1.0, "text": "hello"}
    await diarizer.label_segment(audio, meta)

    # Finalize should persist audio even without soundfile (fallback to scipy/wave)
    mapping, audio_path, speakers = await diarizer.finalize()
    assert audio_path is not None

    # Verify a readable WAV file is present
    with wave.open(audio_path, "rb") as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() in (2, 4)  # wave fallback uses 16-bit; scipy may vary
        assert wf.getnframes() > 0

    # Persistence method should reflect fallback path
    assert getattr(diarizer, "persistence_method", None) in ("scipy", "wave")


def test_detect_speech_fallback_when_hub_disabled(monkeypatch):
    """When enable_torch_hub_fetch=False, VAD load fails fast and falls back to a full span."""
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib as dlib

    # Ensure any attempt to import Silero returns (None, None) if reached
    monkeypatch.setattr(dlib, "_lazy_import_silero_vad", lambda: (None, None))

    # Build service with hub fetching disabled and allow fallback
    svc = dlib.DiarizationService(config={
        "enable_torch_hub_fetch": False,
        "allow_vad_fallback": True,
    })

    waveform = np.zeros(8000, dtype=np.float32)
    segments = svc._detect_speech(waveform, sample_rate=8000, streaming=False)
    assert len(segments) == 1
    assert segments[0]["start"] == 0.0
    assert pytest.approx(segments[0]["end"], rel=1e-6) == 1.0
