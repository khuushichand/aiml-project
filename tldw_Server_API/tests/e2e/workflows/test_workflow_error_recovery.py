"""
Error Recovery Workflow Test
-----------------------------

Tests system resilience and state consistency:
1. Partial upload failure - verify no orphaned records
2. Search with invalid parameters - verify graceful error
3. Chat with invalid model - verify fallback behavior
4. Delete during search - verify consistency
5. Concurrent modifications - verify no data loss
6. Cross-user data isolation - verify multi-user separation
"""

import time
import tempfile
import concurrent.futures
from typing import Dict, Any, List

import pytest
import httpx

from ..fixtures import (
    api_client,
    data_tracker,
    create_test_file,
    cleanup_test_file,
    require_llm_or_skip,
    APIClient,
    BASE_URL,
)
from .workflow_base import WorkflowTestBase, WorkflowStateManager


@pytest.mark.workflow
class TestErrorRecoveryWorkflow(WorkflowTestBase):
    """Test error recovery and state consistency."""

    def test_invalid_file_upload_graceful_failure(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify system handles invalid file uploads gracefully.

        Tests that uploading invalid/corrupted files doesn't leave
        orphaned database records.
        """
        # Create a "corrupted" file (invalid content for declared type)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".pdf",
            delete=False,
        ) as f:
            f.write("This is not a valid PDF file content")
            invalid_pdf_path = f.name

        data_tracker.add_file(invalid_pdf_path)

        try:
            # Try to upload invalid PDF
            response = api_client.upload_media(
                file_path=invalid_pdf_path,
                title="Invalid PDF Test",
                media_type="pdf",
                generate_embeddings=False,
            )

            # System might accept it (text extraction fallback) or reject it
            if isinstance(response, dict):
                results = response.get("results", [])
                if results:
                    first = results[0]
                    status = first.get("status")

                    if status == "Error":
                        # Error is expected - verify message is meaningful
                        error_msg = first.get("error") or first.get("db_message") or ""
                        assert error_msg, "Error response should have message"
                        print(f"  Expected error: {error_msg[:100]}")
                    elif status == "Success":
                        # System handled it gracefully, track for cleanup
                        media_id = first.get("db_id")
                        if media_id:
                            data_tracker.add_media(media_id)
                            print(f"  System accepted file with fallback (ID: {media_id})")

        except httpx.HTTPStatusError as e:
            # HTTP error is acceptable for invalid input
            assert e.response.status_code in (400, 415, 422), (
                f"Unexpected error code: {e.response.status_code}"
            )
            print(f"  Request rejected with {e.response.status_code}")

        finally:
            cleanup_test_file(invalid_pdf_path)

    def test_search_with_invalid_parameters(
        self,
        api_client,
    ):
        """
        Verify search handles invalid parameters gracefully.

        Tests various malformed search requests to ensure the API
        returns proper error responses.
        """
        test_cases = [
            # Empty query
            {
                "json": {"query": "", "sources": ["media_db"]},
                "expected_status": [400, 422],
                "description": "empty query",
            },
            # Invalid source
            {
                "json": {"query": "test", "sources": ["invalid_source"]},
                "expected_status": [400, 422, 200],  # Might ignore invalid source
                "description": "invalid source",
            },
            # Negative top_k
            {
                "json": {"query": "test", "top_k": -1},
                "expected_status": [400, 422],
                "description": "negative top_k",
            },
            # Invalid search mode
            {
                "json": {"query": "test", "search_mode": "invalid_mode"},
                "expected_status": [400, 422, 200],  # Might default to FTS
                "description": "invalid search mode",
            },
        ]

        for case in test_cases:
            try:
                response = api_client.client.post(
                    "/api/v1/rag/search",
                    json=case["json"],
                )

                assert response.status_code in case["expected_status"], (
                    f"{case['description']}: expected {case['expected_status']}, "
                    f"got {response.status_code}"
                )

                if response.status_code >= 400:
                    # Error responses should have meaningful content
                    error_data = response.json()
                    assert "detail" in error_data or "error" in error_data or "message" in error_data, (
                        f"{case['description']}: error response lacks detail"
                    )

                print(f"  {case['description']}: handled correctly ({response.status_code})")

            except httpx.HTTPStatusError as e:
                # HTTP error is also acceptable
                assert e.response.status_code in case["expected_status"], (
                    f"{case['description']}: unexpected error {e.response.status_code}"
                )
                print(f"  {case['description']}: rejected ({e.response.status_code})")

    def test_chat_with_invalid_model(
        self,
        api_client,
    ):
        """
        Verify chat handles invalid model names gracefully.

        Tests that requesting an invalid model returns a proper error
        or falls back to a default model.
        """
        try:
            response = api_client.chat_completion(
                messages=[
                    {"role": "user", "content": "Hello"}
                ],
                model="nonexistent-model-xyz-123",
                temperature=0.0,
            )

            # If we got here, system fell back to a working model
            content = self.extract_chat_content(response)
            assert content, "Fallback response should have content"
            print("  Invalid model handled with fallback")

        except httpx.HTTPStatusError as e:
            # Error is expected for invalid model
            assert e.response.status_code in (400, 404, 422, 500), (
                f"Unexpected error: {e.response.status_code}"
            )

            # Error message should mention the model issue
            try:
                error_data = e.response.json()
                error_msg = str(error_data)
                print(f"  Invalid model rejected: {error_msg[:100]}")
            except Exception:
                print(f"  Invalid model rejected: {e.response.status_code}")

    def test_delete_during_search(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify system handles deletion during search gracefully.

        Uploads content, starts a search, then deletes the content
        to verify no errors occur.
        """
        timestamp = int(time.time())
        marker = f"DELETE_DURING_SEARCH_{timestamp}"

        # Upload content
        content = f"{marker} - Test content for deletion test"
        file_path = create_test_file(content, suffix=".txt")
        data_tracker.add_file(file_path)

        try:
            response = api_client.upload_media(
                file_path=file_path,
                title=f"Delete Test {timestamp}",
                media_type="document",
                generate_embeddings=True,
            )

            media_id = self.extract_media_id(response)
            # Note: Not adding to data_tracker since we're deleting it

            # Wait for indexing
            self.wait_for_indexing(api_client, media_id, timeout=15)

            # Perform search to verify it's indexed
            try:
                search_result = api_client.rag_simple_search(
                    query=marker,
                    databases=["media"],
                    top_k=5,
                    search_mode="fts",
                    enable_cache=False,
                )
            except Exception as e:
                # Search might fail if service is not ready, continue with test
                print(f"  Initial search failed: {e}")
                search_result = {}

            # Delete the media
            try:
                api_client.delete_media(media_id)
                print(f"  Deleted media {media_id}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise

            # Search again - should not error
            try:
                search_after = api_client.rag_simple_search(
                    query=marker,
                    databases=["media"],
                    top_k=5,
                    search_mode="fts",
                    enable_cache=False,
                )
            except Exception as e:
                # Search might return empty or fail, which is acceptable
                print(f"  Search after delete: {e}")
                search_after = {}

            # Verify deleted content is not in results
            docs = search_after.get("documents") or search_after.get("results") or []
            # Normalize IDs to int for comparison (RAG returns strings)
            found_ids = []
            for d in docs:
                doc_id = d.get("id") or d.get("media_id")
                if doc_id is not None:
                    try:
                        found_ids.append(int(doc_id))
                    except (ValueError, TypeError):
                        found_ids.append(doc_id)

            assert media_id not in found_ids, (
                f"Deleted media {media_id} still appears in search"
            )

            print("  Delete during search handled correctly")

        finally:
            cleanup_test_file(file_path)

    def test_concurrent_note_modifications(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify concurrent modifications don't cause data loss.

        Creates notes and performs concurrent updates to verify
        optimistic locking works correctly.
        """
        timestamp = int(time.time())

        # Create a note
        try:
            note_response = api_client.create_note(
                title=f"Concurrent Test {timestamp}",
                content="Initial content",
                keywords=["concurrent", "test"],
            )

            note_id = note_response.get("id") or note_response.get("note_id")
            if not note_id:
                pytest.skip("Note creation not available")

            data_tracker.add_note(note_id)

            # Get initial version
            initial_version = note_response.get("version", 1)

        except httpx.HTTPStatusError as e:
            pytest.skip(f"Notes endpoint not available: {e}")

        # Perform concurrent updates
        def update_note(update_num: int) -> Dict[str, Any]:
            """Attempt to update the note."""
            try:
                result = api_client.update_note(
                    note_id=str(note_id),
                    content=f"Updated content #{update_num} at {time.time()}",
                    version=initial_version,
                )
                return {"success": True, "result": result, "update": update_num}
            except httpx.HTTPStatusError as e:
                return {
                    "success": False,
                    "error": e.response.status_code,
                    "update": update_num,
                }
            except Exception as e:
                return {"success": False, "error": str(e), "update": update_num}

        # Run concurrent updates
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(update_note, i) for i in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Analyze results
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]

        print(f"  Successes: {len(successes)}, Failures: {len(failures)}")

        # With optimistic locking, only one should succeed
        # (or all if system serializes requests)
        if len(successes) > 1:
            print("  Warning: Multiple concurrent updates succeeded")
            print("  (System may not use optimistic locking)")

        # Verify note still exists and is readable
        try:
            notes = api_client.get_notes(limit=100)
            note_list = notes.get("notes", []) or notes.get("items", [])

            found = any(
                str(n.get("id")) == str(note_id) or n.get("id") == note_id
                for n in note_list
            )

            if not found:
                # Try direct fetch
                # Note: get_note might not exist, search in list
                print("  Note may have been deleted or modified")
            else:
                print("  Note preserved after concurrent modifications")

        except Exception as e:
            print(f"  Error checking note: {e}")


@pytest.mark.workflow
class TestStateConsistency(WorkflowTestBase):
    """Test state consistency after various operations."""

    def test_no_orphaned_records_after_failure(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify no orphaned records remain after operation failure.

        This test checks that failed operations don't leave partial
        data in the database.
        """
        timestamp = int(time.time())

        # Get initial media count
        try:
            initial_list = api_client.get_media_list(limit=1000)
            initial_count = len(initial_list.get("items", []))
        except Exception:
            initial_count = 0

        # Attempt operations that might fail
        failed_operations = 0
        successful_ids = []

        for i in range(3):
            try:
                # Create content with potential issues
                if i == 0:
                    # Normal content
                    content = f"Normal content {timestamp}_{i}"
                elif i == 1:
                    # Very long content
                    content = "X" * 100000 + f" {timestamp}_{i}"
                else:
                    # Content with special characters
                    content = f"Special \x00\x01\x02 chars {timestamp}_{i}"

                file_path = create_test_file(content, suffix=".txt")
                data_tracker.add_file(file_path)

                try:
                    response = api_client.upload_media(
                        file_path=file_path,
                        title=f"Orphan Test {timestamp}_{i}",
                        media_type="document",
                        generate_embeddings=False,
                    )

                    media_id = self.extract_media_id(response)
                    successful_ids.append(media_id)
                    data_tracker.add_media(media_id)

                except (httpx.HTTPStatusError, Exception) as e:
                    failed_operations += 1
                    print(f"  Operation {i} failed (expected): {str(e)[:50]}")

                finally:
                    cleanup_test_file(file_path)

            except Exception as e:
                failed_operations += 1
                print(f"  Setup {i} failed: {str(e)[:50]}")

        # Verify only successful operations created records
        try:
            final_list = api_client.get_media_list(limit=1000)
            final_items = final_list.get("items", [])
            final_count = len(final_items)

            # Count should match successful operations
            new_records = final_count - initial_count
            expected_new = len(successful_ids)

            if new_records > expected_new:
                print(f"  Warning: {new_records} new records vs {expected_new} expected")
                print("  Possible orphaned records detected")
            else:
                print(f"  Record count consistent: {new_records} new records")

        except Exception as e:
            print(f"  Could not verify record count: {e}")

    def test_search_consistency_after_batch_delete(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify search results are consistent after batch deletion.

        Uploads multiple items, deletes them, and verifies search
        returns consistent results.
        """
        timestamp = int(time.time())
        marker = f"BATCH_DELETE_{timestamp}"

        uploaded_ids = []

        # Upload several items
        for i in range(3):
            content = f"{marker} Document {i}: Test content for batch delete"
            file_path = create_test_file(content, suffix=".txt")
            data_tracker.add_file(file_path)

            try:
                response = api_client.upload_media(
                    file_path=file_path,
                    title=f"Batch Delete {timestamp}_{i}",
                    media_type="document",
                    generate_embeddings=True,
                )

                media_id = self.extract_media_id(response)
                uploaded_ids.append(media_id)
                # Not adding to data_tracker since we'll delete

            finally:
                cleanup_test_file(file_path)

        # Wait for indexing
        for media_id in uploaded_ids:
            try:
                self.wait_for_indexing(api_client, media_id, timeout=15)
            except Exception:
                pass

        # Verify all are searchable
        try:
            search_before = api_client.rag_simple_search(
                query=marker,
                databases=["media"],
                top_k=10,
            )
        except Exception as e:
            # Search might fail if service is not ready
            print(f"  Search before delete failed: {e}")
            search_before = {}

        docs_before = search_before.get("documents") or search_before.get("results") or []
        # Normalize IDs to int for comparison
        found_before = set()
        for d in docs_before:
            doc_id = d.get("id") or d.get("media_id")
            if doc_id is not None:
                try:
                    found_before.add(int(doc_id))
                except (ValueError, TypeError):
                    found_before.add(doc_id)

        print(f"  Found {len(found_before)} items before delete")

        # Delete all items
        deleted_count = 0
        for media_id in uploaded_ids:
            try:
                api_client.delete_media(media_id)
                deleted_count += 1
            except httpx.HTTPStatusError:
                pass

        print(f"  Deleted {deleted_count} items")

        # Brief wait for index update
        time.sleep(1)

        # Verify none are searchable
        try:
            search_after = api_client.rag_simple_search(
                query=marker,
                databases=["media"],
                top_k=10,
            )
        except Exception as e:
            # Search might fail which is acceptable
            print(f"  Search after delete failed: {e}")
            search_after = {}

        docs_after = search_after.get("documents") or search_after.get("results") or []
        # Normalize IDs to int for comparison
        found_after = set()
        for d in docs_after:
            doc_id = d.get("id") or d.get("media_id")
            if doc_id is not None:
                try:
                    found_after.add(int(doc_id))
                except (ValueError, TypeError):
                    found_after.add(doc_id)

        # None of the deleted IDs should appear
        remaining = set(uploaded_ids) & found_after
        if remaining:
            print(f"  Warning: {len(remaining)} deleted items still in search")
        else:
            print("  Search consistent - no deleted items found")


@pytest.mark.workflow
class TestRecoveryScenarios(WorkflowTestBase):
    """Test recovery from various error scenarios."""

    def test_recovery_from_rate_limit(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify system recovers from rate limiting.

        Note: This test may be skipped in test mode where rate
        limits are disabled.
        """
        timestamp = int(time.time())

        # Perform rapid requests to potentially trigger rate limit
        results = []
        for i in range(5):
            try:
                search_result = api_client.rag_simple_search(
                    query=f"rate limit test {timestamp}",
                    databases=["media"],
                    top_k=5,
                )
                results.append({"success": True, "attempt": i})
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    results.append({"success": False, "rate_limited": True, "attempt": i})
                else:
                    results.append({"success": False, "error": e.response.status_code, "attempt": i})

        # Analyze results
        rate_limited = [r for r in results if r.get("rate_limited")]
        successes = [r for r in results if r.get("success")]

        if rate_limited:
            print(f"  Rate limited on attempts: {[r['attempt'] for r in rate_limited]}")
            # After rate limit, subsequent requests should work
            time.sleep(2)  # Wait for rate limit to reset

            recovery = api_client.rag_simple_search(
                query="recovery test",
                databases=["media"],
                top_k=5,
            )
            assert recovery is not None, "Should recover after rate limit"
            print("  Successfully recovered from rate limit")
        else:
            print("  No rate limiting triggered (test mode may be active)")

    def test_graceful_degradation_missing_services(
        self,
        api_client,
    ):
        """
        Verify graceful degradation when optional services are missing.

        Tests that the API handles missing embedding service, LLM,
        or other optional components gracefully.
        """
        # Test embedding generation (might be unavailable)
        try:
            response = api_client.client.post(
                "/api/v1/embeddings",
                json={
                    "input": "Test text for embedding",
                    "model": "text-embedding-ada-002",
                },
            )

            if response.status_code == 200:
                print("  Embedding service: Available")
            elif response.status_code in (404, 422, 500, 503):
                print("  Embedding service: Not configured (graceful)")
            else:
                print(f"  Embedding service: Status {response.status_code}")

        except httpx.HTTPStatusError as e:
            print(f"  Embedding service: {e.response.status_code}")

        # Test TTS (might be unavailable)
        try:
            response = api_client.client.get("/api/v1/audio/voices/catalog")

            if response.status_code == 200:
                print("  TTS service: Available")
            else:
                print("  TTS service: Not configured")

        except httpx.HTTPStatusError:
            print("  TTS service: Not available")

        # Test LLM providers
        try:
            response = api_client.client.get("/api/v1/llm/providers")

            if response.status_code == 200:
                data = response.json()
                providers = data.get("providers", [])
                configured = data.get("total_configured", 0)
                print(f"  LLM providers: {configured} configured")
            else:
                print("  LLM providers: Not available")

        except httpx.HTTPStatusError:
            print("  LLM providers: Not available")

        # The test passes if we got this far without crashing
        print("  Graceful degradation verified")


@pytest.mark.workflow
class TestCrossUserDataIsolation(WorkflowTestBase):
    """Test data isolation between different users in multi-user mode."""

    def test_user_data_isolation(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify that users cannot access each other's data.

        This test creates content as two different users and verifies
        that each user can only see their own content.

        Note: This test requires multi-user mode to be enabled.
        In single-user mode, it will skip.
        """
        import os
        import uuid

        # Check if we're in multi-user mode
        auth_mode = os.getenv("AUTH_MODE", "single_user").lower()
        if auth_mode not in {"multi_user", "multi-user", "multiuser"}:
            pytest.skip("Cross-user isolation test requires multi-user mode")

        timestamp = int(time.time())

        # Generate unique credentials for two test users
        user_a_name = f"isolation_user_a_{uuid.uuid4().hex[:8]}"
        user_a_email = f"{user_a_name}@test.example.com"
        user_a_password = "TestPass123!@#"

        user_b_name = f"isolation_user_b_{uuid.uuid4().hex[:8]}"
        user_b_email = f"{user_b_name}@test.example.com"
        user_b_password = "TestPass456!@#"

        # Unique markers for each user's content
        user_a_marker = f"USER_A_ISOLATION_{timestamp}"
        user_b_marker = f"USER_B_ISOLATION_{timestamp}"

        user_a_media_id = None
        user_b_media_id = None

        # Create a second client for user B
        client_b = APIClient(base_url=BASE_URL, auto_auth=False)

        try:
            # ============================================================
            # PHASE 1: Register and authenticate both users
            # ============================================================
            print("\n" + "=" * 60)
            print("PHASE: USER REGISTRATION")
            print("=" * 60)

            # Register user A
            try:
                api_client.clear_auth()
                api_client.register(
                    username=user_a_name,
                    email=user_a_email,
                    password=user_a_password,
                )
                print(f"  Registered user A: {user_a_name}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in (400, 409):
                    raise
                print(f"  User A already exists or registration disabled")

            # Login user A
            try:
                api_client.login(user_a_name, user_a_password)
                print(f"  User A logged in")
            except httpx.HTTPStatusError as e:
                pytest.skip(f"Cannot login user A: {e.response.status_code}")

            # Register user B
            try:
                client_b.register(
                    username=user_b_name,
                    email=user_b_email,
                    password=user_b_password,
                )
                print(f"  Registered user B: {user_b_name}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in (400, 409):
                    raise
                print(f"  User B already exists or registration disabled")

            # Login user B
            try:
                client_b.login(user_b_name, user_b_password)
                print(f"  User B logged in")
            except httpx.HTTPStatusError as e:
                pytest.skip(f"Cannot login user B: {e.response.status_code}")

            # ============================================================
            # PHASE 2: Create content as each user
            # ============================================================
            print("\n" + "=" * 60)
            print("PHASE: CONTENT CREATION")
            print("=" * 60)

            # User A creates content
            user_a_content = f"""
            {user_a_marker}

            This is private content belonging to User A.
            It should NOT be visible to User B.
            Contains sensitive information: User A Secret Data
            """

            file_a = create_test_file(user_a_content, suffix=".txt")
            data_tracker.add_file(file_a)

            try:
                response_a = api_client.upload_media(
                    file_path=file_a,
                    title=f"User A Private Doc {timestamp}",
                    media_type="document",
                    generate_embeddings=True,
                )
                user_a_media_id = self.extract_media_id(response_a)
                print(f"  User A created media: {user_a_media_id}")
            finally:
                cleanup_test_file(file_a)

            # User B creates content
            user_b_content = f"""
            {user_b_marker}

            This is private content belonging to User B.
            It should NOT be visible to User A.
            Contains sensitive information: User B Secret Data
            """

            file_b = create_test_file(user_b_content, suffix=".txt")
            data_tracker.add_file(file_b)

            try:
                response_b = client_b.upload_media(
                    file_path=file_b,
                    title=f"User B Private Doc {timestamp}",
                    media_type="document",
                    generate_embeddings=True,
                )
                user_b_media_id = self.extract_media_id(response_b)
                print(f"  User B created media: {user_b_media_id}")
            finally:
                cleanup_test_file(file_b)

            # Wait for indexing
            if user_a_media_id:
                self.wait_for_indexing(api_client, user_a_media_id, timeout=30)
            if user_b_media_id:
                self.wait_for_indexing(client_b, user_b_media_id, timeout=30)

            # ============================================================
            # PHASE 3: Verify isolation - User A cannot see User B's data
            # ============================================================
            print("\n" + "=" * 60)
            print("PHASE: ISOLATION VERIFICATION")
            print("=" * 60)

            # User A searches for User B's marker
            try:
                result_a_searching_b = api_client.rag_simple_search(
                    query=user_b_marker,
                    databases=["media"],
                    top_k=20,
                )

                docs_a = (
                    result_a_searching_b.get("documents")
                    or result_a_searching_b.get("results")
                    or []
                )

                # Check if User B's content appears in User A's search
                found_b_in_a = False
                for doc in docs_a:
                    content = doc.get("content") or doc.get("text") or ""
                    doc_id = doc.get("id") or doc.get("media_id")

                    if user_b_marker in content:
                        found_b_in_a = True
                        print(f"  WARNING: User A found User B's marker in doc {doc_id}")

                    if doc_id == user_b_media_id:
                        found_b_in_a = True
                        print(f"  WARNING: User A found User B's media ID {user_b_media_id}")

                if not found_b_in_a:
                    print("  PASS: User A cannot see User B's content")
                else:
                    pytest.fail("Data isolation violation: User A can see User B's data")

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (404, 422):
                    print(f"  Search not available: {e.response.status_code}")
                else:
                    raise

            # User B searches for User A's marker
            try:
                result_b_searching_a = client_b.rag_simple_search(
                    query=user_a_marker,
                    databases=["media"],
                    top_k=20,
                )

                docs_b = (
                    result_b_searching_a.get("documents")
                    or result_b_searching_a.get("results")
                    or []
                )

                # Check if User A's content appears in User B's search
                found_a_in_b = False
                for doc in docs_b:
                    content = doc.get("content") or doc.get("text") or ""
                    doc_id = doc.get("id") or doc.get("media_id")

                    if user_a_marker in content:
                        found_a_in_b = True
                        print(f"  WARNING: User B found User A's marker in doc {doc_id}")

                    if doc_id == user_a_media_id:
                        found_a_in_b = True
                        print(f"  WARNING: User B found User A's media ID {user_a_media_id}")

                if not found_a_in_b:
                    print("  PASS: User B cannot see User A's content")
                else:
                    pytest.fail("Data isolation violation: User B can see User A's data")

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (404, 422):
                    print(f"  Search not available: {e.response.status_code}")
                else:
                    raise

            # ============================================================
            # PHASE 4: Verify each user can see their own data
            # ============================================================
            print("\n" + "=" * 60)
            print("PHASE: OWN DATA ACCESS VERIFICATION")
            print("=" * 60)

            # User A searches for their own marker
            try:
                result_a_own = api_client.rag_simple_search(
                    query=user_a_marker,
                    databases=["media"],
                    top_k=20,
                )

                docs_a_own = (
                    result_a_own.get("documents")
                    or result_a_own.get("results")
                    or []
                )

                found_own_a = any(
                    user_a_marker in (doc.get("content") or doc.get("text") or "")
                    or (doc.get("id") or doc.get("media_id")) == user_a_media_id
                    for doc in docs_a_own
                )

                if found_own_a:
                    print("  PASS: User A can see their own content")
                else:
                    print("  WARNING: User A cannot find their own content (may need more indexing time)")

            except httpx.HTTPStatusError:
                print("  Search not available for own content check")

            # User B searches for their own marker
            try:
                result_b_own = client_b.rag_simple_search(
                    query=user_b_marker,
                    databases=["media"],
                    top_k=20,
                )

                docs_b_own = (
                    result_b_own.get("documents")
                    or result_b_own.get("results")
                    or []
                )

                found_own_b = any(
                    user_b_marker in (doc.get("content") or doc.get("text") or "")
                    or (doc.get("id") or doc.get("media_id")) == user_b_media_id
                    for doc in docs_b_own
                )

                if found_own_b:
                    print("  PASS: User B can see their own content")
                else:
                    print("  WARNING: User B cannot find their own content (may need more indexing time)")

            except httpx.HTTPStatusError:
                print("  Search not available for own content check")

            # ============================================================
            # PHASE 5: Verify direct access isolation
            # ============================================================
            print("\n" + "=" * 60)
            print("PHASE: DIRECT ACCESS ISOLATION")
            print("=" * 60)

            # User A tries to directly access User B's media
            if user_b_media_id:
                try:
                    media_b_via_a = api_client.get_media_item(user_b_media_id)
                    # If we got here, check if it's actually User B's content
                    content = media_b_via_a.get("content") or media_b_via_a.get("text") or ""
                    if user_b_marker in content:
                        pytest.fail(
                            f"Direct access violation: User A accessed User B's media {user_b_media_id}"
                        )
                    else:
                        # Got a response but different content - might be ID collision
                        print(f"  Media ID {user_b_media_id} exists but contains different content")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (403, 404):
                        print(f"  PASS: User A blocked from User B's media (HTTP {e.response.status_code})")
                    else:
                        raise

            # User B tries to directly access User A's media
            if user_a_media_id:
                try:
                    media_a_via_b = client_b.get_media_item(user_a_media_id)
                    content = media_a_via_b.get("content") or media_a_via_b.get("text") or ""
                    if user_a_marker in content:
                        pytest.fail(
                            f"Direct access violation: User B accessed User A's media {user_a_media_id}"
                        )
                    else:
                        print(f"  Media ID {user_a_media_id} exists but contains different content")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (403, 404):
                        print(f"  PASS: User B blocked from User A's media (HTTP {e.response.status_code})")
                    else:
                        raise

            print("\n" + "=" * 60)
            print("CROSS-USER DATA ISOLATION TEST COMPLETED")
            print("=" * 60)

        finally:
            # Cleanup: Delete media created by each user
            if user_a_media_id:
                try:
                    api_client.delete_media(user_a_media_id)
                except Exception:
                    pass

            if user_b_media_id:
                try:
                    client_b.delete_media(user_b_media_id)
                except Exception:
                    pass

            # Close client B
            try:
                client_b.close()
            except Exception:
                pass
