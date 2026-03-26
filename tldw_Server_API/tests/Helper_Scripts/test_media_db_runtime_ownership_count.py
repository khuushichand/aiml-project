from __future__ import annotations

import importlib
import inspect

from Helper_Scripts.checks import media_db_runtime_ownership_count


def test_media_db_runtime_ownership_count_uses_canonical_dict_based_measurement() -> None:
    media_db_runtime_ownership_count._ensure_minimal_env()

    from tldw_Server_API.app.core.DB_Management.media_db.legacy_identifiers import (
        LEGACY_MEDIA_DB_MODULE,
    )

    media_database = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.media_database"
    )

    expected_names = sorted(
        name
        for name, value in media_database.MediaDatabase.__dict__.items()
        if inspect.isfunction(value)
        and value.__globals__.get("__name__") == LEGACY_MEDIA_DB_MODULE
    )

    assert media_db_runtime_ownership_count.get_legacy_owned_method_names() == expected_names
    assert media_db_runtime_ownership_count.get_legacy_owned_method_count() == len(expected_names)


def test_media_db_runtime_ownership_count_excludes_rebound_template_structure_methods() -> None:
    names = media_db_runtime_ownership_count.get_legacy_owned_method_names()

    assert "list_chunking_templates" not in names
    assert "seed_builtin_templates" not in names
    assert "lookup_section_for_offset" not in names
    assert "lookup_section_by_heading" not in names
