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
            "tts": StepType("tts", "Text-to-speech: synthesize audio from text and persist as artifact"),
            "webhook": StepType("webhook", "POST payload to a webhook with HMAC signing and SSRF protections"),
            "delay": StepType("delay", "Pause the workflow for a fixed time (ms)"),
            "log": StepType("log", "Log a templated message at a chosen level"),
            "wait_for_human": StepType("wait_for_human", "Pause for human approval or edits"),
            "wait_for_approval": StepType("wait_for_approval", "Pause until an approval decision is made"),
            "branch": StepType("branch", "Evaluate a condition and jump to the next step by id"),
            "map": StepType("map", "Fan-out over a list and apply a step with optional concurrency; returns results list"),
            "process_media": StepType("process_media", "Process media using internal services without persistence (ephemeral)"),
            "policy_check": StepType("policy_check", "Detect PII/blocked terms/length to gate content flow"),
            "rss_fetch": StepType("rss_fetch", "Fetch RSS/Atom feeds and return items for downstream steps"),
            "atom_fetch": StepType("atom_fetch", "Alias for rss_fetch (Atom feeds)"),
            "embed": StepType("embed", "Create embeddings for text and upsert into Chroma collection"),
            "translate": StepType("translate", "Translate text to a target language via provider-agnostic chat"),
            "stt_transcribe": StepType("stt_transcribe", "Transcribe audio to text with optional diarization"),
            "notify": StepType("notify", "Send a simple notification via webhook (Slack/email)"),
            "diff_change_detector": StepType("diff_change_detector", "Compare previous vs current content and flag changes"),
        }

    def list(self) -> List[StepType]:
        return list(self._steps.values())

    def has(self, name: str) -> bool:
        return name in self._steps
