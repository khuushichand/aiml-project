from tldw_Server_API.app.core.File_Artifacts.file_artifacts_service import (
    FileArtifactsService,
    INLINE_MAX_BYTES_UPPER_BOUND,
)


def test_inline_max_bytes_caps_at_upper_bound(monkeypatch):
    monkeypatch.setenv("FILES_INLINE_MAX_BYTES", str(INLINE_MAX_BYTES_UPPER_BOUND + 1))
    assert FileArtifactsService._resolve_inline_max_bytes() == INLINE_MAX_BYTES_UPPER_BOUND
