import pytest

from tldw_Server_API.app.core.Resource_Governance import MemoryResourceGovernor, RGRequest


pytestmark = pytest.mark.rate_limit


class FakeTime:
    def __init__(self, t0: float = 0.0):
        self.t = t0

    def __call__(self) -> float:

        return self.t

    def advance(self, s: float) -> None:
        self.t += s


@pytest.mark.asyncio
async def test_combined_requests_tokens_retry_after_aggregation():
    """
    Property-like check: when both requests and tokens are enforced, overall retry_after equals the
    max of per-category retry_after values.
    """
    params = [
        (2, 2),
        (2, 5),
        (5, 2),
        (3, 4),
    ]
    for rpm, per_min in params:
        ft = FakeTime(0.0)
        pols = {"p": {"requests": {"rpm": rpm}, "tokens": {"per_min": per_min}, "scopes": ["global", "user"]}}
        rg = MemoryResourceGovernor(policies=pols, time_source=ft)
        e = "user:combo"
        # Allow up to min(rpm, per_min) combined reservations
        allowed_count = 0
        for i in range(max(rpm, per_min)):
            d, h = await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 1}, "tokens": {"units": 1}}, tags={"policy_id": "p"}), op_id=f"op{i}")
            if d.allowed:
                allowed_count += 1
            else:
                break
        assert allowed_count == min(rpm, per_min)

        # Next attempt should deny; verify overall retry_after aggregation is max across categories
        d2, _ = await rg.reserve(RGRequest(entity=e, categories={"requests": {"units": 1}, "tokens": {"units": 1}}, tags={"policy_id": "p"}))
        assert not d2.allowed
        cats = d2.details.get("categories", {})
        ra_req = int((cats.get("requests") or {}).get("retry_after") or 0)
        ra_tok = int((cats.get("tokens") or {}).get("retry_after") or 0)
        assert int(d2.retry_after or 0) == max(ra_req, ra_tok)
