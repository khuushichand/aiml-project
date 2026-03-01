from pathlib import Path


def test_ingestion_claims_compat_shims_removed() -> None:
    claims_dir = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "core"
        / "Ingestion_Media_Processing"
        / "Claims"
    )
    assert not (claims_dir / "ingestion_claims.py").exists()  # nosec B101
    assert not (claims_dir / "claims_engine.py").exists()  # nosec B101
