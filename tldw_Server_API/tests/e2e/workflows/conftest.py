"""
Workflow Test Configuration
----------------------------

Pytest configuration and fixtures specific to workflow tests.
"""

import os
import time
import tempfile
from typing import Dict, Any, List, Optional, Generator

import pytest
import httpx

from ..fixtures import (
    api_client,
    authenticated_client,
    data_tracker,
    create_test_file,
    create_test_audio,
    cleanup_test_file,
    require_llm_or_skip,
    APIClient,
    TestDataTracker,
)
from .workflow_base import WorkflowTestBase, WorkflowStateManager


# Register custom markers
def pytest_configure(config):
    """Register workflow-specific markers."""
    config.addinivalue_line("markers", "workflow: All workflow tests")
    config.addinivalue_line("markers", "workflow_slow: Long-running workflow tests")
    config.addinivalue_line("markers", "workflow_llm: Workflow tests requiring LLM provider")
    config.addinivalue_line("markers", "workflow_embeddings: Workflow tests requiring embeddings")


@pytest.fixture(scope="function")
def workflow_state() -> Generator[WorkflowStateManager, None, None]:
    """
    Maintain state across workflow phases.

    Provides a WorkflowStateManager instance for tracking data
    throughout multi-phase workflow tests.
    """
    state = WorkflowStateManager()
    yield state
    # State is automatically cleaned up when fixture goes out of scope


@pytest.fixture(scope="function")
def workflow_helper() -> WorkflowTestBase:
    """Provide workflow test helper utilities."""
    return WorkflowTestBase()


@pytest.fixture(scope="function")
def embedding_ready_content(
    api_client: APIClient,
    data_tracker: TestDataTracker,
    workflow_helper: WorkflowTestBase,
) -> Generator[Dict[str, Any], None, None]:
    """
    Upload content and wait for embeddings.

    Creates a text document with unique content, uploads it with
    embedding generation enabled, and waits for it to be searchable.

    Yields:
        Dictionary with media_id, content, and title
    """
    timestamp = int(time.time())
    unique_marker = f"EMBED_TEST_{timestamp}"

    content = f"""
    {unique_marker}

    This is test content for embedding verification.
    It contains information about quantum computing and machine learning.
    The document discusses how quantum algorithms can enhance AI systems.
    Topics include qubits, superposition, and neural network optimization.
    """

    title = f"Embedding Test Document {timestamp}"

    # Create and upload file
    file_path = create_test_file(content, suffix=".txt")
    data_tracker.add_file(file_path)

    try:
        response = api_client.upload_media(
            file_path=file_path,
            title=title,
            media_type="document",
            generate_embeddings=True,
        )

        media_id = workflow_helper.extract_media_id(response)
        data_tracker.add_media(media_id)

        # Wait for indexing
        workflow_helper.wait_for_indexing(api_client, media_id, timeout=30)

        # Try to wait for embeddings (non-fatal if they don't appear)
        workflow_helper.wait_for_embeddings(
            api_client,
            media_id,
            search_query=unique_marker,
            timeout=15,
        )

        yield {
            "media_id": media_id,
            "content": content,
            "title": title,
            "unique_marker": unique_marker,
        }

    finally:
        cleanup_test_file(file_path)


