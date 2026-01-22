from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
    EmbeddingConfigSchema,
    OpenAIModelCfg,
)


def test_embedding_config_schema_discriminates_openai_model():
    config = {
        "default_model_id": "openai:text-embedding-3-small",
        "models": {
            "openai:text-embedding-3-small": {
                "provider": "openai",
                "model_name_or_path": "text-embedding-3-small",
                "api_key": "sk-test",
                "dimensions": 512,
            }
        },
    }

    schema = EmbeddingConfigSchema(**config)
    model_cfg = schema.models["openai:text-embedding-3-small"]
    assert isinstance(model_cfg, OpenAIModelCfg)
    assert model_cfg.dimensions == 512
