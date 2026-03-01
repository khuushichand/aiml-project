from tldw_Server_API.app.api.v1.API_Deps import v1_endpoint_deps


def test_v1_endpoint_deps_verify_token_shim_removed() -> None:
    assert not hasattr(v1_endpoint_deps, "verify_token")  # nosec B101
