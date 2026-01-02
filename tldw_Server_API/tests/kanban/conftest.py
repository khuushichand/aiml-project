# tldw_Server_API/tests/kanban/conftest.py
"""
Pytest fixtures for Kanban database tests.
"""
import shutil
import tempfile
from typing import Generator

import pytest

from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


@pytest.fixture
def temp_db_dir(monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """Create a temporary directory that persists for the entire test."""
    tmpdir = tempfile.mkdtemp()
    monkeypatch.setenv("USER_DB_BASE_DIR", tmpdir)
    yield tmpdir
    # Clean up after the test is completely done
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def temp_db_path(temp_db_dir: str) -> str:
    """Create a temporary database file path."""
    return str(DatabasePaths.get_kanban_db_path("test_user_1"))


@pytest.fixture
def kanban_db(temp_db_path: str) -> Generator[KanbanDB, None, None]:
    """Create a KanbanDB instance with a temporary database."""
    db = KanbanDB(db_path=temp_db_path, user_id="test_user_1")
    yield db
    # No cleanup needed - temp_db_dir fixture handles it


@pytest.fixture
def kanban_db_user2(temp_db_dir: str) -> Generator[KanbanDB, None, None]:
    """Create a second KanbanDB instance for testing user isolation."""
    db_path = DatabasePaths.get_kanban_db_path("test_user_2")
    db = KanbanDB(db_path=str(db_path), user_id="test_user_2")
    yield db


@pytest.fixture
def sample_board(kanban_db: KanbanDB) -> dict:
    """Create a sample board for testing."""
    return kanban_db.create_board(
        name="Test Board",
        client_id="board-client-1",
        description="A test board"
    )


@pytest.fixture
def sample_list(kanban_db: KanbanDB, sample_board: dict) -> dict:
    """Create a sample list for testing."""
    return kanban_db.create_list(
        board_id=sample_board["id"],
        name="Test List",
        client_id="list-client-1"
    )


@pytest.fixture
def sample_card(kanban_db: KanbanDB, sample_list: dict) -> dict:
    """Create a sample card for testing."""
    return kanban_db.create_card(
        list_id=sample_list["id"],
        title="Test Card",
        client_id="card-client-1",
        description="A test card"
    )
