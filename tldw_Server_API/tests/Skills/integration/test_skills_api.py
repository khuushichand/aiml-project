# tests/Skills/integration/test_skills_api.py
#
# Integration tests for Skills REST API endpoints
#

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.main import app

pytestmark = pytest.mark.integration

SKILLS_PREFIX = "/api/v1/skills"
TEST_USER_ID = 999


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Provide a TestClient with mocked auth and isolated user database."""
    user_base = tmp_path / "user_databases" / str(TEST_USER_ID)
    user_base.mkdir(parents=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_databases"))

    db_path = user_base / "ChaChaNotes.db"
    chacha_db = CharactersRAGDB(db_path=db_path, client_id="test_client")

    async def override_user():
        return User(id=TEST_USER_ID, username="skills-test-user", email=None, is_active=True)

    def override_chacha_db():
        return chacha_db

    # Monkeypatch DatabasePaths so SkillsService gets our temp dir
    monkeypatch.setattr(DatabasePaths, "get_user_base_directory", staticmethod(lambda uid: user_base))

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_chacha_db_for_user] = override_chacha_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        chacha_db.close_connection()


SAMPLE_SKILL = """---
name: test-skill
description: A test skill for API integration
argument-hint: "[text]"
context: inline
---

Process $ARGUMENTS with care.
"""


class TestListSkills:
    def test_list_skills_empty(self, client):
        r = client.get(f"{SKILLS_PREFIX}/")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["skills"] == []
        assert data["total"] == 0

    def test_list_skills_pagination(self, client):
        # Create 3 skills
        for i in range(3):
            r = client.post(
                f"{SKILLS_PREFIX}/",
                json={"name": f"skill-{i:02d}", "content": f"Content {i}"},
            )
            assert r.status_code == 201, r.text

        # Page 1
        r = client.get(f"{SKILLS_PREFIX}/?limit=2&offset=0")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert data["total"] == 3

        # Page 2
        r = client.get(f"{SKILLS_PREFIX}/?limit=2&offset=2")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1


class TestCreateAndGetSkill:
    def test_create_skill_and_get(self, client):
        r = client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "new-skill", "content": SAMPLE_SKILL},
        )
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["name"] == "new-skill"
        assert created["description"] == "A test skill for API integration"
        assert created["version"] == 1

        # Get it back
        r = client.get(f"{SKILLS_PREFIX}/new-skill")
        assert r.status_code == 200
        got = r.json()
        assert got["name"] == "new-skill"
        assert "Process $ARGUMENTS" in got["content"]

    def test_create_skill_invalid_name_400(self, client):
        r = client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "Invalid_Name!", "content": "content"},
        )
        assert r.status_code == 422  # Pydantic validation error

    def test_create_skill_duplicate_409(self, client):
        client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "dup-skill", "content": "content"},
        )
        r = client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "dup-skill", "content": "content again"},
        )
        assert r.status_code == 409


class TestUpdateSkill:
    def test_update_skill_content(self, client):
        client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "upd-skill", "content": "original"},
        )

        r = client.put(
            f"{SKILLS_PREFIX}/upd-skill",
            json={"content": "---\ndescription: Updated\n---\nNew content"},
        )
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["description"] == "Updated"
        assert updated["version"] == 2

    def test_update_skill_version_conflict_409(self, client):
        client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "ver-skill", "content": "v1"},
        )
        # Update to v2
        client.put(
            f"{SKILLS_PREFIX}/ver-skill",
            json={"content": "v2"},
        )
        # Try with stale version
        r = client.put(
            f"{SKILLS_PREFIX}/ver-skill",
            json={"content": "v3"},
            headers={"If-Match": "1"},
        )
        assert r.status_code == 409


class TestDeleteSkill:
    def test_delete_skill_204(self, client):
        client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "del-skill", "content": "content"},
        )
        r = client.delete(f"{SKILLS_PREFIX}/del-skill")
        assert r.status_code == 204

        r = client.get(f"{SKILLS_PREFIX}/del-skill")
        assert r.status_code == 404

    def test_delete_skill_not_found_404(self, client):
        r = client.delete(f"{SKILLS_PREFIX}/nonexistent")
        assert r.status_code == 404


class TestImportExport:
    def test_import_skill_json(self, client):
        r = client.post(
            f"{SKILLS_PREFIX}/import",
            json={
                "name": "imported",
                "content": "---\ndescription: Imported\n---\nImported content",
                "overwrite": False,
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["name"] == "imported"

    def test_import_skill_overwrite(self, client):
        client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "overwrite-me", "content": "original"},
        )
        r = client.post(
            f"{SKILLS_PREFIX}/import",
            json={
                "name": "overwrite-me",
                "content": "---\ndescription: Overwritten\n---\nNew",
                "overwrite": True,
            },
        )
        assert r.status_code == 201
        assert r.json()["description"] == "Overwritten"

    def test_import_skill_file_md(self, client, tmp_path):
        skill_file = tmp_path / "my-file-skill.md"
        skill_file.write_text("---\ndescription: From file\n---\nFile content")

        with open(skill_file, "rb") as f:
            r = client.post(
                f"{SKILLS_PREFIX}/import/file",
                files={"file": ("my-file-skill.md", f, "text/markdown")},
            )
        assert r.status_code == 201, r.text

    def test_import_skill_file_zip(self, client, tmp_path):
        import zipfile
        from io import BytesIO

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("zip-skill/SKILL.md", "---\ndescription: Zipped\n---\nZip content")
            zf.writestr("zip-skill/ref.md", "reference data")
        buf.seek(0)

        r = client.post(
            f"{SKILLS_PREFIX}/import/file",
            files={"file": ("skill.zip", buf, "application/zip")},
        )
        assert r.status_code == 201, r.text
        assert r.json()["name"] == "zip-skill"

    def test_export_skill_zip(self, client):
        client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "export-skill", "content": SAMPLE_SKILL},
        )
        r = client.get(f"{SKILLS_PREFIX}/export-skill/export")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        # Zip magic bytes
        assert r.content[:2] == b"PK"

    def test_export_skill_not_found_404(self, client):
        r = client.get(f"{SKILLS_PREFIX}/no-such-skill/export")
        assert r.status_code == 404


class TestExecuteSkill:
    def test_execute_skill_inline(self, client):
        client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "exec-skill", "content": "Do: $ARGUMENTS"},
        )
        r = client.post(
            f"{SKILLS_PREFIX}/exec-skill/execute",
            json={"args": "my test args"},
        )
        assert r.status_code == 200, r.text
        result = r.json()
        assert result["skill_name"] == "exec-skill"
        assert "my test args" in result["rendered_prompt"]
        assert result["execution_mode"] == "inline"


class TestContextPayload:
    def test_get_context_payload(self, client):
        client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "ctx-skill", "content": "---\ndescription: Context test\n---\nBody"},
        )
        r = client.get(f"{SKILLS_PREFIX}/context")
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["available_skills"]) >= 1
        assert "ctx-skill" in data["context_text"]


class TestSupportingFilesLimit:
    def test_supporting_files_aggregate_limit_rejected(self, client):
        """Regression Bug 7: aggregate supporting files over 5MB should be rejected."""
        big_content = "x" * 400_000
        files = {f"file{i:02d}.md": big_content for i in range(15)}
        r = client.post(
            f"{SKILLS_PREFIX}/",
            json={"name": "big-files", "content": "content", "supporting_files": files},
        )
        assert r.status_code == 422  # Pydantic validation error
