"""Local conftest for LLM_Adapters tests.

Provides a lightweight stub for tldw_Server_API.app.main to prevent importing
the full FastAPI app (which pulls heavy modules) during unit tests in this
subtree. Integration tests in this package should import their own TestClient
or rely on explicit fixtures within the file.
"""

import sys
import types

# If the real app.main is importable, leave it alone; otherwise, install a stub
try:  # pragma: no cover - defensive guard
    import tldw_Server_API.app.main as _real_main  # noqa: F401
except Exception:
    m = types.ModuleType("tldw_Server_API.app.main")
    # Provide a minimal 'app' attribute that parent conftests import but do not use
    class _StubApp:  # pragma: no cover - simple container
        pass

    m.app = _StubApp()
    sys.modules["tldw_Server_API.app.main"] = m

