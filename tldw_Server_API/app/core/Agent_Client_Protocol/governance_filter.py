"""GovernanceFilter -- pipeline stage between adapter and event bus.

Intercepts TOOL_CALL events and applies permission tier logic:
- ``auto`` tier tools pass through immediately.
- ``batch`` / ``individual`` tier tools are held pending human approval.
"""
from __future__ import annotations

import uuid

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind
from tldw_Server_API.app.core.Agent_Client_Protocol.permission_tiers import determine_permission_tier


class GovernanceFilter:
    """Pipeline stage that gates tool calls based on permission tiers.

    The adapter's ``event_callback`` should point at :meth:`process`.  Non-tool
    events are forwarded to the bus immediately.  Tool calls are classified via
    :func:`determine_permission_tier` and either forwarded (``auto``) or held
    until a human decision arrives via :meth:`on_permission_response`.
    """

    def __init__(
        self,
        bus: SessionEventBus,
        default_timeout_sec: int = 300,
    ) -> None:
        self._bus = bus
        self._default_timeout_sec = default_timeout_sec
        # request_id -> held AgentEvent
        self._pending: dict[str, AgentEvent] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def pending_count(self) -> int:
        """Number of tool calls awaiting a permission decision."""
        return len(self._pending)

    # ------------------------------------------------------------------
    # Pipeline entry point
    # ------------------------------------------------------------------

    async def process(self, event: AgentEvent) -> None:
        """Route *event* through governance logic.

        Non-TOOL_CALL events are forwarded to the bus immediately.
        TOOL_CALL events are classified by permission tier.
        """
        if event.kind != AgentEventKind.TOOL_CALL:
            await self._bus.publish(event)
            return

        tool_name: str = event.payload.get("tool_name", "")
        # Use the adapter-provided tier if present; fall back to re-resolving
        tier = event.payload.get("permission_tier") or determine_permission_tier(tool_name)

        if tier == "auto":
            await self._bus.publish(event)
            return

        # Hold the event and publish a permission request
        request_id = str(uuid.uuid4())
        self._pending[request_id] = event

        perm_request = AgentEvent(
            session_id=event.session_id,
            kind=AgentEventKind.PERMISSION_REQUEST,
            payload={
                "request_id": request_id,
                "tool_name": tool_name,
                "arguments": event.payload.get("arguments", {}),
                "tier": tier,
                "timeout_sec": self._default_timeout_sec,
            },
        )
        await self._bus.publish(perm_request)
        logger.info(
            "Governance: held tool_call '{}' (tier={}) as request_id={}",
            tool_name,
            tier,
            request_id,
        )

    # ------------------------------------------------------------------
    # Permission responses
    # ------------------------------------------------------------------

    async def on_permission_response(
        self,
        request_id: str,
        decision: str,
        reason: str | None = None,
    ) -> None:
        """Handle a human decision for a held tool call.

        Parameters
        ----------
        request_id:
            The id from the PERMISSION_REQUEST payload.
        decision:
            ``"approve"`` or ``"deny"``.
        reason:
            Optional human-supplied reason (used in deny error message).
        """
        held_event = self._pending.pop(request_id, None)
        if held_event is None:
            logger.warning(
                "Governance: permission response for unknown request_id={}",
                request_id,
            )
            return

        if decision == "approve":
            await self._bus.publish(held_event)
            logger.info("Governance: approved request_id={}", request_id)
        else:
            # Emit an error TOOL_RESULT so the agent knows the call was denied
            tool_name = held_event.payload.get("tool_name", "unknown")
            error_msg = f"Permission denied for tool '{tool_name}'"
            if reason:
                error_msg += f": {reason}"

            error_event = AgentEvent(
                session_id=held_event.session_id,
                kind=AgentEventKind.TOOL_RESULT,
                payload={
                    "tool_id": held_event.payload.get("tool_id", ""),
                    "tool_name": tool_name,
                    "output": error_msg,
                    "is_error": True,
                    "duration_ms": 0,
                },
            )
            await self._bus.publish(error_event)
            logger.info(
                "Governance: denied request_id={} reason={}",
                request_id,
                reason,
            )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def cancel_all_pending(self) -> None:
        """Cancel all pending permission requests (e.g. on session teardown)."""
        for request_id in list(self._pending):
            await self.on_permission_response(
                request_id,
                decision="deny",
                reason="session cancelled",
            )
