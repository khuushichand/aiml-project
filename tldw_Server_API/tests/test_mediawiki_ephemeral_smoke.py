"""
Smoke test for the MediaWiki ephemeral processing endpoint.

Starts a minimal FastAPI app with only the media router, sends a tiny gzipped
MediaWiki dump via multipart/form-data, and asserts NDJSON lines shape.
"""

import io
import json
import gzip
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.media import router as media_router


def _mini_mediawiki_xml() -> str:
    return (
        """
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.10/" version="0.10" xml:lang="en">
  <siteinfo>
    <sitename>TestWiki</sitename>
    <dbname>testwiki</dbname>
    <base>http://example.org/wiki/Main_Page</base>
    <generator>MediaWiki 1.42</generator>
    <case>first-letter</case>
  </siteinfo>
  <page>
    <title>Alan Turing</title>
    <ns>0</ns>
    <id>1</id>
    <revision>
      <id>11</id>
      <timestamp>2024-10-08T12:34:56Z</timestamp>
      <contributor><username>Tester</username><id>100</id></contributor>
      <comment>init</comment>
      <model>wikitext</model>
      <format>text/x-wiki</format>
      <text xml:space="preserve">Alan '''Mathison''' Turing was a mathematician.</text>
      <sha1>dummy</sha1>
    </revision>
  </page>
</mediawiki>
        """.strip()
    )


def _gz_bytes(data: str) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(data.encode("utf-8"))
    return buf.getvalue()


@pytest.mark.integration
def test_mediawiki_process_dump_ephemeral_stream(monkeypatch, tmp_path: Path):
    # Ensure temp dirs created by endpoint are within CWD so validate_file_path passes
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    app = FastAPI()
    app.include_router(media_router, prefix="/api/v1/media")
    client = TestClient(app)

    gz = _gz_bytes(_mini_mediawiki_xml())

    files = {
        "dump_file": ("mini.xml.gz", gz, "application/gzip"),
    }
    data = {
        "wiki_name": "TestWiki",
        "namespaces_str": "0",
        "skip_redirects": "true",
        "chunk_max_size": "500",
        # form dep expects keys but they will be ignored by endpoint storage path
        "api_name_vector_db": "",
    }

    progress_seen = False
    page_seen = False
    summary_seen = False

    with client.stream("POST", "/api/v1/media/mediawiki/process-dump", files=files, data=data) as resp:
        assert resp.status_code == 200
        for raw in resp.iter_lines():
            if not raw:
                continue
            obj = json.loads(raw)
            # Typed events
            if isinstance(obj, dict) and obj.get("type") == "progress_total":
                assert isinstance(obj.get("total_pages"), int)
                assert obj["total_pages"] >= 1
                progress_seen = True
                continue
            if isinstance(obj, dict) and obj.get("type") == "summary":
                assert "Processed" in obj.get("message", "")
                summary_seen = True
                continue
            if isinstance(obj, dict) and obj.get("type") == "error":
                pytest.fail(f"Endpoint returned error: {obj}")

            # Validated page objects (no 'type' key)
            assert isinstance(obj, dict)
            assert "title" in obj and "content" in obj
            assert obj["title"] == "Alan Turing"
            assert isinstance(obj["content"], str) and len(obj["content"]) > 0
            page_seen = True

    assert progress_seen, "Did not see progress_total"
    assert page_seen, "Did not see validated page object"
    assert summary_seen, "Did not see summary"
