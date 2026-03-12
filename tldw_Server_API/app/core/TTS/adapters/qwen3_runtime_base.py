from __future__ import annotations

from typing import Protocol

from .base import TTSCapabilities, TTSRequest, TTSResponse


class Qwen3Runtime(Protocol):
    runtime_name: str

    async def initialize(self) -> bool:
        ...

    async def get_capabilities(self) -> TTSCapabilities:
        ...

    async def generate(self, request: TTSRequest, resolved_model: str, mode: str) -> TTSResponse:
        ...
