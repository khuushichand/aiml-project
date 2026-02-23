from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeStep:
    name: str
    command: list[str]


def build_steps(base_url: str, api_key: str | None) -> list[SmokeStep]:
    key_args = ["--api-key", api_key] if api_key else []
    return [
        SmokeStep(
            name="streaming_unified",
            command=[
                "python",
                "Helper_Scripts/streaming_unified_smoke.py",
                "--base-url",
                base_url,
                *key_args,
            ],
        ),
        SmokeStep(
            name="watchlists_audio",
            command=[
                "python",
                "Helper_Scripts/watchlists/watchlists_audio_smoke.py",
                "--base-url",
                base_url,
                *key_args,
            ],
        ),
    ]
