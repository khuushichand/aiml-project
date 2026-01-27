## Stage 1: Confirm Failures
**Goal**: Reproduce the three reported failure modes locally.
**Success Criteria**: Each failing test shows the same error signature.
**Tests**: Run the three targeted pytest invocations.
**Status**: Complete

## Stage 2: Preserve Stream Holdback On Upstream Error
**Goal**: Ensure buffered early chunks are emitted before a midstream error SSE frame.
**Success Criteria**: Midstream SSE test sees the earlier \"hello\" chunk.
**Tests**: Run midstream SSE test file (or a representative case).
**Status**: Complete

## Stage 3: Make Google Tools + Stream Deltas Backward Compatible
**Goal**: Allow Gemini-native tools through validation and restore `_stream_event_deltas` compatibility.
**Success Criteria**: `test_google_config_fallbacks` and `test_google_stream_preserves_provider_response` pass.
**Tests**: Run both targeted Google tests.
**Status**: In Progress

## Stage 4: Validate End-to-End
**Goal**: Verify all previously failing tests now pass.
**Success Criteria**: All 12 originally failing tests pass locally.
**Tests**: Run the midstream SSE file plus the two Google tests.
**Status**: Not Started
