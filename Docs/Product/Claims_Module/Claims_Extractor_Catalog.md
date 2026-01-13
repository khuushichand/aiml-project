# Claims Extractor Catalog and Multilingual Heuristics

## Summary
Introduce a catalog endpoint that enumerates available claim extractors and improve multilingual heuristics for local extraction. Auto selection remains local-first to reduce latency and cost while supporting NER where available.

## Goals
- Provide a stable extractor catalog for UI selection and configuration.
- Improve sentence splitting for non-space languages.
- Add language-aware auto selection between heuristic and NER extractors.
- Document selection heuristics and configuration knobs.

## Non-goals
- Adding new external dependencies.
- Automatic selection of LLM extractors in auto mode.
- Changing the existing claims verification pipeline.

## Catalog Model
Each catalog entry includes:
- `mode`: unique extractor identifier (`heuristic`, `ner`, `aps`, `llm`, `auto`).
- `label`: human-readable name.
- `description`: short behavior summary.
- `execution`: `local` or `llm`.
- `supports_languages`: list of supported language tags or `["any"]`.
- `providers`: optional list of supported LLM provider keys.
- `auto_selectable`: whether auto mode may select this extractor.

## Auto Selection and Multilingual Heuristics
Auto mode uses lightweight detection and local availability checks:
- Detect language using unicode script hints; fallback to `CLAIMS_EXTRACTOR_LANGUAGE_DEFAULT`.
- For no-space languages (`zh`, `ja`, `ko`, `th`), prefer heuristic extraction to avoid NER gaps.
- If a spaCy pipeline is available and includes `ner`, auto selects `ner`; otherwise fallback to `heuristic`.
- LLM extractors remain opt-in, not auto-selected.

Sentence splitting improvements:
- No-space languages split on `。！？` and use a smaller minimum sentence length.
- Space-delimited languages split on `.?!…؟` with a larger minimum length.

## Configuration
All values may be provided via `.env` or `Config_Files/config.txt` under `[Claims]`:
- `CLAIMS_EXTRACTOR_LANGUAGE_DEFAULT`: fallback language when detection fails (`en` default).
- `CLAIMS_LOCAL_NER_MODEL`: spaCy model to load (`en_core_web_sm` default).
- `CLAIMS_LOCAL_NER_MODEL_MAP`: JSON map of language -> spaCy model name.
- `CLAIMS_LLM_PROVIDER`, `CLAIMS_LLM_MODEL`, `CLAIMS_LLM_TEMPERATURE`: LLM extractor configuration.

## API
`GET /api/v1/claims/extractors` (admin-only) returns:
- `extractors`: catalog entries.
- `default_mode`: current configured mode (`CLAIM_EXTRACTOR_MODE`).
- `auto_mode`: `"auto"` for UI convenience.

## Tests
- Unit tests for auto mode language detection and sentence splitting.
- API test for the extractor catalog endpoint.
