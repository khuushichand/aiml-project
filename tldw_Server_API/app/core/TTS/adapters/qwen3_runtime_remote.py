from __future__ import annotations

import base64
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from tldw_Server_API.app.core.http_client import apost

from ..tts_exceptions import TTSProviderInitializationError
from ..tts_resource_manager import get_resource_manager
from .base import AudioFormat, TTSCapabilities, TTSRequest, TTSResponse

if TYPE_CHECKING:
    from .qwen3_tts_adapter import Qwen3TTSAdapter


class RemoteQwenRuntime:
    runtime_name = "remote"

    def __init__(self, adapter_or_config: "Qwen3TTSAdapter | dict[str, Any]") -> None:
        if hasattr(adapter_or_config, "config"):
            adapter = adapter_or_config
            self._adapter = adapter
            self.config = dict(getattr(adapter, "config", {}) or {})
            self.provider_key = getattr(adapter, "PROVIDER_KEY", "qwen3_tts")
            self.provider_name = getattr(adapter, "provider_name", self.provider_key)
            self.sample_rate = getattr(adapter, "sample_rate", 24000)
            self.supported_languages = set(getattr(adapter, "SUPPORTED_LANGUAGES", {"en"}))
            self.supported_voices = [
                getattr(adapter, "CUSTOMVOICE_SPEAKERS", []),
            ][0]
        else:
            self._adapter = None
            self.config = dict(adapter_or_config or {})
            self.provider_key = "qwen3_tts"
            self.provider_name = "Qwen3TTS"
            self.sample_rate = int(self.config.get("sample_rate") or 24000)
            self.supported_languages = {"auto", "en", "zh", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"}
            self.supported_voices = []

        self.base_url = str(self.config.get("base_url") or "").strip()
        self.api_key = str(self.config.get("api_key") or "").strip() or None
        self.client = None

    async def initialize(self) -> bool:
        if not self.base_url:
            raise TTSProviderInitializationError(
                "Qwen3-TTS remote runtime requires base_url",
                provider=self.provider_key,
            )
        resource_manager = await get_resource_manager()
        self.client = await resource_manager.get_http_client(
            provider=f"{self.provider_key}_{self.runtime_name}",
            base_url=self.base_url,
        )
        return True

    async def get_capabilities(self) -> TTSCapabilities:
        supported_voices = []
        if self.supported_voices:
            from .base import VoiceInfo

            supported_voices = [VoiceInfo(id=voice, name=voice) for voice in self.supported_voices]
        return TTSCapabilities(
            provider_name=self.provider_name,
            supported_languages=set(self.supported_languages),
            supported_voices=supported_voices,
            supported_formats={
                AudioFormat.MP3,
                AudioFormat.OPUS,
                AudioFormat.AAC,
                AudioFormat.WAV,
                AudioFormat.PCM,
            },
            max_text_length=int(self.config.get("max_text_length") or 5000),
            supports_streaming=True,
            supports_voice_cloning=True,
            supports_emotion_control=True,
            sample_rate=self.sample_rate,
            default_format=AudioFormat.PCM,
            metadata={
                "runtime": self.runtime_name,
                "supported_modes": [
                    "custom_voice_preset",
                    "uploaded_custom_voice",
                    "voice_design",
                ],
                "supports_uploaded_custom_voices": True,
            },
        )

    def _build_payload(self, request: TTSRequest, resolved_model: str, mode: str) -> dict[str, Any]:
        extras = request.extra_params or {}
        payload: dict[str, Any] = {
            "model": resolved_model,
            "input": request.text,
            "voice": request.voice or "",
            "response_format": request.format.value,
            "speed": request.speed,
            "extra_body": {},
        }

        language = request.language or extras.get("language")
        if isinstance(language, str) and language.strip():
            payload["extra_body"]["language"] = language.strip()

        if mode == "voice_clone":
            ref_text = (
                extras.get("reference_text")
                or extras.get("ref_text")
                or extras.get("voice_reference_text")
            )
            if ref_text:
                payload["extra_body"]["ref_text"] = ref_text
            if request.voice_reference:
                payload["extra_body"]["ref_audio_b64"] = base64.b64encode(request.voice_reference).decode("ascii")
            if extras.get("x_vector_only_mode") is not None:
                payload["extra_body"]["x_vector_only_mode"] = extras.get("x_vector_only_mode")
            if extras.get("voice_clone_prompt") is not None:
                payload["extra_body"]["voice_clone_prompt"] = extras.get("voice_clone_prompt")
        elif mode == "voice_design":
            description = extras.get("description") or extras.get("instruction") or extras.get("instruct")
            if description:
                payload["extra_body"]["description"] = description

        return payload

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _stream_audio(
        self,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> AsyncGenerator[bytes, None]:
        response = await apost(
            url=self.base_url,
            client=self.client,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        try:
            async for chunk in response.aiter_bytes(chunk_size=1024):
                if chunk:
                    yield chunk
        finally:
            if hasattr(response, "aclose"):
                await response.aclose()  # type: ignore[func-returns-value]

    async def _generate_complete(self, headers: dict[str, str], payload: dict[str, Any]) -> bytes:
        response = await apost(
            url=self.base_url,
            client=self.client,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.content

    async def generate(self, request: TTSRequest, resolved_model: str, mode: str) -> TTSResponse:
        payload = self._build_payload(request, resolved_model=resolved_model, mode=mode)
        headers = self._build_headers()

        if request.stream:
            return TTSResponse(
                audio_stream=self._stream_audio(headers, payload),
                format=request.format,
                sample_rate=self.sample_rate,
                provider=self.provider_key,
                model=resolved_model,
                metadata={"runtime": self.runtime_name},
            )

        audio_data = await self._generate_complete(headers, payload)
        return TTSResponse(
            audio_content=audio_data,
            format=request.format,
            sample_rate=self.sample_rate,
            provider=self.provider_key,
            model=resolved_model,
            metadata={"runtime": self.runtime_name},
        )
