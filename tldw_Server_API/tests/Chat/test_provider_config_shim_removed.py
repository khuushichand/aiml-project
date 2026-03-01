from pathlib import Path


def test_provider_config_shim_removed() -> None:
    shim_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "core"
        / "Chat"
        / "provider_config.py"
    )
    assert not shim_path.exists()  # nosec B101
