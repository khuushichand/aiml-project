"""
Voice Assistant WebSocket Client.

Provides async interface for connecting to tldw voice assistant.
"""

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

import websockets
from websockets.client import WebSocketClientProtocol

from .types import (
    ActionResult,
    IntentResult,
    TranscriptionResult,
    TTSChunk,
    VoiceActionType,
    VoiceAssistantState,
    VoiceError,
    WorkflowComplete,
    WorkflowProgress,
    WSMessageType,
)

logger = logging.getLogger(__name__)


@dataclass
class VoiceAssistantConfig:
    """Configuration for VoiceAssistantClient."""

    ws_url: str
    """WebSocket URL for the voice assistant endpoint."""

    token: str
    """Authentication token (JWT or API key)."""

    stt_model: str = "parakeet"
    """STT model to use."""

    stt_language: Optional[str] = None
    """Language code for STT."""

    tts_provider: str = "kokoro"
    """TTS provider."""

    tts_voice: str = "af_heart"
    """TTS voice."""

    tts_format: str = "mp3"
    """TTS audio format."""

    sample_rate: int = 16000
    """Audio sample rate in Hz."""

    session_id: Optional[str] = None
    """Resume existing session ID."""

    auto_reconnect: bool = True
    """Auto-reconnect on disconnect."""

    max_reconnect_attempts: int = 5
    """Maximum reconnection attempts."""

    reconnect_delay: float = 1.0
    """Initial reconnection delay in seconds."""

    debug: bool = False
    """Enable debug logging."""


# Event callback types
TranscriptionCallback = Callable[[TranscriptionResult], None]
IntentCallback = Callable[[IntentResult], None]
ActionResultCallback = Callable[[ActionResult], None]
TTSChunkCallback = Callable[[TTSChunk], None]
StateChangeCallback = Callable[[VoiceAssistantState, Optional[VoiceAssistantState]], None]
ErrorCallback = Callable[[VoiceError], None]
WorkflowProgressCallback = Callable[[WorkflowProgress], None]
WorkflowCompleteCallback = Callable[[WorkflowComplete], None]


