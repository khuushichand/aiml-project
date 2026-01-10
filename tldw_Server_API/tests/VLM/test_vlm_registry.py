import pytest


def test_vlm_list_backends_importable():
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.VLM.registry import list_backends, get_backend
    except Exception as e:
        pytest.skip(f"VLM module not importable: {e}")

    backends = list_backends()
    assert isinstance(backends, dict)

    # get_backend('nonexistent') should return None
    assert get_backend("__nope__") is None
