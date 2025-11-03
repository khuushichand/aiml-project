from __future__ import annotations

from typing import List

import pytest

from tldw_Server_API.app.core.Sandbox.network_policy import expand_allowlist_to_targets, _build_restore_blob


def test_expand_allowlist_hostname_and_wildcard_with_fake_resolver():
    def fake_resolver(host: str) -> List[str]:
        mapping = {
            "example.com": ["1.1.1.1", "1.1.1.2"],
            "www.example.com": ["1.1.1.3"],
            "api.example.com": ["1.1.1.4"],
            "other.com": ["2.2.2.2"],
        }
        return mapping.get(host, [])

    # Mix CIDR, IP, hostname, and wildcard
    raw = ["10.0.0.0/8", "8.8.8.8", "example.com", "*.example.com", "other.com"]
    out = expand_allowlist_to_targets(raw, resolver=fake_resolver)
    # Expect CIDR preserved, IP promoted to /32, hostnames expanded to /32s
    assert "10.0.0.0/8" in out
    assert "8.8.8.8/32" in out
    # Deduplication and sorting are implementation details; assert required expansions present
    for ip in ("1.1.1.1/32", "1.1.1.2/32", "1.1.1.3/32", "1.1.1.4/32", "2.2.2.2/32"):
        assert ip in out


def test_build_restore_blob_shapes_rules_with_label():
    blob = _build_restore_blob("172.18.0.2", ["1.2.3.0/24", "9.9.9.9/32"], label="tldw-run-abc")
    # Contains DOCKER-USER chain modifications and a final COMMIT
    assert "*filter" in blob and "COMMIT" in blob
    # Contains ACCEPT rules for targets and a final DROP for container IP
    assert "-A DOCKER-USER -s 172.18.0.2 -d 1.2.3.0/24 -j ACCEPT" in blob
    assert "-A DOCKER-USER -s 172.18.0.2 -d 9.9.9.9/32 -j ACCEPT" in blob
    assert "-A DOCKER-USER -s 172.18.0.2 -j DROP" in blob

