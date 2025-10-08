from tldw_Server_API.app.core.Setup.setup_manager import get_config_snapshot, SENSITIVE_KEY_MARKERS


def test_secret_values_are_masked_in_config_snapshot():
    snapshot = get_config_snapshot()
    sections = snapshot.get("sections", [])

    # Collect any entries that should be treated as secret per server rules
    secret_entries = []
    for section in sections:
        for field in section.get("fields", []):
            key = str(field.get("key", "")).lower()
            if any(marker in key for marker in SENSITIVE_KEY_MARKERS):
                secret_entries.append(field)

    # Sanity: there should be at least one secret-like field in the shipped config
    assert secret_entries, "Expected at least one secret-like field in config snapshot"

    # All secret entries must be masked (empty value) but flagged as secret
    for entry in secret_entries:
        assert entry.get("is_secret") is True
        # The server must not expose the raw value for secrets
        assert entry.get("value") == ""
        # is_set helps clients know if a masked secret exists (optional but desirable)
        assert "is_set" in entry
