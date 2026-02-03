# VoiceAssistant/db_helpers.py
# Database helper functions for persisting voice commands and sessions
#
#######################################################################################################################
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from .schemas import ActionType, VoiceCommand, VoiceSessionContext, VoiceSessionState


def save_voice_command(
    db,
    command: VoiceCommand,
) -> str:
    """
    Save a voice command to the database.

    Args:
        db: CharactersRAGDB instance
        command: VoiceCommand to save

    Returns:
        The command ID
    """
    command_id = command.id or str(uuid.uuid4())

    with db.transaction():
        db.execute_query(
            """
            INSERT INTO voice_commands (
                id, user_id, name, phrases, action_type, action_config,
                priority, enabled, requires_confirmation, description,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                phrases = excluded.phrases,
                action_type = excluded.action_type,
                action_config = excluded.action_config,
                priority = excluded.priority,
                enabled = excluded.enabled,
                requires_confirmation = excluded.requires_confirmation,
                description = excluded.description,
                updated_at = excluded.updated_at
            """,
            (
                command_id,
                command.user_id,
                command.name,
                json.dumps(command.phrases),
                command.action_type.value,
                json.dumps(command.action_config),
                command.priority,
                1 if command.enabled else 0,
                1 if command.requires_confirmation else 0,
                command.description,
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )

    logger.debug(f"Saved voice command: {command.name} (id={command_id})")
    return command_id


def get_voice_command(
    db,
    command_id: str,
    user_id: Optional[int] = None,
) -> Optional[VoiceCommand]:
    """
    Get a voice command by ID.

    Args:
        db: CharactersRAGDB instance
        command_id: Command ID
        user_id: Optional user ID filter

    Returns:
        VoiceCommand if found, None otherwise
    """
    query = "SELECT * FROM voice_commands WHERE id = ? AND deleted = 0"
    params = [command_id]

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    result = db.execute_query(query, tuple(params))
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)

    if not rows:
        return None

    return _row_to_voice_command(rows[0])


def get_user_voice_commands(
    db,
    user_id: int,
    include_system: bool = True,
    enabled_only: bool = True,
) -> list[VoiceCommand]:
    """
    Get all voice commands for a user.

    Args:
        db: CharactersRAGDB instance
        user_id: User ID
        include_system: Include system commands (user_id=0)
        enabled_only: Only return enabled commands

    Returns:
        List of VoiceCommand objects
    """
    conditions = ["deleted = 0"]
    params = []

    if include_system:
        conditions.append("(user_id = ? OR user_id = 0)")
        params.append(user_id)
    else:
        conditions.append("user_id = ?")
        params.append(user_id)

    if enabled_only:
        conditions.append("enabled = 1")

    query = f"""
        SELECT * FROM voice_commands
        WHERE {' AND '.join(conditions)}
        ORDER BY priority DESC, name ASC
    """

    result = db.execute_query(query, tuple(params))
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)

    return [_row_to_voice_command(row) for row in rows]


def delete_voice_command(
    db,
    command_id: str,
    user_id: int,
    hard_delete: bool = False,
) -> bool:
    """
    Delete a voice command.

    Args:
        db: CharactersRAGDB instance
        command_id: Command ID
        user_id: User ID (must match for non-system commands)
        hard_delete: If True, permanently delete; otherwise soft delete

    Returns:
        True if deleted, False if not found or not authorized
    """
    # Check command exists and belongs to user
    command = get_voice_command(db, command_id)
    if not command:
        return False

    # Can't delete system commands (user_id=0) unless admin
    if command.user_id == 0:
        return False

    if command.user_id != user_id:
        return False

    with db.transaction():
        if hard_delete:
            db.execute_query(
                "DELETE FROM voice_commands WHERE id = ?",
                (command_id,),
            )
        else:
            db.execute_query(
                "UPDATE voice_commands SET deleted = 1, updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), command_id),
            )

    logger.debug(f"Deleted voice command: {command_id}")
    return True


def save_voice_session(
    db,
    session: VoiceSessionContext,
) -> str:
    """
    Save a voice session to the database.

    Args:
        db: CharactersRAGDB instance
        session: VoiceSessionContext to save

    Returns:
        The session ID
    """
    with db.transaction():
        db.execute_query(
            """
            INSERT INTO voice_sessions (
                session_id, user_id, state, context,
                conversation_history, pending_intent, last_action_result,
                created_at, last_activity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                state = excluded.state,
                context = excluded.context,
                conversation_history = excluded.conversation_history,
                pending_intent = excluded.pending_intent,
                last_action_result = excluded.last_action_result,
                last_activity = excluded.last_activity
            """,
            (
                session.session_id,
                session.user_id,
                session.state.value,
                json.dumps(session.metadata),
                json.dumps(session.conversation_history),
                json.dumps(session.pending_intent.model_dump()) if session.pending_intent else None,
                json.dumps(session.last_action_result) if session.last_action_result else None,
                session.created_at.isoformat(),
                session.last_activity.isoformat(),
            ),
        )

    logger.debug(f"Saved voice session: {session.session_id}")
    return session.session_id


