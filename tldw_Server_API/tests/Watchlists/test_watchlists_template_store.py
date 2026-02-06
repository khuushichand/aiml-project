import pytest

from tldw_Server_API.app.core.Watchlists import template_store
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


def test_assert_within_base_rejects_escape(tmp_path):
    base = tmp_path / "templates"
    escape = base / ".." / "escape.md"
    with pytest.raises(ValueError):
        template_store._assert_within_base(escape, base)


def test_assert_within_base_allows_child_path(tmp_path):
    base = tmp_path / "templates"
    path = base / "safe.md"
    template_store._assert_within_base(path, base)


def test_template_path_rejects_unsanitized_name(tmp_path, monkeypatch):
    monkeypatch.setitem(settings, "WATCHLIST_TEMPLATE_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        template_store._template_path("bad/name", "md")


def test_template_store_version_history_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setitem(settings, "WATCHLIST_TEMPLATE_DIR", str(tmp_path))

    first = template_store.save_template(
        name="daily_md",
        fmt="md",
        content="v1 content",
        description="First version",
        overwrite=False,
    )
    assert first.version == 1
    assert first.history_count == 0
    assert first.available_versions == [1]

    second = template_store.save_template(
        name="daily_md",
        fmt="md",
        content="v2 content",
        description="Second version",
        overwrite=True,
    )
    assert second.version == 2
    assert second.history_count == 1
    assert second.available_versions == [1, 2]

    older = template_store.load_template("daily_md", version=1)
    assert older.version == 1
    assert older.content == "v1 content"
    assert older.description == "First version"

    versions = template_store.list_template_versions("daily_md")
    assert [entry.version for entry in versions] == [1, 2]
    assert versions[-1].is_current is True


def test_template_store_missing_version_raises(tmp_path, monkeypatch):
    monkeypatch.setitem(settings, "WATCHLIST_TEMPLATE_DIR", str(tmp_path))
    template_store.save_template(
        name="snapshot",
        fmt="md",
        content="only version",
        overwrite=False,
    )

    with pytest.raises(template_store.TemplateVersionNotFoundError):
        template_store.load_template("snapshot", version=3)

