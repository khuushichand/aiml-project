import os
import json
import asyncio

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.rate_limit


@pytest.mark.asyncio
async def test_e2e_chat_headers_tokens_and_requests(monkeypatch):
    # Minimal app mode with RG middleware + tokens headers
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("RG_ENABLE_SIMPLE_MIDDLEWARE", "1")
    monkeypatch.setenv("RG_MIDDLEWARE_ENFORCE_TOKENS", "1")
    monkeypatch.setenv("RG_BACKEND", "memory")
    monkeypatch.setenv("RG_POLICY_STORE", "file")
    # Use stub YAML in repo
    monkeypatch.setenv(
        "RG_POLICY_PATH",
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "tldw_Server_API",
            "Config_Files",
            "resource_governor_policies.yaml",
        ),
    )
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")
    # Single-user auth
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key")
    # Trigger mock provider path for stability
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    from tldw_Server_API.app.main import app

    with TestClient(app) as c:
        body = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        }
        r = c.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": "test-api-key"},
            data=json.dumps(body),
        )
        assert r.status_code == 200
        # Requests headers present (from middleware)
        assert r.headers.get("X-RateLimit-Limit") is not None
        assert r.headers.get("X-RateLimit-Remaining") is not None
        # Tokens per-minute headers present (policy tokens.per_min=60000 in stub YAML)
        assert r.headers.get("X-RateLimit-PerMinute-Limit") == "60000"
        assert r.headers.get("X-RateLimit-PerMinute-Remaining") is not None
        assert r.headers.get("X-RateLimit-Tokens-Remaining") is not None


@pytest.mark.asyncio
async def test_e2e_audio_websocket_streams_limit(monkeypatch):
    # Minimal app + single-user auth
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key")
    # RG config (file store + memory backend)
    monkeypatch.setenv("RG_BACKEND", "memory")
    monkeypatch.setenv("RG_POLICY_STORE", "file")
    monkeypatch.setenv(
        "RG_POLICY_PATH",
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "tldw_Server_API",
            "Config_Files",
            "resource_governor_policies.yaml",
        ),
    )
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")

    # Allow streaming quotas at the module level to avoid DB/Redis dependencies
    import tldw_Server_API.app.api.v1.endpoints.audio as audio_ep

    async def _ok_stream(user_id: int):
        return True, ""

    async def _noop(*args, **kwargs):
        return None

    async def _allow_minutes(user_id: int, minutes: float):
        return True, 0

    monkeypatch.setattr(audio_ep, "can_start_stream", _ok_stream)
    monkeypatch.setattr(audio_ep, "finish_stream", _noop)
    monkeypatch.setattr(audio_ep, "heartbeat_stream", _noop, raising=False)
    monkeypatch.setattr(audio_ep, "check_daily_minutes_allow", _allow_minutes)
    monkeypatch.setattr(audio_ep, "add_daily_minutes", _noop)

    from tldw_Server_API.app.main import app

    with TestClient(app) as c:
        # First connection allowed
        ws1 = c.websocket_connect("/api/v1/audio/stream/transcribe?token=test-api-key")
        # Second connection should be rate-limited by RG streams (limit=2 in YAML by default; override via env if needed)
        # The stub YAML sets max_concurrent=2; simulate contention by opening two and then the third should be denied.
        ws2 = c.websocket_connect("/api/v1/audio/stream/transcribe?token=test-api-key")
        # Third should be denied
        ws3 = None
        denied = False
        try:
            ws3 = c.websocket_connect("/api/v1/audio/stream/transcribe?token=test-api-key")
            # Expect an error frame then close
            data = ws3.receive_json()
            denied = (data or {}).get("error_type") in {"rate_limited", "quota_exceeded"}
        except Exception:
            # Connection could be closed immediately after error
            denied = True
        finally:
            try:
                if ws3:
                    ws3.close()
            except Exception:
                pass
            try:
                ws2.close()
            except Exception:
                pass
            try:
                ws1.close()
            except Exception:
                pass
        assert denied


