import pytest

from tldw_Server_API.app.core.Chunking.chunker import Chunker


TS_SAMPLE = """
export interface IUser {
  id: number
}

export type Point = { x: number; y: number }

export const sum = (a: number, b: number) => {
  return a + b
}
""".strip()


@pytest.mark.unit
def test_typescript_interface_and_type_blocks_present_in_metadata():
    ch = Chunker()
    # Use metadata call to assert block kinds recognized
    results = ch.chunk_text_with_metadata(
        TS_SAMPLE,
        method='code',
        max_size=200,
        overlap=0,
        language='typescript',
    )
    assert isinstance(results, list) and len(results) >= 1
    seen_kinds = set()
    for r in results:
        md = r.metadata
        opts = (md.options or {}) if hasattr(md, 'options') else {}
        blocks = opts.get('blocks') or []
        for b in blocks:
            t = str(b.get('type', '')).lower()
            if t:
                seen_kinds.add(t)
    # Ensure both 'interface' and 'type' blocks were identified
    assert 'interface' in seen_kinds
    assert 'type' in seen_kinds

