import pytest

from tldw_Server_API.app.core.AuthNZ.username_utils import (
    InvalidUsernameError,
    _RESERVED_USERNAMES,
    normalize_admin_username,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AdminUser", "adminuser"),
        ("MiXeD_Name-123", "mixed_name-123"),
        ("User_Name", "user_name"),
        ("user-name", "user-name"),
    ],
)
def test_normalize_admin_username_valid(raw: str, expected: str) -> None:
    assert normalize_admin_username(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_normalize_admin_username_required(raw: str) -> None:
    with pytest.raises(InvalidUsernameError) as excinfo:
        normalize_admin_username(raw)
    assert str(excinfo.value) == "Username is required"


@pytest.mark.parametrize(
    ("raw", "expected_message"),
    [
        ("ab", "Username must be at least 3 characters"),
        ("a" * 51, "Username must not exceed 50 characters"),
    ],
)
def test_normalize_admin_username_length_errors(raw: str, expected_message: str) -> None:
    with pytest.raises(InvalidUsernameError) as excinfo:
        normalize_admin_username(raw)
    assert str(excinfo.value) == expected_message


def test_normalize_admin_username_length_boundaries() -> None:


     assert normalize_admin_username("abc") == "abc"
    assert normalize_admin_username("a" * 50) == "a" * 50


@pytest.mark.parametrize("raw", ["bad space", "bad$", "bad.name!", "bad/slash"])
def test_normalize_admin_username_invalid_chars(raw: str) -> None:
    with pytest.raises(InvalidUsernameError) as excinfo:
        normalize_admin_username(raw)
    assert str(excinfo.value) == "Username can only contain letters, numbers, underscores, and hyphens"


@pytest.mark.parametrize(
    "raw",
    sorted({variant for name in _RESERVED_USERNAMES for variant in (name, name.upper(), name.capitalize())}),
)
def test_normalize_admin_username_reserved(raw: str) -> None:
    with pytest.raises(InvalidUsernameError) as excinfo:
        normalize_admin_username(raw)
    assert str(excinfo.value) == "This username is reserved and cannot be used"
