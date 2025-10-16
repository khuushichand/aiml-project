import pytest

from tldw_Server_API.app.core.Chunking.strategies.tokens import TokenChunkingStrategy


def _norm(s: str) -> str:
    return " ".join(s.split())


@pytest.mark.skipif(pytest.importorskip("tiktoken", reason="tiktoken not installed").__class__ is None, reason="tiktoken not installed")
@pytest.mark.skipif(pytest.importorskip("transformers", reason="transformers not installed").__class__ is None, reason="transformers not installed")
def test_tiktoken_vs_transformers_parity():
    text = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n"
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.\n"
        "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.\n"
        "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
    )

    # Prefer tiktoken
    s_tk = TokenChunkingStrategy(language="en", tokenizer_name="gpt-3.5-turbo")
    chunks_tk = s_tk.chunk(text, max_size=80, overlap=20)

    # Prefer transformers
    s_tf = TokenChunkingStrategy(language="en", tokenizer_name="gpt2")
    chunks_tf = s_tf.chunk(text, max_size=80, overlap=20)

    # Validate counts within tolerance (allow +/-1 window difference)
    assert abs(len(chunks_tk) - len(chunks_tf)) <= 1

    # Validate total characters decoded are broadly similar
    total_tk = sum(len(c) for c in chunks_tk)
    total_tf = sum(len(c) for c in chunks_tf)
    # Allow 20% difference due to tokenization/decoding nuances
    if max(total_tk, total_tf) > 0:
        diff = abs(total_tk - total_tf) / max(total_tk, total_tf)
        assert diff <= 0.2

