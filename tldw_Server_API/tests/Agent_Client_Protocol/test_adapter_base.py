"""Unit tests for ProtocolAdapter ABC, AdapterConfig, and AdapterFactory."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Task 2 tests
# ---------------------------------------------------------------------------

def test_protocol_adapter_is_abstract():
    """Instantiating ProtocolAdapter directly must raise TypeError."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import ProtocolAdapter

    with pytest.raises(TypeError):
        ProtocolAdapter()  # type: ignore[abstract]


def test_adapter_config_creation():
    """AdapterConfig holds event_callback, session_id, and protocol_config."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig

    async def _cb(ev):
        pass

    cfg = AdapterConfig(
        event_callback=_cb,
        session_id="sess-42",
        protocol_config={"foo": "bar"},
    )
    assert cfg.event_callback is _cb
    assert cfg.session_id == "sess-42"
    assert cfg.protocol_config == {"foo": "bar"}


def test_adapter_config_defaults():
    """AdapterConfig protocol_config defaults to empty dict."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig

    async def _cb(ev):
        pass

    cfg = AdapterConfig(event_callback=_cb, session_id="s1")
    assert cfg.protocol_config == {}


def test_prompt_options_defaults():
    """PromptOptions has sensible defaults."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import PromptOptions

    opts = PromptOptions()
    assert opts.max_tokens is None
    assert opts.timeout_sec is None
    assert opts.extra == {}


def test_adapter_factory_register_and_create():
    """Register a FakeAdapter, create it, verify type."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import (
        AdapterConfig,
        ProtocolAdapter,
        PromptOptions,
    )
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.factory import AdapterFactory

    class FakeAdapter(ProtocolAdapter):
        protocol_name = "fake"

        async def connect(self, config: AdapterConfig) -> None:
            pass

        async def disconnect(self) -> None:
            pass

        async def send_prompt(self, messages: list[dict], options: PromptOptions | None = None) -> None:
            pass

        async def send_tool_result(self, tool_id: str, output: str, is_error: bool = False) -> None:
            pass

        async def cancel(self) -> None:
            pass

        @property
        def is_connected(self) -> bool:
            return False

        @property
        def supports_streaming(self) -> bool:
            return False

    factory = AdapterFactory()
    factory.register("fake", FakeAdapter)
    adapter = factory.create("fake")
    assert isinstance(adapter, FakeAdapter)
    assert adapter.protocol_name == "fake"


def test_adapter_factory_unknown_protocol_raises():
    """Creating an unknown protocol raises ValueError."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.factory import AdapterFactory

    factory = AdapterFactory()
    with pytest.raises(ValueError, match="Unknown protocol"):
        factory.create("nonexistent")


def test_adapter_factory_available_protocols():
    """available_protocols returns registered names."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import (
        AdapterConfig,
        ProtocolAdapter,
        PromptOptions,
    )
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.factory import AdapterFactory

    class Dummy(ProtocolAdapter):
        protocol_name = "dummy"

        async def connect(self, config: AdapterConfig) -> None:
            pass

        async def disconnect(self) -> None:
            pass

        async def send_prompt(self, messages: list[dict], options: PromptOptions | None = None) -> None:
            pass

        async def send_tool_result(self, tool_id: str, output: str, is_error: bool = False) -> None:
            pass

        async def cancel(self) -> None:
            pass

        @property
        def is_connected(self) -> bool:
            return False

        @property
        def supports_streaming(self) -> bool:
            return False

    factory = AdapterFactory()
    assert factory.available_protocols() == []
    factory.register("dummy", Dummy)
    assert "dummy" in factory.available_protocols()
