from pathlib import Path


def test_inprocess_testclient_fallback_enters_lifespan() -> None:
    source = Path("tldw_Server_API/tests/e2e/fixtures.py").read_text(encoding="utf-8")
    if "from tldw_Server_API.app.main import app" not in source:
        raise AssertionError("fallback helper must import the shared FastAPI app")
    if "def _build_started_testclient():" not in source:
        raise AssertionError("missing _build_started_testclient helper")
    if "client.__enter__()" not in source:
        raise AssertionError("TestClient fallback must enter lifespan")
    if source.count("return _build_started_testclient()") < 2:
        raise AssertionError("both fallback branches must use started TestClient")
