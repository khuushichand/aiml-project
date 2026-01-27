#!/usr/bin/env python3
"""
Basic usage example for tldw Voice Assistant SDK.

This example demonstrates:
1. Connecting to the voice assistant
2. Sending text commands
3. Handling responses and TTS playback

Usage:
    python basic_usage.py --token YOUR_API_KEY
"""

import argparse
import asyncio
import sys

from tldw_voice_assistant import (
    VoiceAssistantClient,
    VoiceAssistantConfig,
    ActionResult,
    TranscriptionResult,
    VoiceError,
)


async def main(ws_url: str, token: str) -> None:
    """Main function."""
    print(f"Connecting to {ws_url}...")

    config = VoiceAssistantConfig(
        ws_url=ws_url,
        token=token,
        debug=True,
    )

    client = VoiceAssistantClient(config)

    # Register event handlers
    @client.on_connected
    def on_connected() -> None:
        print("Connected to voice assistant!")

    @client.on_disconnected
    def on_disconnected(reason: str) -> None:
        print(f"Disconnected: {reason}")

    @client.on_transcription
    def on_transcription(result: TranscriptionResult) -> None:
        if result.is_final:
            print(f"You said: {result.text}")
        else:
            print(f"Transcribing: {result.text}")

    @client.on_action_result
    def on_action_result(result: ActionResult) -> None:
        print(f"\nResponse: {result.response_text}")
        if result.result_data:
            print(f"Data: {result.result_data}")

    @client.on_error
    def on_error(error: VoiceError) -> None:
        print(f"Error: {error.error}")
        if not error.recoverable:
            sys.exit(1)

    # Connect and interact
    async with client:
        print("\nVoice assistant ready!")
        print("Enter commands (or 'quit' to exit):\n")

        while True:
            try:
                command = await asyncio.get_event_loop().run_in_executor(
                    None, input, "> "
                )

                if command.lower() in ("quit", "exit", "q"):
                    break

                if command.strip():
                    await client.send_text(command)

                # Wait a bit for response
                await asyncio.sleep(2)

            except KeyboardInterrupt:
                break
            except EOFError:
                break

    print("\nGoodbye!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="tldw Voice Assistant Demo")
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
    args = parser.parse_args()

    asyncio.run(main(args.url, args.token))
