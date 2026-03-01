from Helper_Scripts.common.tooling_smoke_runner import build_steps


def test_build_steps_default_includes_streaming_and_watchlists():
    steps = build_steps(base_url="http://127.0.0.1:8000", api_key="test-key")
    names = [step.name for step in steps]
    assert names == ["streaming_unified", "watchlists_audio"]
