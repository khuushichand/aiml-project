# Prompt Management Missing Features (API)

## Goals
- Add prompt version history and restore endpoints for `/api/v1/prompts`.
- Add JSON import endpoints for prompts.
- Add template variable extraction and render endpoints.
- Add bulk delete and bulk keyword update endpoints.
- Add sorting parameters to the list endpoint.

## Non-goals
- Prompt Studio project/version workflows.
- Full diff/merge tooling or keyword version snapshots.

## Data Source for Versions
- Use `sync_log` rows where `entity = 'Prompts'` and `operation IN ('create','update')`.
- Build version snapshots from `payload`; fall back to numeric version list when payloads are missing.

## Proposed Endpoints
- `GET /api/v1/prompts/{prompt_identifier}/versions`
  - Response: list of version entries with `version`, `timestamp`, and prompt fields.
- `POST /api/v1/prompts/{prompt_identifier}/versions/{version}/restore`
  - Restores content by applying the snapshot via `update_prompt_by_id` (creates a new version).
- `POST /api/v1/prompts/import`
  - Request: `{"prompts":[{name, content/details, author, system_prompt, user_prompt, keywords}], "skip_duplicates": bool}`
  - Behavior: rename duplicates as `duplicate N - <name>` unless `skip_duplicates` is true.
  - Response: `{"imported": int, "failed": int, "skipped": int, "prompt_ids": [int]}`
- `POST /api/v1/prompts/templates/variables`
  - Request: `{"template": "..."}`
  - Response: `{"variables": ["var1", "var2"]}`
- `POST /api/v1/prompts/templates/render`
  - Request: `{"template": "...", "variables": {...}}`
  - Response: `{"rendered": "..."}`
- `POST /api/v1/prompts/bulk/delete`
  - Request: `{"prompt_ids":[1,2]}`
  - Response: `{"deleted": int, "failed": int, "failed_ids":[...]}`
- `POST /api/v1/prompts/bulk/keywords`
  - Request: `{"prompt_ids":[1,2], "add_keywords":[...], "remove_keywords":[...]}`
  - Response: `{"updated": int, "failed": int, "failed_ids":[...]}`
- `GET /api/v1/prompts?sort_by=...&sort_order=...`
  - Allowed `sort_by`: `last_modified`, `name`, `author`, `id`
  - Allowed `sort_order`: `asc`, `desc`

## DB Updates
- `list_prompts` accepts `sort_by`/`sort_order` and validates columns.
- Add prompt-version helpers that read `sync_log` and provide snapshots.
- Add restore helper that applies a snapshot via `update_prompt_by_id`.

## Error Handling
- `404` for missing prompts or versions.
- `400` for invalid sort params, invalid templates, or missing template variables.

## Tests
- Update `tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompts_api.py` to cover all new endpoints.
