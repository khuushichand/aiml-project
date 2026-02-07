from tldw_Server_API.app.api.v1.schemas.privileges import PrivilegeSnapshotCreateRequest


def test_snapshot_create_request_accepts_async_alias() -> None:
    req = PrivilegeSnapshotCreateRequest(
        target_scope="org",
        **{"async": True},
    )
    assert req.async_job is True


def test_snapshot_create_request_accepts_field_name() -> None:
    req = PrivilegeSnapshotCreateRequest(
        target_scope="team",
        async_job=True,
    )
    assert req.async_job is True
