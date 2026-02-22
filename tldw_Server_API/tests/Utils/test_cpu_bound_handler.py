import base64

import pytest

from tldw_Server_API.app.core.Utils.cpu_bound_handler import (
    _process_pool_disabled,
    decode_large_base64_async,
    json_encode_heavy,
    process_large_json_async,
    run_cpu_bound_thread,
)


@pytest.mark.asyncio
async def test_process_large_json_async_consistent_encoding():
    small = {"text": "café"}
    large = ["café"] * 200

    assert await process_large_json_async(small) == json_encode_heavy(small)
    assert await process_large_json_async(large) == json_encode_heavy(large)


@pytest.mark.asyncio
async def test_decode_large_base64_async_strips_whitespace():
    data = b"hello world"
    b64 = base64.b64encode(data).decode("ascii")
    spaced = f"{b64[:4]} \n{b64[4:]}"

    decoded = await decode_large_base64_async(spaced)

    assert decoded == data


@pytest.mark.asyncio
async def test_run_cpu_bound_thread_accepts_kwargs():
    def combine(prefix: str, *, suffix: str) -> str:
        return f"{prefix}-{suffix}"

    result = await run_cpu_bound_thread(combine, "left", suffix="right")

    assert result == "left-right"


def test_process_pool_disabled_accepts_testing_y(monkeypatch):
    monkeypatch.delenv("TLDR_DISABLE_CPU_PROCPOOL", raising=False)
    monkeypatch.setenv("TESTING", "y")
    assert _process_pool_disabled() is True
