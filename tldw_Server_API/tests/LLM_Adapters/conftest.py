"""Local conftest for LLM_Adapters tests.

Provides:
- Lightweight stub for app.main when real app import fails (unit-only cases)
- Access to shared chat fixtures (client, authenticated_client, auth headers)
- Backward-compat fixture alias client_user_only used by some tests
"""

import sys
import types
import pytest

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

# Shared chat fixtures are registered at the repository root conftest.py


@pytest.fixture
def client_user_only(authenticated_client):  # noqa: D401 - simple alias
    """Compatibility alias used by some adapter tests."""
    return authenticated_client