def get_voice_session(
    db,
    session_id: str,
) -> Optional[VoiceSessionContext]:
    """
    Get a voice session by ID.

    Args:
        db: CharactersRAGDB instance
        session_id: Session ID

    Returns:
        VoiceSessionContext if found, None otherwise
    """
    result = db.execute_query(
        "SELECT * FROM voice_sessions WHERE session_id = ?",
        (session_id,),
    )
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)

    if not rows:
        return None

    return _row_to_voice_session(rows[0])


def get_user_voice_sessions(
    db,
    user_id: int,
    limit: int = 10,
) -> list[VoiceSessionContext]:
    """
    Get recent voice sessions for a user.

    Args:
        db: CharactersRAGDB instance
        user_id: User ID
        limit: Maximum sessions to return

    Returns:
        List of VoiceSessionContext objects
    """
    result = db.execute_query(
        """
        SELECT * FROM voice_sessions
        WHERE user_id = ?
        ORDER BY last_activity DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)

    return [_row_to_voice_session(row) for row in rows]


def delete_voice_session(
    db,
    session_id: str,
) -> bool:
    """
    Delete a voice session.

    Args:
        db: CharactersRAGDB instance
        session_id: Session ID

    Returns:
        True if deleted, False if not found
    """
    with db.transaction():
        result = db.execute_query(
            "DELETE FROM voice_sessions WHERE session_id = ?",
            (session_id,),
        )

    deleted = result.rowcount > 0 if hasattr(result, 'rowcount') else True
    if deleted:
        logger.debug(f"Deleted voice session: {session_id}")
    return deleted


def cleanup_old_sessions(
    db,
    max_age_hours: int = 24,
) -> int:
    """
    Clean up old voice sessions.

    Args:
        db: CharactersRAGDB instance
        max_age_hours: Maximum session age in hours

    Returns:
        Number of sessions deleted
    """
    with db.transaction():
        result = db.execute_query(
            """
            DELETE FROM voice_sessions
            WHERE last_activity < datetime('now', ?)
            """,
            (f"-{max_age_hours} hours",),
        )

    count = result.rowcount if hasattr(result, 'rowcount') else 0
    if count > 0:
        logger.info(f"Cleaned up {count} old voice sessions")
    return count


def record_voice_command_event(
    db,
    *,
    command_id: Optional[str],
    command_name: Optional[str],
    user_id: int,
    action_type: ActionType,
    success: bool,
    response_time_ms: Optional[float] = None,
    session_id: Optional[str] = None,
) -> None:
    """
    Record a voice command execution event for analytics.

    Args:
        db: CharactersRAGDB instance
        command_id: Command ID (nullable for fallback commands)
        command_name: Command name (nullable)
        user_id: User ID
        action_type: Action type for the command
        success: Whether the action succeeded
        response_time_ms: Optional response time
        session_id: Optional session ID
    """
    with db.transaction():
        db.execute_query(
            """
            INSERT INTO voice_command_events (
                command_id, command_name, user_id, action_type,
                success, response_time_ms, session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command_id,
                command_name,
                user_id,
                action_type.value,
                1 if success else 0,
                response_time_ms,
                session_id,
            ),
        )


def get_voice_command_usage_stats(
    db,
    *,
    command_id: str,
    user_id: int,
    days: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """
    Get usage statistics for a specific voice command.

    Args:
        db: CharactersRAGDB instance
        command_id: Command ID
        user_id: User ID
        days: Optional lookback window in days

    Returns:
        Dict with usage stats or None if no data
    """
    params: list[Any] = [command_id, user_id]
    date_filter = ""
    if days is not None:
        date_filter = " AND created_at >= datetime('now', ?)"
        params.append(f"-{days} days")

    result = db.execute_query(
        f"""
        SELECT
            command_id,
            MAX(command_name) AS command_name,
            COUNT(*) AS total_invocations,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS error_count,
            AVG(response_time_ms) AS avg_response_time_ms,
            MAX(created_at) AS last_used
        FROM voice_command_events
        WHERE command_id = ? AND user_id = ?{date_filter}
        """,
        tuple(params),
    )
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)
    if not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        row = dict(row)
    if not row or row.get("total_invocations") in (None, 0):
        return None

    return {
        "command_id": row.get("command_id"),
        "command_name": row.get("command_name"),
        "total_invocations": row.get("total_invocations") or 0,
        "success_count": row.get("success_count") or 0,
        "error_count": row.get("error_count") or 0,
        "avg_response_time_ms": row.get("avg_response_time_ms") or 0.0,
        "last_used": row.get("last_used"),
    }


