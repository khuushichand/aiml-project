from pathlib import Path


def test_migration_inventory_records_disposition() -> None:
    text = Path("Docs/Getting_Started/README.md").read_text()
    assert "| Path | Action | Replacement |" in text
    assert "migrated" in text
