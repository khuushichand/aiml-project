"""Core data model for Watchlists visual template composer nodes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


ComposerNodeType = Literal[
    "HeaderBlock",
    "IntroSummaryBlock",
    "ItemLoopBlock",
    "GroupSectionBlock",
    "CtaFooterBlock",
    "FinalFlowCheckBlock",
    "RawCodeBlock",
]


class ComposerNode(TypedDict, total=False):
    id: str
    type: ComposerNodeType
    source: str
    enabled: bool
    config: dict[str, Any]


class ComposerAst(TypedDict):
    schema_version: str
    nodes: list[ComposerNode]


DEFAULT_COMPOSER_SCHEMA_VERSION = "1.0.0"


def create_composer_ast(
    nodes: list[ComposerNode] | None = None,
    *,
    schema_version: str = DEFAULT_COMPOSER_SCHEMA_VERSION,
) -> ComposerAst:
    return {
        "schema_version": schema_version,
        "nodes": list(nodes or []),
    }

