from pathlib import Path

import numpy as np
import pytest

from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as EC


class _FakeEmbedder:
    def __init__(self, model_identifier, config, hf_cache_dir):
        self.model_identifier = model_identifier

    def create_embeddings(self, texts):
        return np.zeros((len(texts), 2), dtype=float)


@pytest.mark.unit
def test_memory_limit_enforced_when_eviction_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(EC, "HuggingFaceEmbedder", _FakeEmbedder)
    monkeypatch.setattr(EC, "embedding_models", {}, raising=False)
    monkeypatch.setattr(EC, "model_last_used", {}, raising=False)
    monkeypatch.setattr(EC, "model_memory_usage", {}, raising=False)
    monkeypatch.setattr(EC, "model_in_use_counts", {}, raising=False)
    monkeypatch.setattr(EC, "check_memory_limit", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(EC, "evict_lru_models", lambda *args, **kwargs: None)

    monkeypatch.setattr(EC, "_EMBEDDINGS_STORAGE_ALLOWLIST_ROOT", Path(tmp_path).resolve())

    config = {
        "embedding_config": {
            "default_model_id": "huggingface:dummy",
            "model_storage_base_dir": str(tmp_path),
            "models": {
                "huggingface:dummy": {
                    "provider": "huggingface",
                    "model_name_or_path": "dummy",
                }
            },
        }
    }

    with pytest.raises(RuntimeError, match="exceeds memory limit"):
        EC.create_embeddings_batch(["hello"], config)


@pytest.mark.unit
def test_capacity_limit_enforced_when_no_evictable_models(monkeypatch, tmp_path):
    monkeypatch.setattr(EC, "HuggingFaceEmbedder", _FakeEmbedder)
    monkeypatch.setattr(EC, "embedding_models", {"huggingface:existing": object()}, raising=False)
    monkeypatch.setattr(EC, "model_last_used", {"huggingface:existing": 0.0}, raising=False)
    monkeypatch.setattr(EC, "model_memory_usage", {"huggingface:existing": 0.1}, raising=False)
    monkeypatch.setattr(EC, "model_in_use_counts", {"huggingface:existing": 1}, raising=False)
    monkeypatch.setattr(EC, "MAX_MODELS_IN_MEMORY", 1)
    monkeypatch.setattr(EC, "check_memory_limit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(EC, "evict_lru_models", lambda *args, **kwargs: None)

    monkeypatch.setattr(EC, "_EMBEDDINGS_STORAGE_ALLOWLIST_ROOT", Path(tmp_path).resolve())

    config = {
        "embedding_config": {
            "default_model_id": "huggingface:new",
            "model_storage_base_dir": str(tmp_path),
            "models": {
                "huggingface:new": {
                    "provider": "huggingface",
                    "model_name_or_path": "dummy",
                }
            },
        }
    }

    with pytest.raises(RuntimeError, match="cache at capacity"):
        EC.create_embeddings_batch(["hello"], config)


@pytest.mark.unit
def test_inprocess_test_mode_uses_synthetic_huggingface_embeddings(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("E2E_INPROCESS", "1")
    monkeypatch.setattr(
        EC,
        "_import_torch",
        lambda: (_ for _ in ()).throw(AssertionError("torch import should be skipped")),
    )
    monkeypatch.setattr(EC, "_EMBEDDINGS_STORAGE_ALLOWLIST_ROOT", Path(tmp_path).resolve())

    config = {
        "embedding_config": {
            "default_model_id": "huggingface:dummy",
            "model_storage_base_dir": str(tmp_path),
            "models": {
                "huggingface:dummy": {
                    "provider": "huggingface",
                    "model_name_or_path": "dummy",
                }
            },
        }
    }

    embeddings = EC.create_embeddings_batch(["alpha beta", "alpha beta", "gamma"], config)

    assert len(embeddings) == 3
    assert embeddings[0] == embeddings[1]
    assert embeddings[0] != embeddings[2]
    assert len(embeddings[0]) == 384
