from __future__ import annotations

from pathlib import Path

import pytest
import yaml


pytestmark = pytest.mark.unit


def test_tts_provider_priority_starts_with_kitten_then_pocket_cpp() -> None:
    config_path = (
        Path(__file__).resolve().parents[2] / "Config_Files" / "tts_providers_config.yaml"
    )
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    provider_priority = config["provider_priority"]

    assert config["providers"]["kitten_tts"]["enabled"] is True
    assert provider_priority[:2] == ["kitten_tts", "pocket_tts_cpp"]
    assert provider_priority.index("kitten_tts") < provider_priority.index("kokoro")
    assert provider_priority.index("pocket_tts_cpp") < provider_priority.index("kokoro")
