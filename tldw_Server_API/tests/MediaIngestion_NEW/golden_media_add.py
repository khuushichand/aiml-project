"""
Golden-sample envelopes for the /media/add endpoint.

These fixtures are used in tests to assert that the modular
`/api/v1/media/add` path preserves the expected response shape when
core ingestion helpers return known results.

Scenarios covered:
  - VIDEO_ADD_GOLDEN_RESPONSE
      Single video upload (file only).
  - VIDEO_MIXED_URL_FILE_GOLDEN_RESPONSE
      Mixed video URL + file upload in one /add request.
  - DOCUMENT_ADD_GOLDEN_RESPONSE
      Single document upload (file only).
  - DOCUMENT_MIXED_URL_FILE_GOLDEN_RESPONSE
      Mixed document URL + file upload in one /add request.
  - EMAIL_ADD_GOLDEN_RESPONSE
      Single email archive upload with child messages.
  - EMAIL_MIXED_URL_FILE_GOLDEN_RESPONSE
      Mixed email archive URL + email upload, each with children.
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

VIDEO_MIXED_URL_FILE_GOLDEN_RESPONSE: Dict[str, Any] = {
    "results": [
        {
            "status": "Success",
            "input_ref": "https://golden.example/video-url-1",
            "processing_source": "golden://video/url/1",
            "media_type": "video",
            "metadata": {
                "title": "Golden Video URL Sample",
                "source_format": "video",
            },
            "content": None,
            "transcript": "Golden URL video transcript.",
            "segments": [],
            "chunks": [],
            "analysis": "Golden URL video analysis.",
            "summary": "Golden URL video analysis.",
            "analysis_details": {},
            "claims": [],
            "claims_details": {},
            "error": None,
            "warnings": [],
            "db_id": 20,
            "db_message": "Golden URL video persisted.",
            "media_uuid": "00000000-0000-0000-0000-000000000014",
        },
        {
            "status": "Success",
            "input_ref": "golden_video_upload.mp4",
            "processing_source": "golden://video/upload/1",
            "media_type": "video",
            "metadata": {
                "title": "Golden Video Upload Sample",
                "source_format": "video",
            },
            "content": None,
            "transcript": "Golden upload video transcript.",
            "segments": [],
            "chunks": [],
            "analysis": "Golden upload video analysis.",
            "summary": "Golden upload video analysis.",
            "analysis_details": {},
            "claims": [],
            "claims_details": {},
            "error": None,
            "warnings": [],
            "db_id": 21,
            "db_message": "Golden upload video persisted.",
            "media_uuid": "00000000-0000-0000-0000-000000000015",
        },
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

DOCUMENT_MIXED_URL_FILE_GOLDEN_RESPONSE: Dict[str, Any] = {
    "results": [
        {
            "status": "Success",
            "input_ref": "https://golden.example/document-url-1",
            "processing_source": "golden://document/url/1",
            "media_type": "document",
            "metadata": {
                "title": "Golden Document URL Sample",
                "author": "Doc URL Author",
                "source_format": "txt",
            },
            "content": "This is a golden document body from URL.",
            "transcript": None,
            "segments": None,
            "chunks": [],
            "analysis": "Golden URL document analysis.",
            "summary": "Golden URL document analysis.",
            "analysis_details": {},
            "claims": [],
            "claims_details": {},
            "error": None,
            "warnings": [],
            "db_id": 10,
            "db_message": "Golden document from URL persisted.",
            "media_uuid": "00000000-0000-0000-0000-00000000000A",
            "children": [],
        },
        {
            "status": "Success",
            "input_ref": "golden_document_upload.txt",
            "processing_source": "golden://document/upload/1",
            "media_type": "document",
            "metadata": {
                "title": "Golden Document Upload Sample",
                "author": "Doc Upload Author",
                "source_format": "txt",
            },
            "content": "This is a golden document body from upload.",
            "transcript": None,
            "segments": None,
            "chunks": [],
            "analysis": "Golden upload document analysis.",
            "summary": "Golden upload document analysis.",
            "analysis_details": {},
            "claims": [],
            "claims_details": {},
            "error": None,
            "warnings": [],
            "db_id": 11,
            "db_message": "Golden document upload persisted.",
            "media_uuid": "00000000-0000-0000-0000-00000000000B",
            "children": [],
        },
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


EMAIL_MIXED_URL_FILE_GOLDEN_RESPONSE: Dict[str, Any] = {
    "results": [
        {
            "status": "Success",
            "input_ref": "https://golden.example/email-archive-1.zip",
            "processing_source": "golden://email/url/1",
            "media_type": "email",
            "metadata": {
                "title": "Golden Email Archive (URL)",
                "source_format": "zip",
                "tags": ["email_archive:url"],
            },
            "content": None,
            "transcript": None,
            "segments": None,
            "chunks": [],
            "analysis": "Golden email archive (URL) analysis.",
            "summary": "Golden email archive (URL) analysis.",
            "analysis_details": {},
            "claims": [],
            "claims_details": {},
            "error": None,
            "warnings": [],
            "db_id": 4,
            "db_message": "Golden email archive (URL) persisted.",
            "media_uuid": "00000000-0000-0000-0000-000000000004",
            "children": [
                {
                    "status": "Success",
                    "input_ref": "url-child-1.eml",
                    "processing_source": "golden://email/url/1/child/1",
                    "media_type": "email",
                    "metadata": {
                        "email": {"subject": "URL Child One"},
                    },
                    "content": "First URL child email body.",
                    "chunks": [],
                    "analysis": None,
                    "error": None,
                    "warnings": [],
                },
                {
                    "status": "Success",
                    "input_ref": "url-child-2.eml",
                    "processing_source": "golden://email/url/1/child/2",
                    "media_type": "email",
                    "metadata": {
                        "email": {"subject": "URL Child Two"},
                    },
                    "content": "Second URL child email body.",
                    "chunks": [],
                    "analysis": None,
                    "error": None,
                    "warnings": [],
                },
            ],
        },
        {
            "status": "Success",
            "input_ref": "golden_email_upload.eml",
            "processing_source": "golden://email/upload/1",
            "media_type": "email",
            "metadata": {
                "title": "Golden Email Upload",
                "source_format": "eml",
                "tags": ["email_upload:file"],
            },
            "content": None,
            "transcript": None,
            "segments": None,
            "chunks": [],
            "analysis": "Golden email upload analysis.",
            "summary": "Golden email upload analysis.",
            "analysis_details": {},
            "claims": [],
            "claims_details": {},
            "error": None,
            "warnings": [],
            "db_id": 5,
            "db_message": "Golden email upload persisted.",
            "media_uuid": "00000000-0000-0000-0000-000000000005",
            "children": [
                {
                    "status": "Success",
                    "input_ref": "upload-child-1.eml",
                    "processing_source": "golden://email/upload/1/child/1",
                    "media_type": "email",
                    "metadata": {
                        "email": {"subject": "Upload Child One"},
                    },
                    "content": "First upload child email body.",
                    "chunks": [],
                    "analysis": None,
                    "error": None,
                    "warnings": [],
                }
            ],
        },
    ]
}


def clone_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return a shallow copy of the golden results list.

    This avoids accidental mutation of the module-level fixtures in tests.
    """
    return [dict(item) for item in payload.get("results", [])]
