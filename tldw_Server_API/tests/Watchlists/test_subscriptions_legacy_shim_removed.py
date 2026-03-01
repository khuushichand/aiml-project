from pathlib import Path


def test_subscriptions_legacy_shim_removed() -> None:
    shim_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "subscriptions_legacy.py"
    )
    assert not shim_path.exists()  # nosec B101
