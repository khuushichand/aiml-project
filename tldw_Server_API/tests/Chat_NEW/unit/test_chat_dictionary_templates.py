from __future__ import annotations

import os
import re

from tldw_Server_API.app.core.Chat.chat_dictionary import (
    ChatDictionary,
    apply_replacement_once,
    process_user_input,
)


def _enable_templates():


    os.environ["CHAT_DICT_TEMPLATES_ENABLED"] = "1"
    os.environ["TEMPLATE_DEFAULT_TZ"] = "UTC"


def test_literal_replacement_fast_path_when_disabled():


     # Templates disabled by default per PRD. Ensure normal replacement works.
    entry = ChatDictionary(key="today", content="It is TODAY")
    out = process_user_input("I said today already.", [entry])
    assert "It is TODAY" in out


def test_literal_templating_enabled_now_function():


    _enable_templates()
    entry = ChatDictionary(key="today", content="Year={{ now('%Y', tz='UTC') }}")
    text = "today is a keyword"
    out = process_user_input(text, [entry])
    assert "Year=" in out
    assert re.search(r"Year=\d{4}", out)


def test_regex_templating_with_group():


    _enable_templates()
    entry = ChatDictionary(key=r"/price\s+(\w+)/", content="{{ match.group(1)|upper }} is priced")
    text = "The price widget should be evaluated."
    new_text, count = apply_replacement_once(text, entry)
    assert count >= 1
    assert "WIDGET is priced" in new_text


def test_entry_override_disables_templates_when_global_enabled():


    _enable_templates()
    entry = ChatDictionary(
        key="today",
        content="Year={{ now('%Y', tz='UTC') }}",
        enable_templates=False,
    )
    out = process_user_input("today", [entry])
    assert "Year={{ now('%Y', tz='UTC') }}" in out


def test_entry_override_forces_templates_without_auto_detect():


    _enable_templates()
    # No "{{" present, but forced rendering should still execute render path
    # and preserve plain text as-is.
    entry = ChatDictionary(
        key="today",
        content="plain replacement text",
        enable_templates=True,
    )
    out = process_user_input("today", [entry])
    assert "plain replacement text" in out
