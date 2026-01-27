"""
Audio capture and playback utilities.

Requires optional dependencies:
    pip install tldw-voice-assistant[audio]
"""

try:
    from .capture import AudioCapture
    from .player import AudioPlayer

    __all__ = ["AudioCapture", "AudioPlayer"]
except ImportError as e:
    raise ImportError(
        "Audio support requires additional dependencies. "
        "Install with: pip install tldw-voice-assistant[audio]"
    ) from e
