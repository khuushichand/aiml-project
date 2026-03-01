from tldw_Server_API.app.core.AuthNZ import auth_principal_resolver as resolver


def test_auth_principal_resolver_mode_shim_removed() -> None:
    assert not hasattr(resolver, "is_single_user_mode")  # nosec B101
