from tldw_Server_API.app.core.Claims_Extraction import claims_service
from tldw_Server_API.app.core.Embeddings import ChromaDB_Library


def test_refresh_claim_embedding_wraps_config(monkeypatch, tmp_path):
    embedding_cfg = {
        "default_model_id": "huggingface:test-model",
        "models": {
            "huggingface:test-model": {
                "provider": "huggingface",
                "model_name_or_path": "test-model",
            }
        },
    }

    monkeypatch.setitem(claims_service.settings, "CLAIMS_EMBED", True)
    monkeypatch.setitem(claims_service.settings, "EMBEDDING_CONFIG", embedding_cfg)
    monkeypatch.setitem(claims_service.settings, "USER_DB_BASE_DIR", str(tmp_path))

    class DummyCollection:
        def delete(self, *args, **kwargs):
            return None

        def upsert(self, *args, **kwargs):
            return None

    class DummyManager:
        def __init__(self, user_id, user_embedding_config):
            self.user_id = user_id
            self.user_embedding_config = user_embedding_config

        def get_or_create_collection(self, name):
            return DummyCollection()

    called = {}

    def fake_create_embeddings_batch(*, texts, user_app_config, model_id_override=None):
        assert "embedding_config" in user_app_config
        assert user_app_config["embedding_config"] == embedding_cfg
        called["ok"] = True
        return [[0.0, 0.0]]

    monkeypatch.setattr(ChromaDB_Library, "ChromaDBManager", DummyManager)
    monkeypatch.setattr(ChromaDB_Library, "create_embeddings_batch", fake_create_embeddings_batch)

    claims_service._refresh_claim_embedding(
        claim_id=1,
        media_id=2,
        chunk_index=0,
        old_text="old",
        new_text="new",
        user_id="user-1",
    )

    assert called.get("ok") is True
