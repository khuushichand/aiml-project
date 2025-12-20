from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as EC


def test_openai_modelcfg_api_key_used(monkeypatch, tmp_path):
    captured = {}

    def fake_batch(texts, model, app_config=None, dimensions=None):
        captured["app_config"] = app_config
        return [[0.0] for _ in texts]

    monkeypatch.setattr(EC, "get_openai_embeddings_batch", fake_batch)

    cfg = {
        "embedding_config": {
            "default_model_id": "openai:text-embedding-3-small",
            "model_storage_base_dir": str(tmp_path),
            "models": {
                "openai:text-embedding-3-small": EC.OpenAIModelCfg(
                    provider="openai",
                    model_name_or_path="text-embedding-3-small",
                    api_key="sk-test",
                )
            },
        }
    }

    result = EC.create_embeddings_batch(
        texts=["hello"],
        user_app_config=cfg,
        model_id_override="openai:text-embedding-3-small",
    )

    assert result == [[0.0]]
    assert captured["app_config"]["openai_api"]["api_key"] == "sk-test"
