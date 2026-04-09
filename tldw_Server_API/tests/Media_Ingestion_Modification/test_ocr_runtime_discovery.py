from __future__ import annotations


def test_list_ocr_backends_enriches_llamacpp_discovery(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import ocr as ocr_mod

    class _StubLlamaCppBackend:
        def describe(self):
            return {
                "mode": "remote",
                "configured_mode": "auto",
                "model": "vision.gguf",
                "configured": True,
                "supports_structured_output": True,
                "supports_json": True,
                "configured_flags": "--ctx-size 4096",
                "auto_eligible": True,
                "auto_high_quality_eligible": True,
                "url_configured": True,
                "managed_configured": False,
                "managed_running": False,
                "allow_managed_start": False,
                "cli_configured": True,
                "backend_concurrency_cap": 3,
            }

    monkeypatch.setattr(
        ocr_mod,
        "_list_backends",
        lambda: {"llamacpp": {"available": True}},
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.llamacpp_ocr.LlamaCppOCRBackend",
        _StubLlamaCppBackend,
    )

    payload = ocr_mod.list_ocr_backends()

    assert payload["llamacpp"]["available"] is True  # nosec B101
    assert payload["llamacpp"]["mode"] == "remote"  # nosec B101
    assert payload["llamacpp"]["configured_mode"] == "auto"  # nosec B101
    assert payload["llamacpp"]["model"] == "vision.gguf"  # nosec B101
    assert payload["llamacpp"]["configured"] is True  # nosec B101
    assert payload["llamacpp"]["supports_structured_output"] is True  # nosec B101
    assert payload["llamacpp"]["supports_json"] is True  # nosec B101
    assert payload["llamacpp"]["configured_flags"] == "--ctx-size 4096"  # nosec B101
    assert payload["llamacpp"]["auto_eligible"] is True  # nosec B101
    assert payload["llamacpp"]["auto_high_quality_eligible"] is True  # nosec B101
    assert payload["llamacpp"]["url_configured"] is True  # nosec B101
    assert payload["llamacpp"]["managed_configured"] is False  # nosec B101
    assert payload["llamacpp"]["cli_configured"] is True  # nosec B101
    assert payload["llamacpp"]["backend_concurrency_cap"] == 3  # nosec B101


def test_list_ocr_backends_enriches_chatllm_discovery(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import ocr as ocr_mod

    class _StubChatLLMBackend:
        def describe(self):
            return {
                "mode": "managed",
                "configured": True,
                "supports_structured_output": True,
                "supports_json": True,
                "auto_eligible": True,
                "auto_high_quality_eligible": False,
                "managed_configured": True,
                "managed_running": False,
                "allow_managed_start": True,
                "url_configured": False,
                "healthcheck_url_configured": True,
                "cli_configured": False,
                "backend_concurrency_cap": 2,
                "model": "/models/chatllm.gguf",
            }

    monkeypatch.setattr(
        ocr_mod,
        "_list_backends",
        lambda: {"chatllm": {"available": True}},
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.chatllm_ocr.ChatLLMOCRBackend",
        _StubChatLLMBackend,
    )

    payload = ocr_mod.list_ocr_backends()

    assert payload["chatllm"]["available"] is True  # nosec B101
    assert payload["chatllm"]["mode"] == "managed"  # nosec B101
    assert payload["chatllm"]["configured"] is True  # nosec B101
    assert payload["chatllm"]["supports_structured_output"] is True  # nosec B101
    assert payload["chatllm"]["supports_json"] is True  # nosec B101
    assert payload["chatllm"]["auto_eligible"] is True  # nosec B101
    assert payload["chatllm"]["auto_high_quality_eligible"] is False  # nosec B101
    assert payload["chatllm"]["managed_configured"] is True  # nosec B101
    assert payload["chatllm"]["healthcheck_url_configured"] is True  # nosec B101
    assert payload["chatllm"]["backend_concurrency_cap"] == 2  # nosec B101
