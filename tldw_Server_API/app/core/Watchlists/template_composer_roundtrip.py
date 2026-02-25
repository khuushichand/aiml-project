"""Minimal parser/compiler for Watchlists visual composer round-trip contracts."""

from __future__ import annotations

import re
from typing import cast

from tldw_Server_API.app.core.Watchlists.template_composer_ast import (
    ComposerAst,
    ComposerNode,
    create_composer_ast,
)


_UNSUPPORTED_BLOCK_TOKENS = (
    "{% macro",
    "{% include",
    "{% extends",
    "{% import",
    "{% from",
    "{% block",
    "{% call",
)

_ITEM_LOOP_PATTERN = re.compile(
    r"{%\s*for\s+item\s+in\s+items\s*%}[\s\S]*?{%\s*endfor\s*%}",
    re.MULTILINE,
)


def _raw_block(node_id: str, source: str) -> ComposerNode:
    return {"id": node_id, "type": "RawCodeBlock", "source": source}


def _header_or_raw(node_id: str, source: str) -> ComposerNode:
    trimmed = source.strip()
    if "{{ title }}" in trimmed and trimmed.startswith("#"):
        return {"id": node_id, "type": "HeaderBlock", "source": trimmed}
    return _raw_block(node_id, trimmed)


def parse_jinja_to_composer_ast(content: str) -> ComposerAst:
    """Parse Jinja source into a minimal composer AST.

    Supported in this first pass:
    - Header block containing ``{{ title }}``
    - Item loop ``for item in items ... endfor``
    - RawCodeBlock fallback for unsupported or non-recognized constructs
    """
    normalized = str(content or "").strip()
    if not normalized:
        return create_composer_ast([])

    if any(token in normalized for token in _UNSUPPORTED_BLOCK_TOKENS):
        return create_composer_ast([_raw_block("raw-1", normalized)])

    match = _ITEM_LOOP_PATTERN.search(normalized)
    if not match:
        return create_composer_ast([_header_or_raw("node-1", normalized)])

    nodes: list[ComposerNode] = []
    prefix = normalized[: match.start()].strip()
    loop_src = match.group(0).strip()
    suffix = normalized[match.end() :].strip()

    if prefix:
        nodes.append(_header_or_raw("node-1", prefix))
    nodes.append({"id": "item-loop-1", "type": "ItemLoopBlock", "source": loop_src})
    if suffix:
        nodes.append(_header_or_raw(f"node-{len(nodes) + 1}", suffix))

    return create_composer_ast(nodes)


def _default_source_for_type(node_type: str) -> str:
    if node_type == "HeaderBlock":
        return "# {{ title }}"
    if node_type == "ItemLoopBlock":
        return "{% for item in items %}\n{{ item.title }}\n{% endfor %}"
    return ""


def compile_composer_ast_to_jinja(ast: ComposerAst) -> str:
    """Compile composer AST back into deterministic Jinja text."""
    parts: list[str] = []
    for node in ast.get("nodes", []):
        source = str(node.get("source") or "").strip()
        if not source:
            source = _default_source_for_type(cast(str, node.get("type")))
        if source:
            parts.append(source)
    return "\n\n".join(parts).strip()

