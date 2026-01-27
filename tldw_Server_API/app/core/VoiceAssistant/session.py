# VoiceAssistant/session.py
# Voice Session Manager - Maintains context across voice commands
#
#######################################################################################################################
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from loguru import logger

from .schemas import VoiceIntent, VoiceSessionContext, VoiceSessionState


class VoiceSessionManager:
    """
    Manages voice assistant sessions and their contexts.

    Sessions track:
    - Conversation history for context
    - Pending confirmations
    - Session state (idle, listening, processing, etc.)
    - Last action results
    """

    # Session timeout in seconds (30 minutes of inactivity)
    SESSION_TIMEOUT = 30 * 60

    # Maximum concurrent sessions per user
    MAX_SESSIONS_PER_USER = 5

    def __init__(self):
        """Initialize the session manager."""
        self._sessions: Dict[str, VoiceSessionContext] = {}
        self._user_sessions: Dict[int, set] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the session manager and cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Voice session manager started")

    async def stop(self) -> None:
        """Stop the session manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Voice session manager stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup loop: {e}")

    async def _cleanup_expired_sessions(self) -> None:
        """Remove sessions that have exceeded the timeout."""
        now = datetime.utcnow()
        timeout_threshold = now - timedelta(seconds=self.SESSION_TIMEOUT)

        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.last_activity < timeout_threshold
        ]

        for session_id in expired:
            await self.end_session(session_id)

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired voice sessions")

    async def create_session(
        self,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VoiceSessionContext:
        """
        Create a new voice session.

        Args:
            user_id: User ID for the session
            metadata: Optional session metadata

        Returns:
            The new session context
        """
        # Check session limit per user
        if user_id in self._user_sessions:
            if len(self._user_sessions[user_id]) >= self.MAX_SESSIONS_PER_USER:
                # Remove oldest session
                oldest = await self._get_oldest_session(user_id)
                if oldest:
                    await self.end_session(oldest)

        session_id = str(uuid.uuid4())
        session = VoiceSessionContext(
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {},
        )

        self._sessions[session_id] = session

        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = set()
        self._user_sessions[user_id].add(session_id)

        logger.debug(f"Created voice session {session_id} for user {user_id}")
        return session

    async def _get_oldest_session(self, user_id: int) -> Optional[str]:
        """Get the oldest session for a user."""
        if user_id not in self._user_sessions:
            return None

        oldest_id = None
        oldest_time = datetime.utcnow()

        for session_id in self._user_sessions[user_id]:
            session = self._sessions.get(session_id)
            if session and session.created_at < oldest_time:
                oldest_time = session.created_at
                oldest_id = session_id

        return oldest_id

    async def get_session(
        self,
        session_id: str,
        touch: bool = True,
    ) -> Optional[VoiceSessionContext]:
        """
        Get a session by ID.

        Args:
            session_id: The session ID
            touch: Whether to update last_activity timestamp

        Returns:
            The session context if found, None otherwise
        """
        session = self._sessions.get(session_id)
        if session and touch:
            session.last_activity = datetime.utcnow()
        return session

    async def get_or_create_session(
        self,
        session_id: Optional[str],
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[VoiceSessionContext, bool]:
        """
        Get an existing session or create a new one.

        Args:
            session_id: Optional existing session ID
            user_id: User ID
            metadata: Optional metadata for new sessions

        Returns:
            Tuple of (session, was_created)
        """
        if session_id:
            session = await self.get_session(session_id)
            if session and session.user_id == user_id:
                return session, False

        session = await self.create_session(user_id, metadata)
        return session, True

    async def end_session(self, session_id: str) -> bool:
        """
        End a voice session.

        Args:
            session_id: The session ID to end

        Returns:
            True if session was ended, False if not found
        """
        session = self._sessions.pop(session_id, None)
        if session:
            if session.user_id in self._user_sessions:
                self._user_sessions[session.user_id].discard(session_id)
            logger.debug(f"Ended voice session {session_id}")
            return True
        return False

    async def update_state(
        self,
        session_id: str,
        state: VoiceSessionState,
    ) -> bool:
        """
        Update session state.

        Args:
            session_id: The session ID
            state: New state

        Returns:
            True if updated, False if session not found
        """
        session = await self.get_session(session_id)
        if session:
            session.state = state
            return True
        return False

    async def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a conversation turn to the session.

        Args:
            session_id: The session ID
            role: Role (user, assistant, system)
            content: Turn content
            metadata: Optional turn metadata

        Returns:
            True if added, False if session not found
        """
        session = await self.get_session(session_id)
        if session:
            session.add_turn(role, content, metadata)
            return True
        return False

    async def set_pending_intent(
        self,
        session_id: str,
        intent: Optional[VoiceIntent],
    ) -> bool:
        """
        Set or clear the pending intent awaiting confirmation.

        Args:
            session_id: The session ID
            intent: The intent to set, or None to clear

        Returns:
            True if set, False if session not found
        """
        session = await self.get_session(session_id)
        if session:
            session.pending_intent = intent
            if intent:
                session.state = VoiceSessionState.AWAITING_CONFIRMATION
            else:
                session.state = VoiceSessionState.IDLE
            return True
        return False

    async def get_pending_intent(self, session_id: str) -> Optional[VoiceIntent]:
        """
        Get the pending intent for a session.

        Args:
            session_id: The session ID

        Returns:
            The pending intent if any, None otherwise
        """
        session = await self.get_session(session_id, touch=False)
        return session.pending_intent if session else None

    async def set_last_action_result(
        self,
        session_id: str,
        result: Dict[str, Any],
    ) -> bool:
        """
        Store the result of the last executed action.

        Args:
            session_id: The session ID
            result: Action result to store

        Returns:
            True if stored, False if session not found
        """
        session = await self.get_session(session_id)
        if session:
            session.last_action_result = result
            return True
        return False

    def get_session_count(self, user_id: Optional[int] = None) -> int:
        """
        Get the number of active sessions.

        Args:
            user_id: Optional user ID to count sessions for

        Returns:
            Number of active sessions
        """
        if user_id is not None:
            return len(self._user_sessions.get(user_id, set()))
        return len(self._sessions)


# Singleton instance
_session_manager_instance: Optional[VoiceSessionManager] = None


def get_voice_session_manager() -> VoiceSessionManager:
    """Get the singleton voice session manager instance."""
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = VoiceSessionManager()
    return _session_manager_instance


#
# End of VoiceAssistant/session.py
#######################################################################################################################
