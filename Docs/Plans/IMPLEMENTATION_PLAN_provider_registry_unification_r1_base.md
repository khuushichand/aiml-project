## Stage 1: Define Base Registry Foundation Scope
**Goal**: Establish the minimal R1 deliverable and API surface for `ProviderRegistryBase` and config types.
**Success Criteria**: Plan includes module path, class/type names, and test targets for foundation behavior.
**Tests**: N/A
**Status**: In Progress

## Stage 2: Implement Shared Infrastructure Module
**Goal**: Add `ProviderRegistryBase` and related supporting types in Infrastructure with public methods for registration, resolution, and status reporting.
**Success Criteria**: `tldw_Server_API/app/core/Infrastructure/provider_registry.py` exists and imports cleanly.
**Tests**: New unit tests under `tldw_Server_API/tests/Infrastructure/` covering foundational behavior.
**Status**: Not Started

## Stage 3: Validate Foundation with Unit Tests
**Goal**: Run focused pytest for the new base registry tests and ensure green.
**Success Criteria**: Targeted unit tests pass locally.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Infrastructure/test_provider_registry_base.py`
**Status**: Not Started
