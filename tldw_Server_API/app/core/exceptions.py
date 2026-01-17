from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
from typing import Any, Optional


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


class TranscriptionCancelled(RuntimeError):
    """Raised when transcription/conversion is cancelled."""


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


class StoragePathValidationError(Exception):
    """Base exception for storage path validation failures."""


class InvalidStoragePathError(StoragePathValidationError):
    """Raised when a storage path is invalid or outside its allowed base."""


class StorageUnavailableError(StoragePathValidationError):
    """Raised when storage base directories cannot be resolved."""


class InvalidStorageUserIdError(StoragePathValidationError):
    """Raised when a storage path resolution is attempted with an invalid user id."""


class UnsafeUserPathError(StoragePathValidationError):
    """Raised when a user-derived path escapes an allowed base directory."""


class AdminDataOpsError(ValueError):
    """Base exception for admin data ops validation errors."""


class UnknownBackupDatasetError(AdminDataOpsError):
    """Raised when a backup request references an unknown dataset."""


class InvalidBackupUserIdError(AdminDataOpsError):
    """Raised when a backup request references an invalid user id."""


class InvalidBackupPathError(AdminDataOpsError):
    """Raised when a backup path is invalid or unsafe."""


class InvalidBackupIdError(AdminDataOpsError):
    """Raised when a backup id is malformed or unsafe."""


class InvalidRetentionPolicyError(AdminDataOpsError):
    """Raised when a retention policy key is unknown."""


class InvalidRetentionRangeError(AdminDataOpsError):
    """Raised when a retention policy update is out of range."""


class TemplateStoreError(Exception):
    """Base exception for watchlist template store errors."""


class TemplateValidationError(TemplateStoreError, ValueError):
    """Raised when a watchlist template validation check fails."""


class InvalidTemplateNameError(TemplateValidationError):
    """Raised when a template name fails validation."""


class InvalidTemplateFormatError(TemplateValidationError):
    """Raised when a template format is invalid."""


class InvalidTemplatePathError(TemplateValidationError):
    """Raised when a template path escapes the allowed base directory."""


class InvalidSecretRedactionParametersError(ValueError):
    """Raised when secret redaction parameters are invalid."""

    def __init__(self, message: str = "head and tail must be non-negative"):
        super().__init__(message)


class FileArtifactsError(Exception):
    """Base exception for file artifact operations."""

    def __init__(self, code: str, detail: Any | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


class FileArtifactsValidationError(FileArtifactsError):
    """Raised when file artifacts payload validation fails."""


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


class WorkflowAdapterError(Exception):
    """Base exception for workflow adapter errors."""


class AdapterError(WorkflowAdapterError):
    """Workflow adapter-specific error."""


async def video_processing_exception_handler(
    _request: Request,
    exc: VideoProcessingError,
) -> JSONResponse:
    logger.error("Video processing failed: {}", exc)
    return JSONResponse(
        status_code=500,
        content={"message": f"An error occurred during video processing: {exc!s}"},
    )


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(VideoProcessingError, video_processing_exception_handler)
