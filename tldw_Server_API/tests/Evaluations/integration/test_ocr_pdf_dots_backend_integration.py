import io
import json
import os
import tempfile
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_ocr_pdf_endpoint_with_dots_backend_integration(monkeypatch):
    # Skip unless dots_ocr is importable
    pytest.importorskip("dots_ocr")

    # Import app and endpoint module
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.endpoints import evaluations_unified as eval_mod
    from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
        UnifiedEvaluationService,
    )

    # Create a temporary DB for the service to avoid polluting the repo DB
    with tempfile.NamedTemporaryFile(suffix="_eval_test.db", delete=True) as dbf:
        service = UnifiedEvaluationService(db_path=dbf.name)
        # Force the endpoint module to use our service instance
        eval_mod._evaluation_service = service

        # Override auth to bypass API key verification
        async def _ok(*args, **kwargs) -> str:
            return "test_user"

        app.dependency_overrides[eval_mod.verify_api_key] = _ok

        # Override rate limiter to always allow
        from tldw_Server_API.app.api.v1.API_Deps import auth_deps

        class _DummyRateLimiter:
            async def check_rate_limit(self, *args, **kwargs):
                return True, {"retry_after": 0}

        async def _get_rl() -> Any:
            return _DummyRateLimiter()

        app.dependency_overrides[auth_deps.get_rate_limiter_dep] = _get_rl

        # Generate a tiny single-page PDF in-memory with known text
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
            # Use JSON field to avoid multi-part list parsing complexities
            "ground_truths_json": json.dumps(["HELLO"]),
            "enable_ocr": "true",
            "ocr_backend": "dots",
            "ocr_mode": "always",
            "ocr_dpi": "200",
            "ocr_lang": "eng",
            # keep metrics default
        }

        # Exercise the endpoint
        with TestClient(app) as client:
            # Obtain CSRF cookie if middleware is active
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
            # results["results"] should contain one entry for our single PDF
            inner = body.get("results", {})
            assert isinstance(inner.get("results", []), list)
            assert len(inner.get("results", [])) == 1

        # Cleanup dependency overrides
        app.dependency_overrides.pop(eval_mod.verify_api_key, None)
        app.dependency_overrides.pop(auth_deps.get_rate_limiter_dep, None)
