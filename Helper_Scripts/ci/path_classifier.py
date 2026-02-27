from __future__ import annotations

from fnmatch import fnmatch
from typing import Iterable


BACKEND_GLOBS = [
    "tldw_Server_API/**",
    "pyproject.toml",
    "uv.lock",
    ".github/actions/**",
    ".github/workflows/**",
]

COVERAGE_GLOBS = [
    "tldw_Server_API/**",
    "pyproject.toml",
    "uv.lock",
]

FRONTEND_GLOBS = [
    "apps/tldw-frontend/**",
    "apps/packages/ui/**",
    "apps/extension/**",
    "apps/bun.lock",
    "apps/tldw-frontend/package-lock.json",
]

E2E_BACKEND_GLOBS = [
    "tldw_Server_API/app/api/v1/endpoints/**",
    "tldw_Server_API/app/api/v1/schemas/**",
    "tldw_Server_API/app/core/AuthNZ/**",
]


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def classify_paths(paths: Iterable[str]) -> dict[str, bool]:
    normalized_paths = list(paths)
    backend_changed = any(_matches_any(path, BACKEND_GLOBS) for path in normalized_paths)
    coverage_required = any(_matches_any(path, COVERAGE_GLOBS) for path in normalized_paths)
    frontend_changed = any(_matches_any(path, FRONTEND_GLOBS) for path in normalized_paths)
    e2e_changed = frontend_changed or any(_matches_any(path, E2E_BACKEND_GLOBS) for path in normalized_paths)
    security_relevant_changed = backend_changed or any(
        path.endswith(("requirements.txt", "pyproject.toml", "uv.lock")) for path in normalized_paths
    )

    return {
        "backend_changed": backend_changed,
        "frontend_changed": frontend_changed,
        "e2e_changed": e2e_changed,
        "security_relevant_changed": security_relevant_changed,
        "coverage_required": coverage_required,
    }
