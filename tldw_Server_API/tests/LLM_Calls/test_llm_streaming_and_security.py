import json


def test_google_stream_emits_done_once(monkeypatch):
    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, **kwargs):
            class _Resp:
                status_code = 200

                def raise_for_status(self):
                    return None

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def iter_lines(self):
                    first_chunk = {
                        "candidates": [
                            {"content": {"parts": [{"text": "hello"}]}}
                        ]
                    }
                    return iter(
                        [
                            f"data: {json.dumps(first_chunk)}".encode("utf-8"),
                            b"data: [DONE]",
                        ]
                    )

                def close(self):
                    return None

            return _Resp()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.providers.google_adapter.http_client_factory",
        lambda *a, **k: _Client(),
    )

    from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call

    gen = perform_chat_api_call(
        api_provider="google",
        messages=[{"role": "user", "content": "hi"}],
        api_key="test-key",
        model="gemini-1.5-flash-latest",
        streaming=True,
    )
    chunks = list(gen)

    done_count = sum(1 for c in chunks if c.strip().lower() == "data: [done]")
    assert done_count == 1, f"Expected exactly one [DONE], got {done_count}. Chunks: {chunks}"


def test_huggingface_headers_are_masked(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call as _perform_chat

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            class _Resp:
                status_code = 200

                def raise_for_status(self):
                    return None

                def json(self):
                    return {"id": "ok", "choices": [{"message": {"content": "hi"}}]}

                def close(self):
                    return None

            return _Resp()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter.http_client_factory",
        lambda *a, **k: _Client(),
    )

    captured_debug = []

    def _fake_debug(msg, *args, **kwargs):
        rendered = str(msg)
        if args:
            try:
                rendered = rendered.format(*args)
            except Exception:
                rendered = f"{msg} {args}"
        captured_debug.append(rendered)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter.logger.debug",
        _fake_debug,
    )

    secret = "sk-ABCDEF1234567890"
    _perform_chat(
        api_provider="huggingface",
        messages=[{"role": "user", "content": "hi"}],
        api_key=secret,
        streaming=False,
        model="test/Model-Stub",
    )

    joined = "\n".join(captured_debug)
    assert "HuggingFace headers:" in joined
    assert secret not in joined
    assert "***" in joined
