"""Performance profiling for persona selector + prompt assembly (PRD p95 target)."""

from __future__ import annotations

import math
import os
import random
import statistics
import time

import pytest

from tldw_Server_API.app.api.v1.endpoints.chat import _format_persona_exemplar_guidance
from tldw_Server_API.app.core.Character_Chat.modules.persona_exemplar_selector import (
    PersonaExemplarSelectorConfig,
    select_character_exemplars,
)


def _perf_enabled() -> bool:
    return os.getenv("PERF", "0").lower() in {"1", "true", "yes", "y", "on"}


pytestmark = [
    pytest.mark.performance,
    pytest.mark.benchmark,
    pytest.mark.skipif(not _perf_enabled(), reason="set PERF=1 to run performance checks"),
]


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return float(ordered[index])


class _PerfExemplarDB:
    """Simple in-memory DB stub that simulates lexical retrieval over a large corpus."""

    def __init__(self, exemplars: list[dict[str, object]]):
        self._exemplars = exemplars
        self._by_scenario: dict[str, list[dict[str, object]]] = {}
        for item in exemplars:
            scenario = str(item.get("scenario") or "other")
            self._by_scenario.setdefault(scenario, []).append(item)

    def search_character_exemplars(self, character_id: int, query: str, limit: int, offset: int):
        lowered = str(query or "").lower()
        if any(term in lowered for term in ("reporter", "media", "interview")):
            ranked = self._by_scenario.get("press_challenge", self._exemplars)
        elif any(term in lowered for term in ("board", "stakeholder", "strategy", "investor")):
            ranked = self._by_scenario.get("boardroom", self._exemplars)
        elif any(term in lowered for term in ("debate", "argument", "rebuttal")):
            ranked = self._by_scenario.get("debate", self._exemplars)
        elif any(term in lowered for term in ("small talk", "hello", "followup")):
            ranked = self._by_scenario.get("small_talk", self._exemplars)
        else:
            ranked = self._exemplars
        return ranked[offset:offset + limit], len(ranked)

    def list_character_exemplars(self, character_id: int, limit: int, offset: int):
        return self._exemplars[offset:offset + limit]


def _make_perf_corpus(size: int = 10_000) -> list[dict[str, object]]:
    rnd = random.Random(42)
    scenarios = ["press_challenge", "fan_banter", "debate", "boardroom", "small_talk", "other"]
    emotions = ["neutral", "angry", "happy", "other"]
    rhetoricals = [["opener"], ["emphasis"], ["ender"], ["opener", "emphasis"]]
    topic_tokens = [
        "reporter", "strategy", "board", "meeting", "policy", "response", "analysis", "context",
        "facts", "followup", "stakeholder", "media", "debate", "community", "tone",
    ]
    corpus: list[dict[str, object]] = []
    for idx in range(size):
        base = rnd.sample(topic_tokens, k=6)
        text = (
            f"Example {idx} {' '.join(base)} "
            f"keep responses concise grounded factual and policy compliant."
        )
        corpus.append(
            {
                "id": f"ex-{idx}",
                "text": text,
                "scenario": scenarios[idx % len(scenarios)],
                "emotion": emotions[idx % len(emotions)],
                "novelty_hint": "unknown" if idx % 4 else "post_cutoff",
                "rhetorical": rhetoricals[idx % len(rhetoricals)],
                "length_tokens": 60 + (idx % 20),
            }
        )
    return corpus


def test_persona_selector_and_prompt_assembly_p95_under_target():
    warmup = int(os.getenv("PERF_PERSONA_SELECTOR_WARMUP", "10"))
    samples = int(os.getenv("PERF_PERSONA_SELECTOR_SAMPLES", "80"))
    p95_target = float(os.getenv("PERF_PERSONA_SELECTOR_P95_TARGET_SECONDS", "0.120"))

    db = _PerfExemplarDB(_make_perf_corpus(size=10_000))
    cfg = PersonaExemplarSelectorConfig(
        budget_tokens=600,
        max_exemplar_tokens=120,
        mmr_lambda=0.7,
        candidate_pool_size=80,
    )
    turns = [
        "How should I answer this reporter question with clear facts?",
        "Need a boardroom strategy response for stakeholders.",
        "Give me concise debate framing with calm tone.",
        "Help with a small talk followup while staying in persona.",
    ]

    for idx in range(warmup):
        result = select_character_exemplars(
            db=db,  # type: ignore[arg-type]
            character_id=1,
            user_turn=turns[idx % len(turns)],
            config=cfg,
        )
        _ = _format_persona_exemplar_guidance(result.selected)

    timings: list[float] = []
    for idx in range(samples):
        turn = turns[idx % len(turns)]
        start = time.perf_counter()
        result = select_character_exemplars(
            db=db,  # type: ignore[arg-type]
            character_id=1,
            user_turn=turn,
            config=cfg,
        )
        _ = _format_persona_exemplar_guidance(result.selected)
        timings.append(time.perf_counter() - start)

    measured_p95 = _p95(timings)
    measured_p50 = statistics.median(timings) if timings else 0.0
    print(
        "persona_selector_prompt_assembly_perf "
        f"samples={samples} p50={measured_p50:.6f}s p95={measured_p95:.6f}s target={p95_target:.6f}s"
    )
    assert measured_p95 <= p95_target
