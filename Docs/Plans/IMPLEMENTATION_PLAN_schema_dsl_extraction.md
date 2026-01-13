## Stage 1: Schema DSL + Transforms
**Goal**: Implement schema DSL extraction (fields/baseSelector/baseFields) with safe transforms and computed/nested/list field types while preserving watchlist selector extraction.
**Success Criteria**: DSL rules extract structured fields with transforms applied; existing watchlist selector flow remains unchanged.
**Tests**: `tldw_Server_API/tests/WebScraping/test_schema_dsl_extraction.py`
**Status**: Complete

## Stage 2: Selector Stability/Uniqueness Validation
**Goal**: Extend selector validation to report non-unique matches and fragile CSS selectors when sample HTML is provided.
**Success Criteria**: Validation returns warnings for non-unique selectors and hashed/fragile class selectors without failing compilation-only checks.
**Tests**: `tldw_Server_API/tests/WebScraping/test_selector_validation.py`
**Status**: Complete

## Stage 3: Tests and Cleanup
**Goal**: Add/adjust unit tests to cover DSL field types, transforms, and validation warnings; confirm behavior locally.
**Success Criteria**: New tests pass; Stage statuses updated.
**Tests**: `tldw_Server_API/tests/WebScraping/test_schema_dsl_extraction.py`, `tldw_Server_API/tests/WebScraping/test_selector_validation.py`
**Status**: Complete
