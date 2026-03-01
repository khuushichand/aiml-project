from pathlib import Path


def test_ingestion_claims_compat_shims_removed() -> None:
    ingestion_root = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "core"
        / "Ingestion_Media_Processing"
    )
    claims_dir = ingestion_root / "Claims"
    assert not (claims_dir / "ingestion_claims.py").exists()  # nosec B101
    assert not (claims_dir / "claims_engine.py").exists()  # nosec B101
    assert not (ingestion_root / "claims_utils.py").exists()  # nosec B101


def test_claims_rebuild_service_compat_shim_removed() -> None:
    service_shim = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "claims_rebuild_service.py"
    )
    assert not service_shim.exists()  # nosec B101
