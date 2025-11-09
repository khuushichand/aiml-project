"""Local test config to stub missing legacy LLM adapter symbols that some routers import at module load.

This avoids ImportError when importing tldw_Server_API.app.main in environments where optional LLM
adapters are not present.
"""
from __future__ import annotations

try:
    from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _llm_local  # type: ignore
    if not hasattr(_llm_local, "legacy_chat_with_custom_openai_2"):
        def _stub(*args, **kwargs):  # pragma: no cover - simple stub
            return None
        setattr(_llm_local, "legacy_chat_with_custom_openai_2", _stub)
except Exception:
    # If the module path changes or is unavailable, ignore; tests that require it will be skipped upstream.
    pass
