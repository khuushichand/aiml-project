import importlib.util
import json
import os
import tempfile
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.evaluations,
    pytest.mark.local_llm_service,
    pytest.mark.requires_model,
]

if os.getenv("DEEPSEEK_OCR_RUN_INTEGRATION") != "1":
    pytest.skip("Set DEEPSEEK_OCR_RUN_INTEGRATION=1 to enable", allow_module_level=True)

if (
    importlib.util.find_spec(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.deepseek_ocr"
    )
    is None
):
    pytest.skip("DeepSeek OCR backend not available", allow_module_level=True)


def _cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


def test_ocr_pdf_endpoint_with_deepseek_backend_local():
    pytest.importorskip("transformers")
    pytest.importorskip("torch")

    if not _cuda_available():
        pytest.skip("CUDA not available")

    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.endpoints.evaluations import evaluations_unified as eval_mod
    from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
        UnifiedEvaluationService,
    )

    with tempfile.NamedTemporaryFile(suffix="_eval_test.db", delete=True) as dbf:
        service = UnifiedEvaluationService(db_path=dbf.name)
        eval_mod._evaluation_service = service

        async def _ok(*args, **kwargs) -> str:
            return "test_user"

        app.dependency_overrides[eval_mod.verify_api_key] = _ok

        from tldw_Server_API.app.api.v1.API_Deps import auth_deps

        class _DummyRateLimiter:
            async def check_rate_limit(self, *args, **kwargs):
                return True, {"retry_after": 0}

        async def _get_rl() -> Any:
            return _DummyRateLimiter()

        app.dependency_overrides[auth_deps.get_rate_limiter_dep] = _get_rl

        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "HELLO")
        pdf_bytes = doc.tobytes()
        doc.close()

        files = [
            ("files", ("test.pdf", pdf_bytes, "application/pdf")),
        ]

        data = {
            "ground_truths_json": json.dumps(["HELLO"]),
            "enable_ocr": "true",
            "ocr_backend": "deepseek",
            "ocr_mode": "always",
            "ocr_dpi": "200",
            "ocr_lang": "eng",
        }

        with TestClient(app) as client:
            headers = {}
            try:
                r0 = client.get("/api/v1/health")
                token = r0.cookies.get("csrf_token")
                if token:
                    headers["X-CSRF-Token"] = token
            except Exception:
                pass

            r = client.post(
                "/api/v1/evaluations/ocr-pdf",
                files=files,
                data=data,
                headers=headers,
            )

            assert r.status_code == 200, r.text
            body = r.json()
            assert isinstance(body, dict)
            assert "evaluation_id" in body
            assert "results" in body and isinstance(body["results"], dict)
            inner = body.get("results", {})
            assert isinstance(inner.get("results", []), list)
            assert len(inner.get("results", [])) == 1

        app.dependency_overrides.pop(eval_mod.verify_api_key, None)
        app.dependency_overrides.pop(auth_deps.get_rate_limiter_dep, None)
