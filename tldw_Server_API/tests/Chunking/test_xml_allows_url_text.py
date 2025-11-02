from tldw_Server_API.app.core.Chunking.strategies.json_xml import XMLChunkingStrategy


def test_xml_allows_urls_in_text_nodes():
    strategy = XMLChunkingStrategy()
    xml = (
        '<?xml version="1.0"?>\n'
        '<root>\n'
        '  <info>Please visit http://example.com for details.</info>\n'
        '</root>'
    )
    chunks = strategy.chunk(xml, max_size=50)
    assert isinstance(chunks, list)
    assert len(chunks) > 0
