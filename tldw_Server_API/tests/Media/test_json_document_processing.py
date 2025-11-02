import io
import json

import pytest


pytestmark = pytest.mark.unit


def test_process_documents_accepts_json(client_with_single_user):
    client, _ = client_with_single_user

    payload = {"a": 1, "b": {"c": 2}}
    data = json.dumps(payload).encode("utf-8")
    files = [("files", ("example.json", data, "application/json"))]

    resp = client.post(
        "/api/v1/media/process-documents",
        files=files,
        data={"perform_chunking": "false"},
    )

    assert resp.status_code in (200, 207), resp.text
    out = resp.json()
    assert isinstance(out.get("results"), list) and out["results"], out
    item = out["results"][0]
    assert item.get("status") in ("Success", "Warning"), item
    assert item.get("media_type") == "document", item
    # Ensure content is pretty-printed JSON or at least non-empty
    content = item.get("content")
    assert isinstance(content, str) and content.strip().startswith("{")
    # Ensure metadata carries JSON summary when available
    meta = item.get("metadata") or {}
    raw = (meta.get("raw") or {}) if isinstance(meta, dict) else {}
    # json_top_type may be present when JSON parsed successfully
    if isinstance(raw, dict):
        assert raw.get("json_top_type") in (None, "object", "array")
