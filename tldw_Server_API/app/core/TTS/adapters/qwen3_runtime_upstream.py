from __future__ import annotations

from typing import TYPE_CHECKING

from .base import TTSCapabilities, TTSRequest, TTSResponse

if TYPE_CHECKING:
    from .qwen3_tts_adapter import Qwen3TTSAdapter


class Qwen3UpstreamRuntime:
    runtime_name = "upstream"

    def __init__(self, adapter: "Qwen3TTSAdapter") -> None:
        self.adapter = adapter

    async def initialize(self) -> bool:
        return await self.adapter._initialize_upstream_runtime()

    async def get_capabilities(self) -> TTSCapabilities:
        return await self.adapter._get_upstream_capabilities()

    async def generate(self, request: TTSRequest, resolved_model: str, mode: str) -> TTSResponse:
        response = await self.adapter._generate_with_upstream_runtime(
            request=request,
            resolved_model=resolved_model,
            mode=mode,
        )
        response.metadata.setdefault("runtime", self.runtime_name)
        return response
