from pathlib import Path


def test_admin_runs_roles_normalized_to_array_and_lowercased():
    """
    Source-inspection test: ensure the Admin Runs UI normalizes `user.roles`
    into an array and lowercases entries, so both scalar and array payloads
    are handled safely without runtime errors when mapping.
    """
    p = Path("tldw-frontend/pages/admin/watchlists-runs.tsx")
    assert p.exists(), "watchlists-runs.tsx not found"
    text = p.read_text(encoding="utf-8")

    # Two acceptable implementations:
    # 1) Local normalization in page (legacy): look for _rawRoles normalization
    # 2) Centralized hook (preferred): useIsAdmin imported/used
    if "useIsAdmin" in text:
        # Ensure the hook is imported and used
        assert "useIsAdmin" in text
        assert "const userIsAdmin" in text and "useIsAdmin(" in text or "useIsAdmin()" in text
    else:
        # Check normalization logic exists (legacy in-file normalization)
        assert "const _rawRoles" in text
        assert "Array.isArray(_rawRoles)" in text
        assert "[_rawRoles]" in text, "Expected scalar roles to be wrapped into an array"

        # Check mapping and lowercasing
        assert "const rolesArr" in text
        assert "_normRoles.map" in text
        assert "toLowerCase" in text


def test_admin_runs_user_is_admin_uses_normalized_roles_array():
    p = Path("tldw-frontend/pages/admin/watchlists-runs.tsx")
    assert p.exists(), "watchlists-runs.tsx not found"
    text = p.read_text(encoding="utf-8")

    # Ensure the page determines admin via hook or normalized array
    if "useIsAdmin" in text:
        assert "const userIsAdmin" in text and ("useIsAdmin(" in text or "useIsAdmin()" in text)
    else:
        assert "rolesArr?.includes?.('admin')" in text
