from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext import Plaintext_Files as docs


@pytest.mark.unit
def test_convert_document_to_text_requires_defusedxml(monkeypatch, tmp_path):
    xml_path = tmp_path / "sample.xml"
    xml_path.write_text("<root><value>1</value></root>", encoding="utf-8")

    monkeypatch.setattr(docs, "_DEFUSED_AVAILABLE", False)
    monkeypatch.setattr(docs, "DET", None)

    with pytest.raises(ValueError, match="defusedxml"):
        docs.convert_document_to_text(xml_path)
