"""Integration tests for character exemplar endpoints."""

import pytest

pytestmark = pytest.mark.integration


class TestCharacterExemplarEndpoints:
    def _create_character(self, test_client, auth_headers, name: str) -> int:
        response = test_client.post(
            "/api/v1/characters/",
            json={
                "name": name,
                "description": "Character for exemplar endpoint tests",
                "personality": "Confident and concise",
                "first_message": "Hello there.",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        return int(response.json()["id"])

    def test_character_exemplar_crud_and_search(self, test_client, auth_headers):
        char_id = self._create_character(test_client, auth_headers, "Exemplar API Character CRUD")

        create_response = test_client.post(
            f"/api/v1/characters/{char_id}/exemplars",
            json={
                "text": "Opening line for press challenge with measured confidence.",
                "source": {"type": "article", "url_or_id": "doc-1", "date": "2026-02-08"},
                "novelty_hint": "unknown",
                "labels": {
                    "emotion": "neutral",
                    "scenario": "press_challenge",
                    "rhetorical": ["opener", "emphasis"],
                    "register": "formal",
                },
                "safety": {"allowed": ["general"], "blocked": ["harmful"]},
                "rights": {"public_figure": True, "notes": "curated quote"},
            },
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        created = create_response.json()
        exemplar_id = created["id"]
        assert created["character_id"] == char_id
        assert created["labels"]["scenario"] == "press_challenge"

        get_response = test_client.get(
            f"/api/v1/characters/{char_id}/exemplars/{exemplar_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["id"] == exemplar_id

        update_response = test_client.put(
            f"/api/v1/characters/{char_id}/exemplars/{exemplar_id}",
            json={
                "text": "Updated opener line for a media question.",
                "labels": {"emotion": "happy", "scenario": "press_challenge", "rhetorical": ["opener"]},
                "length_tokens": 10,
            },
            headers=auth_headers,
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["labels"]["emotion"] == "happy"
        assert updated["length_tokens"] == 10

        search_response = test_client.post(
            f"/api/v1/characters/{char_id}/exemplars/search",
            json={
                "query": "media question",
                "filter": {"emotion": "happy", "scenario": "press_challenge", "rhetorical": ["opener"]},
                "limit": 10,
                "offset": 0,
            },
            headers=auth_headers,
        )
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert search_data["total"] >= 1
        assert any(item["id"] == exemplar_id for item in search_data["items"])

        delete_response = test_client.delete(
            f"/api/v1/characters/{char_id}/exemplars/{exemplar_id}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 200

        missing_response = test_client.get(
            f"/api/v1/characters/{char_id}/exemplars/{exemplar_id}",
            headers=auth_headers,
        )
        assert missing_response.status_code == 404

    def test_character_exemplar_batch_create_and_debug_selection(self, test_client, auth_headers):
        char_id = self._create_character(test_client, auth_headers, "Exemplar API Character Batch")

        batch_response = test_client.post(
            f"/api/v1/characters/{char_id}/exemplars",
            json=[
                {
                    "text": "Quick opener for fan banter.",
                    "labels": {
                        "emotion": "happy",
                        "scenario": "fan_banter",
                        "rhetorical": ["opener"],
                    },
                },
                {
                    "text": "Closing line that keeps tone respectful.",
                    "labels": {
                        "emotion": "neutral",
                        "scenario": "small_talk",
                        "rhetorical": ["ender"],
                    },
                },
            ],
            headers=auth_headers,
        )

        assert batch_response.status_code == 201
        batch_items = batch_response.json()
        assert isinstance(batch_items, list)
        assert len(batch_items) == 2

        debug_response = test_client.post(
            f"/api/v1/characters/{char_id}/exemplars/select/debug",
            json={
                "user_turn": "Give me a quick fan-facing response.",
                "selection_config": {
                    "budget_tokens": 40,
                    "max_exemplar_tokens": 30,
                    "mmr_lambda": 0.7,
                },
            },
            headers=auth_headers,
        )

        assert debug_response.status_code == 200
        debug_data = debug_response.json()
        assert debug_data["budget_tokens"] <= 40
        assert len(debug_data["selected"]) >= 1
        assert len(debug_data["scores"]) == len(debug_data["selected"])

    def test_character_exemplar_search_filtering(self, test_client, auth_headers):
        char_id = self._create_character(test_client, auth_headers, "Exemplar API Character Filter")

        test_client.post(
            f"/api/v1/characters/{char_id}/exemplars",
            json={
                "text": "Boardroom guidance with measured tone.",
                "labels": {
                    "emotion": "neutral",
                    "scenario": "boardroom",
                    "rhetorical": ["emphasis"],
                },
            },
            headers=auth_headers,
        )
        test_client.post(
            f"/api/v1/characters/{char_id}/exemplars",
            json={
                "text": "Fan banter with upbeat energy.",
                "labels": {
                    "emotion": "happy",
                    "scenario": "fan_banter",
                    "rhetorical": ["opener"],
                },
            },
            headers=auth_headers,
        )

        search_response = test_client.post(
            f"/api/v1/characters/{char_id}/exemplars/search",
            json={
                "filter": {
                    "emotion": "neutral",
                    "scenario": "boardroom",
                    "rhetorical": ["emphasis"],
                },
                "limit": 10,
                "offset": 0,
            },
            headers=auth_headers,
        )

        assert search_response.status_code == 200
        payload = search_response.json()
        assert payload["total"] == 1
        assert len(payload["items"]) == 1
        assert payload["items"][0]["labels"]["scenario"] == "boardroom"
