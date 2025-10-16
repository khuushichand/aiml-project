import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2
from tldw_Server_API.app.core.TTS.adapters.base import TTSAdapter, TTSRequest, TTSResponse, AudioFormat, ProviderStatus, TTSCapabilities


class BlockingAdapter(TTSAdapter):
    def __init__(self, state):
        super().__init__({})
        self._status = ProviderStatus.AVAILABLE
        self._initialized = True
        self.state = state  # dict with keys: current, max, event
        self.provider_id = 'mock'

    async def initialize(self) -> bool:
        self._initialized = True
        self._status = ProviderStatus.AVAILABLE
        return True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        # Return a stream that blocks on the shared event after incrementing counters
        async def _stream():
            # Mark active
            self.state['current'] += 1
            self.state['max'] = max(self.state['max'], self.state['current'])
            try:
                # Hold until event is set
                await self.state['event'].wait()
                yield b'chunk'
            finally:
                # Decrement when done
                self.state['current'] -= 1

        return TTSResponse(audio_stream=_stream(), format=AudioFormat.MP3, provider=self.provider_id)

    async def get_capabilities(self) -> TTSCapabilities:
        from tldw_Server_API.app.core.TTS.adapters.base import VoiceInfo
        return TTSCapabilities(
            provider_name=self.provider_id,
            supports_streaming=True,
            supports_voice_cloning=False,
            supported_languages={"en"},
            supported_formats={AudioFormat.MP3},
            max_text_length=5000,
            supported_voices=[VoiceInfo(id='v1', name='V1')]
        )


@pytest.mark.asyncio
async def test_concurrency_respects_config_limit():
    # Shared state for concurrency tracking
    state = {'current': 0, 'max': 0, 'event': asyncio.Event()}

    # Factory stub with performance.max_concurrent_generations=2
    factory = MagicMock()
    registry = MagicMock()
    registry.config = {"performance": {"max_concurrent_generations": 2}}
    factory.registry = registry
    factory.get_adapter_by_model = AsyncMock(side_effect=lambda model: BlockingAdapter(state))

    svc = TTSServiceV2(factory)

    # Build N concurrent streaming requests
    async def run_one():
        req = OpenAISpeechRequest(input='Hello', model='mock', voice='v1', response_format='mp3', stream=True)
        agen = svc.generate_speech(req)
        # Start consumption to enter streaming body and block on event
        try:
            async for _ in agen:
                break
        except Exception:
            pass

    tasks = [asyncio.create_task(run_one()) for _ in range(5)]
    # Allow tasks to start and contend for the semaphore
    await asyncio.sleep(0.1)

    # At most 2 should be active concurrently
    assert state['max'] <= 2

    # Release and finish
    state['event'].set()
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_service_shutdown_closes_cleanly():
    factory = MagicMock()
    registry = MagicMock()
    registry.config = {"performance": {"max_concurrent_generations": 1}}
    factory.registry = registry
    # Close may be async
    async def close():
        return None
    factory.close = AsyncMock(side_effect=close)

    svc = TTSServiceV2(factory)
    # Should not raise
    await svc.shutdown()
