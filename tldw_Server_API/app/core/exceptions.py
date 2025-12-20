from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional


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


class SecurityAlertWebhookError(Exception):
    """Raised when delivery of a security alert to a webhook fails.

    Carries a concise message including HTTP status and a truncated response body
    to aid debugging without leaking excessive data.
    """


class SecurityAlertEmailError(Exception):
    """Raised when delivery of a security alert via email fails.

    Message should concisely describe the failure (e.g., STARTTLS/login/send).
    """


class SecurityAlertFileError(Exception):
    """Raised when writing a security alert to a file sink fails."""


class ResourceNotFoundError(Exception):
    """Generic resource-not-found error for domain-level lookups."""

    def __init__(self, resource: str, identifier: Optional[str] = None, detail: Optional[str] = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{message}: {identifier}"
        if detail:
            message = f"{message} ({detail})"
        super().__init__(message)
        self.resource = resource
        self.identifier = identifier
        self.detail = detail


class InactiveUserError(Exception):
    """Raised when an authenticated user account is inactive."""


class ServiceInitializationError(Exception):
    """Raised when a service fails to initialize or coordination fails."""


class ServiceInitializationTimeoutError(ServiceInitializationError):
    """Raised when a service initialization exceeds its timeout."""


async def video_processing_exception_handler(request: Request, exc: VideoProcessingError):
    return JSONResponse(
        status_code=500,
        content={"message": f"An error occurred during video processing: {str(exc)}"},
    )


def setup_exception_handlers(app):
    app.add_exception_handler(VideoProcessingError, video_processing_exception_handler)
