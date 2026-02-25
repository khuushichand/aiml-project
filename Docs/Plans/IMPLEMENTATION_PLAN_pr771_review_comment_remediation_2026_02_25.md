## Stage 1: Comment Triage
**Goal**: Convert PR #771 feedback into concrete implementation actions.
**Success Criteria**: Each actionable comment maps to a code/test/doc change or a justified rationale response.
**Tests**: N/A
**Status**: Complete

## Stage 2: Test-First Coverage
**Goal**: Add failing tests for accepted behavior/security/correctness fixes.
**Success Criteria**: New tests fail before implementation and pass after implementation.
**Tests**:
- `tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py`
- `tldw_Server_API/tests/FileArtifacts/test_image_adapter_allowlist.py`
- `tldw_Server_API/tests/Image_Generation/test_image_generation_config_defaults.py`
- `tldw_Server_API/tests/LLM_Adapters/unit/test_qwen_native_http.py`
**Status**: Complete

## Stage 3: Implementation Remediation
**Goal**: Apply minimal, focused code changes to satisfy validated review findings.
**Success Criteria**:
- ModelStudio `auto` mode actually falls back to async.
- ModelStudio URL fetch path has host/policy validation before HTTP fetch.
- ModelStudio exception surfaces avoid raw transport exception text.
- ModelStudio `region` affects base-url resolution.
- `extra_params.mode` is accepted for backend control without passthrough allowlist requirement.
- `_coerce_choice` has a clear docstring.
- Qwen base URL precedence logic remains identical but clearer.
**Tests**: Stage 2 tests + existing targeted suites.
**Status**: Complete

## Stage 4: Verification and PR Thread Responses
**Goal**: Validate behavior and close the review loop in PR threads.
**Success Criteria**:
- Targeted tests pass.
- Bandit run on touched scope.
- Commit pushed to branch.
- Inline review comments receive thread replies with outcomes.
**Tests**:
- `python -m pytest` targeted paths
- `python -m bandit -r` touched scope
**Status**: In Progress
