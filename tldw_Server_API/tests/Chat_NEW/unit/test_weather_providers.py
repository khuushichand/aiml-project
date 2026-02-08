import httpx
import pytest

from tldw_Server_API.app.core.Integrations import weather_providers


@pytest.mark.unit
def test_get_weather_client_falls_back_without_api_key(monkeypatch):
    monkeypatch.setenv("WEATHER_PROVIDER", "openweather")
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    client = weather_providers.get_weather_client()
    assert isinstance(client, weather_providers.NoKeyWeatherClient)


@pytest.mark.unit
def test_get_weather_client_openweather_when_configured(monkeypatch):
    monkeypatch.setenv("WEATHER_PROVIDER", "openweather")
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
    monkeypatch.setenv("WEATHER_UNITS", "imperial")
    monkeypatch.setenv("WEATHER_LANG", "es")
    monkeypatch.setenv("WEATHER_TIMEOUT_MS", "2500")

    client = weather_providers.get_weather_client()
    assert isinstance(client, weather_providers.OpenWeatherClient)
    assert client.units == "imperial"
    assert client.lang == "es"
    assert abs(client.timeout_seconds - 2.5) < 0.001


@pytest.mark.unit
def test_openweather_http_error_response(monkeypatch):
    client = weather_providers.OpenWeatherClient(api_key="k")

    class FakeResponse:
        status_code = 503

        @staticmethod
        def json():
            return {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        @staticmethod
        def get(*args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(weather_providers, "http_client_factory", FakeClient)

    result = client.get_current(location="Boston")
    assert not result.ok
    assert result.metadata.get("error") == "http_error"
    assert result.metadata.get("status_code") == 503


@pytest.mark.unit
def test_openweather_exception_path(monkeypatch):
    client = weather_providers.OpenWeatherClient(api_key="k")

    class RaisingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        @staticmethod
        def get(*args, **kwargs):
            raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(weather_providers, "http_client_factory", RaisingClient)

    result = client.get_current(location="Boston")
    assert not result.ok
    assert result.metadata.get("error") == "exception"
    assert result.metadata.get("provider") == "openweather"


@pytest.mark.unit
def test_openweather_success_response(monkeypatch):
    client = weather_providers.OpenWeatherClient(api_key="k", units="metric")

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "name": "Boston",
                "sys": {"country": "US"},
                "main": {"temp": 12.6},
                "weather": [{"description": "clear sky"}],
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        @staticmethod
        def get(*args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(weather_providers, "http_client_factory", FakeClient)

    result = client.get_current(location="Boston")
    assert result.ok
    assert "Weather for Boston, US" in result.summary
    assert result.metadata.get("provider") == "openweather"
