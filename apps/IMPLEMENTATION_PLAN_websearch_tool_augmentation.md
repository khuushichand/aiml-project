## Stage 1: Review + Design
**Goal**: Confirm current websearch flow and specify required payload/response and prompt-injection changes.
**Success Criteria**: Clear list of backend fields + UI prompt injection approach decided.
**Tests**: N/A
**Status**: Complete

## Stage 2: Backend Extensions
**Goal**: Add Exa/Firecrawl providers, extend request schema and config, and wire into websearch pipeline.
**Success Criteria**: New engines accepted; provider functions and parsers return normalized results; tests cover new parsers/engines.
**Tests**: `tldw_Server_API/tests/WebSearch/unit/test_parsers_extended.py`, `tldw_Server_API/tests/WebSearch/integration/test_websearch_engines_endpoint.py`
**Status**: In Progress

## Stage 3: Frontend Tool-Style Websearch
**Goal**: Websearch augments the selected model by injecting results into prompts and exposing sources (packages/ui + extension).
**Success Criteria**: Websearch no longer replaces model output; search results become prompt context and citations.
**Tests**: UI smoke/manual
**Status**: Not Started

## Stage 4: Docs/Polish
**Goal**: Update config docs/examples and tidy any mismatches.
**Success Criteria**: Config additions documented; no obvious mismatches.
**Tests**: N/A
**Status**: Not Started
