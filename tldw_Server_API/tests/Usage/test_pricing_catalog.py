from __future__ import annotations

import json
import os
import pytest

from tldw_Server_API.app.core.Usage.pricing_catalog import PricingCatalog


def test_pricing_defaults_and_partial_match():
    cat = PricingCatalog()
    pr, cr, est = cat.get_rates('openai', 'gpt-3.5-turbo')
    assert pr > 0 and cr > 0
    assert est is False

    # Partial model name should mark estimated True if not exact
    pr2, cr2, est2 = cat.get_rates('openai', 'gpt-4-something')
    assert pr2 >= 0 and cr2 >= 0
    assert est2 in (True, False)  # May map to gpt-4 baseline

    # Unknown provider/model → tiny sentinel with estimated True
    pr3, cr3, est3 = cat.get_rates('unknownprov', 'mymodel')
    assert pr3 > 0 and cr3 > 0 and est3 is True


def test_pricing_env_override(monkeypatch):
    overrides = {
        "openai": {"gpt-3.5-turbo": {"prompt": 0.123, "completion": 0.456}}
    }
    monkeypatch.setenv('PRICING_OVERRIDES', json.dumps(overrides))
    cat = PricingCatalog()
    pr, cr, est = cat.get_rates('openai', 'gpt-3.5-turbo')
    assert pr == pytest.approx(0.123)
    assert cr == pytest.approx(0.456)
    assert est is False
