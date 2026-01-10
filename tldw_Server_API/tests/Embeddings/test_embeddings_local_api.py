import pytest

from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
    LocalAPICfg,
    create_embeddings_batch,
)


class _DummyResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):

        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):

        return self._payload


@pytest.mark.unit
def test_local_api_embeddings_use_status_code_property(monkeypatch):
    def fake_fetch(**kwargs):
        return _DummyResponse({"embeddings": [[0.1, 0.2, 0.3]]})

    monkeypatch.setattr(
        "tldw_Server_API.app.core.http_client.fetch",
        fake_fetch,
        raising=True,
    )

    model_id = "local_api:stub-model"
    user_app_config = {
        "embedding_config": {
            "default_model_id": model_id,
            "models": {
                model_id: LocalAPICfg(
                    provider="local_api",
                    model_name_or_path="stub-model",
                    api_url="http://localhost:9999/embeddings",
                )
            },
        }
    }

    result = create_embeddings_batch(
        ["hello"],
        user_app_config,
        model_id_override=model_id,
    )

    assert result == [[0.1, 0.2, 0.3]]
