from __future__ import annotations

from .base import VLMBackend

_BACKEND_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _backend_map() -> dict[str, type[VLMBackend]]:
    mapping: dict[str, type[VLMBackend]] = {}
    try:
        from .backends.hf_table_transformer import HFTableTransformerBackend

        mapping[HFTableTransformerBackend.name] = HFTableTransformerBackend
    except ImportError:
        # transformers or PIL may be missing - silently ignore; available() will reflect this
        pass
    try:
        from .backends.docling_vlm import DoclingVLMBackend

        mapping[DoclingVLMBackend.name] = DoclingVLMBackend
    except ImportError:
        # docling may be missing
        pass
    return mapping


def get_backend(name: str | None = None) -> VLMBackend | None:
    """
    Resolve a VLM backend by name, or pick the first available when name=None.
    """
    mapping = _backend_map()
    if name:
        cls = mapping.get(name)
        if cls and cls.available():
            return cls()
        return None

    # Auto-select the first available backend
    for _, cls in mapping.items():
        try:
            if cls.available():
                return cls()
        except _BACKEND_NONCRITICAL_EXCEPTIONS:
            continue
    return None


def list_backends() -> dict[str, dict[str, bool]]:
    """
    Return a lightweight summary of available backends.
    {
      "hf_table_transformer": {"available": true}
    }
    """
    out: dict[str, dict[str, bool]] = {}
    mapping = _backend_map()
    for k, cls in mapping.items():
        ok = False
        try:
            ok = bool(cls.available())
        except _BACKEND_NONCRITICAL_EXCEPTIONS:
            ok = False
        out[k] = {"available": ok}
    return out
