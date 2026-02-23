from Helper_Scripts.common.sidecar_profiles import resolve_workers


def test_resolve_workers_tts_only_profile():
    workers = resolve_workers(
        profile="tts-only",
        explicit_workers_csv=None,
        default_workers_csv="media_ingest,audio_jobs,embeddings",
    )
    assert workers == ["audio_jobs"]
