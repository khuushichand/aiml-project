# 2026-03-02 Runtime Compatibility Inventory

This inventory captures runtime compatibility paths that are still active and now require explicit sunset metadata.

| Registry Key | Source File | Legacy Behavior | Sunset Target |
| --- | --- | --- | --- |
| `web_scraping_legacy_fallback` | `tldw_Server_API/app/services/web_scraping_service.py` | Falls back to legacy scraping implementation when enhanced service is unavailable. | `2026-06-30` |
| `llm_chat_legacy_session` | `tldw_Server_API/app/core/LLM_Calls/chat_calls.py` | Preserves legacy request session behavior for streaming and selected compatibility paths. | `2026-07-15` |
| `auth_db_execute_compat` | `tldw_Server_API/app/services/auth_service.py` | Adapts SQL parameter style and call shape for sqlite-like DB interfaces. | `2026-08-01` |

## Migration Rule

Any runtime compatibility path must be registered in the runtime deprecation registry with:

- A stable registry key.
- A documented sunset date.
- A named successor path.