@pytest.fixture(scope="function")
def multi_source_content(
    api_client: APIClient,
    data_tracker: TestDataTracker,
    workflow_helper: WorkflowTestBase,
) -> Generator[Dict[str, Any], None, None]:
    """
    Create multiple content sources for multi-source RAG testing.

    Creates text documents, markdown, and notes with related content
    to test cross-source search.

    Yields:
        Dictionary with lists of media_ids, note_ids, and topic information
    """
    timestamp = int(time.time())
    topic = f"distributed_systems_{timestamp}"

    documents = []
    media_ids = []
    note_ids = []

    # Create text document
    text_content = f"""
    {topic} - Text Document

    Distributed systems are computing environments where components
    are spread across multiple networked computers. They communicate
    and coordinate their actions by passing messages.

    Key concepts include consistency, availability, and partition tolerance.
    The CAP theorem describes the trade-offs between these properties.
    """

    # Create markdown document
    markdown_content = f"""
    # {topic} - Markdown Document

    ## Introduction to Distributed Computing

    A **distributed system** is a system whose components are located
    on different networked computers, which communicate and coordinate
    their actions by passing messages to one another.

    ### Key Properties

    - **Scalability**: Ability to handle growing amounts of work
    - **Fault Tolerance**: Continued operation despite failures
    - **Consistency**: All nodes see the same data at the same time
    """

    try:
        # Upload text document
        txt_path = create_test_file(text_content, suffix=".txt")
        data_tracker.add_file(txt_path)

        try:
            response = api_client.upload_media(
                file_path=txt_path,
                title=f"Distributed Systems Overview {timestamp}",
                media_type="document",
                generate_embeddings=True,
            )
            media_id = workflow_helper.extract_media_id(response)
            media_ids.append(media_id)
            data_tracker.add_media(media_id)
            documents.append({
                "type": "text",
                "media_id": media_id,
                "content": text_content,
            })
        finally:
            cleanup_test_file(txt_path)

        # Upload markdown document
        md_path = create_test_file(markdown_content, suffix=".md")
        data_tracker.add_file(md_path)

        try:
            response = api_client.upload_media(
                file_path=md_path,
                title=f"Distributed Computing Guide {timestamp}",
                media_type="document",
                generate_embeddings=True,
            )
            media_id = workflow_helper.extract_media_id(response)
            media_ids.append(media_id)
            data_tracker.add_media(media_id)
            documents.append({
                "type": "markdown",
                "media_id": media_id,
                "content": markdown_content,
            })
        finally:
            cleanup_test_file(md_path)

        # Create a note on the same topic
        try:
            note_response = api_client.create_note(
                title=f"Distributed Systems Notes {timestamp}",
                content=f"""
                {topic} - Personal Notes

                Study notes on distributed systems:
                - Consensus algorithms (Paxos, Raft)
                - Message passing vs shared memory
                - Leader election protocols
                - Eventual consistency models
                """,
                keywords=["distributed", "systems", topic],
            )
            note_id = note_response.get("id") or note_response.get("note_id")
            if note_id:
                note_ids.append(note_id)
                data_tracker.add_note(note_id)
        except httpx.HTTPStatusError:
            # Notes endpoint might not be available
            pass

        # Wait for indexing
        for doc in documents:
            workflow_helper.wait_for_indexing(
                api_client,
                doc["media_id"],
                timeout=30,
            )

        yield {
            "topic": topic,
            "media_ids": media_ids,
            "note_ids": note_ids,
            "documents": documents,
        }

    except Exception as e:
        pytest.fail(f"Failed to create multi-source content: {e}")


@pytest.fixture(scope="function")
def transactional_cleanup(
    api_client: APIClient,
    data_tracker: TestDataTracker,
) -> Generator[Dict[str, List[int]], None, None]:
    """
    Auto-cleanup on test failure.

    Tracks resources created during a test and ensures they are
    cleaned up even if the test fails partway through.

    Yields:
        Dictionary with lists to track media_ids, note_ids, chat_ids
    """
    resources = {
        "media_ids": [],
        "note_ids": [],
        "chat_ids": [],
        "character_ids": [],
    }

    yield resources

    # Cleanup in reverse order of likely dependencies
    for chat_id in resources["chat_ids"]:
        try:
            api_client.delete_chat(chat_id)
        except Exception:
            _ = None

    for char_id in resources["character_ids"]:
        try:
            api_client.delete_character(char_id)
        except Exception:
            _ = None

    for note_id in resources["note_ids"]:
        try:
            api_client.delete_note(note_id)
        except Exception:
            _ = None

    for media_id in resources["media_ids"]:
        try:
            api_client.delete_media(media_id)
        except Exception:
            _ = None


@pytest.fixture(scope="function")
def test_audio_file(data_tracker: TestDataTracker) -> Generator[str, None, None]:
    """
    Create a test audio file.

    Creates a minimal WAV file suitable for transcription testing.

    Yields:
        Path to the test audio file
    """
    audio_path = create_test_audio()
    data_tracker.add_file(audio_path)

    yield audio_path

    cleanup_test_file(audio_path)


@pytest.fixture(scope="function")
def llm_model(api_client: APIClient) -> str:
    """
    Get an available LLM model or skip the test.

    Returns:
        Model name string

    Raises:
        pytest.skip if no LLM is available
    """
    return require_llm_or_skip(api_client)


def _create_test_pdf_with_text(content: str) -> str:
    """
    Create a minimal PDF with text content.

    Note: This creates a very basic PDF structure. For actual PDF testing,
    consider using a proper PDF library.
    """
    # Minimal PDF with text
    pdf_template = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 100 >>
stream
BT
/F1 12 Tf
72 720 Td
({content[:100]}) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000416 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
493
%%EOF
"""

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".pdf",
        delete=False,
    ) as f:
        f.write(pdf_template)
        return f.name


@pytest.fixture(scope="function")
def test_pdf_file(data_tracker: TestDataTracker) -> Generator[str, None, None]:
    """
    Create a test PDF file.

    Yields:
        Path to the test PDF file
    """
    content = "Test PDF content for workflow testing"
    pdf_path = _create_test_pdf_with_text(content)
    data_tracker.add_file(pdf_path)

    yield pdf_path

    cleanup_test_file(pdf_path)
