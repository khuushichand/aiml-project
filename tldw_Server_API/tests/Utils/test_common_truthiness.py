import pytest

from tldw_Server_API.app.core.Utils.common import parse_boolean


@pytest.mark.unit
@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "y", "Y", "  y  "])
def test_parse_boolean_accepts_extended_truthy_values(value):
    assert parse_boolean(value) is True


@pytest.mark.unit
def test_parse_boolean_preserves_default_when_none():
    assert parse_boolean(None, default=True) is True
    assert parse_boolean(None, default=False) is False
