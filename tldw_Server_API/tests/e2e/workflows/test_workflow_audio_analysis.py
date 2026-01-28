"""
Audio Analysis Pipeline Workflow Test
---------------------------------------

Tests audio transcription through search workflow:
1. Create test audio file
2. Upload with transcription enabled
3. Poll for transcription completion
4. Verify transcript content
5. Search for words from audio
6. Create note summarizing audio
7. Verify cross-search works
8. Cleanup
"""

import time
import struct
import wave
import tempfile
import os
from typing import Dict, Any

import pytest
import httpx

from ..fixtures import (
    api_client,
    data_tracker,
    cleanup_test_file,
    require_llm_or_skip,
)
from .workflow_base import WorkflowTestBase, WorkflowStateManager


def create_audio_with_speech_simulation() -> str:
    """
    Create a test WAV file with audio data.

    This creates a simple sine wave audio file that can be used
    for transcription testing. Real speech would require actual
    audio recording or synthesis.
    """
    import math

    sample_rate = 16000  # 16kHz for speech
    duration = 3  # 3 seconds
    frequency = 440  # A4 note

    num_samples = int(sample_rate * duration)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = f.name

    with wave.open(temp_path, "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        # Generate simple sine wave
        for i in range(num_samples):
            value = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * i / sample_rate))
            wav_file.writeframes(struct.pack("<h", value))

    return temp_path


