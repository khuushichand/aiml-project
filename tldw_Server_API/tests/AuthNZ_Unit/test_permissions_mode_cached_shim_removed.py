from tldw_Server_API.app.core.AuthNZ import permissions


def test_permissions_mode_cached_shim_removed() -> None:
    assert not hasattr(permissions, "is_single_user_mode_cached")  # nosec B101
