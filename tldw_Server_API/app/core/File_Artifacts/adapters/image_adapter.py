"""File artifact adapter for image generation."""

from __future__ import annotations

from typing import Any

from loguru import logger

from tldw_Server_API.app.core.exceptions import FileArtifactsError, FileArtifactsValidationError
from tldw_Server_API.app.core.File_Artifacts.adapters.base import ExportResult, ValidationIssue
from tldw_Server_API.app.core.Image_Generation.adapter_registry import get_registry
from tldw_Server_API.app.core.Image_Generation.adapters.base import ImageGenRequest
from tldw_Server_API.app.core.Image_Generation.config import get_image_generation_config
from tldw_Server_API.app.core.Image_Generation.exceptions import ImageBackendUnavailableError, ImageGenerationError


class ImageAdapter:
    file_type = "image"
    export_formats = {"png", "jpg", "webp"}

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise FileArtifactsValidationError("image_params_invalid")

        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise FileArtifactsValidationError("image_params_invalid")

        backend = payload.get("backend")
        backend_name = str(backend).strip() if backend is not None else None
        registry = get_registry()
        resolved_backend = registry.resolve_backend(backend_name)
        if not resolved_backend:
            raise FileArtifactsError("image_backend_unavailable")

        structured = {
            "backend": resolved_backend,
            "prompt": prompt.strip(),
            "negative_prompt": self._string_or_none(payload.get("negative_prompt")),
            "width": self._int_or_none(payload.get("width")),
            "height": self._int_or_none(payload.get("height")),
            "steps": self._int_or_none(payload.get("steps")),
            "cfg_scale": self._float_or_none(payload.get("cfg_scale")),
            "seed": self._int_or_none(payload.get("seed")),
            "sampler": self._string_or_none(payload.get("sampler")),
            "model": self._string_or_none(payload.get("model")),
            "extra_params": payload.get("extra_params") or {},
        }

        if not isinstance(structured["extra_params"], dict):
            raise FileArtifactsValidationError("image_params_invalid")

        return structured

    def validate(self, structured: dict[str, Any]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        config = get_image_generation_config()

        prompt = structured.get("prompt")
        if isinstance(prompt, str) and len(prompt) > config.max_prompt_length:
            issues.append(
                ValidationIssue(
                    code="image_params_invalid",
                    message="prompt exceeds max length",
                    path="prompt",
                )
            )

        width = structured.get("width")
        height = structured.get("height")
        if width is not None and (width <= 0 or width > config.max_width):
            issues.append(
                ValidationIssue(
                    code="image_params_invalid",
                    message="width out of range",
                    path="width",
                )
            )
        if height is not None and (height <= 0 or height > config.max_height):
            issues.append(
                ValidationIssue(
                    code="image_params_invalid",
                    message="height out of range",
                    path="height",
                )
            )
        if isinstance(width, int) and isinstance(height, int) and width * height > config.max_pixels:
            issues.append(
                ValidationIssue(
                    code="image_params_invalid",
                    message="image dimensions exceed max pixels",
                    path="width,height",
                )
            )

        steps = structured.get("steps")
        if steps is not None and (steps <= 0 or steps > config.max_steps):
            issues.append(
                ValidationIssue(
                    code="image_params_invalid",
                    message="steps out of range",
                    path="steps",
                )
            )

        self._validate_extra_params(structured, config, issues)

        return issues

    def export(self, structured: dict[str, Any], *, format: str) -> ExportResult:
        backend = structured.get("backend")
        if not backend:
            raise FileArtifactsError("image_backend_unavailable")

        registry = get_registry()
        adapter = registry.get_adapter(str(backend))
        if adapter is None:
            raise FileArtifactsError("image_backend_unavailable")

        request = ImageGenRequest(
            backend=str(backend),
            prompt=str(structured.get("prompt") or ""),
            negative_prompt=self._string_or_none(structured.get("negative_prompt")),
            width=structured.get("width"),
            height=structured.get("height"),
            steps=structured.get("steps"),
            cfg_scale=structured.get("cfg_scale"),
            seed=structured.get("seed"),
            sampler=self._string_or_none(structured.get("sampler")),
            model=self._string_or_none(structured.get("model")),
            format=format,
            extra_params=structured.get("extra_params") or {},
        )

        try:
            result = adapter.generate(request)
        except ImageBackendUnavailableError as exc:
            raise FileArtifactsError("image_backend_unavailable", detail=str(exc)) from exc
        except ImageGenerationError as exc:
            raise FileArtifactsError("image_generation_failed", detail=str(exc)) from exc
        except Exception as exc:
            logger.warning("image adapter: backend generate failed: {}", exc)
            raise FileArtifactsError("image_generation_failed", detail=str(exc)) from exc

        return ExportResult(
            status="ready",
            content_type=result.content_type,
            bytes_len=result.bytes_len,
            content=result.content,
        )

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise FileArtifactsValidationError("image_params_invalid") from None

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            raise FileArtifactsValidationError("image_params_invalid") from None

    @staticmethod
    def _allowed_extra_params(backend: str, config) -> set[str]:
        if backend == "stable_diffusion_cpp":
            return set(config.sd_cpp_allowed_extra_params or [])
        if backend == "swarmui":
            return set(config.swarmui_allowed_extra_params or [])
        if backend == "openrouter":
            return set(config.openrouter_image_allowed_extra_params or [])
        if backend == "novita":
            return set(config.novita_image_allowed_extra_params or [])
        if backend == "together":
            return set(config.together_image_allowed_extra_params or [])
        if backend == "modelstudio":
            return set(config.modelstudio_image_allowed_extra_params or [])
        return set()

    def _validate_extra_params(
        self,
        structured: dict[str, Any],
        config,
        issues: list[ValidationIssue],
    ) -> None:
        extra_params = structured.get("extra_params") or {}
        if not extra_params:
            return
        backend = str(structured.get("backend") or "").strip()
        allowlist = self._allowed_extra_params(backend, config)
        if not allowlist:
            for key in extra_params:
                issues.append(
                    ValidationIssue(
                        code="image_params_invalid",
                        message="extra_params key not allowlisted",
                        path=f"extra_params.{key}",
                    )
                )
            return
        for key in extra_params:
            if key not in allowlist:
                issues.append(
                    ValidationIssue(
                        code="image_params_invalid",
                        message="extra_params key not allowlisted",
                        path=f"extra_params.{key}",
                    )
                )
        if "cli_args" in extra_params and "cli_args" in allowlist:
            cli_args = extra_params.get("cli_args")
            if not isinstance(cli_args, (list, tuple)):
                issues.append(
                    ValidationIssue(
                        code="image_params_invalid",
                        message="cli_args must be a list",
                        path="extra_params.cli_args",
                    )
                )
