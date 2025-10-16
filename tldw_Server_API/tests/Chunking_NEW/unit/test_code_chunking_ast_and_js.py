import pytest

from tldw_Server_API.app.core.Chunking.chunker import Chunker


PY_SAMPLE = """
import os
import sys

def foo(x):
    return x + 1

class Bar:
    def baz(self):
        return 42
""".strip()


JS_SAMPLE = """
import x from 'x'

export default class App {
  start() { return 1 }
}

export const hello = (name) => {
  return `Hi ${name}`;
}
export default function run() { return 2 }
export default () => { return 3 }
export interface Foo { a: string }
export type T = { b: number }
""".strip()


def test_python_code_ast_mode_metadata_and_chunks():
    ch = Chunker()
    rows = ch.process_text(
        PY_SAMPLE,
        options={
            'method': 'code',
            'language': 'python',
            'code_mode': 'ast',
            'max_size': 500,
            'overlap': 0,
        },
    )
    assert isinstance(rows, list) and len(rows) >= 1
    # Metadata normalization should include standardized keys
    md = rows[0]['metadata']
    assert md.get('chunk_method') == 'code'
    assert 'max_size' in md and 'overlap' in md
    assert md.get('code_mode_used') == 'ast'


def test_python_code_auto_mode_sets_flag():
    ch = Chunker()
    rows = ch.process_text(
        PY_SAMPLE,
        options={
            'method': 'code',
            'language': 'python',
            'code_mode': 'auto',
            'max_size': 500,
            'overlap': 0,
        },
    )
    assert isinstance(rows, list) and len(rows) >= 1
    md = rows[0]['metadata']
    assert md.get('chunk_method') == 'code'
    assert md.get('code_mode_used') == 'auto'


def test_javascript_code_chunking_detects_blocks_content():
    ch = Chunker()
    rows = ch.process_text(
        JS_SAMPLE,
        options={
            'method': 'code',
            'language': 'javascript',
            'max_size': 1000,
            'overlap': 0,
        },
    )
    assert isinstance(rows, list) and len(rows) >= 1
    joined = "\n\n".join(r['text'] for r in rows)
    assert 'class App' in joined
    assert 'const hello' in joined
    assert 'export default function run' in joined or 'function run' in joined
    assert 'export interface Foo' in joined or 'interface Foo' in joined
