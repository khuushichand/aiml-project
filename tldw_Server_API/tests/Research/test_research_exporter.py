import pytest


pytestmark = pytest.mark.unit


def test_build_final_package_requires_citations():
    from tldw_Server_API.app.core.Research.exporter import build_final_package

    package = build_final_package(
        brief={"query": "Test"},
        outline={"sections": ["Overview"]},
        report_markdown="# Overview\nBody",
        claims=[{"text": "Claim", "citations": [{"source_id": "src_1"}]}],
        source_inventory=[{"source_id": "src_1", "title": "Source 1"}],
    )
    assert package["claims"][0]["citations"][0]["source_id"] == "src_1"
    assert package["report_markdown"].startswith("# Overview")


def test_build_final_package_rejects_uncited_claim():
    from tldw_Server_API.app.core.Research.exporter import build_final_package

    with pytest.raises(ValueError, match="claim_missing_citations"):
        build_final_package(
            brief={"query": "Test"},
            outline={"sections": ["Overview"]},
            report_markdown="# Overview\nBody",
            claims=[{"text": "Claim", "citations": []}],
            source_inventory=[{"source_id": "src_1", "title": "Source 1"}],
        )
