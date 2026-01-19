import re

import pytest


@pytest.mark.e2e
def test_health_diagnostics_recheck_all(configured_page):
    page = configured_page
    page.goto("/settings/health")

    page.get_by_role("heading", name="Health & diagnostics").wait_for()
    page.get_by_role("button", name="Recheck All").click()

    core_card = page.get_by_role(
        "group", name=re.compile(r"Core API: (Healthy|Unhealthy)")
    )
    core_card.wait_for(timeout=120_000)

    core_card.get_by_role("link", name="Recheck").click()
    core_card.get_by_text("Checking").wait_for()
    core_card.get_by_role("link", name="Recheck").wait_for()