class VoiceAssistantClient:
    """
    WebSocket client for tldw Voice Assistant.

    Usage:
        config = VoiceAssistantConfig(
            ws_url="ws://localhost:8000/api/v1/voice/assistant",
            token="your-api-key",
        )

        client = VoiceAssistantClient(config)

        @client.on_transcription
        def handle_transcription(result):
            print(f"Transcription: {result.text}")

        @client.on_action_result
        def handle_result(result):
            print(f"Response: {result.response_text}")

        async with client:
            await client.send_text("search for machine learning")
    """

    def __init__(self, config: VoiceAssistantConfig):
        """Initialize the voice assistant client."""
        self.config = config
        self._ws: Optional[WebSocketClientProtocol] = None
        self._state: VoiceAssistantState = VoiceAssistantState.IDLE
        self._session_id: Optional[str] = None
        self._user_id: Optional[int] = None
        self._reconnect_attempts = 0
        self._audio_sequence = 0
        self._running = False
        self._receive_task: Optional[asyncio.Task[None]] = None

        # Event callbacks
        self._on_connected: List[Callable[[], None]] = []
        self._on_disconnected: List[Callable[[str], None]] = []
        self._on_transcription: List[TranscriptionCallback] = []
        self._on_intent: List[IntentCallback] = []
        self._on_action_result: List[ActionResultCallback] = []
        self._on_tts_chunk: List[TTSChunkCallback] = []
        self._on_tts_end: List[Callable[[], None]] = []
        self._on_state_change: List[StateChangeCallback] = []
        self._on_error: List[ErrorCallback] = []
        self._on_workflow_progress: List[WorkflowProgressCallback] = []
        self._on_workflow_complete: List[WorkflowCompleteCallback] = []

        if config.debug:
            logging.basicConfig(level=logging.DEBUG)

    async def __aenter__(self) -> "VoiceAssistantClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if connected to the server."""
        return self._ws is not None and self._ws.open

    @property
    def state(self) -> VoiceAssistantState:
        """Get current state."""
        return self._state

    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID."""
        return self._session_id

    @property
    def user_id(self) -> Optional[int]:
        """Get current user ID."""
        return self._user_id

    # Event decorator methods

    def on_connected(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register callback for connection event."""
        self._on_connected.append(callback)
        return callback

    def on_disconnected(self, callback: Callable[[str], None]) -> Callable[[str], None]:
        """Register callback for disconnection event."""
        self._on_disconnected.append(callback)
        return callback

    def on_transcription(self, callback: TranscriptionCallback) -> TranscriptionCallback:
        """Register callback for transcription events."""
        self._on_transcription.append(callback)
        return callback

    def on_intent(self, callback: IntentCallback) -> IntentCallback:
        """Register callback for intent events."""
        self._on_intent.append(callback)
        return callback

    def on_action_result(self, callback: ActionResultCallback) -> ActionResultCallback:
        """Register callback for action result events."""
        self._on_action_result.append(callback)
        return callback

    def on_tts_chunk(self, callback: TTSChunkCallback) -> TTSChunkCallback:
        """Register callback for TTS chunk events."""
        self._on_tts_chunk.append(callback)
        return callback

    def on_tts_end(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register callback for TTS end events."""
        self._on_tts_end.append(callback)
        return callback

    def on_state_change(self, callback: StateChangeCallback) -> StateChangeCallback:
        """Register callback for state change events."""
        self._on_state_change.append(callback)
        return callback

    def on_error(self, callback: ErrorCallback) -> ErrorCallback:
        """Register callback for error events."""
        self._on_error.append(callback)
        return callback

    def on_workflow_progress(
        self, callback: WorkflowProgressCallback
    ) -> WorkflowProgressCallback:
        """Register callback for workflow progress events."""
        self._on_workflow_progress.append(callback)
        return callback

    def on_workflow_complete(
        self, callback: WorkflowCompleteCallback
    ) -> WorkflowCompleteCallback:
        """Register callback for workflow complete events."""
        self._on_workflow_complete.append(callback)
        return callback

    # Connection methods

    async def connect(self) -> None:
        """Connect to the voice assistant server."""
        if self.is_connected:
            logger.debug("Already connected")
            return

        try:
            # Build URL with token
            url = f"{self.config.ws_url}?token={self.config.token}"
            logger.debug(f"Connecting to {self.config.ws_url}")

            self._ws = await websockets.connect(url)

            # Authenticate
            await self._authenticate()

            # Configure
            await self._configure()

            # Start receive loop
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._reconnect_attempts = 0

            for callback in self._on_connected:
                callback()

            logger.info("Connected to voice assistant")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        self._state = VoiceAssistantState.IDLE
        self._session_id = None
        self._user_id = None

        for callback in self._on_disconnected:
            callback("Client disconnect")

        logger.info("Disconnected from voice assistant")

    # Audio methods

    async def send_audio(self, audio_data: Union[bytes, "np.ndarray"]) -> None:  # type: ignore
        """
        Send audio data to the server.

        Args:
            audio_data: Raw PCM bytes or numpy array of float32 samples
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")

        # Convert numpy array to bytes if needed
        if hasattr(audio_data, "tobytes"):
            audio_bytes = audio_data.tobytes()
        else:
            audio_bytes = audio_data

        # Encode as base64
        b64_data = base64.b64encode(audio_bytes).decode("ascii")

        await self._send(
            {
                "type": WSMessageType.AUDIO.value,
                "data": b64_data,
                "sequence": self._audio_sequence,
            }
        )
        self._audio_sequence += 1

    async def commit(self) -> None:
        """Signal end of utterance."""
        if not self.is_connected:
            raise RuntimeError("Not connected")

        self._audio_sequence = 0
        await self._send({"type": WSMessageType.COMMIT.value})

    async def cancel(self) -> None:
        """Cancel current operation."""
        if not self.is_connected:
            raise RuntimeError("Not connected")

        self._audio_sequence = 0
        await self._send({"type": WSMessageType.CANCEL.value})

    async def send_text(self, text: str) -> None:
        """
        Send a text command (bypasses STT).

        Args:
            text: Text command to process
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")

        await self._send({"type": WSMessageType.TEXT.value, "text": text})

    # Workflow methods

    async def subscribe_to_workflow(self, run_id: str) -> None:
        """
        Subscribe to workflow progress updates.

        Args:
            run_id: Workflow run ID
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")

        await self._send(
            {"type": WSMessageType.WORKFLOW_SUBSCRIBE.value, "run_id": run_id}
        )

    async def cancel_workflow(self, run_id: str) -> None:
        """
        Cancel a running workflow.

        Args:
            run_id: Workflow run ID
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")

        await self._send({"type": WSMessageType.WORKFLOW_CANCEL.value, "run_id": run_id})

    # Private methods

    async def _authenticate(self) -> None:
        """Authenticate with the server."""
        await self._send({"type": WSMessageType.AUTH.value, "token": self.config.token})

        # Wait for auth response
        response = await self._receive_one()
        if response.get("type") == WSMessageType.AUTH_OK.value:
            self._user_id = response.get("user_id")
            self._session_id = response.get("session_id")
            logger.debug(f"Authenticated: user={self._user_id}, session={self._session_id}")
        elif response.get("type") == WSMessageType.AUTH_ERROR.value:
            raise RuntimeError(f"Authentication failed: {response.get('error')}")
        else:
            raise RuntimeError(f"Unexpected response: {response}")

    async def _configure(self) -> None:
        """Send configuration to the server."""
        config_msg: Dict[str, Any] = {
            "type": WSMessageType.CONFIG.value,
            "stt_model": self.config.stt_model,
            "tts_provider": self.config.tts_provider,
            "tts_voice": self.config.tts_voice,
            "tts_format": self.config.tts_format,
            "sample_rate": self.config.sample_rate,
        }

        if self.config.stt_language:
            config_msg["stt_language"] = self.config.stt_language
        if self.config.session_id:
            config_msg["session_id"] = self.config.session_id

        await self._send(config_msg)

        # Wait for config ack
        response = await self._receive_one()
        if response.get("type") == WSMessageType.CONFIG_ACK.value:
            self._session_id = response.get("session_id", self._session_id)
            logger.debug(f"Configured: session={self._session_id}")
        else:
            logger.warning(f"Unexpected config response: {response}")

    async def _send(self, message: Dict[str, Any]) -> None:
        """Send a message to the server."""
        if not self._ws:
            raise RuntimeError("Not connected")

        await self._ws.send(json.dumps(message))

    async def _receive_one(self) -> Dict[str, Any]:
        """Receive a single message from the server."""
        if not self._ws:
            raise RuntimeError("Not connected")

        data = await self._ws.recv()
        return json.loads(data)

    async def _receive_loop(self) -> None:
        """Main receive loop."""
        while self._running and self._ws:
            try:
                data = await self._ws.recv()
                message = json.loads(data)
                await self._handle_message(message)
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Connection closed: {e}")
                await self._handle_disconnect(str(e))
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming message."""
        msg_type = message.get("type")
        logger.debug(f"Received: {msg_type}")

        if msg_type == WSMessageType.STATE_CHANGE.value:
            previous = self._state
            self._state = VoiceAssistantState(message.get("state", "idle"))
            for callback in self._on_state_change:
                callback(self._state, previous)

        elif msg_type == WSMessageType.TRANSCRIPTION.value:
            result = TranscriptionResult(
                text=message.get("text", ""),
                is_final=message.get("is_final", False),
                confidence=message.get("confidence"),
            )
            for callback in self._on_transcription:
                callback(result)

        elif msg_type == WSMessageType.INTENT.value:
            result = IntentResult(
                action_type=VoiceActionType(message.get("action_type", "custom")),
                command_name=message.get("command_name"),
                entities=message.get("entities", {}),
                confidence=message.get("confidence", 0.0),
                requires_confirmation=message.get("requires_confirmation", False),
            )
            for callback in self._on_intent:
                callback(result)

        elif msg_type == WSMessageType.ACTION_RESULT.value:
            result = ActionResult(
                success=message.get("success", False),
                action_type=VoiceActionType(message.get("action_type", "custom")),
                response_text=message.get("response_text", ""),
                result_data=message.get("result_data"),
                execution_time_ms=message.get("execution_time_ms", 0.0),
            )
            for callback in self._on_action_result:
                callback(result)

        elif msg_type == WSMessageType.TTS_CHUNK.value:
            chunk = TTSChunk(
                data=base64.b64decode(message.get("data", "")),
                sequence=message.get("sequence", 0),
                format=message.get("format", "mp3"),
            )
            for callback in self._on_tts_chunk:
                callback(chunk)

        elif msg_type == WSMessageType.TTS_END.value:
            for callback in self._on_tts_end:
                callback()

        elif msg_type == WSMessageType.WORKFLOW_PROGRESS.value:
            progress = WorkflowProgress(
                run_id=message.get("run_id", ""),
                event_type=message.get("event_type", ""),
                message=message.get("message"),
                data=message.get("data", {}),
                timestamp=message.get("timestamp", 0.0),
            )
            for callback in self._on_workflow_progress:
                callback(progress)

        elif msg_type == WSMessageType.WORKFLOW_COMPLETE.value:
            complete = WorkflowComplete(
                run_id=message.get("run_id", ""),
                status=message.get("status", ""),
                response_text=message.get("response_text", ""),
                outputs=message.get("outputs"),
                error=message.get("error"),
                duration_ms=message.get("duration_ms"),
            )
            for callback in self._on_workflow_complete:
                callback(complete)

        elif msg_type == WSMessageType.ERROR.value:
            error = VoiceError(
                error=message.get("error", "Unknown error"),
                code=message.get("code"),
                recoverable=message.get("recoverable", True),
            )
            for callback in self._on_error:
                callback(error)

    async def _handle_disconnect(self, reason: str) -> None:
        """Handle disconnection."""
        self._ws = None
        self._state = VoiceAssistantState.IDLE

        for callback in self._on_disconnected:
            callback(reason)

        # Auto-reconnect if enabled
        if (
            self.config.auto_reconnect
            and self._running
            and self._reconnect_attempts < self.config.max_reconnect_attempts
        ):
            delay = self.config.reconnect_delay * (2**self._reconnect_attempts)
            logger.info(
                f"Reconnecting in {delay}s "
                f"(attempt {self._reconnect_attempts + 1}/{self.config.max_reconnect_attempts})"
            )
            await asyncio.sleep(delay)
            self._reconnect_attempts += 1
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
