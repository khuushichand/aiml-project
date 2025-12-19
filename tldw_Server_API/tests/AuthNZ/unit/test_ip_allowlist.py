from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.AuthNZ.ip_allowlist import is_single_user_ip_allowed


def _settings(allowed):
    return SimpleNamespace(SINGLE_USER_ALLOWED_IPS=allowed)


def test_allowlist_empty_allows_any_ip():
    settings = _settings([])
    assert is_single_user_ip_allowed("198.51.100.5", settings) is True
    assert is_single_user_ip_allowed(None, settings) is True


def test_allowlist_denies_missing_client_ip():
    settings = _settings(["203.0.113.10"])
    assert is_single_user_ip_allowed(None, settings) is False


@pytest.mark.parametrize(
    ("allowed", "ip", "expected"),
    [
        (["10.0.0.0/8"], "10.1.2.3", True),
        (["10.0.0.0/8"], "192.168.1.1", False),
        (["192.168.1.5"], "192.168.1.5", True),
        (["192.168.1.5"], "192.168.1.6", False),
        (["2001:db8::/32"], "2001:db8::1", True),
        (["2001:db8::/32"], "2001:db9::1", False),
    ],
)
def test_allowlist_ip_and_cidr_matching(allowed, ip, expected):
    settings = _settings(allowed)
    assert is_single_user_ip_allowed(ip, settings) is expected


def test_allowlist_invalid_entry_is_ignored():
    settings = _settings(["not-an-ip"])
    assert is_single_user_ip_allowed("192.0.2.1", settings) is False


def test_allowlist_invalid_client_ip_rejected():
    settings = _settings(["203.0.113.10"])
    assert is_single_user_ip_allowed("999.999.999.999", settings) is False
