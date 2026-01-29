import pytest

from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import (
    KanbanDBRetriever,
    MultiDatabaseRetriever,
    RetrievalConfig,
)
from tldw_Server_API.app.core.RAG.rag_service.types import DataSource


pytestmark = pytest.mark.unit


@pytest.fixture
def kanban_db(tmp_path, monkeypatch):
    base_dir = tmp_path / "user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    db_path = DatabasePaths.get_kanban_db_path("1")
    db = KanbanDB(db_path=str(db_path), user_id="1")
    yield db
    db.close()


@pytest.fixture
def sample_card(kanban_db):
    board = kanban_db.create_board(name="Test Board", client_id="board-1")
    lst = kanban_db.create_list(board_id=board["id"], name="Todo", client_id="list-1")
    return kanban_db.create_card(
        list_id=lst["id"],
        title="RAG Card",
        description="Hello from kanban",
        client_id="card-1",
    )


@pytest.mark.asyncio
async def test_kanban_retriever_fts(kanban_db, sample_card):
    retriever = KanbanDBRetriever(
        db_path=str(kanban_db.db_path),
        config=RetrievalConfig(max_results=5, use_fts=True, use_vector=False),
        user_id="1",
    )
    docs = await retriever.retrieve("RAG")
    assert docs
    doc = docs[0]
    assert doc.source == DataSource.KANBAN
    assert "RAG Card" in doc.content
    assert doc.metadata.get("card_id") == sample_card["id"]


def test_multi_retriever_includes_kanban(kanban_db):
    retriever = MultiDatabaseRetriever({"kanban_db": str(kanban_db.db_path)}, user_id="1")
    assert DataSource.KANBAN in retriever.retrievers
