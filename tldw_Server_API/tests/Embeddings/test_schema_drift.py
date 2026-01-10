import json
import pathlib

import pytest

from tldw_Server_API.app.core.Embeddings import messages


@pytest.mark.unit
def test_emb_envelope_schema_drift_guard():
    """Guard against drift between code constants and the schema bundle/registry."""
    schema_path = pathlib.Path("Docs/Development/schema/embeddings_v1.schema.json")
    reg_path = pathlib.Path("Docs/Development/schema/embeddings_registry.json")
    assert schema_path.exists(), "Missing embeddings_v1.schema.json"
    assert reg_path.exists(), "Missing embeddings_registry.json"

    schema = json.loads(schema_path.read_text())
    registry = json.loads(reg_path.read_text())

    # CURRENT_SCHEMA should be present in registry and title should include it
    title = (schema.get("title") or "").lower()
    assert messages.CURRENT_SCHEMA in (title.replace(" envelope", ""))

    # Registry entry must match CURRENT_SCHEMA + version
    entries = registry.get("schemas", [])
    names = {e.get("name"): e for e in entries}
    assert messages.CURRENT_SCHEMA in names
    assert int(names[messages.CURRENT_SCHEMA].get("version")) == int(messages.CURRENT_VERSION)
