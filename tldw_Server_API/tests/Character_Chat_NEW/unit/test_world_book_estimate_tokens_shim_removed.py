from tldw_Server_API.app.core.Character_Chat.world_book_manager import WorldBookService


def test_world_book_estimate_tokens_shim_removed() -> None:
    assert not hasattr(WorldBookService, "_estimate_tokens")  # nosec B101
