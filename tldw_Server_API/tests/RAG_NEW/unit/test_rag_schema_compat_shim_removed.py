from pathlib import Path


def test_rag_schema_compat_shim_removed() -> None:
    compat_schema = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "api"
        / "v1"
        / "schemas"
        / "rag_schemas_simple_compat.py"
    )
    assert not compat_schema.exists()  # nosec B101
