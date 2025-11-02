import os
import math
import numpy as np

from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as EC


def _stub_openai_batch(texts, model, app_config=None):
    # Deterministic vector per text; simple small dim for speed
    dim = 16
    out = []
    for t in texts:
        seed = int.from_bytes(t.encode("utf-8"), "little") % (2**32)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim, dtype=np.float32)
        n = np.linalg.norm(vec)
        if n > 0:
            vec = vec / n
        out.append(vec.tolist())
    return out


def test_create_embeddings_batch_accepts_provider_prefixed_model_id(monkeypatch):
    # Ensure limiting is bypassed in tests
    monkeypatch.setenv("TESTING", "true")

    # Patch the OpenAI batch function used inside Embeddings_Create
    EC.get_openai_embeddings_batch = _stub_openai_batch  # type: ignore[attr-defined]

    cfg = EC.get_embedding_config()

    # Inject an OpenAI model entry to avoid network; default config may be HF-only
    models = cfg["embedding_config"]["models"]
    models["openai:text-embedding-3-small"] = EC.OpenAIModelCfg(
        provider="openai",
        model_name_or_path="text-embedding-3-small",
        api_key="sk-test",
    )

    texts = ["hello", "world"]

    # Provider-prefixed override
    embs_prefixed = EC.create_embeddings_batch(texts=texts, user_app_config=cfg, model_id_override="openai:text-embedding-3-small")
    assert isinstance(embs_prefixed, list) and len(embs_prefixed) == 2
    assert all(isinstance(v, list) and len(v) == 16 for v in embs_prefixed)

    # Bare override should resolve to the same entry via normalization
    embs_bare = EC.create_embeddings_batch(texts=texts, user_app_config=cfg, model_id_override="text-embedding-3-small")
    assert isinstance(embs_bare, list) and len(embs_bare) == 2
    assert all(isinstance(v, list) and len(v) == 16 for v in embs_bare)
    # Deterministic property check
    assert embs_prefixed[0] == embs_bare[0]
