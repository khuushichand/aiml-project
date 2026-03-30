import base64
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.implementations.flashcards_module import FlashcardsModule
from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import ConflictError


class FakeFlashcardsDB:
    def __init__(self) -> None:
        self._deck_id = 0
        self.decks: Dict[int, Dict[str, Any]] = {}
        self.cards: Dict[str, Dict[str, Any]] = {}
        self.list_flashcards_calls: List[Dict[str, Any]] = []
        self.count_flashcards_calls: List[Dict[str, Any]] = []
        self.export_flashcards_calls: List[Dict[str, Any]] = []

    def add_deck(self, name: str, description=None):
        self._deck_id += 1
        deck_id = self._deck_id
        self.decks[deck_id] = {"id": deck_id, "name": name, "description": description, "deleted": 0}
        return deck_id

    def list_decks(self, limit=100, offset=0, include_deleted=False):
        decks = list(self.decks.values())
        return decks[offset: offset + limit]

    def get_deck(self, deck_id: int):
        return self.decks.get(deck_id)

    def list_flashcards(
        self,
        deck_id=None,
        workspace_id=None,
        include_workspace_items=False,
        tag=None,
        due_status="all",
        q=None,
        include_deleted=False,
        limit=100,
        offset=0,
        order_by="due_at",
    ):
        self.list_flashcards_calls.append(
            {
                "deck_id": deck_id,
                "workspace_id": workspace_id,
                "include_workspace_items": include_workspace_items,
                "tag": tag,
                "due_status": due_status,
                "q": q,
                "include_deleted": include_deleted,
                "limit": limit,
                "offset": offset,
                "order_by": order_by,
            }
        )
        items = list(self.cards.values())
        if deck_id is not None:
            items = [c for c in items if c.get("deck_id") == deck_id]
        return items[offset: offset + limit]

    def count_flashcards(
        self,
        deck_id=None,
        workspace_id=None,
        include_workspace_items=False,
        tag=None,
        due_status="all",
        q=None,
        include_deleted=False,
    ):
        self.count_flashcards_calls.append(
            {
                "deck_id": deck_id,
                "workspace_id": workspace_id,
                "include_workspace_items": include_workspace_items,
                "tag": tag,
                "due_status": due_status,
                "q": q,
                "include_deleted": include_deleted,
            }
        )
        return len(
            self.list_flashcards(
                deck_id=deck_id,
                workspace_id=workspace_id,
                include_workspace_items=include_workspace_items,
                tag=tag,
                due_status=due_status,
                q=q,
                include_deleted=include_deleted,
                limit=100000,
                offset=0,
            )
        )

    def get_flashcard(self, card_uuid: str):
        return self.cards.get(card_uuid)

    def add_flashcard(self, card_data: Dict[str, Any]):
        uuid = f"card-{len(self.cards) + 1}"
        card = dict(card_data)
        card.update({"uuid": uuid, "version": 1, "deleted": 0})
        self.cards[uuid] = card
        return uuid

    def add_flashcards_bulk(self, cards: List[Dict[str, Any]]):
        uuids = []
        for card in cards:
            uuids.append(self.add_flashcard(card))
        return uuids

    def update_flashcard(self, card_uuid: str, updates: Dict[str, Any], expected_version=None, tags=None):
        card = self.cards.get(card_uuid)
        if not card:
            return False
        if expected_version is not None and card["version"] != expected_version:
            raise ConflictError("Version mismatch", entity="flashcards", identifier=card_uuid)
        card.update(updates)
        card["version"] += 1
        return True

    def soft_delete_flashcard(self, card_uuid: str, expected_version: int):
        card = self.cards.get(card_uuid)
        if not card:
            raise ConflictError("Not found", entity="flashcards", identifier=card_uuid)
        if card["version"] != expected_version:
            raise ConflictError("Version mismatch", entity="flashcards", identifier=card_uuid)
        card["deleted"] = 1
        card["version"] += 1
        return True

    def review_flashcard(self, card_uuid: str, rating: int, answer_time_ms=None):
        return {"card_uuid": card_uuid, "rating": rating, "answer_time_ms": answer_time_ms}

    def set_flashcard_tags(self, card_uuid: str, tags: List[str]):
        card = self.cards.get(card_uuid)
        if not card:
            return False
        card["tags"] = tags
        return True

    def get_keywords_for_flashcard(self, card_uuid: str):
        card = self.cards.get(card_uuid)
        if not card:
            return []
        return [{"keyword": t} for t in card.get("tags", [])]

    def export_flashcards_csv(
        self,
        deck_id=None,
        workspace_id=None,
        include_workspace_items=False,
        tag=None,
        q=None,
        delimiter=",",
        include_header=True,
        extended_header=False,
    ):
        self.export_flashcards_calls.append(
            {
                "deck_id": deck_id,
                "workspace_id": workspace_id,
                "include_workspace_items": include_workspace_items,
                "tag": tag,
                "q": q,
                "delimiter": delimiter,
                "include_header": include_header,
                "extended_header": extended_header,
            }
        )
        return "front,back\nQ,A\n".encode("utf-8")

    def close_all_connections(self) -> None:
        return None


