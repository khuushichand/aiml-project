import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


def _detect_vllm_base_url():
    # Try common env vars or default to local vLLM
    for key in ("VLLM_API_URL", "OPENAI_API_BASE", "OPENAI_BASE_URL"):
        val = os.getenv(key)
        if val:
            return val.rstrip("/")
    return "http://127.0.0.1:8000/v1"


def _vllm_available():
    try:
        import httpx

        base = _detect_vllm_base_url()
        url = f"{base}/models"
        r = httpx.get(url, timeout=1.5)
        # Accept 200 OK; some setups may require auth and return 401, treat that as available too
        if r.status_code in (200, 401):
            return True
        return False
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.requires_llm
def test_ocr_pdf_with_dots_and_vllm_text_accuracy():
    # Skip if dots_ocr is not installed
    pytest.importorskip("dots_ocr")

    # Skip if vLLM endpoint isn't responding
    if not _vllm_available():
        pytest.skip("vLLM server not available on expected endpoint")

    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.endpoints import evaluations_unified as eval_mod
    from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import UnifiedEvaluationService

    # Use a temporary DB to isolate test
    with tempfile.NamedTemporaryFile(suffix="_eval_test.db", delete=True) as dbf:
        service = UnifiedEvaluationService(db_path=dbf.name)
        eval_mod._evaluation_service = service

        # Override auth and rate limits
        async def _ok(*args, **kwargs) -> str:
            return "test_user"

        app.dependency_overrides[eval_mod.verify_api_key] = _ok

        from tldw_Server_API.app.api.v1.API_Deps import auth_deps

        class _DummyRateLimiter:
            async def check_rate_limit(self, *args, **kwargs):
                return True, {"retry_after": 0}

        async def _get_rl():
            return _DummyRateLimiter()

        app.dependency_overrides[auth_deps.get_rate_limiter_dep] = _get_rl

        # Build a clear, single-word PDF to minimize OCR ambiguity
        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)  # A4 @72DPI
        # Use a larger font for clarity
        page.insert_text((72, 120), "HELLO", fontsize=28)
        pdf_bytes = doc.tobytes()
        doc.close()

        files = [("files", ("hello.pdf", pdf_bytes, "application/pdf"))]
        thresholds = {"max_cer": 0.25, "max_wer": 0.25, "min_coverage": 0.5}

        data = {
            "ground_truths_json": json.dumps(["HELLO"]),
            "enable_ocr": "true",
            "ocr_backend": "dots",
            "ocr_mode": "always",
            "ocr_dpi": "200",
            "ocr_lang": "eng",
            "thresholds_json": json.dumps(thresholds),
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
            results = body.get("results", {})
            per_items = results.get("results", [])
            assert len(per_items) == 1

            item = per_items[0]
            # Assert some reasonable accuracy when vLLM is available
            cer = item.get("cer")
            wer = item.get("wer")
            cov = item.get("coverage")
            assert cer is not None and wer is not None and cov is not None
            assert cer <= thresholds["max_cer"] + 1e-6
            assert wer <= thresholds["max_wer"] + 1e-6
            assert cov >= thresholds["min_coverage"] - 1e-6

        # Cleanup overrides
        app.dependency_overrides.pop(eval_mod.verify_api_key, None)
        app.dependency_overrides.pop(auth_deps.get_rate_limiter_dep, None)
