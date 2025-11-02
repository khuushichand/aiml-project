import pytest


def test_normalize_safe_metadata_doi_valid():
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    sm = normalize_safe_metadata({"DOI": "10.1000/xyz.ABC-123"})
    assert sm.get("doi") == "10.1000/xyz.ABC-123"


def test_normalize_safe_metadata_doi_invalid_raises():
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    with pytest.raises(ValueError):
        normalize_safe_metadata({"doi": "not-a-doi"})


def test_normalize_safe_metadata_pmcid_normalizes():
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    sm = normalize_safe_metadata({"PMCID": "PMC123456"})
    assert sm.get("pmcid") == "123456"


def test_normalize_safe_metadata_pmid_digits():
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    sm = normalize_safe_metadata({"pmid": "PMID 987654"})
    assert sm.get("pmid") == "987654"


def test_normalize_safe_metadata_arxiv_pass_through():
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    sm = normalize_safe_metadata({"arXiv": "1706.03762v2"})
    assert sm.get("arxiv_id") == "1706.03762v2"
