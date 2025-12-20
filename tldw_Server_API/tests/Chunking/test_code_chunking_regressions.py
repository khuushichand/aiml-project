from tldw_Server_API.app.core.Chunking import Chunker


def test_code_single_line_brace_block_does_not_merge_next():
    ck = Chunker()
    src = "function foo() {}\nfunction bar() {}\n"
    chunks = ck.chunk_text(
        src,
        method="code",
        max_size=30,
        overlap=0,
        language="javascript",
    )

    assert chunks == ["function foo() {}", "function bar() {}"]
