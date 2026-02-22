import xml.etree.ElementTree as ET

from tldw_Server_API.app.core.Chunking.strategies.json_xml import XMLChunkingStrategy


def test_xml_chunk_preserves_tail_text():
    strategy = XMLChunkingStrategy()
    xml_text = "<root><item>One</item>tail<item>Two</item></root>"

    chunks = strategy.chunk(xml_text, max_size=50, overlap=0, output_format="xml")

    assert chunks
    root = ET.fromstring(chunks[0])  # nosec B314
    first_item = root.find("item")
    assert first_item is not None
    assert first_item.tail is not None
    assert first_item.tail.strip() == "tail"
