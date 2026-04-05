from __future__ import annotations

import pytest

from tldw_Server_API.app.core.External_Sources.reference_manager_dedupe import (
    build_metadata_fingerprint,
    rank_reference_item_match,
)
from tldw_Server_API.app.core.External_Sources.reference_manager_types import NormalizedReferenceItem


def _build_item(*, doi: str | None = "10.1000/example", title: str = "Attention Is All You Need") -> NormalizedReferenceItem:
    return NormalizedReferenceItem(
        provider="zotero",
        provider_item_key="ITEM1234",
        provider_library_id="123456",
        collection_key="COLL1234",
        collection_name="Language Models",
        doi=doi,
        title=title,
        authors="Ashish Vaswani, Noam Shazeer",
        publication_date="2017-06-12",
        year="2017",
        journal="NeurIPS",
        abstract="Transformers.",
        source_url="https://www.zotero.org/users/123456/items/ITEM1234",
        attachments=[],
    )


@pytest.mark.unit
def test_rank_reference_item_match_prefers_same_provider_then_doi_then_file_hash_then_metadata() -> None:
    item = _build_item()

    same_provider = rank_reference_item_match(
        item,
        same_provider_item={"media_id": 5},
        doi_match={"media_id": 77},
        hash_match={"media_id": 88},
        metadata_match={"media_id": 99},
    )
    doi_only = rank_reference_item_match(
        item,
        same_provider_item=None,
        doi_match={"media_id": 77},
        hash_match={"media_id": 88},
        metadata_match={"media_id": 99},
    )
    hash_only = rank_reference_item_match(
        item,
        same_provider_item=None,
        doi_match=None,
        hash_match={"media_id": 88},
        metadata_match={"media_id": 99},
    )
    metadata_only = rank_reference_item_match(
        item,
        same_provider_item=None,
        doi_match=None,
        hash_match=None,
        metadata_match={"media_id": 99},
    )

    assert same_provider.reason == "same_provider_item"
    assert same_provider.media_id == 5
    assert doi_only.reason == "doi"
    assert doi_only.media_id == 77
    assert hash_only.reason == "file_hash"
    assert hash_only.media_id == 88
    assert metadata_only.reason == "metadata_fingerprint"
    assert metadata_only.media_id == 99


@pytest.mark.unit
def test_metadata_fingerprint_matching_is_conservative_for_similar_but_distinct_titles() -> None:
    first = build_metadata_fingerprint(
        title="Attention Is All You Need",
        authors="Ashish Vaswani, Noam Shazeer",
        year="2017",
    )
    second = build_metadata_fingerprint(
        title="Attention Is All You Need for Speech",
        authors="Ashish Vaswani, Noam Shazeer",
        year="2017",
    )

    assert first is not None
    assert second is not None
    assert first != second


@pytest.mark.unit
def test_metadata_fingerprint_normalizes_common_author_separators() -> None:
    comma_delimited = build_metadata_fingerprint(
        title="Attention Is All You Need",
        authors="Ashish Vaswani, Noam Shazeer",
        year="2017",
    )
    summary_delimited = build_metadata_fingerprint(
        title="Attention Is All You Need",
        authors="Ashish Vaswani and Noam Shazeer",
        year="2017",
    )

    assert comma_delimited is not None
    assert summary_delimited is not None
    assert comma_delimited == summary_delimited
