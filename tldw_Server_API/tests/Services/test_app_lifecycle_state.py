from fastapi import FastAPI

from tldw_Server_API.app.services.app_lifecycle import (
    get_or_create_lifecycle_state,
    mark_lifecycle_shutdown,
    mark_lifecycle_startup,
    reset_lifecycle_state,
)


def test_get_or_create_lifecycle_state_is_app_scoped() -> None:
    app = FastAPI()
    state = get_or_create_lifecycle_state(app)
    assert state.phase == "starting"
    assert state.ready is False


def test_mark_lifecycle_startup_and_shutdown_update_app_state() -> None:
    app = FastAPI()
    state = get_or_create_lifecycle_state(app)
    mark_lifecycle_startup(app)
    assert state.phase == "ready"
    assert state.ready is True
    mark_lifecycle_shutdown(app)
    assert state.phase == "draining"
    assert state.ready is False


def test_get_or_create_lifecycle_state_isolated_per_app_instance() -> None:
    first_app = FastAPI()
    second_app = FastAPI()

    first_state = get_or_create_lifecycle_state(first_app)
    second_state = get_or_create_lifecycle_state(second_app)

    assert first_state is not second_state
    assert first_state.phase == "starting"
    assert second_state.phase == "starting"

    mark_lifecycle_startup(first_app)
    assert first_state.phase == "ready"
    assert second_state.phase == "starting"


def test_reset_lifecycle_state_restores_default_state_for_reuse() -> None:
    app = FastAPI()
    original_state = get_or_create_lifecycle_state(app)

    mark_lifecycle_startup(app)
    assert original_state.phase == "ready"
    assert original_state.ready is True

    reset_state = reset_lifecycle_state(app)

    assert reset_state is not original_state
    assert reset_state.phase == "starting"
    assert reset_state.ready is False
    assert reset_state.draining is False
    assert app.state._tldw_lifecycle_state is reset_state

    reused_state = get_or_create_lifecycle_state(app)
    assert reused_state is reset_state
