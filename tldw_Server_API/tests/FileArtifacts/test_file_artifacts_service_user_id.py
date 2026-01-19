import pytest

from tldw_Server_API.app.core.File_Artifacts.file_artifacts_service import FileArtifactsService


def test_file_artifacts_service_user_id_int():
    service = FileArtifactsService(object(), user_id=123)
    assert service._user_id_int == 123
    assert service._user_id == "123"


def test_file_artifacts_service_user_id_str():
    service = FileArtifactsService(object(), user_id="456")
    assert service._user_id_int == 456
    assert service._user_id == "456"


def test_file_artifacts_service_user_id_invalid():
    with pytest.raises(ValueError, match="invalid user_id: must be integer or numeric string"):
        FileArtifactsService(object(), user_id="abc")