def get_voice_top_commands(
    db,
    *,
    user_id: int,
    days: Optional[int] = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Get top voice commands by usage.

    Args:
        db: CharactersRAGDB instance
        user_id: User ID
        days: Optional lookback window in days
        limit: Maximum commands to return

    Returns:
        List of usage stats for top commands
    """
    params: list[Any] = [user_id]
    date_filter = ""
    if days is not None:
        date_filter = " AND created_at >= datetime('now', ?)"
        params.append(f"-{days} days")

    params.append(limit)

    result = db.execute_query(
        f"""
        SELECT
            command_id,
            MAX(command_name) AS command_name,
            COUNT(*) AS total_invocations,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS error_count,
            AVG(response_time_ms) AS avg_response_time_ms,
            MAX(created_at) AS last_used
        FROM voice_command_events
        WHERE user_id = ?{date_filter}
        GROUP BY command_id
        ORDER BY total_invocations DESC
        LIMIT ?
        """,
        tuple(params),
    )
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)

    top_commands = []
    for row in rows:
        if not isinstance(row, dict):
            row = dict(row)
        top_commands.append(
            {
                "command_id": row.get("command_id"),
                "command_name": row.get("command_name"),
                "total_invocations": row.get("total_invocations") or 0,
                "success_count": row.get("success_count") or 0,
                "error_count": row.get("error_count") or 0,
                "avg_response_time_ms": row.get("avg_response_time_ms") or 0.0,
                "last_used": row.get("last_used"),
            }
        )
    return top_commands


def get_voice_usage_by_day(
    db,
    *,
    user_id: Optional[int] = None,
    days: int = 7,
) -> list[dict[str, Any]]:
    """
    Get daily voice usage metrics.

    Args:
        db: CharactersRAGDB instance
        user_id: Optional user ID filter
        days: Lookback window in days

    Returns:
        List of daily analytics dicts
    """
    params: list[Any] = [f"-{days} days"]
    user_filter = ""
    if user_id is not None:
        user_filter = " AND user_id = ?"
        params.append(user_id)

    result = db.execute_query(
        f"""
        SELECT
            date(created_at) AS day,
            COUNT(*) AS total_commands,
            COUNT(DISTINCT user_id) AS unique_users,
            COALESCE(SUM(success) * 1.0 / NULLIF(COUNT(*), 0), 0.0) AS success_rate,
            AVG(response_time_ms) AS avg_response_time_ms
        FROM voice_command_events
        WHERE created_at >= datetime('now', ?){user_filter}
        GROUP BY day
        ORDER BY day ASC
        """,
        tuple(params),
    )
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)

    usage_by_day = []
    for row in rows:
        if not isinstance(row, dict):
            row = dict(row)
        usage_by_day.append(
            {
                "date": row.get("day"),
                "total_commands": row.get("total_commands") or 0,
                "unique_users": row.get("unique_users") or 0,
                "success_rate": row.get("success_rate") or 0.0,
                "avg_response_time_ms": row.get("avg_response_time_ms") or 0.0,
            }
        )
    return usage_by_day


def get_voice_analytics_summary_stats(
    db,
    *,
    user_id: Optional[int] = None,
    days: int = 7,
) -> dict[str, Any]:
    """
    Get aggregate voice analytics stats.

    Args:
        db: CharactersRAGDB instance
        user_id: Optional user ID filter
        days: Lookback window in days

    Returns:
        Dict with total, success_rate, avg_response_time_ms
    """
    params: list[Any] = [f"-{days} days"]
    user_filter = ""
    if user_id is not None:
        user_filter = " AND user_id = ?"
        params.append(user_id)

    result = db.execute_query(
        f"""
        SELECT
            COUNT(*) AS total_commands,
            COALESCE(SUM(success) * 1.0 / NULLIF(COUNT(*), 0), 0.0) AS success_rate,
            AVG(response_time_ms) AS avg_response_time_ms
        FROM voice_command_events
        WHERE created_at >= datetime('now', ?){user_filter}
        """,
        tuple(params),
    )
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)
    if not rows:
        return {"total_commands": 0, "success_rate": 0.0, "avg_response_time_ms": 0.0}

    row = rows[0]
    if not isinstance(row, dict):
        row = dict(row)
    return {
        "total_commands": row.get("total_commands") or 0,
        "success_rate": row.get("success_rate") or 0.0,
        "avg_response_time_ms": row.get("avg_response_time_ms") or 0.0,
    }


def get_active_voice_session_count(
    db,
    *,
    user_id: int,
    activity_window_seconds: int,
) -> int:
    """
    Count active voice sessions within a recent activity window.

    Args:
        db: CharactersRAGDB instance
        user_id: User ID
        activity_window_seconds: Window in seconds to consider active

    Returns:
        Active session count
    """
    result = db.execute_query(
        """
        SELECT COUNT(*) AS count
        FROM voice_sessions
        WHERE user_id = ?
          AND last_activity >= datetime('now', ?)
        """,
        (user_id, f"-{activity_window_seconds} seconds"),
    )
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)
    if not rows:
        return 0
    row = rows[0]
    if not isinstance(row, dict):
        row = dict(row)
    return int(row.get("count") or 0)


def get_voice_command_counts(
    db,
    *,
    user_id: int,
) -> dict[str, int]:
    """
    Count total and enabled voice commands for a user (excluding system commands).

    Args:
        db: CharactersRAGDB instance
        user_id: User ID

    Returns:
        Dict with total and enabled counts
    """
    result = db.execute_query(
        """
        SELECT
            COUNT(*) AS total_commands,
            SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) AS enabled_commands
        FROM voice_commands
        WHERE user_id = ? AND deleted = 0
        """,
        (user_id,),
    )
    rows = result.fetchall() if hasattr(result, 'fetchall') else list(result)
    if not rows:
        return {"total": 0, "enabled": 0}
    row = rows[0]
    if not isinstance(row, dict):
        row = dict(row)
    return {"total": row.get("total_commands") or 0, "enabled": row.get("enabled_commands") or 0}


def _row_to_voice_command(row: dict[str, Any]) -> VoiceCommand:
    """Convert a database row to a VoiceCommand."""
    if not isinstance(row, dict):
        row = dict(row)
    phrases = row.get("phrases", "[]")
    if isinstance(phrases, str):
        phrases = json.loads(phrases)

    action_config = row.get("action_config", "{}")
    if isinstance(action_config, str):
        action_config = json.loads(action_config)

    created_at = row.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)

    updated_at = row.get("updated_at")
    if isinstance(updated_at, str):
        updated_at = datetime.fromisoformat(updated_at)

    return VoiceCommand(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        phrases=phrases,
        action_type=ActionType(row["action_type"]),
        action_config=action_config,
        priority=row.get("priority", 0),
        enabled=bool(row.get("enabled", 1)),
        requires_confirmation=bool(row.get("requires_confirmation", 0)),
        description=row.get("description"),
        created_at=created_at,
        updated_at=updated_at,
    )


def _row_to_voice_session(row: dict[str, Any]) -> VoiceSessionContext:
    """Convert a database row to a VoiceSessionContext."""
    from .schemas import VoiceIntent

    if not isinstance(row, dict):
        row = dict(row)
    metadata = row.get("context", "{}")
    if isinstance(metadata, str):
        metadata = json.loads(metadata) if metadata else {}

    conversation_history = row.get("conversation_history", "[]")
    if isinstance(conversation_history, str):
        conversation_history = json.loads(conversation_history) if conversation_history else []

    pending_intent_data = row.get("pending_intent")
    pending_intent = None
    if pending_intent_data:
        if isinstance(pending_intent_data, str):
            pending_intent_data = json.loads(pending_intent_data)
        if pending_intent_data:
            pending_intent = VoiceIntent(**pending_intent_data)

    last_action_result = row.get("last_action_result")
    if isinstance(last_action_result, str):
        last_action_result = json.loads(last_action_result) if last_action_result else None

    created_at = row.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)

    last_activity = row.get("last_activity")
    if isinstance(last_activity, str):
        last_activity = datetime.fromisoformat(last_activity)

    return VoiceSessionContext(
        session_id=row["session_id"],
        user_id=row["user_id"],
        state=VoiceSessionState(row.get("state", "idle")),
        conversation_history=conversation_history,
        pending_intent=pending_intent,
        last_action_result=last_action_result,
        metadata=metadata,
        created_at=created_at or datetime.utcnow(),
        last_activity=last_activity or datetime.utcnow(),
    )


#
# End of VoiceAssistant/db_helpers.py
#######################################################################################################################
