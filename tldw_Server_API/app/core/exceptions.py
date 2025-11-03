from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class VideoProcessingError(Exception):
    """Raised when video processing fails."""


class EgressPolicyError(Exception):
    """Raised when an outbound URL violates the egress/SSRF policy."""


class NetworkError(Exception):
    """Raised for network transport errors (connect/read timeouts, DNS, TLS, etc.)."""


class RetryExhaustedError(Exception):
    """Raised when a request exhausts all retry attempts without success."""


class JSONDecodeError(Exception):
    """Raised when a response expected to be JSON cannot be decoded or is invalid."""


class StreamingProtocolError(Exception):
    """Raised for streaming protocol violations (e.g., malformed SSE)."""


class DownloadError(Exception):
    """Raised when a download fails or post-download validation fails (checksum, size)."""


async def video_processing_exception_handler(request: Request, exc: VideoProcessingError):
    return JSONResponse(
        status_code=500,
        content={"message": f"An error occurred during video processing: {str(exc)}"},
    )


def setup_exception_handlers(app):
    app.add_exception_handler(VideoProcessingError, video_processing_exception_handler)
