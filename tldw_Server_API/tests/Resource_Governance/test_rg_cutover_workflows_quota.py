from types import SimpleNamespace

import pytest

from tldw_Server_API.app.api.v1.endpoints import workflows as workflows_ep


class _LoaderWithDailyCap:
    def get_policy(self, _policy_id: str):
        return {workflows_ep.workflows_ledger_category(): {"daily_cap": 1}}


class _LoaderWithoutDailyCap:
    def get_policy(self, _policy_id: str):
        return {}


def _make_request(*, governor, loader=None) -> SimpleNamespace:
    app_state = SimpleNamespace(
        rg_policy_loader=loader or _LoaderWithDailyCap(),
        rg_governor=governor,
    )
    return SimpleNamespace(
        app=SimpleNamespace(state=app_state),
        state=SimpleNamespace(rg_policy_id="workflows.test"),
        url=SimpleNamespace(path="/api/v1/workflows/run"),
    )


@pytest.mark.asyncio
async def test_workflows_daily_cap_rg_unavailable_uses_diagnostics_only_shim(monkeypatch):
    request = _make_request(governor=None)
    current_user = SimpleNamespace(id=123, tenant_id="default")

    reasons: list[str] = []

    def _capture(reason: str, policy_id: str) -> None:
        reasons.append(f"{reason}:{policy_id}")

    async def _no_ledger():
        return None

    monkeypatch.setattr(workflows_ep, "env_flag_enabled", lambda _flag: False)
    monkeypatch.setattr(workflows_ep, "derive_entity_key", lambda _req: "user:123")
    monkeypatch.setattr(workflows_ep, "resolve_user_id_for_request", lambda _u, error_status=500: "123")
    monkeypatch.setattr(workflows_ep, "get_workflows_daily_ledger", _no_ledger)
    monkeypatch.setattr(workflows_ep, "_log_workflows_quota_rg_fallback_once", _capture)

    await workflows_ep._enforce_workflows_daily_cap(
        request=request,
        current_user=current_user,
        db=SimpleNamespace(),
    )

    assert reasons == ["rg_governor_unavailable:workflows.test"]


@pytest.mark.asyncio
async def test_workflows_daily_cap_rg_check_failure_uses_diagnostics_only_shim(monkeypatch):
    class _BrokenGovernor:
        async def check(self, _request):
            raise RuntimeError("boom")

    request = _make_request(governor=_BrokenGovernor())
    current_user = SimpleNamespace(id=123, tenant_id="default")

    reasons: list[str] = []

    def _capture(reason: str, policy_id: str) -> None:
        reasons.append(f"{reason}:{policy_id}")

    async def _no_ledger():
        return None

    monkeypatch.setattr(workflows_ep, "env_flag_enabled", lambda _flag: False)
    monkeypatch.setattr(workflows_ep, "derive_entity_key", lambda _req: "user:123")
    monkeypatch.setattr(workflows_ep, "resolve_user_id_for_request", lambda _u, error_status=500: "123")
    monkeypatch.setattr(workflows_ep, "get_workflows_daily_ledger", _no_ledger)
    monkeypatch.setattr(workflows_ep, "_log_workflows_quota_rg_fallback_once", _capture)

    await workflows_ep._enforce_workflows_daily_cap(
        request=request,
        current_user=current_user,
        db=SimpleNamespace(),
    )

    assert reasons == ["rg_check_failed:RuntimeError:workflows.test"]


@pytest.mark.asyncio
async def test_workflows_daily_cap_without_policy_uses_diagnostics_only_shim(monkeypatch):
    request = _make_request(governor=None, loader=_LoaderWithoutDailyCap())
    current_user = SimpleNamespace(id=123, tenant_id="default")

    reasons: list[str] = []

    def _capture(reason: str, policy_id: str) -> None:
        reasons.append(f"{reason}:{policy_id}")

    monkeypatch.setattr(workflows_ep, "_log_workflows_quota_rg_fallback_once", _capture)

    await workflows_ep._enforce_workflows_daily_cap(
        request=request,
        current_user=current_user,
        db=SimpleNamespace(),
    )

    assert reasons == ["missing_rg_daily_cap_policy:workflows.test"]
