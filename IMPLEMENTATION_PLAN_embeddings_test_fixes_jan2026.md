## Stage 1: Eviction Off-by-One
**Goal**: Keep exactly `max_models_in_memory` models after eviction.
**Success Criteria**: `test_async_local_provider_eviction_calls_cpu_cleanup` passes.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Embeddings/test_async_local_provider.py::test_async_local_provider_eviction_calls_cpu_cleanup -q`
**Status**: Complete

## Stage 2: Idempotent Metrics Registration
**Goal**: Avoid Prometheus duplication errors on re-import.
**Success Criteria**: Re-importing `Embeddings_Create` does not raise; optional-deps import test passes.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_optional_deps_import.py::test_embeddings_create_imports_without_optional_deps -q`
**Status**: Complete

## Stage 3: Dimensions Policy for Non-OpenAI Providers
**Goal**: Allow `dimensions` on non-OpenAI providers and apply local policy.
**Success Criteria**: dimensions policy unit tests and HF dimension override integration test pass.
**Tests**: 
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_dimensions_policy.py -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_v5_integration.py::TestEmbeddingsIntegration::test_huggingface_embedding_dimension_override_reduce -q`
**Status**: Complete

## Stage 4: Token Array Decode Fallback
**Goal**: Log decode failures and fall back to empty string(s) rather than raising.
**Success Criteria**: decode failure logging test passes.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_token_arrays.py::test_tokens_to_texts_logs_decode_failure -q`
**Status**: Complete

## Stage 5: Re-run Affected Tests
**Goal**: Validate all previously failing Embeddings tests now pass.
**Success Criteria**: All targeted failing tests pass.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_async_local_provider.py::test_async_local_provider_eviction_calls_cpu_cleanup -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_optional_deps_import.py::test_embeddings_create_imports_without_optional_deps -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_dimensions_policy.py -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_token_arrays.py::test_tokens_to_texts_logs_decode_failure -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_v5_integration.py::TestEmbeddingsIntegration::test_real_huggingface_embedding -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_v5_integration.py::TestEmbeddingsIntegration::test_huggingface_embedding_base64_format -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_v5_integration.py::TestEmbeddingsIntegration::test_huggingface_embedding_dimension_override_reduce -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_embeddings_v5_property.py -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_hyde_backfill_cli.py::test_hyde_backfill_embeds_real_vectors -q`
- `python -m pytest -q tldw_Server_API/tests/Embeddings/test_request_batching.py -q`
**Status**: In Progress
