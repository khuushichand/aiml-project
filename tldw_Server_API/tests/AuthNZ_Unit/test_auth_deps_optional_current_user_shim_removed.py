from tldw_Server_API.app.api.v1.API_Deps import auth_deps


def test_auth_deps_optional_current_user_shim_removed() -> None:
    assert not hasattr(auth_deps, "get_optional_current_user")  # nosec B101
