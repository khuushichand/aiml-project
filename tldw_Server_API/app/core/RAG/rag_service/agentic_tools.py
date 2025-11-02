from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Protocol, Any, Dict, Optional

from .types import Document


class AgenticTool(Protocol):
    name: str
    def __call__(self, *args, **kwargs) -> Any: ...


@dataclass
class ToolsRegistry:
    tools: Dict[str, AgenticTool]

    def register(self, name: str, tool: AgenticTool) -> None:
        self.tools[name] = tool

    def get(self, name: str) -> Optional[AgenticTool]:
        return self.tools.get(name)


def make_default_registry(toolbox: Any) -> ToolsRegistry:
    """Bind toolbox methods into tool implementations and register them."""
    reg = ToolsRegistry(tools={})

    def _search_within(doc: Document, query: str, max_hits: int = 8, window: int = 300) -> List[Tuple[int, int]]:
        return toolbox.search_within(doc, query, max_hits=max_hits, window=window)
    _search_within.name = "search_within"  # type: ignore[attr-defined]
    reg.register("search_within", _search_within)  # type: ignore[arg-type]

    def _open_section(doc: Document, heading: str) -> Optional[Tuple[int, int]]:
        return toolbox.open_section(doc, heading)
    _open_section.name = "open_section"  # type: ignore[attr-defined]
    reg.register("open_section", _open_section)  # type: ignore[arg-type]

    def _expand(doc: Document, start: int, end: int, delta: int = 200) -> Tuple[int, int]:
        return toolbox.expand_window(doc, start, end, delta=delta)
    _expand.name = "expand_window"  # type: ignore[attr-defined]
    reg.register("expand_window", _expand)  # type: ignore[arg-type]

    def _quote_spans(doc: Document, spans: List[Tuple[int, int]]) -> List[str]:
        return toolbox.quote_spans(doc, spans)
    _quote_spans.name = "quote_spans"  # type: ignore[attr-defined]
    reg.register("quote_spans", _quote_spans)  # type: ignore[arg-type]

    return reg
