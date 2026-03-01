import pytest

from tldw_Server_API.app.api.v1.endpoints import media as media_mod


def test_media_module_no_longer_exposes_video_audio_shim_wrappers() -> None:
    assert not callable(getattr(media_mod, "process_videos", None))
    assert not hasattr(media_mod, "process_audio_files")


def test_media_module_no_longer_exposes_document_like_shim() -> None:
    assert not hasattr(media_mod, "_process_document_like_item")
