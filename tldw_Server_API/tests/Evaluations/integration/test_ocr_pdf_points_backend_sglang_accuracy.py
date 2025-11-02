import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


def _sglang_available():
    url = os.getenv("POINTS_SGLANG_URL", "http://127.0.0.1:8081/v1/chat/completions")
    base = url.rsplit("/v1", 1)[0] + "/v1/models"
    try:
        import httpx

        r = httpx.get(base, timeout=1.5)
        return r.status_code in (200, 401)
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.requires_llm
def test_points_sglang_accuracy():
    pytest.importorskip("requests")

    if os.getenv("POINTS_MODE") not in ("sglang", "auto"):
        pytest.skip("POINTS_MODE not set to sglang/auto")
    if not _sglang_available():
        pytest.skip("SGLang endpoint not reachable")

    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.endpoints import evaluations_unified as eval_mod
    from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import UnifiedEvaluationService

    # temp DB
    with tempfile.NamedTemporaryFile(suffix="_eval_test.db", delete=True) as dbf:
        service = UnifiedEvaluationService(db_path=dbf.name)
        eval_mod._evaluation_service = service

        async def _ok(*args, **kwargs):
            return "test_user"

        app.dependency_overrides[eval_mod.verify_api_key] = _ok

        # rate limiter override
        from tldw_Server_API.app.api.v1.API_Deps import auth_deps

        class _RL:
            async def check_rate_limit(self, *a, **k):
                return True, {"retry_after": 0}

        async def _get_rl():
            return _RL()

        app.dependency_overrides[auth_deps.get_rate_limiter_dep] = _get_rl

        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 120), "HELLO", fontsize=28)
        b = doc.tobytes()
        doc.close()

        files = [("files", ("hello.pdf", b, "application/pdf"))]
        thresholds = {"max_cer": 0.35, "max_wer": 0.35, "min_coverage": 0.4}
        data = {
            "ground_truths_json": json.dumps(["HELLO"]),
            "enable_ocr": "true",
            "ocr_backend": "points",
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

            r = client.post("/api/v1/evaluations/ocr-pdf", files=files, data=data, headers=headers)
            assert r.status_code == 200, r.text
            body = r.json()
            items = body.get("results", {}).get("results", [])
            assert len(items) == 1
            item = items[0]
            assert item.get("cer") is not None and item.get("wer") is not None
            assert item["cer"] <= thresholds["max_cer"] + 1e-6
            assert item["wer"] <= thresholds["max_wer"] + 1e-6
            assert item["coverage"] >= thresholds["min_coverage"] - 1e-6

        app.dependency_overrides.pop(eval_mod.verify_api_key, None)
        app.dependency_overrides.pop(auth_deps.get_rate_limiter_dep, None)
