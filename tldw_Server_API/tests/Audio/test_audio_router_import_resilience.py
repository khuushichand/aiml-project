import importlib
import sys
from types import ModuleType

import pytest


@pytest.mark.unit
def test_audio_router_import_survives_broken_streaming_module(monkeypatch):
    """Aggregate audio router should still expose REST routes when streaming import breaks."""
    audio_module_name = "tldw_Server_API.app.api.v1.endpoints.audio.audio"
    streaming_module_name = "tldw_Server_API.app.api.v1.endpoints.audio.audio_streaming"
    original_audio_module = sys.modules.pop(audio_module_name, None)
    original_streaming_module = sys.modules.get(streaming_module_name)

    class _BrokenStreamingModule(ModuleType):
        def __getattr__(self, name: str):
            raise RuntimeError(f"streaming dependency unavailable for {name}")

    monkeypatch.setitem(sys.modules, streaming_module_name, _BrokenStreamingModule(streaming_module_name))

    try:
        audio_module = importlib.import_module(audio_module_name)
        route_paths = {route.path for route in audio_module.router.routes}

        assert "/transcriptions" in route_paths
        assert "/transcriptions/health" in route_paths
        assert all(not path.startswith("/stream") for path in route_paths)
        assert audio_module.ws_router.routes == []
    finally:
        sys.modules.pop(audio_module_name, None)
        if original_streaming_module is not None:
            sys.modules[streaming_module_name] = original_streaming_module
        else:
            sys.modules.pop(streaming_module_name, None)
        if original_audio_module is not None:
            sys.modules[audio_module_name] = original_audio_module
