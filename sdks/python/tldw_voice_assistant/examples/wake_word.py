#!/usr/bin/env python3
"""
Wake word example for tldw Voice Assistant SDK.

This example demonstrates:
1. Wake word detection using Porcupine or OpenWakeWord
2. Audio streaming to voice assistant after wake word
3. TTS playback of responses

Usage:
    # With Porcupine (requires access key)
    python wake_word.py --token YOUR_API_KEY --engine porcupine --access-key YOUR_PORCUPINE_KEY

    # With OpenWakeWord (open source)
    python wake_word.py --token YOUR_API_KEY --engine openwakeword
"""

import argparse
import asyncio
import sys
from typing import Optional

import numpy as np


async def main(
    ws_url: str,
    token: str,
    engine: str,
    access_key: Optional[str] = None,
    keyword: str = "jarvis",
) -> None:
    """Main function."""
    from tldw_voice_assistant import VoiceAssistantClient, VoiceAssistantConfig
    from tldw_voice_assistant.audio import AudioCapture, AudioPlayer

    print(f"Initializing wake word detection with {engine}...")

    # Initialize wake word detector
    if engine == "porcupine":
        if not access_key:
            print("Error: Porcupine requires --access-key")
            sys.exit(1)

        try:
            import pvporcupine
        except ImportError:
            print("Error: pvporcupine not installed. Run: pip install pvporcupine")
            sys.exit(1)

        porcupine = pvporcupine.create(
            access_key=access_key,
            keywords=[keyword],
            sensitivities=[0.5],
        )
        frame_length = porcupine.frame_length
        sample_rate = porcupine.sample_rate

        def detect_wake_word(audio: np.ndarray) -> bool:
            # Convert to int16 for Porcupine
            pcm = (audio * 32767).astype(np.int16)
            result = porcupine.process(pcm[:frame_length])
            return result >= 0

    elif engine == "openwakeword":
        try:
            import openwakeword
            from openwakeword.model import Model
        except ImportError:
            print("Error: openwakeword not installed. Run: pip install openwakeword")
            sys.exit(1)

        # Download and load default models
        openwakeword.utils.download_models()
        oww_model = Model()
        sample_rate = 16000

        def detect_wake_word(audio: np.ndarray) -> bool:
            predictions = oww_model.predict(audio)
            # Check if any model detected wake word
            for model_name, scores in predictions.items():
                if any(score > 0.5 for score in scores):
                    return True
            return False

    else:
        print(f"Error: Unknown engine: {engine}")
        sys.exit(1)

    # Initialize voice assistant client
    config = VoiceAssistantConfig(
        ws_url=ws_url,
        token=token,
        sample_rate=sample_rate,
    )

    client = VoiceAssistantClient(config)

    # Initialize audio
    capture = AudioCapture(sample_rate=sample_rate)
    player = AudioPlayer()

    # State
    is_listening = False
    audio_buffer: list[np.ndarray] = []
    silence_frames = 0
    max_silence_frames = 30  # About 2 seconds of silence

    # Event handlers
    @client.on_connected
    def on_connected() -> None:
        print("Connected to voice assistant")

    @client.on_action_result
    def on_result(result) -> None:
        print(f"\nAssistant: {result.response_text}\n")

    @client.on_tts_chunk
    def on_tts(chunk) -> None:
        player.add_chunk(chunk.data, format=chunk.format)

    @client.on_error
    def on_error(error) -> None:
        print(f"Error: {error.error}")

    # Audio processing
    @capture.on_data
    def on_audio(audio: np.ndarray) -> None:
        nonlocal is_listening, audio_buffer, silence_frames

        if not is_listening:
            # Check for wake word
            if detect_wake_word(audio):
                print("\n*** Wake word detected! Listening... ***")
                is_listening = True
                audio_buffer = []
                silence_frames = 0

                # Connect if not already
                if not client.is_connected:
                    asyncio.create_task(client.connect())
        else:
            # Add to buffer
            audio_buffer.append(audio)

            # Check for silence (end of utterance)
            level = np.sqrt(np.mean(audio**2))
            if level < 0.01:
                silence_frames += 1
                if silence_frames >= max_silence_frames:
                    print("*** End of speech detected ***")
                    is_listening = False

                    # Send buffered audio
                    if client.is_connected and audio_buffer:
                        full_audio = np.concatenate(audio_buffer)
                        asyncio.create_task(client.send_audio(full_audio))
                        asyncio.create_task(client.commit())

                    audio_buffer = []
            else:
                silence_frames = 0

            # Stream audio in real-time if connected
            if client.is_connected:
                asyncio.create_task(client.send_audio(audio))

    @capture.on_level
    def on_level(level: float) -> None:
        if is_listening:
            # Simple level indicator
            bars = int(level * 20)
            print(f"\r[{'=' * bars}{' ' * (20 - bars)}]", end="", flush=True)

    # Start
    print(f"\nListening for wake word: '{keyword}'")
    print("Speak after the wake word is detected.")
    print("Press Ctrl+C to exit.\n")

    capture.start()

    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        capture.stop()
        player.stop()
        await client.disconnect()

        # Cleanup Porcupine if used
        if engine == "porcupine":
            porcupine.delete()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wake Word Voice Assistant")
    parser.add_argument(
        "--url",
        default="ws://localhost:8000/api/v1/voice/assistant",
        help="WebSocket URL",
    )
    parser.add_argument(
        "--token",
        required=True,
        help="API key or JWT token",
    )
    parser.add_argument(
        "--engine",
        choices=["porcupine", "openwakeword"],
        default="openwakeword",
        help="Wake word engine to use",
    )
    parser.add_argument(
        "--access-key",
        help="Porcupine access key (required for porcupine engine)",
    )
    parser.add_argument(
        "--keyword",
        default="jarvis",
        help="Wake word keyword (for porcupine)",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            args.url,
            args.token,
            args.engine,
            args.access_key,
            args.keyword,
        )
    )
