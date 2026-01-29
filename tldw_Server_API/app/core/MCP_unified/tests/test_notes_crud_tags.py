import pytest
from types import SimpleNamespace
from typing import Any, Dict, List

from tldw_Server_API.app.core.MCP_unified.modules.implementations.notes_module import NotesModule
from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig


class FakeNotesDB:
    def __init__(self) -> None:
        self._notes: Dict[str, Dict[str, Any]] = {}
        self._note_counter = 0
        self._keywords: Dict[int, str] = {}
        self._keywords_by_text: Dict[str, int] = {}
        self._note_keywords: Dict[str, set[int]] = {}

    def add_note(self, title: str, content: str, note_id: str | None = None, **_kwargs) -> str:
        self._note_counter += 1
        nid = note_id or f"note-{self._note_counter}"
        self._notes[nid] = {
            "id": nid,
            "title": title,
            "content": content,
            "version": 1,
            "deleted": 0,
            "created_at": None,
            "last_modified": None,
        }
        return nid

    def get_note_by_id(self, note_id: str):
        row = self._notes.get(note_id)
        if not row or row.get("deleted"):
            return None
        return dict(row)

    def update_note(self, note_id: str, update_data: Dict[str, Any], expected_version: int):
        row = self._notes.get(note_id)
        if not row or row.get("deleted"):
            return False
        if int(row.get("version")) != expected_version:
            raise ValueError("version mismatch")
        for k, v in update_data.items():
            row[k] = v
        row["version"] = expected_version + 1
        return True

    def delete_note(self, note_id: str, expected_version: int | None = None, hard_delete: bool = False) -> bool:
        row = self._notes.get(note_id)
        if not row:
            return False
        if hard_delete:
            self._notes.pop(note_id, None)
            self._note_keywords.pop(note_id, None)
            return True
        if row.get("deleted"):
            return True
        if expected_version is not None and int(row.get("version")) != expected_version:
            raise ValueError("version mismatch")
        row["deleted"] = 1
        row["version"] = int(row.get("version", 1)) + 1
        return True

    def add_keyword(self, keyword_text: str) -> int:
        key = keyword_text.strip().lower()
        if key in self._keywords_by_text:
            return self._keywords_by_text[key]
        kid = len(self._keywords) + 1
        self._keywords[kid] = key
        self._keywords_by_text[key] = kid
        return kid

    def get_keyword_by_text(self, keyword_text: str):
        key = keyword_text.strip().lower()
        kid = self._keywords_by_text.get(key)
        if kid is None:
            return None
        return {"id": kid, "keyword": self._keywords[kid]}

    def link_note_to_keyword(self, note_id: str, keyword_id: int) -> bool:
        self._note_keywords.setdefault(note_id, set()).add(int(keyword_id))
        return True

    def unlink_note_from_keyword(self, note_id: str, keyword_id: int) -> bool:
        if note_id in self._note_keywords:
            self._note_keywords[note_id].discard(int(keyword_id))
        return True

    def get_keywords_for_note(self, note_id: str) -> List[Dict[str, Any]]:
        ids = sorted(self._note_keywords.get(note_id, set()), key=lambda i: self._keywords.get(i, ""))
        return [{"id": kid, "keyword": self._keywords.get(kid)} for kid in ids]

    def list_keywords(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        items = sorted(self._keywords.items(), key=lambda kv: kv[1])
        sliced = items[offset: offset + limit]
        return [{"id": kid, "keyword": kw} for kid, kw in sliced]

    def count_keywords(self) -> int:
        return len(self._keywords)

    def close_all_connections(self) -> None:
        return None


@pytest.mark.asyncio
async def test_notes_crud_and_tags_flow():
    mod = NotesModule(ModuleConfig(name="notes"))
    fake_db = FakeNotesDB()
    mod._open_db = lambda ctx: fake_db  # type: ignore[attr-defined]

    ctx = SimpleNamespace(metadata={"roles": []})

    created = await mod.execute_tool(
        "notes.create",
        {"title": "Hello", "content": "Body", "tags": ["Foo", "bar", "foo"]},
        context=ctx,
    )
    note_id = created["note_id"]
    assert created["success"] is True
    assert created["meta"]["title"] == "Hello"

    tags_list = await mod.execute_tool("notes.tags.list", {"note_id": note_id}, context=ctx)
    assert tags_list["tags"] == ["bar", "foo"]

    added = await mod.execute_tool("notes.tags.add", {"note_id": note_id, "tags": ["Baz"]}, context=ctx)
    assert "baz" in added["tags"]

    removed = await mod.execute_tool("notes.tags.remove", {"note_id": note_id, "tags": ["foo"]}, context=ctx)
    assert "foo" not in removed["tags"]

    cleared = await mod.execute_tool("notes.tags.set", {"note_id": note_id, "tags": []}, context=ctx)
    assert cleared["tags"] == []

    updated = await mod.execute_tool(
        "notes.update",
        {"note_id": note_id, "updates": {"title": "Updated"}},
        context=ctx,
    )
    assert "title" in updated["updated_fields"]

    # List all tags (should be empty after clear)
    tags_all = await mod.execute_tool("notes.tags.list", {"limit": 10, "offset": 0}, context=ctx)
    assert tags_all["tags"] == []


@pytest.mark.asyncio
async def test_notes_delete_permanent_requires_admin():
    mod = NotesModule(ModuleConfig(name="notes"))
    fake_db = FakeNotesDB()
    mod._open_db = lambda ctx: fake_db  # type: ignore[attr-defined]

    user_ctx = SimpleNamespace(metadata={"roles": []})
    admin_ctx = SimpleNamespace(metadata={"roles": ["admin"]})

    created = await mod.execute_tool(
        "notes.create",
        {"title": "ToDelete", "content": "Body"},
        context=admin_ctx,
    )
    note_id = created["note_id"]

    with pytest.raises(PermissionError):
        await mod.execute_tool(
            "notes.delete",
            {"note_id": note_id, "permanent": True},
            context=user_ctx,
        )

    deleted = await mod.execute_tool(
        "notes.delete",
        {"note_id": note_id, "permanent": True},
        context=admin_ctx,
    )
    assert deleted["action"] == "permanently_deleted"
