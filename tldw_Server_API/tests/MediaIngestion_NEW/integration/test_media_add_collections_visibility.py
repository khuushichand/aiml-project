from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import status


@pytest.mark.integration
def test_media_add_document_is_visible_in_items_origin_feed(
    test_client,
    auth_headers,
    test_media_dir: Path,
):
    title = f"Media Add Collections {uuid4().hex}"
    source_path = test_media_dir / "collections_dual_write.txt"
    source_path.write_text(
        "Collections dual-write integration test content.",
        encoding="utf-8",
    )

    with source_path.open("rb") as handle:
        response = test_client.post(
            "/api/v1/media/add",
            data={
                "media_type": "document",
                "title": title,
                "chunk_method": "words",
                "chunk_size": "100",
                "chunk_overlap": "10",
            },
            files=[("files", (source_path.name, handle, "text/plain"))],
            headers=auth_headers,
        )

    assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS), response.text
    payload = response.json()
    results = payload.get("results") or []
    success_row = next(
        (
            row
            for row in results
            if row.get("status") in {"Success", "Warning"} and row.get("db_id") is not None
        ),
        None,
    )
    assert success_row is not None, payload
    assert success_row.get("collections_item_id") is not None
    assert success_row.get("collections_origin") == "media_add"

    items_response = test_client.get(
        "/api/v1/items",
        params={
            "origin": "media_add",
            "page": 1,
            "size": 200,
        },
        headers=auth_headers,
    )
    assert items_response.status_code == status.HTTP_200_OK, items_response.text
    items_payload = items_response.json()
    assert items_payload["total"] >= 1

    media_id = int(success_row["db_id"])
    matching_item = next(
        (
            item
            for item in items_payload.get("items", [])
            if item.get("media_id") == media_id and item.get("type") == "media_add"
        ),
        None,
    )
    assert matching_item is not None, items_payload
