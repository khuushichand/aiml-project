import json
from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.Flashcards.apkg_exporter import export_apkg_from_rows
from tldw_Server_API.app.core.Flashcards.apkg_importer import (
    APKGImportError,
    import_rows_from_apkg_bytes,
)


def test_import_rows_from_apkg_bytes_round_trip_models_and_scheduling():
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = [
        {
            "deck_name": "RoundTripDeck",
            "model_type": "basic",
            "front": "Q1",
            "back": "A1",
            "extra": "E1",
            "ef": 2.5,
            "interval_days": 0,
            "repetitions": 0,
            "lapses": 0,
            "due_at": None,
            "tags_json": json.dumps(["tag-basic"]),
        },
        {
            "deck_name": "RoundTripDeck",
            "model_type": "basic_reverse",
            "front": "Q2",
            "back": "A2",
            "extra": "E2",
            "ef": 2.2,
            "interval_days": 12,
            "repetitions": 4,
            "lapses": 1,
            "due_at": None,
            "tags_json": json.dumps(["tag-reverse"]),
            "reverse": True,
        },
        {
            "deck_name": "RoundTripDeck",
            "model_type": "cloze",
            "front": "Cloze {{c1::test}} prompt",
            "back": "",
            "extra": "cloze extra",
            "ef": 2.4,
            "interval_days": 0,
            "repetitions": 1,
            "lapses": 0,
            "due_at": now_iso,
            "tags_json": json.dumps(["tag-cloze"]),
        },
    ]
    apkg = export_apkg_from_rows(rows, include_reverse=False)
    parsed, errors = import_rows_from_apkg_bytes(
        apkg,
        max_notes=100,
        max_field_length=8192,
    )

    assert errors == []
    assert len(parsed) == 3

    by_front = {row["front"]: row for row in parsed}
    basic = by_front["Q1"]
    assert basic["model_type"] == "basic"
    assert basic["tags"] == ["tag-basic"]
    assert basic["repetitions"] == 0
    assert basic["due_at"] is None

    reverse = by_front["Q2"]
    assert reverse["model_type"] == "basic_reverse"
    assert reverse["reverse"] is True
    assert reverse["interval_days"] == 12
    assert reverse["repetitions"] == 4
    assert pytest.approx(reverse["ef"], rel=1e-3) == 2.2
    assert reverse["tags"] == ["tag-reverse"]
    assert reverse["due_at"] is not None

    cloze = by_front["Cloze {{c1::test}} prompt"]
    assert cloze["model_type"] == "cloze"
    assert cloze["is_cloze"] is True
    assert cloze["extra"] == "cloze extra"
    assert cloze["repetitions"] == 1
    assert cloze["tags"] == ["tag-cloze"]
    assert cloze["due_at"] is not None


def test_import_rows_from_apkg_bytes_invalid_archive_raises():
    with pytest.raises(APKGImportError, match="Invalid APKG archive"):
        import_rows_from_apkg_bytes(
            b"not-a-zip",
            max_notes=10,
            max_field_length=8192,
        )


def test_import_rows_from_apkg_bytes_respects_max_notes_limit():
    rows = [
        {"deck_name": "L", "model_type": "basic", "front": "F1", "back": "B1"},
        {"deck_name": "L", "model_type": "basic", "front": "F2", "back": "B2"},
        {"deck_name": "L", "model_type": "basic", "front": "F3", "back": "B3"},
    ]
    apkg = export_apkg_from_rows(rows)
    parsed, errors = import_rows_from_apkg_bytes(
        apkg,
        max_notes=2,
        max_field_length=8192,
    )
    assert len(parsed) == 2
    assert any("Maximum import item limit reached (2)" in err.get("error", "") for err in errors)
