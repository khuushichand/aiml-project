from __future__ import annotations

from tldw_Server_API.app.core.Sandbox.network_policy import expand_allowlist_to_targets


def _stub_resolver_factory(mapping: dict[str, list[str]]):
    def _res(host: str) -> list[str]:
        return mapping.get(host, [])
    return _res


def test_expand_allowlist_basic_ip_and_cidr():


     raw = ["192.168.1.10", "10.0.0.0/8"]
    out = expand_allowlist_to_targets(raw, resolver=_stub_resolver_factory({}))
    assert "192.168.1.10/32" in out and "10.0.0.0/8" in out


def test_expand_allowlist_hostname_and_wildcard():


     mapping = {
        "example.com": ["93.184.216.34"],
        "www.example.org": ["203.0.113.10"],
        "api.example.org": ["203.0.113.11"],
    }
    res = _stub_resolver_factory(mapping)
    # Hostname resolution
    out1 = expand_allowlist_to_targets(["example.com"], resolver=res)
    assert "93.184.216.34/32" in out1
    # Wildcard resolution samples apex+www+api by default
    out2 = expand_allowlist_to_targets(["*.example.org"], resolver=res)
    assert "203.0.113.10/32" in out2 and "203.0.113.11/32" in out2


def test_expand_allowlist_suffix_and_scheme_handling():


     mapping = {
        "example.net": ["198.51.100.10"],
        "www.example.net": ["198.51.100.11"],
        "api.example.net": ["198.51.100.12"],
    }
    res = _stub_resolver_factory(mapping)
    # Suffix token should behave like wildcard and include apex + common subs
    out = expand_allowlist_to_targets([".example.net"], resolver=res)
    for ip in ("198.51.100.10/32", "198.51.100.11/32", "198.51.100.12/32"):
        assert ip in out
    # Scheme should be stripped
    out2 = expand_allowlist_to_targets(["https://example.net"], resolver=res)
    assert "198.51.100.10/32" in out2
