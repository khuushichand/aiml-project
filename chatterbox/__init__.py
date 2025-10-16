try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:  # Python <3.8
    from importlib_metadata import version, PackageNotFoundError  # type: ignore

# Be resilient when vendored: version metadata may not exist
try:
    __version__ = version("chatterbox-tts")
except Exception:  # PackageNotFoundError or other metadata issues
    __version__ = "0.0.0"

# Lazy attribute access to avoid importing heavy dependencies at module import time.
# The tldw adapter probes `import chatterbox` during initialization; defer heavy
# imports (transformers, torchaudio, huggingface_hub, perth, etc.) until actually used.
def __getattr__(name: str):
    if name == "ChatterboxTTS":
        from .tts import ChatterboxTTS  # noqa: WPS433
        return ChatterboxTTS
    if name == "ChatterboxVC":
        from .vc import ChatterboxVC  # noqa: WPS433
        return ChatterboxVC
    if name == "ChatterboxMultilingualTTS":
        from .mtl_tts import ChatterboxMultilingualTTS  # noqa: WPS433
        return ChatterboxMultilingualTTS
    if name == "SUPPORTED_LANGUAGES":
        from .mtl_tts import SUPPORTED_LANGUAGES  # noqa: WPS433
        return SUPPORTED_LANGUAGES
    raise AttributeError(name)

