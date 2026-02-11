"""Tests for content dedupe persistence safety and compatibility behavior."""

import json
import pickle
from datetime import datetime

import pytest

from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import ContentDeduplicator


def _sample_hash_map():
    return {
        "deadbeef": {
            "url": "https://example.com",
            "title": "Example",
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        }
    }


def test_content_deduplicator_persists_as_json(tmp_path):
    storage_path = tmp_path / "content_hashes.json"
    deduplicator = ContentDeduplicator(storage_path=storage_path)

    deduplicator.add_content("https://example.com/page", "Example Content", "Example Title")
    deduplicator.flush()

    assert storage_path.exists()
    with open(storage_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert len(data) == 1


def test_legacy_pickle_hashes_not_loaded_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("WEBSCRAPER_ALLOW_LEGACY_PICKLE_HASHES", raising=False)
    json_path = tmp_path / "content_hashes.json"
    legacy_pickle_path = tmp_path / "content_hashes.pkl"

    with open(legacy_pickle_path, "wb") as f:
        pickle.dump(_sample_hash_map(), f)

    deduplicator = ContentDeduplicator(storage_path=json_path)
    assert deduplicator._hashes == {}


def test_legacy_pickle_hashes_migrate_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSCRAPER_ALLOW_LEGACY_PICKLE_HASHES", "true")
    json_path = tmp_path / "content_hashes.json"
    legacy_pickle_path = tmp_path / "content_hashes.pkl"
    expected = _sample_hash_map()

    with open(legacy_pickle_path, "wb") as f:
        pickle.dump(expected, f)

    deduplicator = ContentDeduplicator(storage_path=json_path)

    assert deduplicator._hashes == expected
    assert json_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        migrated = json.load(f)
    assert migrated == expected
