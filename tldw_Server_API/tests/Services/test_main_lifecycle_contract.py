from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_startup_shutdown_contract_is_reentrant() -> None:
    from tldw_Server_API.app.main import app

    with TestClient(app) as first_client:
        first_response = first_client.get("/health")
        assert first_response.status_code == 200
        first_state = app.state._tldw_lifecycle_state
        assert first_state.phase == "ready"
        assert first_state.ready is True

    assert app.state._tldw_lifecycle_state is first_state
    assert app.state._tldw_lifecycle_state.phase == "draining"
    assert app.state._tldw_lifecycle_state.ready is False

    with TestClient(app) as second_client:
        second_response = second_client.get("/health")
        assert second_response.status_code == 200
        assert app.state._tldw_lifecycle_state is first_state
        assert app.state._tldw_lifecycle_state.phase == "ready"
        assert app.state._tldw_lifecycle_state.ready is True

    assert app.state._tldw_lifecycle_state is first_state
    assert app.state._tldw_lifecycle_state.phase == "draining"
    assert app.state._tldw_lifecycle_state.ready is False


@pytest.mark.asyncio
async def test_asgi_transport_without_lifespan_bypasses_shutdown_coordinator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app import main as main_module

    app = main_module.app

    for attr_name in (
        "_tldw_lifecycle_events",
        "_tldw_lifecycle_state",
        "_tldw_shutdown_legacy_coordinator_summary",
        "_tldw_shutdown_legacy_coordinator_component_names",
        "_tldw_shutdown_legacy_coordinator_phase_groups",
    ):
        if hasattr(app.state, attr_name):
            delattr(app.state, attr_name)

    startup_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    shutdown_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    original_mark_startup = main_module.mark_lifecycle_startup
    original_mark_shutdown = main_module.mark_lifecycle_shutdown

    def _record_mark_startup(*args, **kwargs):
        startup_calls.append((args, kwargs))
        return original_mark_startup(*args, **kwargs)

    def _record_mark_shutdown(*args, **kwargs):
        shutdown_calls.append((args, kwargs))
        return original_mark_shutdown(*args, **kwargs)

    monkeypatch.setattr(main_module, "mark_lifecycle_startup", _record_mark_startup)
    monkeypatch.setattr(main_module, "mark_lifecycle_shutdown", _record_mark_shutdown)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert startup_calls == []
    assert shutdown_calls == []
    assert not hasattr(app.state, "_tldw_shutdown_legacy_coordinator_summary")

    lifecycle_state = getattr(app.state, "_tldw_lifecycle_state", None)
    assert lifecycle_state is None or lifecycle_state.phase != "draining"
    assert lifecycle_state is None or lifecycle_state.draining is False


def test_build_legacy_shutdown_context_uses_explicit_fields() -> None:
    from tldw_Server_API.app.main import _build_legacy_shutdown_context
    from tldw_Server_API.app.services.shutdown_legacy_adapters import LegacyShutdownContext

    readiness_state = {"ready": True}
    usage_task = object()
    llm_usage_task = object()
    chatbooks_cleanup_task = object()
    chatbooks_cleanup_stop_event = object()
    storage_cleanup_service = object()

    context = _build_legacy_shutdown_context(
        readiness_state=readiness_state,
        usage_task=usage_task,
        llm_usage_task=llm_usage_task,
        authnz_scheduler_started=True,
        chatbooks_cleanup_task=chatbooks_cleanup_task,
        chatbooks_cleanup_stop_event=chatbooks_cleanup_stop_event,
        storage_cleanup_service=storage_cleanup_service,
    )

    assert isinstance(context, LegacyShutdownContext)
    assert context.readiness_state is readiness_state
    assert context.usage_task is usage_task
    assert context.llm_usage_task is llm_usage_task
    assert context.authnz_scheduler_started is True
    assert context.chatbooks_cleanup_task is chatbooks_cleanup_task
    assert context.chatbooks_cleanup_stop_event is chatbooks_cleanup_stop_event
    assert context.storage_cleanup_service is storage_cleanup_service


