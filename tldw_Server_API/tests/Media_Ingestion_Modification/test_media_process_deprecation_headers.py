from pathlib import Path


PROCESS_ENDPOINT_DEPRECATION_SOURCES = {
    "process_videos.py": "/api/v1/media/process-videos",
    "process_audios.py": "/api/v1/media/process-audios",
    "process_pdfs.py": "/api/v1/media/process-pdfs",
    "process_documents.py": "/api/v1/media/process-documents",
    "process_ebooks.py": "/api/v1/media/process-ebooks",
}


def _endpoint_source_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "media"
    )


def test_process_endpoint_sources_wire_deprecation_signal_for_legacy_url_sentinel():
    source_dir = _endpoint_source_dir()
    for filename, successor_path in PROCESS_ENDPOINT_DEPRECATION_SOURCES.items():
        source = (source_dir / filename).read_text(encoding="utf-8")
        assert "build_media_legacy_signal(" in source
        assert "apply_media_legacy_headers(" in source
        assert successor_path in source
        assert "legacy_urls_empty_sentinel" in source

