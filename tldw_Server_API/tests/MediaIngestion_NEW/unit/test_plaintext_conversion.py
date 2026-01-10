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


@pytest.mark.unit
def test_convert_document_to_text_rejects_outside_base_dir(tmp_path):
     base_dir = tmp_path / "base"
    base_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="outside allowed base directory"):
        docs.convert_document_to_text(outside, base_dir=base_dir)
