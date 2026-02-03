from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.registry import (
    list_backends as _list_backends,
)

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.get("/backends")
def list_ocr_backends() -> dict[str, Any]:
    """List available OCR backends with lightweight health information."""
    out = _list_backends()

    # Enrich with backend-specific details without heavy loading
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.points_reader import (
            PointsReaderBackend,
        )
        out.setdefault("points", {})
        out["points"]["mode"] = PointsReaderBackend().describe().get("mode")
        # If SGLang configured, attempt a quick availability check
        url = PointsReaderBackend().describe().get("url")
        if url:
            try:
                from tldw_Server_API.app.core.http_client import create_client as _create_client
                with _create_client(timeout=1.5) as _c:
                    r = _c.get(url.rsplit("/v1", 1)[0] + "/v1/models")
                    out["points"]["sglang_reachable"] = r.status_code in (200, 401)
            except Exception:
                out["points"]["sglang_reachable"] = False
    except Exception:
        pass

    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.dots_ocr import (
            DotsOCRBackend,
        )
        dots_desc = DotsOCRBackend().describe()
        out.setdefault("dots", {}).update({"prompt": dots_desc.get("prompt")})
        vllm = dots_desc.get("vllm_url")
        if vllm:
            try:
                from tldw_Server_API.app.core.http_client import create_client as _create_client
                with _create_client(timeout=1.5) as _c:
                    r = _c.get(vllm.rsplit("/v1", 1)[0] + "/v1/models")
                    out["dots"]["vllm_reachable"] = r.status_code in (200, 401)
            except Exception:
                out["dots"]["vllm_reachable"] = False
    except Exception:
        pass

    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.hunyuan_ocr import (
            HunyuanOCRBackend,
        )
        hun_desc = HunyuanOCRBackend().describe()
        out.setdefault("hunyuan", {}).update(
            {
                "mode": hun_desc.get("mode"),
                "prompt_preset": hun_desc.get("prompt_preset"),
            }
        )
        vllm = hun_desc.get("url")
        if vllm:
            try:
                from tldw_Server_API.app.core.http_client import create_client as _create_client
                with _create_client(timeout=1.5) as _c:
                    r = _c.get(vllm.rsplit("/v1", 1)[0] + "/v1/models")
                    out["hunyuan"]["vllm_reachable"] = r.status_code in (200, 401)
            except Exception:
                out["hunyuan"]["vllm_reachable"] = False
    except Exception:
        pass

    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.nemotron_parse import (
            NemotronParseBackend,
        )
        nemo_desc = NemotronParseBackend().describe()
        out.setdefault("nemotron_parse", {}).update(
            {
                "mode": nemo_desc.get("mode"),
                "prompt": nemo_desc.get("prompt"),
                "text_format": nemo_desc.get("text_format"),
                "table_format": nemo_desc.get("table_format"),
            }
        )
        vllm = nemo_desc.get("url")
        if vllm:
            try:
                from tldw_Server_API.app.core.http_client import create_client as _create_client
                with _create_client(timeout=1.5) as _c:
                    r = _c.get(vllm.rsplit("/v1", 1)[0] + "/v1/models")
                    out["nemotron_parse"]["vllm_reachable"] = r.status_code in (200, 401)
            except Exception:
                out["nemotron_parse"]["vllm_reachable"] = False
    except Exception:
        pass

    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.dolphin_ocr import (
            DolphinOCRBackend,
        )
        dolph_desc = DolphinOCRBackend().describe()
        out.setdefault("dolphin", {}).update(
            {
                "mode": dolph_desc.get("mode"),
                "remote_mode": dolph_desc.get("remote_mode"),
                "prompt_preset": dolph_desc.get("prompt_preset"),
            }
        )
    except Exception:
        pass

    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.deepseek_ocr import (
            DeepSeekOCRBackend,
        )

        deepseek_desc = DeepSeekOCRBackend().describe()
        out.setdefault("deepseek", {}).update(
            {
                "model_id": deepseek_desc.get("model_id"),
                "prompt": deepseek_desc.get("prompt"),
                "base_size": deepseek_desc.get("base_size"),
                "image_size": deepseek_desc.get("image_size"),
                "crop_mode": deepseek_desc.get("crop_mode"),
                "device": deepseek_desc.get("device"),
                "dtype": deepseek_desc.get("dtype"),
                "attn_impl": deepseek_desc.get("attn_impl"),
            }
        )
    except Exception:
        pass

    return out


@router.post("/points/preload")
def preload_points_transformers() -> dict[str, Any]:
    """Preload POINTS transformers model to surface errors early."""
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.points_reader import (
            _load_transformers,
        )
        _load_transformers()
        return {"status": "ok", "mode": "transformers"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