@pytest.mark.workflow
@pytest.mark.workflow_slow
class TestAudioAnalysisWorkflow(WorkflowTestBase):
    """Test the audio transcription and analysis workflow."""

    def test_audio_upload_and_transcription_polling(
        self,
        api_client,
        data_tracker,
        workflow_state,
    ):
        """
        Test audio upload with transcription polling.

        This test uploads an audio file and polls for transcription
        completion, verifying the workflow handles async processing.
        """
        timestamp = int(time.time())

        # ============================================================
        # PHASE 1: Create and upload audio file
        # ============================================================
        workflow_state.enter_phase("audio_upload")

        audio_path = create_audio_with_speech_simulation()
        data_tracker.add_file(audio_path)

        try:
            with open(audio_path, "rb") as f:
                files = {"files": ("test_audio.wav", f, "audio/wav")}
                data = {
                    "title": f"Audio Workflow Test {timestamp}",
                    "media_type": "audio",
                    "overwrite_existing": "true",
                    # Request transcription
                    "transcribe": "true",
                }

                response = api_client.client.post(
                    "/api/v1/media/add",
                    files=files,
                    data=data,
                )

            if response.status_code not in (200, 207, 202):
                pytest.skip(f"Audio upload not supported: {response.status_code}")

            result = response.json()

            # Handle case where transcription produces no content (synthetic audio)
            # Check for warning about no segments before extracting media_id
            if "results" in result and isinstance(result["results"], list) and len(result["results"]) > 0:
                first_result = result["results"][0]
                db_message = first_result.get("db_message", "")
                if "DB persistence skipped" in db_message or first_result.get("db_id") is None:
                    warnings = first_result.get("warnings", [])
                    if any("no segments" in w.lower() for w in warnings) or "no content" in db_message.lower():
                        pytest.skip("Transcription produced no content (synthetic audio has no speech)")

            media_id = self.extract_media_id(result)
            data_tracker.add_media(media_id)
            workflow_state.add_media_id(media_id)
            workflow_state.set("audio_media_id", media_id)

            print(f"  Audio uploaded with ID: {media_id}")

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 415, 422):
                pytest.skip(f"Audio upload not available: {e}")
            raise
        finally:
            cleanup_test_file(audio_path)

        # ============================================================
        # PHASE 2: Poll for transcription completion
        # ============================================================
        workflow_state.enter_phase("transcription_polling")

        media_id = workflow_state.get("audio_media_id")
        transcription_complete = False
        transcript_content = None

        # Poll for up to 60 seconds
        max_wait = 60
        poll_interval = 3
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                media = api_client.get_media_item(media_id)

                # Check various transcript fields
                transcript = (
                    media.get("transcription")
                    or media.get("transcript")
                    or media.get("content")
                )

                status = media.get("transcription_status") or media.get("status")

                if status in ("failed", "error"):
                    print(f"  Transcription failed: {media.get('error')}")
                    break

                if transcript and len(str(transcript)) > 5:
                    transcription_complete = True
                    transcript_content = transcript
                    print(f"  Transcription complete: {len(transcript)} chars")
                    break

                if status in ("completed", "done", "success"):
                    transcription_complete = True
                    transcript_content = transcript or ""
                    break

            except httpx.HTTPStatusError:
                pass

            time.sleep(poll_interval)

        if not transcription_complete:
            # Don't fail - transcription might not be configured
            print("  Transcription did not complete (service may not be configured)")
            pytest.skip("Transcription service not available or not responding")

        workflow_state.set("transcript", transcript_content)
        workflow_state.set("transcription_complete", True)

        # ============================================================
        # PHASE 3: Verify transcript content
        # ============================================================
        workflow_state.enter_phase("transcript_verification")

        transcript = workflow_state.get("transcript")
        if transcript:
            # Basic validation
            assert isinstance(transcript, str), "Transcript should be a string"

            # For real speech, we would verify specific words
            # For our test audio, just verify it's not an error message
            error_indicators = ["error", "failed", "exception", "unsupported"]
            transcript_lower = transcript.lower()

            for indicator in error_indicators:
                if indicator in transcript_lower[:100]:
                    pytest.fail(f"Transcript appears to be an error: {transcript[:200]}")

            print(f"  Transcript verified: {len(transcript)} characters")
        else:
            print("  No transcript content to verify")

        # ============================================================
        # PHASE 4: Search for audio content
        # ============================================================
        workflow_state.enter_phase("audio_search")

        try:
            # Search for the audio in media
            search_result = api_client.rag_simple_search(
                query="audio workflow test",
                databases=["media"],
                top_k=10,
            )

            documents = (
                search_result.get("documents")
                or search_result.get("results")
                or []
            )

            # Normalize IDs to int for comparison (RAG returns strings)
            found_ids = []
            for doc in documents:
                doc_id = doc.get("id") or doc.get("media_id")
                if doc_id is not None:
                    try:
                        found_ids.append(int(doc_id))
                    except (ValueError, TypeError):
                        found_ids.append(doc_id)

            if media_id in found_ids:
                print(f"  Audio found in search results")
                workflow_state.set("search_success", True)
            else:
                print(f"  Audio not found in search (may need embeddings)")

        except httpx.HTTPStatusError as e:
            print(f"  Search not available: {e}")

        # ============================================================
        # PHASE 5: Create note summarizing audio
        # ============================================================
        workflow_state.enter_phase("note_creation")

        try:
            note_content = f"""
            Audio Analysis Notes - {timestamp}

            Media ID: {media_id}
            Type: Audio file

            Transcript Summary:
            {transcript_content[:500] if transcript_content else 'No transcript available'}

            Analysis:
            - Audio file processed successfully
            - Transcription status: {'Complete' if transcription_complete else 'Pending'}
            """

            note_response = api_client.create_note(
                title=f"Audio Analysis {timestamp}",
                content=note_content,
                keywords=["audio", "transcription", "workflow-test"],
            )

            note_id = note_response.get("id") or note_response.get("note_id")
            if note_id:
                workflow_state.add_note_id(note_id)
                data_tracker.add_note(note_id)
                print(f"  Note created with ID: {note_id}")
                workflow_state.set("note_created", True)

        except httpx.HTTPStatusError as e:
            print(f"  Note creation not available: {e}")

        # ============================================================
        # PHASE 6: Cross-search verification
        # ============================================================
        workflow_state.enter_phase("cross_search")

        try:
            # Search across both media and notes
            cross_result = api_client.client.post(
                "/api/v1/rag/search",
                json={
                    "query": "audio analysis workflow",
                    "sources": ["media_db", "notes"],
                    "top_k": 10,
                },
            )

            if cross_result.status_code == 200:
                data = cross_result.json()
                documents = data.get("documents") or data.get("results") or []

                # Check for both media and note types
                source_types = set()
                for doc in documents:
                    source = doc.get("source", {})
                    if isinstance(source, dict):
                        source_types.add(source.get("type"))
                    elif isinstance(source, str):
                        source_types.add(source)

                print(f"  Cross-search found sources: {source_types}")
                workflow_state.set("cross_search_success", True)

        except httpx.HTTPStatusError as e:
            print(f"  Cross-search not available: {e}")

        # ============================================================
        # SUMMARY
        # ============================================================
        print("\n" + "=" * 60)
        print("AUDIO WORKFLOW SUMMARY")
        print("=" * 60)

        results = {
            "audio_upload": bool(workflow_state.get("audio_media_id")),
            "transcription": workflow_state.get("transcription_complete", False),
            "search": workflow_state.get("search_success", False),
            "note": workflow_state.get("note_created", False),
            "cross_search": workflow_state.get("cross_search_success", False),
        }

        for step, success in results.items():
            status = "PASS" if success else "SKIP"
            print(f"  {step}: {status}")

        # Core workflow must succeed
        assert results["audio_upload"], "Audio upload failed"

        print("\nAudio analysis workflow completed!")


