import pytest

from tldw_Server_API.app.core.Usage import audio_quota


@pytest.mark.asyncio
async def test_audio_stream_rg_unavailable_uses_diagnostics_only_shim(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    audio_quota._reset_in_process_counters_for_tests()

    async def _no_rg_governor():
        return None

    fallback_reasons: list[str] = []

    async def _capture_fallback(reason: str):
        fallback_reasons.append(reason)

    monkeypatch.setattr(audio_quota, "_rg_audio_enabled", lambda: True)
    monkeypatch.setattr(audio_quota, "_get_audio_rg_governor", _no_rg_governor)
    monkeypatch.setattr(audio_quota, "_log_rg_audio_fallback", _capture_fallback)

    ok, msg = await audio_quota.can_start_stream(123)

    assert ok is True
    assert msg == "OK"
    assert fallback_reasons == ["rg_governor_unavailable_streams"]
    assert audio_quota._rg_stream_handles == {}
    assert audio_quota._rg_job_handles == {}

    # No-op in diagnostics-only mode when no RG handles exist.
    await audio_quota.finish_stream(123)
    await audio_quota.heartbeat_stream(123)


@pytest.mark.asyncio
async def test_audio_jobs_rg_unavailable_uses_diagnostics_only_shim(monkeypatch):
    monkeypatch.setenv("RG_ENABLED", "1")
    audio_quota._reset_in_process_counters_for_tests()

    async def _no_rg_governor():
        return None

    fallback_reasons: list[str] = []

    async def _capture_fallback(reason: str):
        fallback_reasons.append(reason)

    monkeypatch.setattr(audio_quota, "_rg_audio_enabled", lambda: True)
    monkeypatch.setattr(audio_quota, "_get_audio_rg_governor", _no_rg_governor)
    monkeypatch.setattr(audio_quota, "_log_rg_audio_fallback", _capture_fallback)

    ok, msg = await audio_quota.can_start_job(123)

    assert ok is True
    assert msg == "OK"
    assert fallback_reasons == ["rg_governor_unavailable_jobs"]
    assert audio_quota._rg_stream_handles == {}
    assert audio_quota._rg_job_handles == {}

    # No-op in diagnostics-only mode when no RG handles exist.
    await audio_quota.finish_job(123)
    await audio_quota.heartbeat_jobs(123)
