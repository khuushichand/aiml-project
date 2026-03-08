import pytest


pytestmark = pytest.mark.unit


def test_build_final_package_requires_citations():
    from tldw_Server_API.app.core.Research.exporter import build_final_package

    package = build_final_package(
        brief={"query": "Test"},
        outline={"sections": ["Overview"]},
        report_markdown="# Overview\nBody",
        claims=[{"text": "Claim", "citations": [{"source_id": "src_1"}], "support_level": "strong"}],
        source_inventory=[{"source_id": "src_1", "title": "Source 1"}],
        verification_summary={"supported_claim_count": 1, "unsupported_claim_count": 0},
        contradictions=[],
        unsupported_claims=[],
        source_trust=[{"source_id": "src_1", "snapshot_policy": "full_artifact"}],
    )
    assert package["claims"][0]["citations"][0]["source_id"] == "src_1"
    assert package["report_markdown"].startswith("# Overview")
    assert package["verification_summary"]["supported_claim_count"] == 1
    assert package["source_trust"][0]["snapshot_policy"] == "full_artifact"


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
