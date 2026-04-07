# Knowledge QA Answer Model Selection Design

## Goal
Expose answer-generation provider and model controls directly in the Knowledge QA search flow so users can choose which API/model answers their question without leaving the page.

## Design
- Reuse existing `generation_provider` and `generation_model` fields in `RagSettings` and the unified RAG request builder.
- Add an inline `Answer model` control block to the QA quick settings row.
- Show a provider dropdown sourced from the server's LLM provider/model metadata and a model autocomplete sourced from the selected provider's known models.
- Allow custom model text entry so local/custom OpenAI-compatible backends still work even when server metadata is incomplete.
- Keep the settings page and quick settings row in sync by writing through the shared `updateSetting` path.

## Data Flow
- `KnowledgePanel` passes `generation_provider` / `generation_model` and update callbacks into `QASearchTab`.
- `QASearchTab` passes them into `QAQuickSettings`.
- `QAQuickSettings` fetches provider/model metadata from the existing TLDW client and updates shared settings state.
- `buildRagSearchRequest()` already forwards these fields into the request payload when present.

## Error Handling
- If provider/model metadata cannot be loaded, keep the controls usable with an empty provider list and free-text model entry.
- Do not block searches on metadata fetch failures.

## Testing
- Add a focused QA quick-settings test covering provider/model rendering and update callbacks.
- Re-run the existing unified RAG request builder test to confirm `generation_provider` / `generation_model` still forward correctly.
