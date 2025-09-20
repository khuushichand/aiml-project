from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class StepType:
    name: str
    description: str


class StepTypeRegistry:
    """Static step type registry for v0.1 stub."""

    def __init__(self) -> None:
        self._steps: Dict[str, StepType] = {
            "media_ingest": StepType("media_ingest", "Ingest and process media (download, extract, chunk, index)"),
            "prompt": StepType("prompt", "LLM prompt step producing text or JSON output"),
            "rag_search": StepType("rag_search", "Run a unified RAG search and return documents"),
            "mcp_tool": StepType("mcp_tool", "Invoke an MCP tool with arguments"),
            "webhook": StepType("webhook", "POST payload to a webhook with HMAC signing and SSRF protections"),
            "wait_for_human": StepType("wait_for_human", "Pause for human approval or edits"),
        }

    def list(self) -> List[StepType]:
        return list(self._steps.values())

    def has(self, name: str) -> bool:
        return name in self._steps

