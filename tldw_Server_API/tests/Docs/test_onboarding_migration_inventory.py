from pathlib import Path


def test_migration_inventory_records_disposition() -> None:
    text = Path("Docs/Plans/2026-02-28-onboarding-migration-inventory.md").read_text()
    assert "| Path | Action | Replacement |" in text
    assert "migrated" in text