def test_apply_shutdown_transition_gate_logs_guard_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    from fastapi import FastAPI

    from tldw_Server_API.app import main as main_module

    app = FastAPI()
    debug_messages: list[str] = []
    warning_messages: list[str] = []

    def _raise_lifecycle_state(_app):
        raise RuntimeError("lookup failed")

    def _raise_mark_shutdown(_app, _readiness_state):
        raise RuntimeError("mark failed")

    class _FailingJobManager:
        @classmethod
        def set_acquire_gate(cls, _enabled: bool) -> None:
            raise RuntimeError("gate failed")

    fake_jobs_manager = types.ModuleType("tldw_Server_API.app.core.Jobs.manager")
    fake_jobs_manager.JobManager = _FailingJobManager

    monkeypatch.setattr(main_module, "get_or_create_lifecycle_state", _raise_lifecycle_state)
    monkeypatch.setattr(main_module, "mark_lifecycle_shutdown", _raise_mark_shutdown)
    monkeypatch.setattr(main_module.logger, "debug", lambda message, *args, **kwargs: debug_messages.append(str(message)))
    monkeypatch.setattr(
        main_module.logger,
        "warning",
        lambda message, *args, **kwargs: warning_messages.append(str(message)),
    )
    monkeypatch.setitem(sys.modules, fake_jobs_manager.__name__, fake_jobs_manager)

    main_module._apply_shutdown_transition_gate(app, {})

    assert any("lifecycle state lookup skipped" in message for message in debug_messages)
    assert any("failed to mark lifecycle shutdown" in message for message in warning_messages)
    assert any("job acquire gate unavailable" in message for message in debug_messages)


@pytest.mark.integration
def test_lifecycle_hooks_called_in_order() -> None:
    from tldw_Server_API.app.main import app

    if hasattr(app.state, "_tldw_lifecycle_events"):
        delattr(app.state, "_tldw_lifecycle_events")
    if hasattr(app.state, "_tldw_lifecycle_state"):
        delattr(app.state, "_tldw_lifecycle_state")

    with TestClient(app):
        assert getattr(app.state, "_tldw_lifecycle_events", [])[-1:] == ["startup"]
        assert app.state._tldw_lifecycle_state.phase == "ready"
        assert app.state._tldw_lifecycle_state.ready is True

    assert getattr(app.state, "_tldw_lifecycle_events", [])[-2:] == ["startup", "shutdown"]
    assert app.state._tldw_lifecycle_state.phase == "draining"
    assert app.state._tldw_lifecycle_state.ready is False


@pytest.mark.integration
def test_shutdown_falls_back_to_direct_drain_when_transition_gate_component_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.core.Jobs.manager import JobManager
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.services import shutdown_legacy_adapters
    from tldw_Server_API.app.services.shutdown_models import (
        ShutdownComponent,
        ShutdownPhase,
        ShutdownPolicy,
    )

    if hasattr(app.state, "_tldw_lifecycle_events"):
        delattr(app.state, "_tldw_lifecycle_events")
    if hasattr(app.state, "_tldw_lifecycle_state"):
        delattr(app.state, "_tldw_lifecycle_state")

    gate_calls: list[bool] = []

    def _record_gate(cls, enabled: bool) -> None:
        gate_calls.append(enabled)

    monkeypatch.setattr(
        JobManager,
        "set_acquire_gate",
        classmethod(_record_gate),
    )
    def _failing_transition_stop() -> None:
        raise RuntimeError("shadow transition component failed")

    monkeypatch.setattr(
        shutdown_legacy_adapters,
        "build_legacy_shutdown_plan",
        lambda *_args, **_kwargs: [
            ShutdownComponent(
                name="lifecycle_gate",
                phase=ShutdownPhase.TRANSITION,
                policy=ShutdownPolicy.DEV_FAST,
                default_timeout_ms=1000,
                stop=_failing_transition_stop,
            )
        ],
    )

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert app.state._tldw_lifecycle_state.phase == "ready"
        assert app.state._tldw_lifecycle_state.ready is True
        gate_calls.clear()

    assert gate_calls == [True, False]
    assert app.state._tldw_lifecycle_state.phase == "draining"
    assert app.state._tldw_lifecycle_state.ready is False
    assert app.state._tldw_lifecycle_state.draining is True


