from tldw_Server_API.app.core.Workflows.adapters import registry as adapter_registry
from tldw_Server_API.app.core.Workflows.registry import StepTypeRegistry


ENGINE_NATIVE_STEP_TYPES = {"wait_for_human", "wait_for_approval"}


def test_step_registry_entries_have_runtime_handlers():
    step_types = {step.name for step in StepTypeRegistry().list()}
    adapter_step_types = set(adapter_registry.list_adapters())

    uncovered = sorted(step_types - adapter_step_types)
    assert uncovered == sorted(ENGINE_NATIVE_STEP_TYPES)  # nosec B101
