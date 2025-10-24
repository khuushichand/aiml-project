import io

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import XML_Ingestion_Lib as xml_lib


@pytest.mark.unit
def test_import_xml_handler_reports_malformed_input(monkeypatch):
    if not xml_lib._DEFUSED_AVAILABLE:
        pytest.skip("defusedxml not installed")

    monkeypatch.setattr(xml_lib, "create_media_database", lambda client_id: "db_stub")
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
