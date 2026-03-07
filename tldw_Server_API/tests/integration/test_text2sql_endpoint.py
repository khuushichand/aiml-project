from fastapi.testclient import TestClient


def test_text2sql_route_exists(client_user_only: TestClient):
    response = client_user_only.post(
        "/api/v1/text2sql/query",
        json={"query": "count media", "target_id": "media_db"},
    )
    assert response.status_code in (200, 422, 403), response.text