@pytest.mark.integration
def test_shutdown_migrated_legacy_slice_uses_prod_drain_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    from tldw_Server_API.app.services import shutdown_coordinator as shutdown_coordinator_module
    from tldw_Server_API.app.services import shutdown_legacy_adapters
    from tldw_Server_API.app.services.shutdown_models import (
        ShutdownComponent,
        ShutdownComponentSummary,
        ShutdownPhase,
        ShutdownPhaseSummary,
        ShutdownPolicy,
        ShutdownSummary,
    )

    class _SpyShutdownCoordinator:
        created_profiles: list[str] = []
        instances: list["_SpyShutdownCoordinator"] = []

        def __init__(self, profile: str = "dev_fast", **_kwargs) -> None:
            self.profile = profile
            self.registered: list[ShutdownComponent] = []
            type(self).created_profiles.append(profile)
            type(self).instances.append(self)

        def register(self, component: ShutdownComponent) -> ShutdownComponent:
            self.registered.append(component)
            return component

        async def shutdown(self) -> ShutdownSummary:
            phase_names: dict[ShutdownPhase, list[str]] = {}
            component_summaries: dict[str, ShutdownComponentSummary] = {}

            for component in self.registered:
                phase_names.setdefault(component.phase, []).append(component.name)
                component_summaries[component.name] = ShutdownComponentSummary(
                    name=component.name,
                    phase=component.phase,
                    policy=component.policy,
                    result="stopped",
                    started_at=0.0,
                    finished_at=0.0,
                    duration_ms=0,
                    timeout_ms=0,
                )

            phase_summaries = {
                phase: ShutdownPhaseSummary(
                    phase=phase,
                    started_at=0.0,
                    finished_at=0.0,
                    duration_ms=0,
                    budget_ms=0,
                    component_names=component_names,
                )
                for phase, component_names in phase_names.items()
            }
            return ShutdownSummary(
                profile=self.profile,
                started_at=0.0,
                finished_at=0.0,
                deadline_at=0.0,
                hard_cutoff_at=0.0,
                wall_time_ms=0,
                soft_overrun_used_ms=0,
                components=component_summaries,
                phases=phase_summaries,
            )

    captured_contexts: list[object] = []

    def _fake_build_legacy_shutdown_plan(_app, _context):
        if _context is not None:
            captured_contexts.append(_context)
        return [
            ShutdownComponent(
                name="lifecycle_gate",
                phase=ShutdownPhase.TRANSITION,
                policy=ShutdownPolicy.DEV_FAST,
                default_timeout_ms=1000,
                stop=lambda: None,
            ),
            ShutdownComponent(
                name="chatbooks_cleanup",
                phase=ShutdownPhase.WORKERS,
                policy=ShutdownPolicy.BEST_EFFORT,
                default_timeout_ms=1000,
                stop=lambda: None,
            ),
            ShutdownComponent(
                name="usage_aggregator",
                phase=ShutdownPhase.RESOURCES,
                policy=ShutdownPolicy.BEST_EFFORT,
                default_timeout_ms=1000,
                stop=lambda: None,
            ),
            ShutdownComponent(
                name="storage_cleanup_service",
                phase=ShutdownPhase.FINALIZERS,
                policy=ShutdownPolicy.PROD_DRAIN,
                default_timeout_ms=5000,
                stop=lambda: None,
            ),
        ]

    fake_shutdown_legacy_adapters = types.ModuleType(
        "tldw_Server_API.app.services.shutdown_legacy_adapters"
    )
    fake_shutdown_legacy_adapters.LegacyShutdownContext = shutdown_legacy_adapters.LegacyShutdownContext
    fake_shutdown_legacy_adapters.build_legacy_shutdown_plan = _fake_build_legacy_shutdown_plan
    fake_shutdown_legacy_adapters.register_legacy_shutdown_components = (
        shutdown_legacy_adapters.register_legacy_shutdown_components
    )
    fake_shutdown_legacy_adapters.get_legacy_shutdown_suppressed_component_names = (
        shutdown_legacy_adapters.get_legacy_shutdown_suppressed_component_names
    )
    monkeypatch.setitem(sys.modules, fake_shutdown_legacy_adapters.__name__, fake_shutdown_legacy_adapters)

    monkeypatch.setattr(shutdown_coordinator_module, "ShutdownCoordinator", _SpyShutdownCoordinator)

    from tldw_Server_API.app.main import app

    if hasattr(app.state, "_tldw_lifecycle_events"):
        delattr(app.state, "_tldw_lifecycle_events")
    if hasattr(app.state, "_tldw_lifecycle_state"):
        delattr(app.state, "_tldw_lifecycle_state")

    expected_migrated_names = [
        component.name
        for component in _fake_build_legacy_shutdown_plan(None, None)
        if component.name != "lifecycle_gate"
    ]

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    assert _SpyShutdownCoordinator.created_profiles == ["dev_fast", "prod_drain"]
    assert len(captured_contexts) == 1
    assert getattr(captured_contexts[0], "readiness_state", None) is not None
    assert hasattr(captured_contexts[0], "usage_task")
    assert hasattr(captured_contexts[0], "llm_usage_task")
    assert hasattr(captured_contexts[0], "authnz_scheduler_started")
    assert [component.name for component in _SpyShutdownCoordinator.instances[0].registered] == [
        "lifecycle_gate",
    ]
    expected_transport_names = getattr(app.state, "_tldw_shutdown_transport_component_names", [])
    migrated_registered_names = [
        component.name for component in _SpyShutdownCoordinator.instances[1].registered
    ]
    assert migrated_registered_names == expected_migrated_names + expected_transport_names
    assert "lifecycle_gate" not in migrated_registered_names


