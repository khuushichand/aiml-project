import json
import os
import subprocess
from pathlib import Path

import pytest


def test_start_sidecars_default_health_url_targets_root_health():
    script = Path("start-sidecars.sh").read_text(encoding="utf-8")
    if 'TLDW_SERVER_HEALTH_URL:-http://${UVICORN_HOST}:${UVICORN_PORT}/health}' not in script:
        pytest.fail("Expected start-sidecars.sh to default health probe URL to /health")


def test_start_sidecars_dry_run_profile(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "default_workers": ["media_ingest", "audio_jobs"],
                "workers": [
                    {"key": "media_ingest", "slug": "media", "module": "x.y.z"},
                    {"key": "audio_jobs", "slug": "audio", "module": "x.y.z"},
                ],
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["TLDW_WORKERS_MANIFEST"] = str(manifest)
    env["TLDW_SIDECAR_PROFILE"] = "tts-only"
    env["TLDW_SIDECAR_DRY_RUN"] = "true"
    env["PYTHON_BIN"] = "python3"

    result = subprocess.run(
        ["bash", "start-sidecars.sh"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    assert result.returncode == 0
    assert "audio_jobs" in result.stdout
    assert "media_ingest" not in result.stdout
