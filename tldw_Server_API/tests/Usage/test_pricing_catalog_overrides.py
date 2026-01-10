from __future__ import annotations

import os
import pytest


def test_pricing_overrides_env(monkeypatch):
    """Environment PRICING_OVERRIDES should override default rates and support partial matches.

    Verifies that an override for a provider/model is picked up and that
    requesting a model name with the override as a substring returns the
    same rates but marked as estimated.
    """
    monkeypatch.setenv(
        "PRICING_OVERRIDES",
        '{"OpenAI": {"gpt-xyz-test": {"prompt": 0.123, "completion": 0.456}}}',
    )

    # Import inside test so env is set before class is constructed
    from tldw_Server_API.app.core.Usage.pricing_catalog import PricingCatalog

    catalog = PricingCatalog()

    # Exact match should not be estimated
    p_in, p_out, est = catalog.get_rates("openai", "gpt-xyz-test")
    assert pytest.approx(p_in, rel=1e-6) == 0.123
    assert pytest.approx(p_out, rel=1e-6) == 0.456
    assert est is False

    # Partial model match should be estimated=True but same rates
    p_in2, p_out2, est2 = catalog.get_rates("openai", "gpt-xyz-test-v2")
    assert pytest.approx(p_in2, rel=1e-6) == 0.123
    assert pytest.approx(p_out2, rel=1e-6) == 0.456
    assert est2 is True
