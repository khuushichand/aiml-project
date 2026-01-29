from pathlib import Path


def test_admin_runs_roles_normalized_to_array_and_lowercased():
    """
    Source-inspection test: ensure role normalization and admin checks are
    centralized in the WebUI authz helpers (used by admin pages and headers).
    """
    p = Path("apps/tldw-frontend/lib/authz.ts")
    assert p.exists(), "authz.ts not found"
    text = p.read_text(encoding="utf-8")

    # Normalization should wrap scalars into arrays and lowercase values.
    assert "normalizeStringArray" in text
    assert "Array.isArray(input)" in text
    assert "[input]" in text, "Expected scalar roles to be wrapped into an array"
    assert "toLowerCase" in text


def test_admin_runs_user_is_admin_uses_normalized_roles_array():
    """
    Ensure the admin decision uses normalized roles (no direct includes on
    possibly-scalar payloads).
    """
    p = Path("apps/tldw-frontend/lib/authz.ts")
    assert p.exists(), "authz.ts not found"
    text = p.read_text(encoding="utf-8")

    assert "isAdmin" in text
    assert "normalizeStringArray(user.roles)" in text
    assert "rolesArr.includes('admin')" in text
