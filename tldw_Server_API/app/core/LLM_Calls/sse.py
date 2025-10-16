import json
from typing import Any, Dict, Iterable, Iterator, Optional


def finalize_stream(response: Optional[Any], done_already: bool = False) -> Iterable[str]:
    """Yield a final DONE (if not already sent) and always close the response safely.

    This is a tiny DRY helper to unify end-of-stream handling across providers.
    """
    try:
        if not done_already:
            yield sse_done()
    finally:
        try:
            if response is not None:
                response.close()
        except Exception:
            pass


def sse_data(payload: Dict[str, Any]) -> str:
    """Return an SSE data line with a blank line terminator."""
    return f"data: {json.dumps(payload)}\n\n"


def sse_done() -> str:
    """Return the SSE end-of-stream sentinel."""
    return "data: [DONE]\n\n"


def ensure_sse_line(line: str) -> str:
    """Ensure an incoming data line is terminated as SSE (with a blank line)."""
    if not line.endswith("\n\n"):
        if line.endswith("\n"):
            return line + "\n"
        return line + "\n\n"
    return line


def openai_delta_chunk(text: str) -> str:
    """Wrap a plain text delta into an OpenAI-compatible SSE chunk."""
    return sse_data({"choices": [{"delta": {"content": text}}]})
