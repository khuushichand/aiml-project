import pytest
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from tldw_Server_API.app.core.MCP_unified.modules.implementations.kanban_module import KanbanModule
from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.DB_Management.Kanban_DB import NotFoundError, InputError


class FakeKanbanDB:
    def __init__(self) -> None:
        self._boards: Dict[int, Dict[str, Any]] = {}
        self._lists: Dict[int, Dict[str, Any]] = {}
        self._cards: Dict[int, Dict[str, Any]] = {}
        self._labels: Dict[int, Dict[str, Any]] = {}
        self._card_labels: Dict[int, set[int]] = {}
        self._comments: Dict[int, Dict[str, Any]] = {}
        self._checklists: Dict[int, Dict[str, Any]] = {}
        self._checklist_items: Dict[int, Dict[str, Any]] = {}
        self._board_counter = 0
        self._list_counter = 0
        self._card_counter = 0
        self._label_counter = 0
        self._comment_counter = 0
        self._checklist_counter = 0
        self._checklist_item_counter = 0

    def create_board(
        self,
        name: str,
        client_id: str,
        description: Optional[str] = None,
        activity_retention_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._board_counter += 1
        board = {
            "id": self._board_counter,
            "name": name,
            "client_id": client_id,
            "description": description,
            "activity_retention_days": activity_retention_days,
            "metadata": metadata,
            "archived": 0,
            "deleted": 0,
        }
        self._boards[self._board_counter] = board
        return dict(board)

    def list_boards(
        self,
        include_archived: bool = False,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        boards = [
            b for b in self._boards.values()
            if (include_archived or not b.get("archived"))
            and (include_deleted or not b.get("deleted"))
        ]
        total = len(boards)
        return boards[offset: offset + limit], total

    def get_board(self, board_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        board = self._boards.get(board_id)
        if not board:
            return None
        if board.get("deleted") and not include_deleted:
            return None
        return dict(board)

    def create_list(
        self,
        board_id: int,
        name: str,
        client_id: str,
        position: Optional[int] = None,
    ) -> Dict[str, Any]:
        if board_id not in self._boards:
            raise NotFoundError("Board not found", entity="board", entity_id=board_id)
        self._list_counter += 1
        lst = {
            "id": self._list_counter,
            "board_id": board_id,
            "name": name,
            "client_id": client_id,
            "position": position or 0,
            "archived": 0,
            "deleted": 0,
        }
        self._lists[self._list_counter] = lst
        return dict(lst)

    def list_lists(
        self,
        board_id: int,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        if board_id not in self._boards:
            raise NotFoundError("Board not found", entity="board", entity_id=board_id)
        return [
            dict(lst)
            for lst in self._lists.values()
            if lst["board_id"] == board_id
            and (include_archived or not lst.get("archived"))
            and (include_deleted or not lst.get("deleted"))
        ]

    def create_card(
        self,
        list_id: int,
        title: str,
        client_id: str,
        description: Optional[str] = None,
        position: Optional[int] = None,
        due_date: Optional[str] = None,
        start_date: Optional[str] = None,
        priority: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if list_id not in self._lists:
            raise NotFoundError("List not found", entity="list", entity_id=list_id)
        self._card_counter += 1
        card = {
            "id": self._card_counter,
            "list_id": list_id,
            "board_id": self._lists[list_id]["board_id"],
            "title": title,
            "description": description,
            "client_id": client_id,
            "position": position or 0,
            "due_date": due_date,
            "start_date": start_date,
            "priority": priority,
            "metadata": metadata,
            "archived": 0,
            "deleted": 0,
        }
        self._cards[self._card_counter] = card
        return dict(card)

    def list_cards(
        self,
        list_id: int,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        if list_id not in self._lists:
            raise NotFoundError("List not found", entity="list", entity_id=list_id)
        return [
            dict(card)
            for card in self._cards.values()
            if card["list_id"] == list_id
            and (include_archived or not card.get("archived"))
            and (include_deleted or not card.get("deleted"))
        ]

    def move_card(
        self,
        card_id: int,
        target_list_id: int,
        position: Optional[int] = None,
    ) -> Dict[str, Any]:
        card = self._cards.get(card_id)
        if not card:
            raise NotFoundError("Card not found", entity="card", entity_id=card_id)
        if target_list_id not in self._lists:
            raise NotFoundError("List not found", entity="list", entity_id=target_list_id)
        if self._lists[target_list_id]["board_id"] != card["board_id"]:
            raise InputError("Cannot move card to a list in a different board")
        card["list_id"] = target_list_id
        if position is not None:
            card["position"] = position
        return dict(card)

    def search_cards(
        self,
        query: str,
        board_id: Optional[int] = None,
        label_ids: Optional[List[int]] = None,
        priority: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        needle = query.lower()
        results = []
        for card in self._cards.values():
            if board_id and card["board_id"] != board_id:
                continue
            if priority and card.get("priority") != priority:
                continue
            if not include_archived and card.get("archived"):
                continue
            hay = f"{card.get('title', '')} {card.get('description', '')}".lower()
            if needle in hay:
                results.append(dict(card))
        total = len(results)
        return results[offset: offset + limit], total

    def create_label(self, board_id: int, name: str, color: Optional[str] = None) -> Dict[str, Any]:
        if board_id not in self._boards:
            raise NotFoundError("Board not found", entity="board", entity_id=board_id)
        self._label_counter += 1
        label = {
            "id": self._label_counter,
            "board_id": board_id,
            "name": name,
            "color": color,
        }
        self._labels[self._label_counter] = label
        return dict(label)

    def list_labels(self, board_id: int) -> List[Dict[str, Any]]:
        if board_id not in self._boards:
            raise NotFoundError("Board not found", entity="board", entity_id=board_id)
        return [dict(lbl) for lbl in self._labels.values() if lbl["board_id"] == board_id]

    def update_label(
        self,
        label_id: int,
        name: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Dict[str, Any]:
        label = self._labels.get(label_id)
        if not label:
            raise NotFoundError("Label not found", entity="label", entity_id=label_id)
        if name is not None:
            label["name"] = name
        if color is not None:
            label["color"] = color
        return dict(label)

    def delete_label(self, label_id: int) -> bool:
        if label_id not in self._labels:
            return False
        self._labels.pop(label_id, None)
        for card_id in list(self._card_labels.keys()):
            self._card_labels[card_id].discard(label_id)
        return True

    def assign_label_to_card(self, card_id: int, label_id: int) -> bool:
        card = self._cards.get(card_id)
        label = self._labels.get(label_id)
        if not card:
            raise NotFoundError("Card not found", entity="card", entity_id=card_id)
        if not label:
            raise NotFoundError("Label not found", entity="label", entity_id=label_id)
        if label["board_id"] != card["board_id"]:
            raise InputError("Label does not belong to the card's board")
        self._card_labels.setdefault(card_id, set()).add(label_id)
        return True

    def remove_label_from_card(self, card_id: int, label_id: int) -> bool:
        if card_id not in self._cards:
            raise NotFoundError("Card not found", entity="card", entity_id=card_id)
        if label_id not in self._labels:
            raise NotFoundError("Label not found", entity="label", entity_id=label_id)
        labels = self._card_labels.setdefault(card_id, set())
        if label_id in labels:
            labels.discard(label_id)
            return True
        return False

    def get_card_labels(self, card_id: int) -> List[Dict[str, Any]]:
        if card_id not in self._cards:
            raise NotFoundError("Card not found", entity="card", entity_id=card_id)
        label_ids = self._card_labels.get(card_id, set())
        return [dict(self._labels[lid]) for lid in label_ids if lid in self._labels]

    def create_comment(self, card_id: int, content: str) -> Dict[str, Any]:
        if card_id not in self._cards:
            raise NotFoundError("Card not found", entity="card", entity_id=card_id)
        self._comment_counter += 1
        comment = {
            "id": self._comment_counter,
            "card_id": card_id,
            "content": content,
            "deleted": 0,
        }
        self._comments[self._comment_counter] = comment
        return dict(comment)

    def list_comments(
        self,
        card_id: int,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        if card_id not in self._cards:
            raise NotFoundError("Card not found", entity="card", entity_id=card_id)
        comments = [
            dict(comment)
            for comment in self._comments.values()
            if comment["card_id"] == card_id
            and (include_deleted or not comment.get("deleted"))
        ]
        total = len(comments)
        return comments[offset: offset + limit], total

    def update_comment(self, comment_id: int, content: str) -> Dict[str, Any]:
        comment = self._comments.get(comment_id)
        if not comment:
            raise NotFoundError("Comment not found", entity="comment", entity_id=comment_id)
        comment["content"] = content
        return dict(comment)

    def delete_comment(self, comment_id: int, hard_delete: bool = False) -> bool:
        comment = self._comments.get(comment_id)
        if not comment:
            return False
        if hard_delete:
            self._comments.pop(comment_id, None)
            return True
        comment["deleted"] = 1
        return True

    def create_checklist(
        self,
        card_id: int,
        name: str,
        position: Optional[int] = None,
    ) -> Dict[str, Any]:
        if card_id not in self._cards:
            raise NotFoundError("Card not found", entity="card", entity_id=card_id)
        self._checklist_counter += 1
        checklist = {
            "id": self._checklist_counter,
            "card_id": card_id,
            "name": name,
            "position": position or 0,
        }
        self._checklists[self._checklist_counter] = checklist
        return dict(checklist)

    def list_checklists(self, card_id: int) -> List[Dict[str, Any]]:
        if card_id not in self._cards:
            raise NotFoundError("Card not found", entity="card", entity_id=card_id)
        return [
            dict(ch)
            for ch in self._checklists.values()
            if ch["card_id"] == card_id
        ]

    def update_checklist(self, checklist_id: int, name: Optional[str] = None) -> Dict[str, Any]:
        checklist = self._checklists.get(checklist_id)
        if not checklist:
            raise NotFoundError("Checklist not found", entity="checklist", entity_id=checklist_id)
        if name is not None:
            checklist["name"] = name
        return dict(checklist)

    def delete_checklist(self, checklist_id: int) -> bool:
        if checklist_id not in self._checklists:
            return False
        self._checklists.pop(checklist_id, None)
        for item_id in list(self._checklist_items.keys()):
            if self._checklist_items[item_id]["checklist_id"] == checklist_id:
                self._checklist_items.pop(item_id, None)
        return True

    def create_checklist_item(
        self,
        checklist_id: int,
        name: str,
        position: Optional[int] = None,
        checked: bool = False,
    ) -> Dict[str, Any]:
        if checklist_id not in self._checklists:
            raise NotFoundError("Checklist not found", entity="checklist", entity_id=checklist_id)
        self._checklist_item_counter += 1
        item = {
            "id": self._checklist_item_counter,
            "checklist_id": checklist_id,
            "name": name,
            "position": position or 0,
            "checked": bool(checked),
        }
        self._checklist_items[self._checklist_item_counter] = item
        return dict(item)

    def list_checklist_items(self, checklist_id: int) -> List[Dict[str, Any]]:
        if checklist_id not in self._checklists:
            raise NotFoundError("Checklist not found", entity="checklist", entity_id=checklist_id)
        return [
            dict(item)
            for item in self._checklist_items.values()
            if item["checklist_id"] == checklist_id
        ]

    def update_checklist_item(
        self,
        item_id: int,
        name: Optional[str] = None,
        checked: Optional[bool] = None,
    ) -> Dict[str, Any]:
        item = self._checklist_items.get(item_id)
        if not item:
            raise NotFoundError("Checklist item not found", entity="checklist_item", entity_id=item_id)
        if name is not None:
            item["name"] = name
        if checked is not None:
            item["checked"] = bool(checked)
        return dict(item)

    def delete_checklist_item(self, item_id: int) -> bool:
        if item_id not in self._checklist_items:
            return False
        self._checklist_items.pop(item_id, None)
        return True


@pytest.mark.asyncio
async def test_kanban_module_basic_flow():
    mod = KanbanModule(ModuleConfig(name="kanban"))
    fake_db = FakeKanbanDB()
    mod._open_db = lambda ctx: fake_db  # type: ignore[assignment]

    ctx = SimpleNamespace(user_id="1", db_paths={"kanban": "/tmp/kanban.db"})

    empty = await mod.execute_tool("kanban.boards.list", {}, context=ctx)
    assert empty["total"] == 0

    created_board = await mod.execute_tool(
        "kanban.boards.create",
        {"name": "Work Board"},
        context=ctx,
    )
    board_id = created_board["board"]["id"]

    fetched = await mod.execute_tool(
        "kanban.boards.get",
        {"board_id": board_id},
        context=ctx,
    )
    assert fetched["board"]["name"] == "Work Board"

    created_list = await mod.execute_tool(
        "kanban.lists.create",
        {"board_id": board_id, "name": "Todo"},
        context=ctx,
    )
    list_id = created_list["list"]["id"]

    lists = await mod.execute_tool(
        "kanban.lists.list",
        {"board_id": board_id},
        context=ctx,
    )
    assert len(lists["lists"]) == 1

    created_card = await mod.execute_tool(
        "kanban.cards.create",
        {"list_id": list_id, "title": "Ship MCP"},
        context=ctx,
    )
    card_id = created_card["card"]["id"]
    assert created_card["card"]["title"] == "Ship MCP"

    cards = await mod.execute_tool(
        "kanban.cards.list",
        {"list_id": list_id},
        context=ctx,
    )
    assert len(cards["cards"]) == 1

    created_label = await mod.execute_tool(
        "kanban.labels.create",
        {"board_id": board_id, "name": "Urgent", "color": "red"},
        context=ctx,
    )
    label_id = created_label["label"]["id"]
    assigned = await mod.execute_tool(
        "kanban.labels.assign",
        {"card_id": card_id, "label_id": label_id},
        context=ctx,
    )
    assert any(lbl["id"] == label_id for lbl in assigned["labels"])

    comments = await mod.execute_tool(
        "kanban.comments.create",
        {"card_id": card_id, "content": "Looks good"},
        context=ctx,
    )
    comment_id = comments["comment"]["id"]
    comment_list = await mod.execute_tool(
        "kanban.comments.list",
        {"card_id": card_id},
        context=ctx,
    )
    assert comment_list["total"] == 1

    checklist = await mod.execute_tool(
        "kanban.checklists.create",
        {"card_id": card_id, "name": "Launch"},
        context=ctx,
    )
    checklist_id = checklist["checklist"]["id"]
    item = await mod.execute_tool(
        "kanban.checklists.items.create",
        {"checklist_id": checklist_id, "name": "Announce"},
        context=ctx,
    )
    item_id = item["item"]["id"]
    updated_item = await mod.execute_tool(
        "kanban.checklists.items.update",
        {"item_id": item_id, "checked": True},
        context=ctx,
    )
    assert updated_item["item"]["checked"] is True

    moved_list = await mod.execute_tool(
        "kanban.lists.create",
        {"board_id": board_id, "name": "Done"},
        context=ctx,
    )
    moved_list_id = moved_list["list"]["id"]
    moved = await mod.execute_tool(
        "kanban.cards.move",
        {"card_id": card_id, "target_list_id": moved_list_id},
        context=ctx,
    )
    assert moved["card"]["list_id"] == moved_list_id

    searched = await mod.execute_tool(
        "kanban.cards.search",
        {"query": "mcp"},
        context=ctx,
    )
    assert searched["total"] == 1
