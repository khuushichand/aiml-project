"""
tldw Voice Assistant SDK

A Python SDK for connecting to tldw_server voice assistant.
Supports real-time audio streaming, STT, and TTS.
"""

from .client import VoiceAssistantClient, VoiceAssistantConfig
from .types import (
    VoiceAssistantState,
    VoiceActionType,
    WSMessageType,
    TranscriptionResult,
    IntentResult,
    ActionResult,
)

__version__ = "0.1.0"
__all__ = [
    "VoiceAssistantClient",
    "VoiceAssistantConfig",
    "VoiceAssistantState",
    "VoiceActionType",
    "WSMessageType",
    "TranscriptionResult",
    "IntentResult",
    "ActionResult",
]
