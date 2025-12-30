"""
weather_providers.py

Stage 4 stub weather provider abstraction.

Provides a simple interface with a NoKey client that always returns
an "unavailable" message. This allows command router tests to mock
and future providers to plug in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class WeatherResult:
    ok: bool
    summary: str
    metadata: Dict


class WeatherClient:
    def get_current(self, location: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> WeatherResult:
        raise NotImplementedError


class NoKeyWeatherClient(WeatherClient):
    def get_current(self, location: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> WeatherResult:
        loc = location or (f"{lat},{lon}" if lat is not None and lon is not None else "your area")
        return WeatherResult(
            ok=False,
            summary=f"Weather information is unavailable for {loc}.",
            metadata={"provider": "noop", "location": loc},
        )


def get_weather_client() -> WeatherClient:
    # Stage 4: always return NoKey client; future stages may branch on env/API keys
    return NoKeyWeatherClient()
