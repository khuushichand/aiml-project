"""
Golden-sample envelopes for the /media/add endpoint.

These fixtures are used in tests to assert that the modular
`/api/v1/media/add` path preserves the expected response shape when
core ingestion helpers return known results.
"""

from __future__ import annotations

from typing import Any, Dict, List


VIDEO_ADD_GOLDEN_RESPONSE: Dict[str, Any] = {
    "results": [
        {
            "status": "Success",
            "input_ref": "golden-video-1",
            "processing_source": "golden://video/1",
            "media_type": "video",
            "metadata": {
                "title": "Golden Video Sample",
                "source_format": "video",
            },
            "content": None,
            "transcript": "This is a golden video transcript.",
            "segments": [],
            "chunks": [],
            "analysis": "Golden video analysis.",
            "summary": "Golden video analysis.",
            "analysis_details": {},
            "claims": [],
            "claims_details": {},
            "error": None,
            "warnings": [],
            "db_id": 1,
            "db_message": "Golden DB write succeeded.",
            "media_uuid": "00000000-0000-0000-0000-000000000001",
        }
    ]
}


DOCUMENT_ADD_GOLDEN_RESPONSE: Dict[str, Any] = {
    "results": [
        {
            "status": "Success",
            "input_ref": "golden-document-1.txt",
            "processing_source": "golden://document/1",
            "media_type": "document",
            "metadata": {
                "title": "Golden Document Sample",
                "author": "Doc Author",
                "source_format": "txt",
            },
            "content": "This is a golden document body.",
            "transcript": None,
            "segments": None,
            "chunks": [],
            "analysis": "Golden document analysis.",
            "summary": "Golden document analysis.",
            "analysis_details": {},
            "claims": [],
            "claims_details": {},
            "error": None,
            "warnings": [],
            "db_id": 2,
            "db_message": "Golden document persisted.",
            "media_uuid": "00000000-0000-0000-0000-000000000002",
            "children": [],
        }
    ]
}


EMAIL_ADD_GOLDEN_RESPONSE: Dict[str, Any] = {
    "results": [
        {
            "status": "Success",
            "input_ref": "golden-email-archive.eml",
            "processing_source": "golden://email/parent",
            "media_type": "email",
            "metadata": {
                "title": "Golden Email Thread",
                "source_format": "eml",
            },
            "content": None,
            "transcript": None,
            "segments": None,
            "chunks": [],
            "analysis": "Golden email thread analysis.",
            "summary": "Golden email thread analysis.",
            "analysis_details": {},
            "claims": [],
            "claims_details": {},
            "error": None,
            "warnings": [],
            "db_id": 3,
            "db_message": "Golden email archive persisted.",
            "media_uuid": "00000000-0000-0000-0000-000000000003",
            "children": [
                {
                    "status": "Success",
                    "input_ref": "child-1.eml",
                    "processing_source": "golden://email/child/1",
                    "media_type": "email",
                    "metadata": {
                        "email": {"subject": "Child One"},
                    },
                    "content": "First child email body.",
                    "chunks": [],
                    "analysis": None,
                    "error": None,
                    "warnings": [],
                },
                {
                    "status": "Success",
                    "input_ref": "child-2.eml",
                    "processing_source": "golden://email/child/2",
                    "media_type": "email",
                    "metadata": {
                        "email": {"subject": "Child Two"},
                    },
                    "content": "Second child email body.",
                    "chunks": [],
                    "analysis": None,
                    "error": None,
                    "warnings": [],
                },
            ],
        }
    ]
}


def clone_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return a shallow copy of the golden results list.

    This avoids accidental mutation of the module-level fixtures in tests.
    """
    return [dict(item) for item in payload.get("results", [])]

