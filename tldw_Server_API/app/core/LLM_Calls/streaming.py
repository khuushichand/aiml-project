"""
Common streaming helpers for LLM providers.

These utilities standardize how we iterate provider streams and normalize
their output into OpenAI-compatible SSE chunks. They intentionally suppress
forwarding a provider's own [DONE] line; callers should append a single
final sentinel using sse_done()/finalize_stream to avoid duplicates.
"""

from typing import Iterator, AsyncIterator

import requests
import httpx

from .sse import normalize_provider_line, is_done_line, sse_data


def iter_sse_lines_requests(response: requests.Response, *, decode_unicode: bool = True, provider: str = "provider") -> Iterator[str]:
    """Yield normalized SSE lines from a requests.Response stream.

    - Skips blank/control lines and suppresses provider [DONE] frames
      (caller should append a final sentinel once).
    - Wraps unexpected payloads as OpenAI delta chunks.
    - Converts common transport errors into SSE error payloads rather than
      raising mid-stream.
    """
    try:
        for raw_line in response.iter_lines(decode_unicode=decode_unicode):
            if not raw_line:
                continue
            # raw_line can be bytes when decode_unicode=False
            line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, (bytes, bytearray)) else str(raw_line)
            if not line:
                continue
            if is_done_line(line):
                # Suppress forwarding provider's [DONE]; caller will append one.
                continue
            normalized = normalize_provider_line(line)
            if normalized is None:
                continue
            yield normalized
    except requests.exceptions.ChunkedEncodingError as e_chunk:
        # Surface as an SSE error frame so the client can handle gracefully
        yield sse_data({"error": {"message": f"Stream connection error: {str(e_chunk)}", "type": f"{provider}_stream_error"}})
    except Exception as e_stream:
        yield sse_data({"error": {"message": f"Stream iteration error: {str(e_stream)}", "type": f"{provider}_stream_error"}})


async def aiter_sse_lines_httpx(resp: httpx.Response, *, provider: str = "provider") -> AsyncIterator[str]:
    """Async iterator of normalized SSE lines for an httpx streaming response.

    - Skips provider [DONE] frames; callers should append one final sentinel.
    - Wraps unexpected payloads as OpenAI delta chunks.
    - Converts transport errors during iteration into SSE error payloads.
    """
    try:
        async for line in resp.aiter_lines():
            if not line:
                continue
            if is_done_line(line):
                continue
            normalized = normalize_provider_line(line)
            if normalized is None:
                continue
            yield normalized
    except httpx.HTTPError as e_stream:
        yield sse_data({"error": {"message": f"Stream iteration error: {str(e_stream)}", "type": f"{provider}_stream_error"}})
    except Exception as e_stream:
        yield sse_data({"error": {"message": f"Stream iteration error: {str(e_stream)}", "type": f"{provider}_stream_error"}})
