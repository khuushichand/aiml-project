from fastapi.testclient import TestClient
from tldw_Server_API.app.main import app as fastapi_app


def test_rag_capabilities_citation_styles_lowercased():
    """Capabilities should expose citation styles in lowercase to match schema literals."""
    with TestClient(fastapi_app) as client:
        resp = client.get("/api/v1/rag/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        features = data.get("features") or {}
        cg = features.get("citation_generation") or {}
        styles = cg.get("styles") or []
        assert styles, "Expected citation styles in capabilities"
        # Ensure all are lowercase and within the expected set
        expected = {"apa", "mla", "chicago", "harvard", "ieee"}
        assert set(styles).issubset(expected)
        assert all(s == s.lower() for s in styles)
