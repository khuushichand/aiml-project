import pytest
from tldw_Server_API.app.core.Chunking.regex_safety import check_pattern as rx_check, compile_flags as rx_flags, warn_ambiguity as rx_warn
from tldw_Server_API.app.core.Chunking.templates import TemplateClassifier


pytestmark = pytest.mark.unit


def test_regex_safety_detects_nested_quantifiers():
    assert rx_check(r"(a+)+b") is not None
    assert rx_check(r"((a*)*)*b") is not None


def test_regex_safety_allows_simple_and_flags():
    assert rx_check(r"^Chapter \d+$") is None
    flags, err = rx_flags("im")
    assert err is None
    assert flags != 0


def test_regex_ambiguity_warning_unanchored_wildcard():
    warn = rx_warn(r"Chapter .*\d+")
    assert isinstance(warn, str) and "overmatch" in warn.lower()


def test_template_classifier_ignores_unsafe_patterns():
    cfg = {
        "classifier": {
            "filename_regex": r"(a+)+b",  # unsafe
            "title_regex": r"^ok$",
            "min_score": 0.0,
        }
    }
    # Unsafe filename_regex should be ignored; safe title_regex can match
    score = TemplateClassifier.score(cfg, media_type=None, title="ok", url=None, filename="aaaaab")
    assert score > 0.0

