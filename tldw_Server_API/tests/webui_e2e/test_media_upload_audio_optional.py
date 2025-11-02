import io
import os
import wave
import math
import struct
import shutil
import tempfile

import pytest


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _make_tiny_wav(path: str, seconds: float = 0.3, freq: float = 440.0, rate: int = 16000):
    frames = int(seconds * rate)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(rate)
        for i in range(frames):
            # Sine wave; clip to 16-bit
            val = int(32767 * 0.2 * math.sin(2 * math.pi * freq * (i / rate)))
            wf.writeframes(struct.pack('<h', val))


@pytest.mark.e2e
def test_process_audios_upload_optional(page, server_url):
    if not os.environ.get('RUN_AUDIO_E2E'):
        pytest.skip("Audio E2E disabled; set RUN_AUDIO_E2E=1 to enable.")
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available; skipping audio E2E.")

    # Generate a tiny wav file in temp dir
    with tempfile.TemporaryDirectory() as td:
        wav_path = os.path.join(td, 'tiny.wav')
        _make_tiny_wav(wav_path)

        page.goto(f"{server_url}/webui/")
        page.get_by_role("tab", name="Media").click()
        page.get_by_role("tab", name="Processing (No DB)").click()

        # Scroll to the Process Audios section
        page.get_by_text("POST /api/v1/media/process-audios").scroll_into_view_if_needed()

        # Disable analysis to avoid external LLM dependency
        checkbox = page.locator("#processAudios_perform_analysis")
        if checkbox.is_checked():
            checkbox.uncheck()

        # Attach the test wav
        page.set_input_files("#processAudios_files", wav_path)

        # Send the request (scoped button)
        page.locator("#processAudios").get_by_text("Send Request").click()

        # Wait for response to render
        page.wait_for_selector("#processAudios_response")
        resp_text = page.locator("#processAudios_response").inner_text()

        # Basic sanity: backend responded and included results structure for our file
        assert "results" in resp_text
        assert "tiny.wav" in resp_text
