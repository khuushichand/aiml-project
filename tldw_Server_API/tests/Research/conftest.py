"""Shared fixtures for Research endpoint tests."""

from fastapi import FastAPI
import pytest

from tldw_Server_API.app.api.v1.endpoints.paper_search import router as paper_search_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    get_request_user,
    get_single_user_instance,
)


@pytest.fixture
def paper_search_app() -> FastAPI:
    """Provide a lightweight FastAPI app with only the paper-search routes registered."""
    app = FastAPI()
    app.include_router(paper_search_router, prefix="/api/v1/paper-search")
    app.dependency_overrides[get_request_user] = get_single_user_instance

    try:
        yield app
    finally:
        app.dependency_overrides.clear()
