from __future__ import annotations

from typing import List

import pytest


def test_refresh_egress_rules_deletes_then_applies(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    # Fake delete that records the label
    def fake_delete(label: str) -> None:
        calls.append(f"del:{label}")

    # Fake apply that records targets and returns a spec list
    def fake_apply(container_ip: str, targets: List[str], label: str):
        calls.append(f"apply:{label}:{container_ip}:{';'.join(sorted(targets))}")
        return ["ok"]

    # Monkeypatch module-level functions
    import tldw_Server_API.app.core.Sandbox.network_policy as np
    monkeypatch.setattr(np, "delete_rules_by_label", fake_delete, raising=True)
    monkeypatch.setattr(np, "apply_egress_rules_atomic", fake_apply, raising=True)

    # Also patch resolver to deterministic mapping
    def res(host: str) -> List[str]:
        return {"example.com": ["1.2.3.4"], "www.example.com": ["1.2.3.5"], "api.example.com": ["1.2.3.6"]}.get(host, [])

    out = np.refresh_egress_rules("172.18.0.2", [".example.com"], label="lbl", resolver=res)
    assert out == ["ok"]
    # First call is delete, then apply
    assert calls and calls[0] == "del:lbl"
    assert any(c.startswith("apply:lbl:172.18.0.2:") for c in calls)
