from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


def _stt_provider_adapter_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "app"
        / "core"
        / "Ingestion_Media_Processing"
        / "Audio"
        / "stt_provider_adapter.py"
    )


def test_stt_provider_adapter_has_no_top_level_audio_transcription_import() -> None:
    module_path = _stt_provider_adapter_path()
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert (
                module_name != ".Audio_Transcription_Lib"
            ), "stt_provider_adapter should not import Audio_Transcription_Lib at module import time"


def test_media_processing_deps_import_does_not_abort_process() -> None:
    script = (
        "import tldw_Server_API.app.api.v1.API_Deps.media_processing_deps as deps\n"
        "print(bool(deps))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("True"), result.stdout
