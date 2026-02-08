"""Unit tests for persona exemplar selector (Sprint 2)."""

import pytest

from tldw_Server_API.app.core.Character_Chat.modules.persona_exemplar_selector import (
    PersonaExemplarSelectorConfig,
    classify_user_turn,
    select_character_exemplars,
)


class _StubExemplarDB:
    def __init__(self, exemplars: list[dict]):
        self._exemplars = exemplars

    def search_character_exemplars(self, character_id: int, query: str, limit: int, offset: int):
        return self._exemplars[offset:offset + limit], len(self._exemplars)

    def list_character_exemplars(self, character_id: int, limit: int, offset: int):
        return self._exemplars[offset:offset + limit]


@pytest.mark.unit
def test_classify_user_turn_detects_scenario_and_emotion():
    heuristics = classify_user_turn("The reporter asked an angry media question in the interview")

    assert heuristics.scenario == "press_challenge"
    assert heuristics.emotion == "angry"
    assert "reporter" in heuristics.intent_terms or "media" in heuristics.intent_terms


@pytest.mark.unit
def test_selector_respects_budget_and_max_exemplar_tokens():
    db = _StubExemplarDB(
        [
            {
                "id": "a",
                "text": "press interview response for a media challenge",
                "scenario": "press_challenge",
                "emotion": "neutral",
                "novelty_hint": "unknown",
                "rhetorical": ["opener"],
                "length_tokens": 50,
            },
            {
                "id": "b",
                "text": "This exemplar should be rejected for being too long",
                "scenario": "press_challenge",
                "emotion": "neutral",
                "novelty_hint": "unknown",
                "rhetorical": ["emphasis"],
                "length_tokens": 300,
            },
            {
                "id": "c",
                "text": "short follow-up line for response",
                "scenario": "small_talk",
                "emotion": "neutral",
                "novelty_hint": "unknown",
                "rhetorical": ["ender"],
                "length_tokens": 70,
            },
        ]
    )

    result = select_character_exemplars(
        db=db,  # type: ignore[arg-type]
        character_id=1,
        user_turn="reporter media response",
        config=PersonaExemplarSelectorConfig(
            budget_tokens=100,
            max_exemplar_tokens=120,
            mmr_lambda=0.7,
            candidate_pool_size=20,
        ),
    )

    assert result.budget_tokens_used <= 100
    assert all(int(item.get("length_tokens", 0)) <= 120 for item in result.selected)
    assert all(item["id"] != "b" for item in result.selected)


@pytest.mark.unit
def test_selector_hybrid_scoring_uses_embedding_callback():
    exemplars = [
        {
            "id": "lexical",
            "text": "budget strategy board meeting plan",
            "scenario": "fan_banter",
            "emotion": "angry",
            "novelty_hint": "pre_cutoff",
            "rhetorical": ["opener"],
            "length_tokens": 25,
        },
        {
            "id": "embedded",
            "text": "generic line with little lexical overlap",
            "scenario": "boardroom",
            "emotion": "neutral",
            "novelty_hint": "post_cutoff",
            "rhetorical": ["emphasis"],
            "length_tokens": 25,
        },
    ]
    db = _StubExemplarDB(exemplars)

    def _embedding_scores(query: str, candidates: list[dict]) -> dict[str, float]:
        assert query
        return {"embedded": 1.0, "lexical": 0.0}

    result = select_character_exemplars(
        db=db,  # type: ignore[arg-type]
        character_id=1,
        user_turn="board meeting strategy and budget",
        config=PersonaExemplarSelectorConfig(
            budget_tokens=60,
            max_exemplar_tokens=40,
            mmr_lambda=0.8,
            candidate_pool_size=20,
        ),
        embedding_score_fn=_embedding_scores,
    )

    assert result.selected
    assert result.selected[0]["id"] == "embedded"


@pytest.mark.unit
def test_selector_mmr_and_dedupe_avoid_near_duplicates():
    db = _StubExemplarDB(
        [
            {
                "id": "dup1",
                "text": "press statement update right now",
                "scenario": "press_challenge",
                "emotion": "neutral",
                "novelty_hint": "unknown",
                "rhetorical": ["opener"],
                "length_tokens": 25,
            },
            {
                "id": "dup2",
                "text": "press statement update right now",
                "scenario": "press_challenge",
                "emotion": "neutral",
                "novelty_hint": "unknown",
                "rhetorical": ["opener"],
                "length_tokens": 25,
            },
            {
                "id": "diverse",
                "text": "boardroom strategy answer with different wording",
                "scenario": "boardroom",
                "emotion": "neutral",
                "novelty_hint": "post_cutoff",
                "rhetorical": ["ender"],
                "length_tokens": 25,
            },
        ]
    )

    result = select_character_exemplars(
        db=db,  # type: ignore[arg-type]
        character_id=1,
        user_turn="press statement update",
        config=PersonaExemplarSelectorConfig(
            budget_tokens=100,
            max_exemplar_tokens=40,
            mmr_lambda=0.2,
            candidate_pool_size=20,
        ),
    )

    selected_ids = [item["id"] for item in result.selected]
    duplicate_count = len({"dup1", "dup2"}.intersection(selected_ids))
    assert duplicate_count == 1


@pytest.mark.unit
def test_selector_reports_coverage_counts():
    db = _StubExemplarDB(
        [
            {
                "id": "o",
                "text": "opener sample text",
                "scenario": "small_talk",
                "emotion": "neutral",
                "novelty_hint": "unknown",
                "rhetorical": ["opener"],
                "length_tokens": 20,
            },
            {
                "id": "e",
                "text": "emphasis sample text",
                "scenario": "small_talk",
                "emotion": "neutral",
                "novelty_hint": "unknown",
                "rhetorical": ["emphasis"],
                "length_tokens": 20,
            },
            {
                "id": "n",
                "text": "ender sample text",
                "scenario": "small_talk",
                "emotion": "neutral",
                "novelty_hint": "unknown",
                "rhetorical": ["ender"],
                "length_tokens": 20,
            },
        ]
    )

    result = select_character_exemplars(
        db=db,  # type: ignore[arg-type]
        character_id=1,
        user_turn="hey there thanks",
        config=PersonaExemplarSelectorConfig(
            budget_tokens=80,
            max_exemplar_tokens=40,
            mmr_lambda=0.7,
            candidate_pool_size=20,
        ),
    )

    assert result.coverage["openers"] >= 1
    assert result.coverage["emphasis"] >= 1
    assert result.coverage["enders"] >= 1


@pytest.mark.unit
def test_selector_returns_empty_for_blank_turn():
    db = _StubExemplarDB([])

    result = select_character_exemplars(
        db=db,  # type: ignore[arg-type]
        character_id=1,
        user_turn="   ",
        config=PersonaExemplarSelectorConfig(),
    )

    assert result.selected == []
    assert result.budget_tokens_used == 0
    assert result.scores == []
