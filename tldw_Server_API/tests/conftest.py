from __future__ import annotations

import sys
import types
from typing import Any, Dict


def _install_test_stubs() -> None:
    """Registers lightweight stubs for App_Function_Libraries to satisfy imports during tests."""

    if "App_Function_Libraries" in sys.modules:
        return

    base_pkg = types.ModuleType("App_Function_Libraries")
    sys.modules["App_Function_Libraries"] = base_pkg

    summarization_pkg = types.ModuleType("App_Function_Libraries.Summarization")
    sys.modules[summarization_pkg.__name__] = summarization_pkg
    summarize_mod = types.ModuleType("App_Function_Libraries.Summarization.Summarization_General_Lib")
    summarize_mod.summarize = lambda *args, **kwargs: ""  # type: ignore[assignment]
    sys.modules[summarize_mod.__name__] = summarize_mod

    utils_pkg = types.ModuleType("App_Function_Libraries.Utils")
    sys.modules[utils_pkg.__name__] = utils_pkg

    import logging as py_logging

    utils_mod = types.ModuleType("App_Function_Libraries.Utils.Utils")
    utils_mod.loaded_config_data = {"search_engines": {}}
    utils_mod.logging = py_logging
    sys.modules[utils_mod.__name__] = utils_mod

    chat_pkg = types.ModuleType("App_Function_Libraries.Chat")
    sys.modules[chat_pkg.__name__] = chat_pkg
    chat_mod = types.ModuleType("App_Function_Libraries.Chat.Chat_Functions")
    chat_mod.chat_api_call = lambda *args, **kwargs: ""  # type: ignore[assignment]
    sys.modules[chat_mod.__name__] = chat_mod

    scraping_pkg = types.ModuleType("App_Function_Libraries.Web_Scraping")
    sys.modules[scraping_pkg.__name__] = scraping_pkg

    scraping_mod = types.ModuleType("App_Function_Libraries.Web_Scraping.Article_Extractor_Lib")

    async def dummy_scrape_article(*_: Any, **__: Any) -> Dict[str, Any]:
        return {"content": ""}

    scraping_mod.scrape_article = dummy_scrape_article  # type: ignore[assignment]
    sys.modules[scraping_mod.__name__] = scraping_mod


_install_test_stubs()
