"""Local LLM inference exception types.

Defines a small hierarchy of exceptions for the Local_LLM module.
"""

# Base class
class LLMInferenceLibError(Exception):
    """Base exception for the Local LLM inference library."""
    pass

# Backwards-compatibility alias (fix prior typo while avoiding import breaks)
LLMInfereceLibError = LLMInferenceLibError


class ModelNotFoundError(LLMInferenceLibError):
    """Raised when a model is not found."""
    pass


class ModelDownloadError(LLMInferenceLibError):
    """Raised when a model download fails."""
    pass


class ServerError(LLMInferenceLibError):
    """Raised for server-related errors (start, stop, connection)."""
    pass


class InferenceError(LLMInferenceLibError):
    """Raised during model inference."""
    pass

# End of LLM_Inference_Exceptions.py
