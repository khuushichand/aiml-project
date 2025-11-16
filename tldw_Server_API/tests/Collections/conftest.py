import pytest


@pytest.fixture(scope="session", autouse=True)
def preserve_app_state():
    # Override chat_fixtures.preserve_app_state to avoid early app import
    yield


@pytest.fixture(autouse=True)
def reset_app_overrides():
    # Override chat_fixtures.reset_app_overrides for these tests
    yield

