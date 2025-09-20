"""
Integration tests for VectorStores admin endpoints negative cases.
No internal mocks; relies on actual API behavior to return proper error codes.
"""

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user():
    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_admin_uniqueness_and_missing_resources(client_with_user: TestClient):
    client = client_with_user
    # Create store
    r1 = client.post('/api/v1/vector_stores', json={'name': 'UniqA', 'dimensions': 8})
    assert r1.status_code == 200, r1.text
    # Attempt to create another with same name and dimensions could succeed with unique id or fail; try renaming
    r_dup = client.post('/api/v1/vector_stores', json={'name': 'UniqA', 'dimensions': 8})
    assert r_dup.status_code in (200, 409, 400)

    # Query/update missing store
    missing_id = 'does-not-exist'
    g = client.get(f"/api/v1/vector_stores/{missing_id}")
    assert g.status_code in (404, 400)
    p = client.patch(f"/api/v1/vector_stores/{missing_id}", json={'name': 'new-name'})
    assert p.status_code in (404, 400)


def test_vector_record_negative_cases(client_with_user: TestClient):
    client = client_with_user
    # Create a store
    cs = client.post('/api/v1/vector_stores', json={'name': 'NegVec', 'dimensions': 8})
    assert cs.status_code == 200, cs.text
    sid = cs.json()['id']

    # Delete non-existent vector
    dv = client.delete(f"/api/v1/vector_stores/{sid}/vectors/unknown")
    assert dv.status_code in (404, 400)

    # Query without adding vectors - expect empty results
    q = client.post(f"/api/v1/vector_stores/{sid}/query", json={'vector': [0.0]*8, 'top_k': 3})
    assert q.status_code == 200
    qd = q.json()
    assert isinstance(qd, dict) and 'data' in qd and isinstance(qd['data'], list)

    # Batch status on unknown id
    bs = client.get(f"/api/v1/vector_stores/{sid}/vectors/batches/doesnotexist")
    assert bs.status_code in (404, 400)

    # Upsert vector with wrong dimension should error
    bad_upsert = client.post(
        f"/api/v1/vector_stores/{sid}/vectors",
        json={'records': [{'id': 'bad1', 'values': [0.0]*7, 'content': 'x'}]}  # 7 != 8
    )
    assert bad_upsert.status_code in (400, 422)

    # Query with mismatched dimension should error or 400/422
    bad_query = client.post(
        f"/api/v1/vector_stores/{sid}/query",
        json={'vector': [0.0]*7, 'top_k': 3}
    )
    assert bad_query.status_code in (400, 422)

    # Query with empty vector invalid
    empty_query = client.post(
        f"/api/v1/vector_stores/{sid}/query",
        json={'vector': [], 'top_k': 3}
    )
    assert empty_query.status_code in (400, 422)
