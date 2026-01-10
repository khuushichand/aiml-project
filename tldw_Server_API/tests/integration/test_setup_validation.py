from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint


def _make_client():
    return TestClient(app)


def test_update_config_rejects_unknown_section(mocker):
    mocker.patch.object(
        setup_endpoint.setup_manager,
        'get_status_snapshot',
        return_value={'enabled': True, 'needs_setup': True},
    )
    payload = {'updates': {'NopeSection': {'foo': 'bar'}}}
    with _make_client() as client:
        resp = client.post('/api/v1/setup/config', json=payload)
    assert resp.status_code == 400
    assert 'Unknown section' in resp.text


def test_update_config_rejects_unknown_key(mocker):
    mocker.patch.object(
        setup_endpoint.setup_manager,
        'get_status_snapshot',
        return_value={'enabled': True, 'needs_setup': True},
    )
    # Known section, fake key
    payload = {'updates': {'Setup': {'does_not_exist': '1'}}}
    with _make_client() as client:
        resp = client.post('/api/v1/setup/config', json=payload)
    assert resp.status_code == 400
    assert 'Unknown key' in resp.text


def test_update_config_type_validation_boolean(mocker):
    mocker.patch.object(
        setup_endpoint.setup_manager,
        'get_status_snapshot',
        return_value={'enabled': True, 'needs_setup': True},
    )
    # enable_first_time_setup should be boolean-like; provide invalid string
    payload = {'updates': {'Setup': {'enable_first_time_setup': 'not_boolean'}}}
    with _make_client() as client:
        resp = client.post('/api/v1/setup/config', json=payload)
    assert resp.status_code == 400
    assert 'Invalid boolean' in resp.text
