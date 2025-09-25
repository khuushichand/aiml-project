import pytest
from hypothesis import given, strategies as st


@given(st.integers(min_value=1, max_value=999999999))
def test_pmcid_property_strips_prefix_and_keeps_digits(n):
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    pmcid_str = f"PMC{n}"
    sm = normalize_safe_metadata({"pmcid": pmcid_str})
    assert sm.get("pmcid") == str(n)


@given(st.integers(min_value=1, max_value=999999999))
def test_pmid_property_digits_only(n):
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    noisy = f"PMID: {n}"
    sm = normalize_safe_metadata({"PMID": noisy})
    assert sm.get("pmid") == str(n)


_DOI_ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._;()/:"

@given(
    st.integers(min_value=1000, max_value=999999).map(lambda p: f"10.{p}"),
    st.text(alphabet=st.sampled_from(list(_DOI_ALLOWED)), min_size=1, max_size=20),
)
def test_doi_property_accepts_simple_valids(prefix, suffix):
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    doi = f"{prefix}/{suffix}"
    sm = normalize_safe_metadata({"doi": doi})
    assert sm.get("doi") == doi


@given(st.text(min_size=1, max_size=20).filter(lambda s: not s.startswith("10.")))
def test_doi_property_rejects_non_doi(s):
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    with pytest.raises(ValueError):
        normalize_safe_metadata({"doi": s})


# -------- arXiv ID property tests --------

def _arxiv_new_style_ids():
    ver = st.integers(min_value=1, max_value=9).map(lambda v: f"v{v}") | st.just("")
    return st.builds(
        lambda a, b, c: f"{a:04d}.{b:04d}{c}",
        st.integers(min_value=1000, max_value=9999),
        st.integers(min_value=0, max_value=99999),
        ver,
    )


def _arxiv_old_style_ids():
    cats = st.text(alphabet=st.sampled_from(list("abcdefghijklmnopqrstuvwxyz-")), min_size=1, max_size=10)
    nums = st.integers(min_value=0, max_value=9999999).map(lambda n: f"{n:07d}")
    return st.builds(lambda c, n: f"{c}/{n}", cats, nums)


@given((_arxiv_new_style_ids() | _arxiv_old_style_ids()))
def test_arxiv_normalization_removes_spaces_only(arxid):
    from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata

    spaced = f"  {arxid}  ".replace("", "")
    sm = normalize_safe_metadata({"arxiv_id": spaced})
    assert sm.get("arxiv_id") == spaced.replace(" ", "")
