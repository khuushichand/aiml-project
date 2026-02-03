# VoiceAssistant/workflow_handler.py
# Workflow Handler - Bridges voice commands to workflow engine execution
#
#######################################################################################################################
import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any, Optional
from uuid import uuid4

from loguru import logger

from .schemas import ActionResult, ActionType, VoiceSessionContext


class WorkflowProgressEvent:
    """Represents a workflow progress event for streaming."""

    def __init__(
        self,
        event_type: str,
        run_id: str,
        data: Optional[dict[str, Any]] = None,
        message: Optional[str] = None,
        is_terminal: bool = False,
    ):
        self.event_type = event_type
        self.run_id = run_id
        self.data = data or {}
        self.message = message
        self.is_terminal = is_terminal
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "run_id": self.run_id,
            "data": self.data,
            "message": self.message,
            "is_terminal": self.is_terminal,
            "timestamp": self.timestamp,
        }


class VoiceWorkflowHandler:
    """
    Handles execution of workflows triggered by voice commands.

    Supports:
    - Synchronous execution (blocks until complete)
    - Asynchronous execution with progress streaming
    - Pre-defined workflow templates for common voice commands
    """

    # Terminal workflow statuses
    TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}

    def __init__(self):
        """Initialize the workflow handler."""
        self._db = None
        self._engine = None
        self._initialized = False

    async def _ensure_initialized(self) -> bool:
        """Lazy initialization of workflow components."""
        if self._initialized:
            return True

        try:
            from tldw_Server_API.app.core.DB_Management.DB_Manager import (
                create_workflows_database,
                get_content_backend_instance,
            )
            from tldw_Server_API.app.core.Workflows import WorkflowEngine

            backend = get_content_backend_instance()
            self._db = create_workflows_database(backend=backend)
            self._engine = WorkflowEngine(self._db)
            self._initialized = True
            logger.debug("Voice workflow handler initialized")
            return True

        except ImportError as e:
            logger.warning(f"Workflow engine not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize workflow handler: {e}")
            return False

    async def execute_workflow(
        self,
        workflow_id: Optional[int],
        workflow_definition: Optional[dict[str, Any]],
        inputs: dict[str, Any],
        user_id: int,
        session: VoiceSessionContext,
        sync: bool = True,
        timeout_seconds: float = 60.0,
    ) -> ActionResult:
        """
        Execute a workflow and return the result.

        Args:
            workflow_id: ID of saved workflow (if using stored workflow)
            workflow_definition: Ad-hoc workflow definition (if not using ID)
            inputs: Workflow inputs
            user_id: User executing the workflow
            session: Voice session context
            sync: If True, wait for completion; if False, return immediately
            timeout_seconds: Maximum time to wait for sync execution

        Returns:
            ActionResult with workflow execution status
        """
        start_time = time.time()

        if not await self._ensure_initialized():
            return ActionResult(
                success=False,
                action_type=ActionType.WORKFLOW,
                response_text="Workflows are not available right now.",
                error_message="Workflow engine not initialized",
            )

        try:
            from tldw_Server_API.app.core.Workflows import RunMode

            # Get workflow definition if using ID
            if workflow_id and not workflow_definition:
                workflow = self._db.get_workflow(workflow_id)
                if not workflow:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.WORKFLOW,
                        response_text="I couldn't find that workflow.",
                        error_message=f"Workflow {workflow_id} not found",
                    )
                workflow_definition = json.loads(workflow.definition_json)

            if not workflow_definition:
                return ActionResult(
                    success=False,
                    action_type=ActionType.WORKFLOW,
                    response_text="No workflow definition provided.",
                    error_message="Missing workflow definition",
                )

            # Create run
            run_id = str(uuid4())
            self._db.create_run(
                run_id=run_id,
                tenant_id="default",
                user_id=str(user_id),
                inputs=inputs,
                workflow_id=workflow_id,
                definition_snapshot=workflow_definition,
            )

            # Log voice command event
            self._db.append_event(
                "default",
                run_id,
                "voice_command_triggered",
                {
                    "session_id": session.session_id,
                    "inputs": inputs,
                },
            )

            if sync:
                # Execute synchronously
                mode = RunMode.SYNC
                await self._engine.start_run(run_id, mode=mode)

                # Get final result
                final_run = self._db.get_run(run_id)
                if not final_run:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.WORKFLOW,
                        response_text="The workflow completed but I couldn't retrieve the results.",
                        error_message="Run not found after execution",
                    )

                outputs = json.loads(final_run.outputs_json) if final_run.outputs_json else {}
                success = final_run.status == "succeeded"

                # Generate response text
                response_text = self._generate_workflow_response(
                    workflow_definition, final_run.status, outputs, final_run.error
                )

                return ActionResult(
                    success=success,
                    action_type=ActionType.WORKFLOW,
                    result_data={
                        "run_id": run_id,
                        "status": final_run.status,
                        "outputs": outputs,
                        "duration_ms": final_run.duration_ms,
                    },
                    response_text=response_text,
                    error_message=final_run.error if not success else None,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            else:
                # Execute asynchronously
                mode = RunMode.ASYNC
                self._engine.submit(run_id, mode=mode)

                return ActionResult(
                    success=True,
                    action_type=ActionType.WORKFLOW,
                    result_data={"run_id": run_id, "status": "queued"},
                    response_text=f"I've started the workflow. You can ask about its progress.",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        except asyncio.TimeoutError:
            return ActionResult(
                success=False,
                action_type=ActionType.WORKFLOW,
                response_text="The workflow is taking too long. I'll continue in the background.",
                error_message="Workflow execution timeout",
            )
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return ActionResult(
                success=False,
                action_type=ActionType.WORKFLOW,
                response_text=f"The workflow encountered an error.",
                error_message=str(e),
            )

    async def stream_workflow_progress(
        self,
        run_id: str,
        user_id: int,
        poll_interval: float = 0.5,
        timeout_seconds: float = 300.0,
    ) -> AsyncGenerator[WorkflowProgressEvent, None]:
        """
        Stream workflow progress events.

        Args:
            run_id: Workflow run ID
            user_id: User ID (for authorization)
            poll_interval: How often to poll for events
            timeout_seconds: Maximum streaming duration

        Yields:
            WorkflowProgressEvent objects
        """
        if not await self._ensure_initialized():
            yield WorkflowProgressEvent(
                event_type="error",
                run_id=run_id,
                message="Workflow engine not available",
                is_terminal=True,
            )
            return

        start_time = time.time()
        last_event_seq = None

        while time.time() - start_time < timeout_seconds:
            try:
                # Get run status
                run = self._db.get_run(run_id)
                if not run:
                    yield WorkflowProgressEvent(
                        event_type="error",
                        run_id=run_id,
                        message="Workflow run not found",
                        is_terminal=True,
                    )
                    return

                # Verify user authorization
                if str(run.user_id) != str(user_id):
                    yield WorkflowProgressEvent(
                        event_type="error",
                        run_id=run_id,
                        message="Not authorized to view this workflow",
                        is_terminal=True,
                    )
                    return

                # Get new events
                events = self._db.get_events(run_id, since=last_event_seq)
                for event in events:
                    last_event_seq = event.get("event_seq")
                    yield WorkflowProgressEvent(
                        event_type=event.get("event_type", "unknown"),
                        run_id=run_id,
                        data=json.loads(event.get("payload_json", "{}")) if event.get("payload_json") else {},
                        message=self._event_to_message(event),
                        is_terminal=False,
                    )

                # Check if workflow completed
                if run.status in self.TERMINAL_STATUSES:
                    outputs = json.loads(run.outputs_json) if run.outputs_json else {}
                    yield WorkflowProgressEvent(
                        event_type=f"workflow_{run.status}",
                        run_id=run_id,
                        data={
                            "status": run.status,
                            "outputs": outputs,
                            "duration_ms": run.duration_ms,
                            "error": run.error,
                        },
                        message=self._generate_workflow_response(
                            None, run.status, outputs, run.error
                        ),
                        is_terminal=True,
                    )
                    return

                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error streaming workflow progress: {e}")
                yield WorkflowProgressEvent(
                    event_type="error",
                    run_id=run_id,
                    message=str(e),
                    is_terminal=True,
                )
                return

        # Timeout
        yield WorkflowProgressEvent(
            event_type="timeout",
            run_id=run_id,
            message="Workflow progress streaming timed out",
            is_terminal=True,
        )

    async def get_workflow_status(
        self,
        run_id: str,
        user_id: int,
    ) -> Optional[dict[str, Any]]:
        """
        Get current workflow status.

        Args:
            run_id: Workflow run ID
            user_id: User ID

        Returns:
            Status dict or None if not found/authorized
        """
        if not await self._ensure_initialized():
            return None

        run = self._db.get_run(run_id)
        if not run or str(run.user_id) != str(user_id):
            return None

        return {
            "run_id": run.run_id,
            "status": run.status,
            "status_reason": run.status_reason,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "duration_ms": run.duration_ms,
            "outputs": json.loads(run.outputs_json) if run.outputs_json else None,
            "error": run.error,
        }

    async def cancel_workflow(
        self,
        run_id: str,
        user_id: int,
    ) -> bool:
        """
        Cancel a running workflow.

        Args:
            run_id: Workflow run ID
            user_id: User ID

        Returns:
            True if cancelled, False otherwise
        """
        if not await self._ensure_initialized():
            return False

        run = self._db.get_run(run_id)
        if not run or str(run.user_id) != str(user_id):
            return False

        if run.status in self.TERMINAL_STATUSES:
            return False

        try:
            self._engine.cancel(run_id)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel workflow {run_id}: {e}")
            return False

    def _generate_workflow_response(
        self,
        definition: Optional[dict[str, Any]],
        status: str,
        outputs: dict[str, Any],
        error: Optional[str],
    ) -> str:
        """Generate a TTS-friendly response from workflow results."""
        if status == "succeeded":
            # Try to extract a response from outputs
            if "response" in outputs:
                return str(outputs["response"])
            if "summary" in outputs:
                return str(outputs["summary"])
            if "result" in outputs:
                return str(outputs["result"])
            if "text" in outputs:
                return str(outputs["text"])

            # Generic success
            workflow_name = definition.get("name", "workflow") if definition else "workflow"
            return f"The {workflow_name} completed successfully."

        elif status == "failed":
            if error:
                return f"The workflow failed: {error}"
            return "The workflow encountered an error."

        elif status == "cancelled":
            return "The workflow was cancelled."

        else:
            return f"The workflow is {status}."

    def _event_to_message(self, event: dict[str, Any]) -> str:
        """Convert a workflow event to a human-readable message."""
        event_type = event.get("event_type", "")
        payload = json.loads(event.get("payload_json", "{}")) if event.get("payload_json") else {}

        if event_type == "step_started":
            step_id = payload.get("step_id", "a step")
            return f"Starting {step_id}..."

        elif event_type == "step_completed":
            step_id = payload.get("step_id", "a step")
            return f"Completed {step_id}."

        elif event_type == "step_failed":
            step_id = payload.get("step_id", "a step")
            error = payload.get("error", "unknown error")
            return f"{step_id} failed: {error}"

        elif event_type == "run_started":
            return "Workflow started."

        elif event_type == "run_completed":
            return "Workflow completed."

        elif event_type == "run_failed":
            return "Workflow failed."

        return event_type.replace("_", " ").capitalize()

    def get_voice_workflow_templates(self) -> dict[str, dict[str, Any]]:
        """
        Get pre-defined workflow templates for common voice commands.

        Returns:
            Dict mapping command names to workflow definitions
        """
        return {
            "search_and_summarize": {
                "name": "Voice Search and Summarize",
                "version": 1,
                "metadata": {
                    "description": "Search documents and summarize results",
                    "voice_trigger": True,
                },
                "steps": [
                    {
                        "id": "search",
                        "type": "rag_search",
                        "config": {
                            "query": "{{ inputs.query }}",
                            "top_k": 5,
                            "search_mode": "hybrid",
                        },
                        "timeout_seconds": 30,
                        "on_success": "summarize",
                    },
                    {
                        "id": "summarize",
                        "type": "prompt",
                        "config": {
                            "template": "Summarize these search results concisely for a voice response:\n\n{{ last.results }}\n\nProvide a brief, natural-sounding summary.",
                            "model": "gpt-4",
                        },
                        "timeout_seconds": 30,
                    },
                ],
            },
            "analyze_topic": {
                "name": "Voice Topic Analysis",
                "version": 1,
                "metadata": {
                    "description": "Analyze a topic from ingested content",
                    "voice_trigger": True,
                },
                "steps": [
                    {
                        "id": "search",
                        "type": "rag_search",
                        "config": {
                            "query": "{{ inputs.topic }}",
                            "top_k": 10,
                            "enable_reranking": True,
                        },
                        "timeout_seconds": 30,
                        "on_success": "analyze",
                    },
                    {
                        "id": "analyze",
                        "type": "prompt",
                        "config": {
                            "template": "Based on the following documents, provide an insightful analysis about {{ inputs.topic }}:\n\n{{ last.results }}\n\nKeep the analysis concise and suitable for voice output.",
                            "model": "gpt-4",
                        },
                        "timeout_seconds": 45,
                    },
                ],
            },
            "daily_briefing": {
                "name": "Voice Daily Briefing",
                "version": 1,
                "metadata": {
                    "description": "Generate a daily briefing from recent content",
                    "voice_trigger": True,
                },
                "steps": [
                    {
                        "id": "get_recent",
                        "type": "rag_search",
                        "config": {
                            "query": "recent updates important news",
                            "top_k": 10,
                            "time_filter": "last_24h",
                        },
                        "timeout_seconds": 30,
                        "on_success": "generate_briefing",
                    },
                    {
                        "id": "generate_briefing",
                        "type": "prompt",
                        "config": {
                            "template": "Create a brief daily briefing from these recent items:\n\n{{ last.results }}\n\nFormat as a natural voice briefing with key points.",
                            "model": "gpt-4",
                        },
                        "timeout_seconds": 45,
                    },
                ],
            },
        }


# Singleton instance
_workflow_handler_instance: Optional[VoiceWorkflowHandler] = None


def get_voice_workflow_handler() -> VoiceWorkflowHandler:
    """Get the singleton voice workflow handler instance."""
    global _workflow_handler_instance
    if _workflow_handler_instance is None:
        _workflow_handler_instance = VoiceWorkflowHandler()
    return _workflow_handler_instance


#
# End of VoiceAssistant/workflow_handler.py
#######################################################################################################################
