import os
import uuid

import pytest
from fastapi.testclient import TestClient
from loguru import logger

# Keep this module self-contained and deterministic by disabling optional
# reading-digest startup paths that pull heavyweight STT deps during app import.
os.environ.setdefault("READING_DIGEST_JOBS_WORKER_ENABLED", "0")
os.environ.setdefault("READING_DIGEST_SCHEDULER_ENABLED", "0")
os.environ.setdefault("TEST_MODE", "1")

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


def test_quiz_multi_select_endpoints_flow(client_with_quizzes_db: TestClient):
    response = client_with_quizzes_db.post(
        "/api/v1/quizzes",
        json={"name": "Multi Select Quiz"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    quiz_id = response.json()["id"]

    response = client_with_quizzes_db.post(
        f"/api/v1/quizzes/{quiz_id}/questions",
        json={
            "question_type": "multi_select",
            "question_text": "Select even numbers",
            "options": ["1", "2", "3", "4"],
            "correct_answer": [1, 3],
            "points": 2,
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    question_id = response.json()["id"]
    assert response.json()["correct_answer"] == [1, 3]

    response = client_with_quizzes_db.post(
        f"/api/v1/quizzes/{quiz_id}/attempts",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    attempt_id = response.json()["id"]

    response = client_with_quizzes_db.put(
        f"/api/v1/quizzes/attempts/{attempt_id}",
        json={"answers": [{"question_id": question_id, "user_answer": [3, 1]}]},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["score"] == 2
    assert payload["answers"][0]["is_correct"] is True


def test_quiz_matching_endpoints_flow(client_with_quizzes_db: TestClient):
    response = client_with_quizzes_db.post(
        "/api/v1/quizzes",
        json={"name": "Matching Quiz"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    quiz_id = response.json()["id"]

    response = client_with_quizzes_db.post(
        f"/api/v1/quizzes/{quiz_id}/questions",
        json={
            "question_type": "matching",
            "question_text": "Match term to definition",
            "options": ["CPU", "RAM"],
            "correct_answer": {
                "CPU": "Processor",
                "RAM": "Temporary memory"
            },
            "points": 2,
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    question_id = response.json()["id"]
    assert response.json()["correct_answer"] == {
        "CPU": "Processor",
        "RAM": "Temporary memory"
    }

    response = client_with_quizzes_db.post(
        f"/api/v1/quizzes/{quiz_id}/attempts",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    attempt_id = response.json()["id"]

    response = client_with_quizzes_db.put(
        f"/api/v1/quizzes/attempts/{attempt_id}",
        json={
            "answers": [{
                "question_id": question_id,
                "user_answer": {"cpu": "processor", "ram": "temporary memory"}
            }]
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["score"] == 2
    assert payload["answers"][0]["is_correct"] is True


def test_quiz_hint_penalty_scoring_flow(client_with_quizzes_db: TestClient):
    response = client_with_quizzes_db.post(
        "/api/v1/quizzes",
        json={"name": "Hint Penalty Quiz"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    quiz_id = response.json()["id"]

    response = client_with_quizzes_db.post(
        f"/api/v1/quizzes/{quiz_id}/questions",
        json={
            "question_type": "multiple_choice",
            "question_text": "Capital of France?",
            "options": ["Berlin", "Paris", "Rome"],
            "correct_answer": 1,
            "hint": "Think Eiffel Tower.",
            "hint_penalty_points": 2,
            "points": 5,
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    question_id = response.json()["id"]
    assert response.json()["hint"] == "Think Eiffel Tower."
    assert response.json()["hint_penalty_points"] == 2

    response = client_with_quizzes_db.post(
        f"/api/v1/quizzes/{quiz_id}/attempts",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    attempt_id = response.json()["id"]

    response = client_with_quizzes_db.put(
        f"/api/v1/quizzes/attempts/{attempt_id}",
        json={
            "answers": [{
                "question_id": question_id,
                "user_answer": 1,
                "hint_used": True
            }]
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["score"] == 3
    assert payload["answers"][0]["is_correct"] is True
    assert payload["answers"][0]["points_awarded"] == 3
    assert payload["answers"][0]["hint_used"] is True
    assert payload["answers"][0]["hint_penalty_points"] == 2


def test_quiz_json_import_roundtrip(client_with_quizzes_db: TestClient):
    source_quiz_response = client_with_quizzes_db.post(
        "/api/v1/quizzes",
        json={
            "name": "Roundtrip Quiz",
            "description": "roundtrip source",
            "workspace_tag": "workspace:science",
            "media_id": 99,
            "time_limit_seconds": 900,
            "passing_score": 80,
        },
        headers=AUTH_HEADERS,
    )
    assert source_quiz_response.status_code == 200
    source_quiz = source_quiz_response.json()
    source_quiz_id = source_quiz["id"]

    source_questions_payload = [
        {
            "question_type": "multiple_choice",
            "question_text": "What is 2 + 2?",
            "options": ["3", "4", "5"],
            "correct_answer": 1,
            "hint": "Think of pairs.",
            "hint_penalty_points": 1,
            "source_citations": [
                {
                    "label": "Arithmetic primer",
                    "quote": "Two plus two equals four.",
                    "media_id": 99,
                    "chunk_id": "math-1",
                    "timestamp_seconds": 12.2,
                }
            ],
            "points": 1,
            "order_index": 0,
            "tags": ["math", "easy"],
        },
        {
            "question_type": "matching",
            "question_text": "Match hardware to role",
            "options": ["CPU", "RAM"],
            "correct_answer": {"CPU": "Processor", "RAM": "Memory"},
            "hint": "CPU computes, RAM stores temporary data.",
            "hint_penalty_points": 1,
            "source_citations": [
                {
                    "label": "Hardware glossary",
                    "quote": "RAM stores short-term data used by the CPU.",
                    "media_id": 99,
                    "chunk_id": "hardware-3",
                }
            ],
            "points": 2,
            "order_index": 1,
            "tags": ["hardware"],
        },
    ]

    for question in source_questions_payload:
        create_question_response = client_with_quizzes_db.post(
            f"/api/v1/quizzes/{source_quiz_id}/questions",
            json=question,
            headers=AUTH_HEADERS,
        )
        assert create_question_response.status_code == 200

    source_questions_response = client_with_quizzes_db.get(
        f"/api/v1/quizzes/{source_quiz_id}/questions",
        params={"include_answers": True},
        headers=AUTH_HEADERS,
    )
    assert source_questions_response.status_code == 200
    source_questions = source_questions_response.json()["items"]

    import_payload = {
        "export_format": "tldw.quiz.export.v1",
        "quizzes": [
            {
                "quiz": source_quiz,
                "questions": source_questions,
            }
        ],
    }

    import_response = client_with_quizzes_db.post(
        "/api/v1/quizzes/import/json",
        json=import_payload,
        headers=AUTH_HEADERS,
    )
    assert import_response.status_code == 200
    import_result = import_response.json()
    assert import_result["imported_quizzes"] == 1
    assert import_result["failed_quizzes"] == 0
    assert import_result["imported_questions"] == 2
    assert import_result["failed_questions"] == 0
    assert import_result["errors"] == []
    assert len(import_result["items"]) == 1

    imported_quiz_id = import_result["items"][0]["quiz_id"]
    assert imported_quiz_id != source_quiz_id

    imported_quiz_response = client_with_quizzes_db.get(
        f"/api/v1/quizzes/{imported_quiz_id}",
        headers=AUTH_HEADERS,
    )
    assert imported_quiz_response.status_code == 200
    imported_quiz = imported_quiz_response.json()
    assert imported_quiz["name"] == source_quiz["name"]
    assert imported_quiz["description"] == source_quiz["description"]
    assert imported_quiz["workspace_tag"] == source_quiz["workspace_tag"]
    assert imported_quiz["media_id"] == source_quiz["media_id"]
    assert imported_quiz["time_limit_seconds"] == source_quiz["time_limit_seconds"]
    assert imported_quiz["passing_score"] == source_quiz["passing_score"]

    imported_questions_response = client_with_quizzes_db.get(
        f"/api/v1/quizzes/{imported_quiz_id}/questions",
        params={"include_answers": True},
        headers=AUTH_HEADERS,
    )
    assert imported_questions_response.status_code == 200
    imported_questions = imported_questions_response.json()["items"]
    assert len(imported_questions) == len(source_questions)

    source_by_order = {
        int(question["order_index"]): question
        for question in source_questions
    }
    for imported_question in imported_questions:
        source_question = source_by_order[int(imported_question["order_index"])]
        assert imported_question["question_type"] == source_question["question_type"]
        assert imported_question["question_text"] == source_question["question_text"]
        assert imported_question["options"] == source_question["options"]
        assert imported_question["correct_answer"] == source_question["correct_answer"]
        assert imported_question["hint"] == source_question["hint"]
        assert imported_question["hint_penalty_points"] == source_question["hint_penalty_points"]
        assert imported_question["source_citations"] == source_question["source_citations"]
        assert imported_question["points"] == source_question["points"]
        assert imported_question["tags"] == source_question["tags"]

    imported_attempt_response = client_with_quizzes_db.post(
        f"/api/v1/quizzes/{imported_quiz_id}/attempts",
        headers=AUTH_HEADERS,
    )
    assert imported_attempt_response.status_code == 200
    imported_attempt = imported_attempt_response.json()

    question_ids_by_type = {
        question["question_type"]: question["id"]
        for question in imported_questions
    }
    submit_response = client_with_quizzes_db.put(
        f"/api/v1/quizzes/attempts/{imported_attempt['id']}",
        json={
            "answers": [
                {
                    "question_id": question_ids_by_type["multiple_choice"],
                    "user_answer": 1,
                },
                {
                    "question_id": question_ids_by_type["matching"],
                    "user_answer": {"cpu": "processor", "ram": "memory"},
                },
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert submit_response.status_code == 200
    submit_payload = submit_response.json()
    assert submit_payload["score"] == 3
    assert all(answer["is_correct"] for answer in submit_payload["answers"])
    answer_by_question_id = {
        int(answer["question_id"]): answer
        for answer in submit_payload["answers"]
    }
    source_by_type = {
        question["question_type"]: question["source_citations"]
        for question in imported_questions
    }
    assert answer_by_question_id[question_ids_by_type["multiple_choice"]]["source_citations"] == source_by_type["multiple_choice"]
    assert answer_by_question_id[question_ids_by_type["matching"]]["source_citations"] == source_by_type["matching"]
