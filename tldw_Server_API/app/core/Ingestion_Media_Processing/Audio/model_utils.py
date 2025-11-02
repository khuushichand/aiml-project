from __future__ import annotations

from typing import Optional, Tuple

ALLOWED_PARAKEET_VARIANTS = {"standard", "onnx", "mlx"}


def normalize_model_and_variant(
    raw_model: Optional[str],
    current_model: str,
    current_variant: str,
    variant_override: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Normalize streaming STT model + variant selection from potentially combined identifiers.

    Rules (kept in parity with unified WebSocket handler expectations):
    - If model is hyphenated (e.g., "parakeet-onnx"):
      - When base is "parakeet" and no explicit override is given, set model="parakeet"
        and model_variant to the suffix (only if recognized), else keep current variant.
      - For non-parakeet bases (e.g., "whisper-1", "canary-1b"), collapse to base model
        ("whisper", "canary"). Suffix is ignored.
    - If an explicit override (variant/model_variant) is provided and the target model is
      Parakeet, the override wins.
    - If raw_model is None, only apply variant override when current model is Parakeet.
    """

    model_out = current_model
    variant_out = current_variant

    if raw_model is not None:
        s = str(raw_model)
        base, sep, suffix = s.partition("-")
        base_lower = base.lower()

        if base_lower == "parakeet":
            model_out = "parakeet"
            if variant_override:
                variant_out = str(variant_override).lower()
            elif sep and suffix:
                v = suffix.lower()
                if v in ALLOWED_PARAKEET_VARIANTS:
                    variant_out = v
                # else: keep existing variant
        else:
            # For non-Parakeet hyphenated names, collapse to base model to match selector logic
            model_out = base if sep else s
            # Don't apply Parakeet variant overrides to non-Parakeet models
            # variant_out unchanged
    elif variant_override and current_model.lower() == "parakeet":
        variant_out = str(variant_override).lower()

    return model_out, variant_out


__all__ = ["normalize_model_and_variant", "ALLOWED_PARAKEET_VARIANTS"]
