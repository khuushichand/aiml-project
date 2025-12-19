import numpy as np

from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as EC


def test_model_id_normalization_shares_cache(monkeypatch, tmp_path):
    class StubEmbedder:
        def __init__(self, model_identifier, config, hf_cache_dir):
            self.model_identifier = model_identifier

        def create_embeddings(self, texts):
            return np.zeros((len(texts), 3), dtype=np.float32)

        def unload_model(self):
            return None

    monkeypatch.setattr(EC, "HuggingFaceEmbedder", StubEmbedder)

    cfg = {
        "embedding_config": {
            "default_model_id": "huggingface:fake-model",
            "model_storage_base_dir": str(tmp_path),
            "models": {
                "huggingface:fake-model": EC.HFModelCfg(
                    provider="huggingface",
                    model_name_or_path="fake-model",
                    trust_remote_code=False,
                    hf_cache_dir_subpath="hf_cache",
                )
            },
        }
    }

    with EC.embedding_models_lock:
        EC.embedding_models.clear()
        EC.model_last_used.clear()
        EC.model_memory_usage.clear()

    try:
        EC.create_embeddings_batch(
            texts=["one"],
            user_app_config=cfg,
            model_id_override="fake-model",
        )
        EC.create_embeddings_batch(
            texts=["two"],
            user_app_config=cfg,
            model_id_override="huggingface:fake-model",
        )
        with EC.embedding_models_lock:
            assert len(EC.embedding_models) == 1
            assert "huggingface:fake-model" in EC.embedding_models
    finally:
        with EC.embedding_models_lock:
            EC.embedding_models.clear()
            EC.model_last_used.clear()
            EC.model_memory_usage.clear()
