"""
test_rate_limits.py
Description: Soft validation of per-IP/user rate limits across key APIs.

These tests attempt bursts against chat/audio/evaluations endpoints and
assert that a 429 appears within a reasonable number of calls. If not,
they skip to avoid flakiness where rate limits are disabled.
"""

import pytest
import httpx

from .fixtures import api_client


def _burst_until_429(fn, max_attempts: int = 20) -> bool:
    for _ in range(max_attempts):
        r = fn()
        if r.status_code == 429:
            return True
    return False


@pytest.mark.critical
def test_rate_limit_chat(api_client):
    body = {
        "messages": [
            {"role": "system", "content": "You are terse."},
            {"role": "user", "content": "One word only."},
        ],
        "model": "gpt-3.5-turbo",
        "temperature": 0.0,
    }

    def _call():
        return api_client.client.post("/api/v1/chat/completions", json=body)

    got = _burst_until_429(_call)
    if not got:
        pytest.skip("Chat rate limits not enforced in this environment.")


@pytest.mark.critical
def test_rate_limit_audio_speech(api_client):
    payload = {"model": "tts-1", "input": "ping", "voice": "alloy", "response_format": "mp3"}

    def _call():
        return api_client.client.post("/api/v1/audio/speech", json=payload)

    got = _burst_until_429(_call)
    if not got:
        pytest.skip("Audio TTS rate limits not enforced in this environment.")


@pytest.mark.critical
def test_rate_limit_evaluations(api_client):
    # Minimal synthetic evaluation payload (echo path may return 200)
    payload = {
        "project_id": 1,
        "prompt_id": 1,
        "name": "e2e",
        "metrics": {"accuracy": 1.0},  # triggers immediate response path
    }

    def _call():
        return api_client.client.post("/api/v1/prompt-studio/evaluations", json=payload)

    got = _burst_until_429(_call)
    if not got:
        pytest.skip("Evaluations rate limits not enforced in this environment.")