@pytest.mark.integration
def test_shutdown_skipped_best_effort_component_falls_back_to_direct_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    from tldw_Server_API.app.services import shutdown_coordinator as shutdown_coordinator_module
    from tldw_Server_API.app.services import shutdown_legacy_adapters
    from tldw_Server_API.app.services.shutdown_models import (
        ShutdownComponent,
        ShutdownComponentSummary,
        ShutdownPhase,
        ShutdownPhaseSummary,
        ShutdownPolicy,
        ShutdownSummary,
    )

    class _DummyUsageTask:
        def __init__(self) -> None:
            self.cancel_calls = 0
            self.stop_calls = 0
            self._stopped = False

        def cancel(self) -> None:
            self.cancel_calls += 1

    usage_task_holder: dict[str, _DummyUsageTask] = {}

    async def _fake_start_usage_aggregator() -> _DummyUsageTask:
        task = _DummyUsageTask()
        usage_task_holder["task"] = task
        return task

    async def _fake_stop_usage_aggregator(task: _DummyUsageTask | None) -> None:
        if task is None:
            return
        if not task._stopped:
            task._stopped = True
            task.stop_calls += 1
        task.cancel()

    class _SpyShutdownCoordinator:
        def __init__(self, profile: str = "dev_fast", **_kwargs) -> None:
            self.profile = profile
            self.registered: list[ShutdownComponent] = []

        def register(self, component: ShutdownComponent) -> ShutdownComponent:
            self.registered.append(component)
            return component

        async def shutdown(self) -> ShutdownSummary:
            phase_names: dict[ShutdownPhase, list[str]] = {}
            component_summaries: dict[str, ShutdownComponentSummary] = {}

            for component in self.registered:
                phase_names.setdefault(component.phase, []).append(component.name)
                result = "skipped" if component.name == "usage_aggregator" else "stopped"
                component_summaries[component.name] = ShutdownComponentSummary(
                    name=component.name,
                    phase=component.phase,
                    policy=component.policy,
                    result=result,
                    started_at=0.0,
                    finished_at=0.0,
                    duration_ms=0,
                    timeout_ms=0,
                )

            phase_summaries = {
                phase: ShutdownPhaseSummary(
                    phase=phase,
                    started_at=0.0,
                    finished_at=0.0,
                    duration_ms=0,
                    budget_ms=0,
                    component_names=component_names,
                )
                for phase, component_names in phase_names.items()
            }
            return ShutdownSummary(
                profile=self.profile,
                started_at=0.0,
                finished_at=0.0,
                deadline_at=0.0,
                hard_cutoff_at=0.0,
                wall_time_ms=0,
                soft_overrun_used_ms=0,
                components=component_summaries,
                phases=phase_summaries,
            )

    def _fake_build_legacy_shutdown_plan(_app, _context):
        return [
            ShutdownComponent(
                name="lifecycle_gate",
                phase=ShutdownPhase.TRANSITION,
                policy=ShutdownPolicy.DEV_FAST,
                default_timeout_ms=1000,
                stop=lambda: None,
            ),
            ShutdownComponent(
                name="usage_aggregator",
                phase=ShutdownPhase.RESOURCES,
                policy=ShutdownPolicy.BEST_EFFORT,
                default_timeout_ms=1000,
                stop=lambda: None,
            ),
        ]

    fake_shutdown_legacy_adapters = types.ModuleType(
        "tldw_Server_API.app.services.shutdown_legacy_adapters"
    )
    fake_shutdown_legacy_adapters.LegacyShutdownContext = shutdown_legacy_adapters.LegacyShutdownContext
    fake_shutdown_legacy_adapters.build_legacy_shutdown_plan = _fake_build_legacy_shutdown_plan
    fake_shutdown_legacy_adapters.register_legacy_shutdown_components = (
        shutdown_legacy_adapters.register_legacy_shutdown_components
    )
    fake_shutdown_legacy_adapters.get_legacy_shutdown_suppressed_component_names = (
        shutdown_legacy_adapters.get_legacy_shutdown_suppressed_component_names
    )
    monkeypatch.setitem(sys.modules, fake_shutdown_legacy_adapters.__name__, fake_shutdown_legacy_adapters)

    fake_usage_aggregator = types.ModuleType("tldw_Server_API.app.services.usage_aggregator")
    fake_usage_aggregator.start_usage_aggregator = _fake_start_usage_aggregator
    fake_usage_aggregator.stop_usage_aggregator = _fake_stop_usage_aggregator
    monkeypatch.setitem(sys.modules, fake_usage_aggregator.__name__, fake_usage_aggregator)

    monkeypatch.setenv("DISABLE_LLM_USAGE_AGGREGATOR", "1")
    monkeypatch.setattr(shutdown_coordinator_module, "ShutdownCoordinator", _SpyShutdownCoordinator)

    from tldw_Server_API.app.main import app

    for attr_name in (
        "_tldw_lifecycle_events",
        "_tldw_lifecycle_state",
        "_tldw_shutdown_legacy_coordinator_summary",
        "_tldw_shutdown_legacy_coordinator_component_names",
        "_tldw_shutdown_legacy_coordinator_phase_groups",
    ):
        if hasattr(app.state, attr_name):
            delattr(app.state, attr_name)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    usage_task = usage_task_holder["task"]
    assert usage_task.stop_calls == 1
    assert usage_task.cancel_calls >= 1
    assert app.state._tldw_shutdown_legacy_coordinator_summary.components["usage_aggregator"].result == "skipped"


@pytest.mark.integration
def test_lifespan_exposes_openapi_after_startup(client_user_only) -> None:
    response = client_user_only.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert "paths" in payload
