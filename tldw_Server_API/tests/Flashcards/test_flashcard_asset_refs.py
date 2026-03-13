import pytest

from tldw_Server_API.app.core.Flashcards.asset_refs import (
    FLASHCARD_ASSET_SCHEME,
    build_flashcard_asset_markdown,
    build_flashcard_asset_reference,
    extract_flashcard_asset_uuids,
    replace_markdown_asset_refs_for_export,
    sanitize_flashcard_text_for_search,
)


ASSET_UUID = "123e4567-e89b-12d3-a456-426614174000"
SECOND_ASSET_UUID = "123e4567-e89b-12d3-a456-426614174001"


def test_build_flashcard_asset_reference_returns_canonical_scheme():
    assert build_flashcard_asset_reference(ASSET_UUID) == f"{FLASHCARD_ASSET_SCHEME}{ASSET_UUID}"


def test_build_flashcard_asset_markdown_builds_inline_image_snippet():
    assert (
        build_flashcard_asset_markdown(ASSET_UUID, alt_text="Histology slide")
        == f"![Histology slide]({FLASHCARD_ASSET_SCHEME}{ASSET_UUID})"
    )


def test_extract_flashcard_asset_uuids_returns_unique_encounter_order():
    text = (
        f"Start ![one]({FLASHCARD_ASSET_SCHEME}{ASSET_UUID}) "
        f"middle ![two]({FLASHCARD_ASSET_SCHEME}{SECOND_ASSET_UUID}) "
        f"again ![dup]({FLASHCARD_ASSET_SCHEME}{ASSET_UUID}) end"
    )

    assert extract_flashcard_asset_uuids(text) == [ASSET_UUID, SECOND_ASSET_UUID]


def test_sanitize_flashcard_text_for_search_preserves_alt_text_and_strips_refs():
    text = (
        "Intro "
        f"![Histology slide]({FLASHCARD_ASSET_SCHEME}{ASSET_UUID}) "
        "summary "
        f"![Diagram]({FLASHCARD_ASSET_SCHEME}{SECOND_ASSET_UUID})"
    )

    assert sanitize_flashcard_text_for_search(text) == "Intro Histology slide summary Diagram"


def test_replace_markdown_asset_refs_for_export_uses_resolver_for_each_ref():
    text = (
        f'Before ![Slide A]({FLASHCARD_ASSET_SCHEME}{ASSET_UUID}) '
        f'and ![Slide B]({FLASHCARD_ASSET_SCHEME}{SECOND_ASSET_UUID}) after'
    )

    exported = replace_markdown_asset_refs_for_export(
        text,
        resolver=lambda asset_uuid: {
            ASSET_UUID: ("data:image/png;base64,AAAA", "image/png"),
            SECOND_ASSET_UUID: ("data:image/webp;base64,BBBB", "image/webp"),
        }[asset_uuid],
    )

    assert "Before " in exported
    assert '<img src="data:image/png;base64,AAAA" alt="Slide A"' in exported
    assert '<img src="data:image/webp;base64,BBBB" alt="Slide B"' in exported
    assert exported.endswith(" after")


def test_replace_markdown_asset_refs_for_export_raises_for_missing_asset():
    text = f"![Missing]({FLASHCARD_ASSET_SCHEME}{ASSET_UUID})"

    with pytest.raises(KeyError):
        replace_markdown_asset_refs_for_export(
            text,
            resolver=lambda _asset_uuid: (_ for _ in ()).throw(KeyError("missing asset")),
        )