@pytest.mark.asyncio
async def test_flashcards_crud_and_export(monkeypatch, tmp_path):
    mod = FlashcardsModule(ModuleConfig(name="flashcards"))
    fake_db = FakeFlashcardsDB()
    mod._open_db = lambda ctx: fake_db  # type: ignore[attr-defined]

    ctx = SimpleNamespace(db_paths={"chacha": str(tmp_path / "chacha.db")})

    created_deck = await mod.execute_tool("flashcards.decks.create", {"name": "Deck"}, context=ctx)
    deck_id = created_deck["deck_id"]
    assert created_deck["success"] is True

    card = await mod.execute_tool(
        "flashcards.create",
        {"deck_id": deck_id, "front": "Q", "back": "A", "model_type": "basic"},
        context=ctx,
    )
    card_uuid = card["card_uuid"]

    updated = await mod.execute_tool(
        "flashcards.update",
        {"card_uuid": card_uuid, "updates": {"front": "Q2"}},
        context=ctx,
    )
    assert updated["success"] is True

    reviewed = await mod.execute_tool("flashcards.review", {"card_uuid": card_uuid, "rating": 3}, context=ctx)
    assert reviewed["review_result"]["rating"] == 3

    tags = await mod.execute_tool("flashcards.tags.set", {"card_uuid": card_uuid, "tags": ["Tag1"]}, context=ctx)
    assert tags["tags"] == ["tag1"]

    listed = await mod.execute_tool("flashcards.list", {}, context=ctx)
    assert listed["total"] == 1
    assert fake_db.list_flashcards_calls[-1]["include_workspace_items"] is True
    assert fake_db.count_flashcards_calls[-1]["include_workspace_items"] is True

    csv_export = await mod.execute_tool("flashcards.export", {"format": "csv"}, context=ctx)
    assert csv_export["mime_type"].startswith("text/")
    csv_bytes = base64.b64decode(csv_export["content_base64"])
    assert csv_bytes.startswith(b"front")
    assert fake_db.export_flashcards_calls[-1]["include_workspace_items"] is True

    # Stub APKG exporter
    from tldw_Server_API.app.core.Flashcards import apkg_exporter
    monkeypatch.setattr(apkg_exporter, "export_apkg_from_rows", lambda rows, include_reverse=False: b"apkg")

    apkg_export = await mod.execute_tool("flashcards.export", {"format": "apkg"}, context=ctx)
    apkg_bytes = base64.b64decode(apkg_export["content_base64"])
    assert apkg_bytes == b"apkg"
    assert fake_db.list_flashcards_calls[-1]["include_workspace_items"] is True
