from __future__ import annotations

from typing import Dict, Optional, Type

from .base import VLMBackend


def _backend_map() -> Dict[str, Type[VLMBackend]]:
    mapping: Dict[str, Type[VLMBackend]] = {}
    try:
        from .backends.hf_table_transformer import HFTableTransformerBackend

        mapping[HFTableTransformerBackend.name] = HFTableTransformerBackend
    except Exception:
        # transformers or PIL may be missing - silently ignore; available() will reflect this
        pass
    try:
        from .backends.docling_vlm import DoclingVLMBackend

        mapping[DoclingVLMBackend.name] = DoclingVLMBackend
    except Exception:
        # docling may be missing
        pass
    return mapping


def get_backend(name: Optional[str] = None) -> Optional[VLMBackend]:
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
        except Exception:
            continue
    return None


def list_backends() -> Dict[str, Dict[str, bool]]:
    """
    Return a lightweight summary of available backends.
    {
      "hf_table_transformer": {"available": true}
    }
    """
    out: Dict[str, Dict[str, bool]] = {}
    mapping = _backend_map()
    for k, cls in mapping.items():
        ok = False
        try:
            ok = bool(cls.available())
        except Exception:
            ok = False
        out[k] = {"available": ok}
    return out