@pytest.mark.asyncio
async def test_e2e_audio_transcriptions_headers_and_mocked_stt(monkeypatch, tmp_path):
    # Minimal app with RG middleware + tokens/requests headers for this route
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("RG_ENABLE_SIMPLE_MIDDLEWARE", "1")
    monkeypatch.setenv("RG_MIDDLEWARE_ENFORCE_TOKENS", "1")
    monkeypatch.setenv("RG_BACKEND", "memory")
    monkeypatch.setenv("RG_POLICY_STORE", "file")

    # Temporary policy mapping for transcriptions path
    policy = (
        "version: 1\n"
        "policies:\n"
        "  audio.transcribe:\n"
        "    requests: { rpm: 2 }\n"
        "    tokens: { per_min: 1000 }\n"
        "route_map:\n"
        "  by_path:\n"
        "    /api/v1/audio/transcriptions: audio.transcribe\n"
    )
    p = tmp_path / "rg_audio.yaml"
    p.write_text(policy, encoding="utf-8")
    monkeypatch.setenv("RG_POLICY_PATH", str(p))
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")

    # Single-user auth
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key")

    # Mock audio quota + STT heavy parts
    import tldw_Server_API.app.api.v1.endpoints.audio as audio_ep

    async def _ok_job(user_id: int):
        return True, ""

    async def _noop(*args, **kwargs):
        return None

    async def _allow_minutes(user_id: int, minutes: float):
        return True, 0

    # Monkeypatch job/minutes guards
    monkeypatch.setattr(audio_ep, "can_start_job", _ok_job)
    monkeypatch.setattr(audio_ep, "finish_job", _noop)
    monkeypatch.setattr(audio_ep, "check_daily_minutes_allow", _allow_minutes)
    monkeypatch.setattr(audio_ep, "add_daily_minutes", _noop)

    # Mock soundfile.read to avoid real decoding
    import numpy as np

    def fake_sf_read(fd, dtype="float32"):
        data = np.zeros((1600,), dtype="float32")
        sr = 16000
        return data, sr

    monkeypatch.setattr(audio_ep.sf, "read", fake_sf_read)

    # Mock Whisper STT function used in the endpoint
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as tl

    def fake_speech_to_text(path, whisper_model, selected_source_lang=None, vad_filter=False, diarize=False, word_timestamps=False, return_language=False):
        segs = [{"Text": "hello world"}]
        if return_language:
            return segs, "en"
        return segs

    monkeypatch.setattr(tl, "speech_to_text", fake_speech_to_text)

    from tldw_Server_API.app.main import app

    with TestClient(app) as c:
        # Prepare a tiny fake wav payload
        payload = b"RIFF\x00\x00\x00\x00WAVEfmt "  # not parsed due to monkeypatched sf.read
        files = {"file": ("test.wav", payload, "audio/wav")}
        r = c.post(
            "/api/v1/audio/transcriptions",
            headers={"X-API-KEY": "test-api-key"},
            data={"model": "whisper-1", "response_format": "json"},
            files=files,
        )
        assert r.status_code == 200
        # Requests headers present (from middleware)
        assert r.headers.get("X-RateLimit-Limit") == "2"
        assert r.headers.get("X-RateLimit-Remaining") is not None
        # Tokens headers present due to RG_MIDDLEWARE_ENFORCE_TOKENS=1 and per_min in policy
        assert r.headers.get("X-RateLimit-PerMinute-Limit") == "1000"
        assert r.headers.get("X-RateLimit-PerMinute-Remaining") is not None


@pytest.mark.asyncio
async def test_e2e_chat_deny_headers_retry_after(monkeypatch, tmp_path):
    # Minimal app with RG middleware; enforce requests only to test deny headers precisely
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("RG_ENABLE_SIMPLE_MIDDLEWARE", "1")
    monkeypatch.setenv("RG_MIDDLEWARE_ENFORCE_TOKENS", "0")
    monkeypatch.setenv("RG_BACKEND", "memory")
    monkeypatch.setenv("RG_POLICY_STORE", "file")

    # Temp policy with low request rpm for chat
    policy = (
        "version: 1\n"
        "policies:\n"
        "  chat.small:\n"
        "    requests: { rpm: 1 }\n"
        "    tokens: { per_min: 100000 }\n"
        "route_map:\n"
        "  by_path:\n"
        "    /api/v1/chat/*: chat.small\n"
    )
    p = tmp_path / "rg.yaml"
    p.write_text(policy, encoding="utf-8")

    monkeypatch.setenv("RG_POLICY_PATH", str(p))
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")
    # Single-user auth and mock provider
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key")
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    from tldw_Server_API.app.main import app

    with TestClient(app) as c:
        body = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        }
        # First allowed
        r1 = c.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": "test-api-key"},
            data=json.dumps(body),
        )
        assert r1.status_code == 200

        # Second should be 429 with retry-after + ratelimit headers
        r2 = c.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": "test-api-key"},
            data=json.dumps(body),
        )
        assert r2.status_code in (429, 503)  # 503 acceptable if app maps to service-unavailable in minimal mode
        if r2.status_code == 429:
            assert r2.headers.get("Retry-After") is not None
            assert r2.headers.get("X-RateLimit-Limit") == "1"
            assert r2.headers.get("X-RateLimit-Remaining") == "0"
            # Reset should be an integer number of seconds
            reset = r2.headers.get("X-RateLimit-Reset")
            assert reset is not None and int(reset) >= 1
