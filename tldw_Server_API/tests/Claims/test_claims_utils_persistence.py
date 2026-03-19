from __future__ import annotations

import contextlib

import pytest

from tldw_Server_API.app.core.Claims_Extraction import claims_utils


pytestmark = pytest.mark.unit


class _InlineLoop:
    async def run_in_executor(self, _executor, func):
        return func()


@pytest.mark.asyncio
async def test_persist_claims_if_applicable_uses_managed_media_database(monkeypatch):
    events = []

    class _FakeDb:
        def soft_delete_claims_for_media(self, media_id: int) -> None:
            events.append(("soft_delete", media_id))

    @contextlib.contextmanager
    def _fake_managed_media_database(client_id, **kwargs):
        events.append(("open", client_id, kwargs))
        yield _FakeDb()

    def _fake_store_claims(
        db,
        *,
        media_id,
        chunk_texts_by_index,
        claims,
        extractor,
        extractor_version,
    ):
        events.append(
            (
                "store_claims",
                db.__class__.__name__,
                media_id,
                chunk_texts_by_index,
                claims,
                extractor,
                extractor_version,
            )
        )
        return 2

    monkeypatch.setattr(
        claims_utils,
        "MediaDatabase",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("claims_utils should not construct MediaDatabase directly")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        claims_utils,
        "managed_media_database",
        _fake_managed_media_database,
        raising=False,
    )
    monkeypatch.setattr(claims_utils, "store_claims", _fake_store_claims)

    process_result = {"claims_details": {"enabled": True}}
    claims_context = {
        "claims": [{"claim_text": "Example claim"}],
        "chunk_text_map": {0: "Example source text"},
        "extractor": "heuristic",
    }

    await claims_utils.persist_claims_if_applicable(
        claims_context=claims_context,
        media_id=42,
        db_path="/tmp/claims-utils.db",
        client_id="claims-worker",
        loop=_InlineLoop(),
        process_result=process_result,
    )

    assert process_result["claims_details"]["stored_in_db"] == 2
    assert events == [
        (
            "open",
            "claims-worker",
            {
                "db_path": "/tmp/claims-utils.db",
                "initialize": False,
                "suppress_close_exceptions": claims_utils._CLAIMS_DB_EXCEPTIONS,
            },
        ),
        ("soft_delete", 42),
        (
            "store_claims",
            "_FakeDb",
            42,
            {0: "Example source text"},
            [{"claim_text": "Example claim"}],
            "heuristic",
            "v1",
        ),
    ]