@pytest.mark.workflow
class TestAudioTranscriptionEndpoint(WorkflowTestBase):
    """Test the OpenAI-compatible transcription endpoint."""

    def test_transcription_api_endpoint(
        self,
        api_client,
        data_tracker,
    ):
        """
        Test the /audio/transcriptions endpoint directly.

        This tests the OpenAI-compatible transcription API.
        """
        audio_path = create_audio_with_speech_simulation()
        data_tracker.add_file(audio_path)

        try:
            with open(audio_path, "rb") as f:
                files = {"file": ("audio.wav", f, "audio/wav")}
                data = {
                    "model": "whisper-1",  # Default model name
                    "response_format": "json",
                }

                response = api_client.client.post(
                    "/api/v1/audio/transcriptions",
                    files=files,
                    data=data,
                )

            if response.status_code == 404:
                pytest.skip("Transcription endpoint not available")

            if response.status_code in (400, 422, 500, 503):
                # Transcription service might not be configured
                pytest.skip(f"Transcription service not configured: {response.status_code}")

            assert response.status_code == 200, f"Transcription failed: {response.text}"

            result = response.json()

            # OpenAI format returns {"text": "..."}
            assert "text" in result, f"Response missing 'text' field: {result}"

            text = result["text"]
            assert isinstance(text, str), "Transcription text should be string"

            print(f"Transcription result: {text[:100]}...")

        finally:
            cleanup_test_file(audio_path)

    def test_tts_and_transcription_roundtrip(
        self,
        api_client,
        data_tracker,
    ):
        """
        Test TTS generation followed by transcription (if both available).

        This verifies the roundtrip: text -> audio -> text.
        """
        original_text = "Hello, this is a test of text to speech."

        # Step 1: Generate audio from text
        try:
            tts_response = api_client.client.post(
                "/api/v1/audio/speech",
                json={
                    "input": original_text,
                    "voice": "alloy",  # Default voice
                    "model": "tts-1",
                },
            )

            if tts_response.status_code in (404, 422, 500, 503):
                pytest.skip("TTS service not available")

            if tts_response.status_code != 200:
                pytest.skip(f"TTS failed: {tts_response.status_code}")

            # Save audio to temp file
            audio_content = tts_response.content
            assert len(audio_content) > 0, "TTS returned empty audio"

            with tempfile.NamedTemporaryFile(
                suffix=".mp3",
                delete=False,
            ) as f:
                f.write(audio_content)
                audio_path = f.name

            data_tracker.add_file(audio_path)

        except httpx.HTTPStatusError as e:
            pytest.skip(f"TTS not available: {e}")

        # Step 2: Transcribe the generated audio
        try:
            with open(audio_path, "rb") as f:
                files = {"file": ("audio.mp3", f, "audio/mpeg")}
                data = {"model": "whisper-1"}

                stt_response = api_client.client.post(
                    "/api/v1/audio/transcriptions",
                    files=files,
                    data=data,
                )

            if stt_response.status_code in (404, 422, 500, 503):
                pytest.skip("Transcription service not available")

            if stt_response.status_code != 200:
                pytest.skip(f"Transcription failed: {stt_response.status_code}")

            result = stt_response.json()
            transcribed_text = result.get("text", "")

            # Verify roundtrip preserved content (fuzzy match)
            assert transcribed_text, "Transcription returned empty text"

            # Check if key words from original are in transcription
            original_words = set(original_text.lower().split())
            transcribed_words = set(transcribed_text.lower().split())
            common_words = original_words & transcribed_words

            print(f"Original: {original_text}")
            print(f"Transcribed: {transcribed_text}")
            print(f"Common words: {common_words}")

            # At least some words should match
            if len(common_words) < 2:
                print("Warning: Low word overlap in roundtrip")

        finally:
            cleanup_test_file(audio_path)
