import pytest

from tldw_Server_API.app.core.AuthNZ.byok_helpers import validate_base_url_override
from tldw_Server_API.app.core.Security import egress


def _clear_egress_env(monkeypatch) -> None:


     monkeypatch.setenv("WORKFLOWS_EGRESS_PROFILE", "permissive")
    monkeypatch.setenv("WORKFLOWS_EGRESS_BLOCK_PRIVATE", "true")
    monkeypatch.delenv("WORKFLOWS_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.delenv("WORKFLOWS_EGRESS_DENYLIST", raising=False)
    monkeypatch.delenv("EGRESS_ALLOWLIST", raising=False)
    monkeypatch.delenv("EGRESS_DENYLIST", raising=False)


def test_validate_base_url_override_rejects_invalid_scheme(monkeypatch):


     _clear_egress_env(monkeypatch)
    with pytest.raises(ValueError) as exc:
        validate_base_url_override("ftp://example.com/resource")
    assert "scheme" in str(exc.value).lower()


def test_validate_base_url_override_blocks_private_ip(monkeypatch):


     _clear_egress_env(monkeypatch)
    with pytest.raises(ValueError) as exc:
        validate_base_url_override("http://127.0.0.1")
    assert "private" in str(exc.value).lower()


def test_validate_base_url_override_blocks_metadata_ip(monkeypatch):


     _clear_egress_env(monkeypatch)
    with pytest.raises(ValueError) as exc:
        validate_base_url_override("http://169.254.169.254/latest/meta-data")
    assert "private" in str(exc.value).lower()


def test_validate_base_url_override_blocks_dns_rebind(monkeypatch):


     _clear_egress_env(monkeypatch)

    def _fake_resolve(host: str):
        if host == "rebind.test":
            return False, ["127.0.0.1"]
        return True, ["203.0.113.10"]

    monkeypatch.setattr(egress, "_resolve_and_check_private", _fake_resolve)

    with pytest.raises(ValueError) as exc:
        validate_base_url_override("https://rebind.test")
    assert "private" in str(exc.value).lower()


def test_validate_base_url_override_allows_public_host(monkeypatch):


     _clear_egress_env(monkeypatch)

    def _always_public(host: str):
        return True, ["203.0.113.10"]

    monkeypatch.setattr(egress, "_resolve_and_check_private", _always_public)

    assert (
        validate_base_url_override("https://public.example.com/api") == "https://public.example.com/api"
    )
