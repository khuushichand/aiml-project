from pathlib import Path


def test_admin_runs_page_redirects_to_admin_server():
    """
    Smoke-test the Admin Runs page wrapper to ensure it remains a client-only
    redirect to the consolidated /admin/server route.
    """
    p = Path("apps/tldw-frontend/pages/admin/watchlists-runs.tsx")
    assert p.exists(), "watchlists-runs.tsx not found"
    text = p.read_text(encoding="utf-8")
    assert "useRouter" in text
    assert "useEffect" in text
    assert 'router.replace("/admin/server")' in text
    assert "ssr: false" in text
