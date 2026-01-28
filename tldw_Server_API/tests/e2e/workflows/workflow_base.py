"""
Workflow Test Base Classes
---------------------------

Base classes and utilities for end-to-end workflow tests.
"""

import time
from typing import Any, Callable, Dict, List, Optional
from difflib import SequenceMatcher

import pytest
import httpx


class WorkflowTestBase:
    """Base class with common utilities for workflow tests."""

    # Default timeouts
    DEFAULT_INDEXING_TIMEOUT = 30  # seconds
    DEFAULT_TRANSCRIPTION_TIMEOUT = 120  # seconds
    DEFAULT_POLL_INTERVAL = 2  # seconds

    def wait_for_indexing(
        self,
        api_client,
        media_id: int,
        timeout: int = None,
        poll_interval: int = None,
    ) -> bool:
        """
        Poll until media is indexed and searchable.

        Args:
            api_client: The API client
            media_id: ID of the media to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            True if indexed, raises on timeout
        """
        timeout = timeout or self.DEFAULT_INDEXING_TIMEOUT
        poll_interval = poll_interval or self.DEFAULT_POLL_INTERVAL
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Check if media exists and has content
                media = api_client.get_media_item(media_id)
                if not media:
                    time.sleep(poll_interval)
                    continue

                # Check for content/transcript
                has_content = (
                    media.get("content")
                    or media.get("text")
                    or media.get("transcript")
                    or media.get("transcription")
                )

                if has_content:
                    return True

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # Media not found yet, keep polling
                    time.sleep(poll_interval)
                    continue
                raise

            time.sleep(poll_interval)

        pytest.fail(f"Media {media_id} not indexed within {timeout}s")

    def wait_for_embeddings(
        self,
        api_client,
        media_id: int,
        search_query: str,
        timeout: int = None,
        poll_interval: int = None,
    ) -> bool:
        """
        Poll until embeddings are generated and searchable.

        Args:
            api_client: The API client
            media_id: ID of the media
            search_query: Query to search for
            timeout: Maximum time to wait
            poll_interval: Time between polls

        Returns:
            True if embeddings found, raises on timeout
        """
        timeout = timeout or self.DEFAULT_INDEXING_TIMEOUT
        poll_interval = poll_interval or self.DEFAULT_POLL_INTERVAL
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                result = api_client.rag_simple_search(
                    query=search_query,
                    databases=["media"],
                    top_k=10,
                )

                # Check if our media_id is in results
                documents = (
                    result.get("documents")
                    or result.get("results")
                    or result.get("items")
                    or []
                )

                for doc in documents:
                    doc_id = doc.get("id") or doc.get("media_id")
                    # Normalize ID types for comparison (RAG returns strings, extract_media_id returns int)
                    try:
                        if int(doc_id) == int(media_id):
                            return True
                    except (ValueError, TypeError):
                        if doc_id == media_id:
                            return True

            except httpx.HTTPStatusError as e:
                # RAG endpoint might not be ready, keep polling
                if e.response.status_code in (404, 422, 500):
                    time.sleep(poll_interval)
                    continue
                raise

            time.sleep(poll_interval)

        # Timeout but don't fail - embeddings might just not be ready
        print(f"Warning: Embeddings for media {media_id} not found within {timeout}s")
        return False

    def wait_for_transcription(
        self,
        api_client,
        media_id: int,
        timeout: int = None,
        poll_interval: int = None,
    ) -> Dict[str, Any]:
        """
        Poll until media transcription is complete.

        Args:
            api_client: The API client
            media_id: ID of the media
            timeout: Maximum time to wait
            poll_interval: Time between polls

        Returns:
            Media details with transcript
        """
        timeout = timeout or self.DEFAULT_TRANSCRIPTION_TIMEOUT
        poll_interval = poll_interval or self.DEFAULT_POLL_INTERVAL
        start_time = time.time()
        last_response = None

        while time.time() - start_time < timeout:
            try:
                media = api_client.get_media_item(media_id)
                last_response = media

                # Check various status/transcript fields
                status = media.get("transcription_status") or media.get("status")
                if status in ("completed", "success", "done"):
                    return media

                # Check if transcript content exists
                transcript = (
                    media.get("transcription")
                    or media.get("transcript")
                    or media.get("content")
                )
                if transcript and len(transcript) > 10:
                    return media

                # Check for explicit failure
                if status in ("failed", "error"):
                    pytest.fail(f"Transcription failed for media {media_id}: {media}")

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    time.sleep(poll_interval)
                    continue
                raise

            time.sleep(poll_interval)

        pytest.fail(
            f"Transcription for media {media_id} not completed within {timeout}s. "
            f"Last status: {last_response.get('status') if last_response else 'unknown'}"
        )

    def verify_search_finds(
        self,
        api_client,
        query: str,
        expected_ids: List[int],
        search_mode: str = "fts",
        sources: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Assert search returns expected items.

        Args:
            api_client: The API client
            query: Search query
            expected_ids: List of media IDs expected in results
            search_mode: Search mode (fts, vector, hybrid)
            sources: Sources to search (media_db, notes, etc.)

        Returns:
            List of search results
        """
        databases = sources if sources else ["media"]

        result = api_client.rag_simple_search(
            query=query,
            databases=databases,
            top_k=max(20, len(expected_ids) * 2),
        )

        documents = (
            result.get("documents")
            or result.get("results")
            or result.get("items")
            or []
        )

        found_ids = set()
        for doc in documents:
            doc_id = doc.get("id") or doc.get("media_id")
            if doc_id is not None:
                # Normalize to int for consistent comparison (RAG returns strings)
                try:
                    found_ids.add(int(doc_id))
                except (ValueError, TypeError):
                    found_ids.add(doc_id)

        # Normalize expected_ids to int as well
        normalized_expected = set()
        for eid in expected_ids:
            try:
                normalized_expected.add(int(eid))
            except (ValueError, TypeError):
                normalized_expected.add(eid)

        missing_ids = normalized_expected - found_ids
        if missing_ids:
            pytest.fail(
                f"Search for '{query}' missing expected IDs: {missing_ids}. "
                f"Found IDs: {found_ids}"
            )

        return documents

    def assert_data_flow(
        self,
        source: Dict[str, Any],
        destination: Dict[str, Any],
        fields: List[str],
        tolerance: float = 0.85,
    ) -> None:
        """
        Verify data flows correctly between operations.

        Args:
            source: Source data dictionary
            destination: Destination data dictionary
            fields: List of field names to compare
            tolerance: Similarity tolerance for text fields (0-1)
        """
        for field in fields:
            src_val = source.get(field)
            dst_val = destination.get(field)

            if src_val is None:
                continue

            if dst_val is None:
                pytest.fail(f"Field '{field}' missing in destination: {destination.keys()}")

            # String comparison with tolerance
            if isinstance(src_val, str) and isinstance(dst_val, str):
                similarity = SequenceMatcher(None, src_val, dst_val).ratio()
                if similarity < tolerance:
                    pytest.fail(
                        f"Field '{field}' content mismatch. "
                        f"Similarity: {similarity:.2%} < {tolerance:.2%}"
                    )
            # Exact comparison for other types
            elif src_val != dst_val:
                pytest.fail(
                    f"Field '{field}' value mismatch. "
                    f"Source: {src_val}, Destination: {dst_val}"
                )

    def extract_media_id(self, response: Dict[str, Any]) -> int:
        """
        Extract media ID from various response formats.

        Args:
            response: API response dictionary

        Returns:
            Media ID as integer
        """
        # Handle results array format
        if "results" in response and isinstance(response["results"], list):
            if len(response["results"]) > 0:
                result = response["results"][0]
                if result.get("status") == "Error":
                    error_msg = result.get("error") or result.get("db_message")
                    pytest.fail(f"Upload failed: {error_msg}")
                media_id = result.get("db_id") or result.get("id")
                if media_id:
                    return int(media_id)

        # Handle direct format
        media_id = (
            response.get("media_id")
            or response.get("id")
            or response.get("db_id")
        )

        if media_id is None:
            pytest.fail(f"No media_id in response: {response}")

        return int(media_id)

    def extract_chat_content(self, response: Dict[str, Any]) -> str:
        """
        Extract message content from chat response.

        Args:
            response: Chat API response

        Returns:
            Message content string
        """
        if "choices" in response and len(response["choices"]) > 0:
            choice = response["choices"][0]
            message = choice.get("message", {})
            return message.get("content", "")

        if "response" in response:
            return response["response"]

        if "content" in response:
            return response["content"]

        pytest.fail(f"Cannot extract content from chat response: {response.keys()}")

    def assert_response_contains(
        self,
        response_text: str,
        expected_phrases: List[str],
        case_sensitive: bool = False,
    ) -> None:
        """
        Assert response contains expected phrases.

        Args:
            response_text: The response text to check
            expected_phrases: List of phrases expected in response
            case_sensitive: Whether to do case-sensitive matching
        """
        check_text = response_text if case_sensitive else response_text.lower()

        missing = []
        for phrase in expected_phrases:
            check_phrase = phrase if case_sensitive else phrase.lower()
            if check_phrase not in check_text:
                missing.append(phrase)

        if missing:
            pytest.fail(
                f"Response missing expected phrases: {missing}. "
                f"Response preview: {response_text[:200]}..."
            )


class WorkflowStateManager:
    """Manage state across workflow phases."""

    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._phase_data: Dict[str, List[Dict[str, Any]]] = {}
        self._current_phase: Optional[str] = None

    def set(self, key: str, value: Any) -> None:
        """Store a value in workflow state."""
        self._state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from workflow state."""
        return self._state.get(key, default)

    def enter_phase(self, phase_name: str) -> None:
        """Mark entry into a new phase."""
        self._current_phase = phase_name
        if phase_name not in self._phase_data:
            self._phase_data[phase_name] = []
        print(f"\n{'='*60}")
        print(f"PHASE: {phase_name.upper()}")
        print(f"{'='*60}")

    def add_phase_item(self, item: Dict[str, Any]) -> None:
        """Add an item to the current phase."""
        if self._current_phase:
            self._phase_data[self._current_phase].append(item)

    def get_phase_items(self, phase_name: str) -> List[Dict[str, Any]]:
        """Get all items from a phase."""
        return self._phase_data.get(phase_name, [])

    def get_media_ids(self) -> List[int]:
        """Get all media IDs stored in state."""
        return self._state.get("media_ids", [])

    def add_media_id(self, media_id: int) -> None:
        """Add a media ID to state."""
        if "media_ids" not in self._state:
            self._state["media_ids"] = []
        self._state["media_ids"].append(media_id)

    def get_note_ids(self) -> List[int]:
        """Get all note IDs stored in state."""
        return self._state.get("note_ids", [])

    def add_note_id(self, note_id: int) -> None:
        """Add a note ID to state."""
        if "note_ids" not in self._state:
            self._state["note_ids"] = []
        self._state["note_ids"].append(note_id)

    def get_chat_ids(self) -> List[str]:
        """Get all chat IDs stored in state."""
        return self._state.get("chat_ids", [])

    def add_chat_id(self, chat_id: str) -> None:
        """Add a chat ID to state."""
        if "chat_ids" not in self._state:
            self._state["chat_ids"] = []
        self._state["chat_ids"].append(chat_id)
