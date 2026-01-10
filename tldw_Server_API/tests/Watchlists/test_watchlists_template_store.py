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
