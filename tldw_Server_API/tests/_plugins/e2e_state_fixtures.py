"""Pytest plugin: e2e state and reporting fixtures

Provides shared state containers and lightweight reporting hooks used by e2e
tests. This keeps suite conftest minimal and free of heavy logic.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, Generator
import pytest


# Session-scoped fixture to store test results
@pytest.fixture(scope="session")
def test_results(request):
    """Store test results across the session for reporting.

    Also attach the dict to session config so session-level hooks
    (pytest_sessionfinish) can read it for summary output.
    """
    results = {
        "passed": [],
        "failed": [],
        "skipped": [],
        "errors": [],
    }
    # Wire into the session config for access in pytest_sessionfinish
    try:
        request.session.config._test_results = results  # type: ignore[attr-defined]
    except Exception:
        # Some older pytest configurations expose a global config; ignore if unavailable
        try:  # pragma: no cover - defensive
            import pytest as _pytest
            _pytest.config._test_results = results  # type: ignore[attr-defined]
        except Exception:
            pass
    return results


# Session-scoped fixture for shared media state
@pytest.fixture(scope="session")
def shared_media_state():
    """Session-wide shared state for uploaded media and related artifacts."""
    return {
        "uploaded_media": {},  # media_id -> media_data mapping
        "generated_embeddings": set(),  # Set of media_ids with embeddings
        "test_users": {},  # user_id -> user_data mapping
        "api_clients": {},  # client_id -> api_client mapping
    }


# Class-scoped fixture for test workflow state
@pytest.fixture(scope="class")
def test_workflow_state(shared_media_state):
    """
    Class-scoped fixture providing helpers to manage per-class workflow state
    while referencing session-shared resources.
    """

    class WorkflowState:
        def __init__(self):
            self.media_items = []  # Local to this test class
            self.current_user = None
            self.api_client = None
            self._shared = shared_media_state  # Reference to session state

        def add_media(self, media_id: int, media_data: Dict[str, Any]):
            self.media_items.append(media_data)
            self._shared["uploaded_media"][media_id] = media_data

        def get_any_media(self) -> Optional[Dict[str, Any]]:
            if self.media_items:
                return self.media_items[0]
            elif self._shared["uploaded_media"]:
                return next(iter(self._shared["uploaded_media"].values()))
            return None

        def get_media_by_id(self, media_id: int) -> Optional[Dict[str, Any]]:
            return self._shared["uploaded_media"].get(media_id)

        def mark_embeddings_generated(self, media_id: int):
            self._shared["generated_embeddings"].add(media_id)

        def has_embeddings(self, media_id: int) -> bool:
            return media_id in self._shared["generated_embeddings"]

        def get_or_create_user(self, user_id: str, user_data: Dict[str, Any] | None = None):
            if user_id not in self._shared["test_users"]:
                self._shared["test_users"][user_id] = user_data or {}
            return self._shared["test_users"][user_id]

        def set_api_client(self, client_id: str, api_client):
            self._shared["api_clients"][client_id] = api_client
            self.api_client = api_client

        def get_api_client(self, client_id: str = "default"):
            return self._shared["api_clients"].get(client_id, self.api_client)

    return WorkflowState()


# Function-scoped fixture for ensuring media has embeddings
@pytest.fixture
def ensure_embeddings(test_workflow_state):
    """
    Fixture that returns a function to ensure embeddings exist for media.
    Usage in tests:
        await ensure_embeddings(api_client, media_id)
    """

    async def _ensure_embeddings(api_client, media_id: int) -> bool:
        if test_workflow_state.has_embeddings(media_id):
            return True
        try:
            response = api_client.client.post(
                f"{api_client.base_url}/api/v1/media/{media_id}/embeddings",
                json={"force_regenerate": False},
                headers=api_client.get_auth_headers(),
            )
            if response.status_code == 200:
                test_workflow_state.mark_embeddings_generated(media_id)
                return True
            else:
                print(f"Failed to generate embeddings: {response.text}")
                return False
        except Exception as e:
            # Broad except is intentional: this fixture runs in diverse environments
            # (live server, in-process app, varied auth modes). We prefer tests to
            # continue and record the failure rather than crash the entire session.
            print(f"Error generating embeddings: {e}")
            return False

    return _ensure_embeddings


# Lightweight reporting hooks (no heavy work at import-time)
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    del call  # explicitly unused in this wrapper; report pulled from outcome
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        if hasattr(item, "funcargs") and "test_results" in item.funcargs:
            results = item.funcargs["test_results"]
            test_info = {
                "name": item.name,
                "nodeid": item.nodeid,
                "duration": report.duration,
                "markers": [m.name for m in item.iter_markers()],
            }
            if report.passed:
                results["passed"].append(test_info)
            elif report.failed:
                test_info["error"] = str(report.longrepr)
                results["failed"].append(test_info)
            elif report.skipped:
                test_info["reason"] = str(report.longrepr)
                results["skipped"].append(test_info)


def pytest_sessionfinish(session, exitstatus):
    del exitstatus  # not used; present to match pytest hook signature
    # Only generate report if tests were run and results captured
    if hasattr(session.config, "_test_results"):
        results = session.config._test_results
        print("\n" + "=" * 70)
        print("E2E TEST SUMMARY - Real User Simulation")
        print("=" * 70)
        print(f"✅ Passed: {len(results['passed'])}")
        print(f"❌ Failed: {len(results['failed'])}")
        print(f"⏭️  Skipped: {len(results['skipped'])}")
        if results["failed"]:
            print("\n⚠️  Failed Tests:")
            for test in results["failed"]:
                print(f"  - {test['name']}")
        print("=" * 70)


__all__ = [
    "test_results",
    "shared_media_state",
    "test_workflow_state",
    "ensure_embeddings",
]
