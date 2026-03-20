import io
from contextlib import contextmanager

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import XML_Ingestion_Lib as xml_lib


@pytest.mark.unit
def test_import_xml_handler_reports_malformed_input(monkeypatch):
    if not xml_lib._DEFUSED_AVAILABLE:
        pytest.skip("defusedxml not installed")

    monkeypatch.setattr(
        xml_lib,
        "managed_media_database",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("db should not be opened for malformed XML")),
        raising=False,
    )
    monkeypatch.setattr(xml_lib, "add_media_with_keywords", lambda **kwargs: {"status": "ok"})

    malformed_xml = io.BytesIO(b"<root><unclosed>")

    result = xml_lib.import_xml_handler(
        import_file=malformed_xml,
        title="Broken XML",
        author="Tester",
        keywords="",
        system_prompt=None,
        custom_prompt=None,
        auto_summarize=False,
        api_name=None,
        api_key=None,
    )

    assert "Error parsing XML file" in result


@pytest.mark.unit
def test_import_xml_handler_uses_managed_media_database(monkeypatch):
    if not xml_lib._DEFUSED_AVAILABLE:
        pytest.skip("defusedxml not installed")

    class _FakeDb:
        def __init__(self) -> None:
            self.closed = False

        def close_connection(self) -> None:
            self.closed = True

    fake_db = _FakeDb()
    managed_calls: list[dict[str, object]] = []
    captured_add_calls: list[dict[str, object]] = []

    @contextmanager
    def _fake_managed_media_database(client_id, *, initialize=True, **kwargs):
        managed_calls.append(
            {
                "client_id": client_id,
                "initialize": initialize,
                "kwargs": kwargs,
            }
        )
        try:
            yield fake_db
        finally:
            fake_db.close_connection()

    def _fake_add_media_with_keywords(**kwargs):
        captured_add_calls.append(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(xml_lib, "managed_media_database", _fake_managed_media_database, raising=False)
    monkeypatch.setattr(
        xml_lib,
        "create_media_database",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("legacy raw factory should not be used")),
        raising=False,
    )
    monkeypatch.setattr(xml_lib, "add_media_with_keywords", _fake_add_media_with_keywords)

    xml_file = io.BytesIO(b"<root><item>Hello</item><item>World</item></root>")

    result = xml_lib.import_xml_handler(
        import_file=xml_file,
        title="XML Title",
        author="Tester",
        keywords="xml,import",
        system_prompt=None,
        custom_prompt="custom prompt",
        auto_summarize=False,
        api_name=None,
        api_key=None,
    )

    assert "import complete" in result
    assert fake_db.closed is True
    assert managed_calls == [
        {
            "client_id": "xml_import",
            "initialize": False,
            "kwargs": {},
        }
    ]
    assert len(captured_add_calls) == 1
    assert captured_add_calls[0]["db_instance"] is fake_db
    assert captured_add_calls[0]["url"] == "uploaded.xml"
    assert captured_add_calls[0]["info_dict"]["title"] == "XML Title"
    assert captured_add_calls[0]["keywords"] == ["xml", "import"]
