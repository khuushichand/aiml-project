import json
from pathlib import Path
from typing import Dict, Tuple

import pytest
from fastapi.testclient import TestClient
from fastapi import status

from tldw_Server_API.app.main import app as fastapi_app_instance, app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, _single_user_instance
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user


def check_batch_response(response, expected_status, expected_processed=None, expected_errors=None, check_results_len=None):
    assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"
    data = response.json()
    assert isinstance(data, dict)
    assert "results" in data and isinstance(data["results"], list)
    assert "processed_count" in data and "errors_count" in data and "errors" in data
    if expected_processed is not None:
        assert data["processed_count"] == expected_processed
    if expected_errors is not None:
        assert data["errors_count"] == expected_errors
    if check_results_len is not None:
        assert len(data["results"]) == check_results_len
    return data


@pytest.fixture(scope="module")
def client():
    def _override_get_request_user_proc_test():
        _single_user_instance.id = 1
        return _single_user_instance

    async def _fake_get_media_db_for_user():
        class _FakeDB:
            def close_all_connections(self):
                return None
        yield _FakeDB()

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_request_user] = _override_get_request_user_proc_test
    app.dependency_overrides[get_media_db_for_user] = _fake_get_media_db_for_user

    with TestClient(fastapi_app_instance) as c:
        yield c

    app.dependency_overrides = original_overrides


@pytest.fixture
def dummy_headers():
    return {"token": "dummy"}


class TestProcessCode:
    ENDPOINT = "/api/v1/media/process-code"

    def test_process_code_upload_py_success(self, client, dummy_headers, tmp_path: Path):
        code_path = tmp_path / "sample.py"
        code_path.write_text(
            """
def add(a, b):
    return a + b
""".strip(),
            encoding="utf-8",
        )

        with open(code_path, "rb") as f:
            files = {"files": (code_path.name, f, "text/x-python")}
            resp = client.post(self.ENDPOINT, files=files, headers=dummy_headers)

        data = check_batch_response(
            resp, status.HTTP_200_OK, expected_processed=1, expected_errors=0, check_results_len=1
        )
        result = data["results"][0]
        assert result["status"] == "Success"
        assert result["media_type"] == "code"
        assert result["input_ref"] == code_path.name
        assert "add(a, b)" in (result.get("content") or "")
        assert result.get("metadata", {}).get("language") == "python"
        assert isinstance(result.get("chunks"), list)

    def test_process_code_upload_py_with_code_metadata(self, client, dummy_headers, tmp_path: Path):
        code_path = tmp_path / "sample_meta.py"
        code_path.write_text(
            """
import os

def foo(x):
    return x + 1

class Bar:
    def baz(self):
        return 42
""".strip(),
            encoding="utf-8",
        )

        with open(code_path, "rb") as f:
            files = {"files": (code_path.name, f, "text/x-python")}
            resp = client.post(self.ENDPOINT, files=files, headers=dummy_headers)

        data = check_batch_response(
            resp, status.HTTP_200_OK, expected_processed=1, expected_errors=0, check_results_len=1
        )
        result = data["results"][0]
        chunks = result.get("chunks") or []
        assert isinstance(chunks, list) and len(chunks) >= 1
        # Check that code-specific metadata exists
        md = chunks[0].get("metadata", {})
        assert md.get("chunk_method") == "code"
        assert md.get("language") in ("python", "py")
        # line-range metadata should exist
        assert isinstance(md.get("start_line"), int) and isinstance(md.get("end_line"), int)

    def test_process_code_upload_invalid_extension_rejected(self, client, dummy_headers, tmp_path: Path):
        bad_path = tmp_path / "malware.exe"
        bad_path.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00")
        with open(bad_path, "rb") as f:
            files = {"files": (bad_path.name, f, "application/octet-stream")}
            resp = client.post(self.ENDPOINT, files=files, headers=dummy_headers)

        data = check_batch_response(
            resp, status.HTTP_207_MULTI_STATUS, expected_processed=0, expected_errors=1, check_results_len=1
        )
        result = data["results"][0]
        assert result["status"] == "Error"
        assert result["input_ref"] == bad_path.name
        assert "Invalid file type" in (result.get("error") or "")

    def test_process_code_upload_chunking_disabled(self, client, dummy_headers, tmp_path: Path):
        c_path = tmp_path / "sample.c"
        c_path.write_text(
            """
#include <stdio.h>
int main(){ printf("hi\n"); return 0; }
""".strip(),
            encoding="utf-8",
        )
        with open(c_path, "rb") as f:
            files = {"files": (c_path.name, f, "text/x-c")}
            resp = client.post(
                self.ENDPOINT, data={"perform_chunking": "false"}, files=files, headers=dummy_headers
            )

        data = check_batch_response(
            resp, status.HTTP_200_OK, expected_processed=1, expected_errors=0, check_results_len=1
        )
        result = data["results"][0]
        assert result["status"] == "Success"
        assert result["media_type"] == "code"
        assert result.get("chunks") in ([], None)
