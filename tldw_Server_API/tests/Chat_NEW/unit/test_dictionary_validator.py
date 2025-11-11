from __future__ import annotations

from tldw_Server_API.app.core.Chat.validate_dictionary import validate_dictionary


def _mk(payload_entries):
    return {"name": "test", "entries": payload_entries}


def test_schema_invalid_missing_entries_warns():
    res = validate_dictionary({"name": "x"}, schema_version=1)
    assert any(w.get("code") == "schema_invalid" and w.get("field") == "entries" for w in res.warnings)


def test_regex_invalid_is_caught():
    payload = _mk([{"type": "regex", "pattern": "(unclosed", "replacement": "x"}])
    res = validate_dictionary(payload)
    assert any(e.get("code") == "regex_invalid" for e in res.errors)


def test_regex_unsafe_nested_quantifiers():
    payload = _mk([{"type": "regex", "pattern": "(a+)+$", "replacement": "x"}])
    res = validate_dictionary(payload)
    assert any(e.get("code") == "regex_unsafe" for e in res.errors)


def test_template_forbidden_construct():
    payload = _mk([{"type": "literal", "pattern": "hello", "replacement": "{% for x in y %}hi{% endfor %}"}])
    res = validate_dictionary(payload)
    assert any(e.get("code") == "template_forbidden_construct" for e in res.errors)


def test_template_unknown_function_weather_marked_external():
    payload = _mk([{"type": "literal", "pattern": "w", "replacement": "{{ weather('Boston') }}"}])
    res = validate_dictionary(payload)
    assert any(e.get("code") == "template_external_calls_disabled" for e in res.errors)


def test_probability_out_of_range():
    payload = _mk([{"type": "literal", "pattern": "x", "replacement": "y", "probability": 2.0}])
    res = validate_dictionary(payload)
    assert any(e.get("code") == "probability_out_of_range" for e in res.errors)


def test_duplicate_pattern_detected():
    payload = _mk([
        {"type": "literal", "pattern": "x", "replacement": "a"},
        {"type": "literal", "pattern": "x", "replacement": "b"},
    ])
    res = validate_dictionary(payload)
    assert any(e.get("code") == "duplicate_pattern" for e in res.errors)

