import pytest


pytestmark = pytest.mark.unit


def test_research_package_adapter_registers_and_exports_markdown():
    from tldw_Server_API.app.core.File_Artifacts.adapter_registry import FileAdapterRegistry

    registry = FileAdapterRegistry()
    adapter = registry.get_adapter("research_package")
    assert adapter is not None
    export = adapter.export(
        {
            "question": "What changed?",
            "report_markdown": "# Report\nAnswer",
            "claims": [{"text": "Claim", "citations": [{"source_id": "src_1"}]}],
            "source_inventory": [{"source_id": "src_1", "title": "Source 1"}],
        },
        format="md",
    )
    assert export.status == "ready"
    assert export.content.startswith(b"# Report")
