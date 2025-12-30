import uuid

import pytest
from fastapi.testclient import TestClient
from loguru import logger

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.tests.test_config import TestConfig

AUTH_HEADERS = {"X-API-KEY": TestConfig.TEST_API_KEY}


@pytest.fixture(scope="function")
def quizzes_db(tmp_path):
    db_path = tmp_path / "quizzes.db"
    db = CharactersRAGDB(str(db_path), client_id=f"test-{uuid.uuid4().hex[:6]}")
    yield db
    db.close_connection()


@pytest.fixture
def client_with_quizzes_db(quizzes_db: CharactersRAGDB):
    TestConfig.setup_test_environment()
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

    def override_get_db():
        logger.info("[TEST] override get_chacha_db_for_user -> quizzes_db")
        try:
            yield quizzes_db
        finally:
            pass

    async def override_user():
        return User(
            id=1,
            username="testuser",
            email="test@example.com",
            is_active=True,
            roles=["admin"],
            is_admin=True,
        )

    fastapi_app.dependency_overrides[get_chacha_db_for_user] = override_get_db
    fastapi_app.dependency_overrides[get_request_user] = override_user

    with TestClient(fastapi_app, headers=AUTH_HEADERS) as client:
        yield client
    fastapi_app.dependency_overrides.clear()
    TestConfig.reset_settings()


def test_quiz_endpoints_flow(client_with_quizzes_db: TestClient):
    r = client_with_quizzes_db.post(
        "/api/v1/quizzes",
        json={"name": "Quiz One", "description": "desc"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    quiz_id = r.json()["id"]

    r = client_with_quizzes_db.post(
        f"/api/v1/quizzes/{quiz_id}/questions",
        json={
            "question_type": "multiple_choice",
            "question_text": "What is 2+2?",
            "options": ["1", "2", "4", "5"],
            "correct_answer": 2,
            "points": 1,
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    question_id = r.json()["id"]

    r = client_with_quizzes_db.get(f"/api/v1/quizzes/{quiz_id}/questions", headers=AUTH_HEADERS)
    assert r.status_code == 200
    questions_payload = r.json()
    questions = questions_payload["items"]
    assert questions
    assert "correct_answer" not in questions[0]

    r = client_with_quizzes_db.get(
        f"/api/v1/quizzes/{quiz_id}/questions",
        params={"include_answers": True},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    admin_payload = r.json()
    assert admin_payload["items"][0]["correct_answer"] == 2

    r = client_with_quizzes_db.post(f"/api/v1/quizzes/{quiz_id}/attempts", headers=AUTH_HEADERS)
    assert r.status_code == 200
    attempt = r.json()
    assert attempt["quiz_id"] == quiz_id
    assert attempt["questions"]
    assert "correct_answer" not in attempt["questions"][0]

    r = client_with_quizzes_db.put(
        f"/api/v1/quizzes/attempts/{attempt['id']}",
        json={"answers": [{"question_id": question_id, "user_answer": 2}]},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    result = r.json()
    assert result["score"] == 1
    assert result["answers"][0]["is_correct"] is True
