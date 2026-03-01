from tldw_Server_API.app.core.Character_Chat.chat_dictionary import ChatDictionaryService


def test_chat_dictionary_estimate_tokens_shim_removed() -> None:
    assert not hasattr(ChatDictionaryService, "_estimate_tokens")  # nosec B101
