import pytest

from tldw_Server_API.app.core.Watchlists.template_composer_roundtrip import (
    compile_composer_ast_to_jinja,
    parse_jinja_to_composer_ast,
)


pytestmark = pytest.mark.unit


def test_supported_header_and_item_loop_roundtrip_is_stable():
    src = "# {{ title }}\n{% for item in items %}\n{{ item.title }}\n{% endfor %}"

    ast = parse_jinja_to_composer_ast(src)
    assert len(ast["nodes"]) >= 1

    out = compile_composer_ast_to_jinja(ast)
    assert "{% for item in items %}" in out
    assert "{{ item.title }}" in out
    assert "{% endfor %}" in out


def test_unsupported_macro_preserved_as_raw_code_block():
    src = "{% macro card(x) %}{{ x }}{% endmacro %}{{ card(title) }}"

    ast = parse_jinja_to_composer_ast(src)
    assert any(node["type"] == "RawCodeBlock" for node in ast["nodes"])

    out = compile_composer_ast_to_jinja(ast)
    assert "{% macro card(x) %}" in out
    assert "{% endmacro %}" in out
