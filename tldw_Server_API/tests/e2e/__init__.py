"""E2E tests package marker.

This also provides a lightweight import alias so that tests written as
`from fixtures import ...` continue to work when running the full suite
from the repository root (where `fixtures` is not a top-level module).
"""

try:
    # Expose e2e.fixtures as a top-level module alias for test imports
    from . import fixtures as _e2e_fixtures  # type: ignore
    import sys as _sys

    if "fixtures" not in _sys.modules:
        _sys.modules["fixtures"] = _e2e_fixtures  # type: ignore
    # Also alias other common helper modules used with absolute imports
    try:
        from . import test_data as _e2e_test_data  # type: ignore
        _sys.modules.setdefault("test_data", _e2e_test_data)  # type: ignore
    except Exception:
        pass
    try:
        from . import workflow_helpers as _e2e_workflow_helpers  # type: ignore
        _sys.modules.setdefault("workflow_helpers", _e2e_workflow_helpers)  # type: ignore
    except Exception:
        pass
except Exception:
    # Never break test discovery on aliasing issues
    pass
