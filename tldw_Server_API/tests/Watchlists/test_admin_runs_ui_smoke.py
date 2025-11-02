from pathlib import Path


def test_admin_runs_ui_includes_include_tallies_param_in_server_csv_links():
    """
    Smoke-test the Admin Runs UI page to ensure the server CSV links
    include the include_tallies query parameter bound to the toggle.

    This is a source inspection test because the frontend does not have
    a configured test runner in this repo. It prevents regressions where
    the toggle is forgotten in the server CSV URLs.
    """
    p = Path("tldw-frontend/pages/admin/watchlists-runs.tsx")
    assert p.exists(), "watchlists-runs.tsx not found"
    text = p.read_text(encoding="utf-8")
    # Expect include_tallies in both global and by-job server CSV link hrefs
    assert "scope=global" in text and "include_tallies=" in text
    assert "scope=job" in text and "include_tallies=" in text
