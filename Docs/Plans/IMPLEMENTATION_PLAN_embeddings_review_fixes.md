## Stage 1: Audit & Repro
**Goal**: Identify failing Embeddings paths and missing modules/tests.
**Success Criteria**: Failing tests enumerated; root causes noted.
**Tests**: N/A (diagnostic stage)
**Status**: Complete

## Stage 2: Routing & Defaults
**Goal**: Align default_model_id handling and local/local_api routing across async and batch paths.
**Success Criteria**: Batch/async paths resolve provider+model consistently and local routing honors api_url.
**Tests**: `tldw_Server_API/tests/Embeddings/test_request_batching.py`
**Status**: Complete

## Stage 3: Validation & Safety
**Goal**: Add HF response shape validation and safer cache deserialization; fill missing schema/helpers.
**Success Criteria**: HF async normalization handles pooled/nested shapes; cache reads hardened; schema files present.
**Tests**: `tldw_Server_API/tests/Embeddings/test_async_embeddings_normalization.py`, `tldw_Server_API/tests/Embeddings/test_message_validator.py`
**Status**: Complete

## Stage 4: Missing-Key Behavior
**Goal**: Keep missing-provider-credentials errors for explicit BYOK while allowing provider-validation tests.
**Success Criteria**: Provider validation property tests pass; missing key returns 503 when explicitly unresolved.
**Tests**: `tldw_Server_API/tests/Embeddings/test_embeddings_v5_property.py::TestInputValidationProperties::test_provider_validation`, `tldw_Server_API/tests/Embeddings/test_embeddings_v5_unit.py::TestErrorHandling::test_missing_provider_credentials_returns_503`
**Status**: Complete
