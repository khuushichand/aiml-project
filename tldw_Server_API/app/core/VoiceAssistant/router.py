# VoiceAssistant/router.py
# Voice Command Router - Orchestrates the voice command pipeline
#
# Pipeline: STT (transcription) -> Intent Parse -> Action Execute -> TTS (response)
#
#######################################################################################################################
import time
from typing import Any, Callable, Optional

from loguru import logger

from .intent_parser import IntentParser, get_intent_parser
from .registry import VoiceCommandRegistry, get_voice_command_registry
from .schemas import (
    ActionResult,
    ActionType,
    ParsedIntent,
    VoiceIntent,
    VoiceSessionContext,
    VoiceSessionState,
)
from .session import VoiceSessionManager, get_voice_session_manager
from .workflow_handler import VoiceWorkflowHandler, get_voice_workflow_handler


class VoiceCommandRouter:
    """
    Routes voice commands through the processing pipeline.

    Responsibilities:
    - Coordinate between intent parser, session manager, and action handlers
    - Execute matched commands via MCP tools, workflows, or custom handlers
    - Generate appropriate responses for TTS
    - Handle confirmation flows
    """

    def __init__(
        self,
        registry: Optional[VoiceCommandRegistry] = None,
        parser: Optional[IntentParser] = None,
        session_manager: Optional[VoiceSessionManager] = None,
        workflow_handler: Optional[VoiceWorkflowHandler] = None,
    ):
        """
        Initialize the voice command router.

        Args:
            registry: Voice command registry
            parser: Intent parser
            session_manager: Session manager
            workflow_handler: Workflow execution handler
        """
        self.registry = registry or get_voice_command_registry()
        self.parser = parser or get_intent_parser()
        self.session_manager = session_manager or get_voice_session_manager()
        self.workflow_handler = workflow_handler or get_voice_workflow_handler()

        # Custom action handlers
        self._custom_handlers: dict[str, Callable] = {}
        self._register_builtin_handlers()

    def _register_builtin_handlers(self) -> None:
        """Register handlers for built-in commands."""
        self._custom_handlers["stop"] = self._handle_stop
        self._custom_handlers["cancel"] = self._handle_cancel
        self._custom_handlers["help"] = self._handle_help
        self._custom_handlers["repeat"] = self._handle_repeat
        self._custom_handlers["confirmation"] = self._handle_confirmation
        self._custom_handlers["empty_input"] = self._handle_empty
        self._custom_handlers["workflow_status"] = self._handle_workflow_status
        self._custom_handlers["workflow_cancel"] = self._handle_workflow_cancel

    def register_custom_handler(
        self,
        action_name: str,
        handler: Callable,
    ) -> None:
        """
        Register a custom action handler.

        Args:
            action_name: Name of the action
            handler: Async callable that takes (intent, session) and returns ActionResult
        """
        self._custom_handlers[action_name] = handler
        logger.debug(f"Registered custom voice handler: {action_name}")

    async def process_command(
        self,
        text: str,
        user_id: int,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        db: Optional[Any] = None,
        persona_id: Optional[str] = None,
    ) -> tuple[ActionResult, str]:
        """
        Process a voice command through the full pipeline.

        Args:
            text: Transcribed text from STT
            user_id: User ID
            session_id: Optional existing session ID
            metadata: Optional command metadata
            db: Optional CharactersRAGDB instance for persistence/analytics

        Returns:
            Tuple of (ActionResult, session_id)
        """
        start_time = time.time()

        # Ensure session cleanup loop is running
        await self.session_manager.start()

        # Get or create session
        session, created = await self.session_manager.get_or_create_session(
            session_id, user_id, metadata
        )

        # Refresh registry from DB when available
        if db:
            try:
                self.registry.load_defaults()
                self.registry.refresh_user_commands(
                    db,
                    user_id,
                    include_disabled=True,
                    persona_id=persona_id,
                )
                if created:
                    from .db_helpers import save_voice_session

                    save_voice_session(db, session)
            except Exception as e:
                logger.warning(f"Failed to refresh voice commands from DB: {e}")

        parsed: Optional[ParsedIntent] = None

        try:
            previous_state = session.state
            # Update session state
            await self.session_manager.update_state(
                session.session_id, VoiceSessionState.PROCESSING
            )

            # Add user turn to history
            await self.session_manager.add_turn(
                session.session_id, "user", text
            )

            # Build context for parser
            context = {
                "awaiting_confirmation": previous_state == VoiceSessionState.AWAITING_CONFIRMATION,
                "conversation_history": session.conversation_history,
                "last_action_result": session.last_action_result,
            }

            # Parse intent
            parsed = await self.parser.parse(
                text,
                user_id,
                context,
                persona_id=persona_id,
            )
            logger.debug(
                f"Parsed intent: {parsed.intent.action_type} "
                f"(method={parsed.match_method}, confidence={parsed.intent.confidence:.2f})"
            )

            # Execute action
            result = await self._execute_intent(parsed.intent, session)

            # Add assistant response to history
            await self.session_manager.add_turn(
                session.session_id,
                "assistant",
                result.response_text,
                {"action_type": result.action_type.value, "success": result.success},
            )

            # Store action result
            await self.session_manager.set_last_action_result(
                session.session_id,
                {
                    "success": result.success,
                    "action_type": result.action_type.value,
                    "data": result.result_data,
                },
            )

            # Update session state
            if session.pending_intent:
                await self.session_manager.update_state(
                    session.session_id, VoiceSessionState.AWAITING_CONFIRMATION
                )
            elif result.success:
                await self.session_manager.update_state(
                    session.session_id, VoiceSessionState.IDLE
                )
            else:
                await self.session_manager.update_state(
                    session.session_id, VoiceSessionState.ERROR
                )

            result.execution_time_ms = (time.time() - start_time) * 1000

            # Persist session + analytics when DB is available
            if db and parsed:
                try:
                    from .db_helpers import record_voice_command_event, save_voice_session

                    command_name = None
                    if parsed.intent.command_id:
                        cmd = self.registry.get_command(
                            parsed.intent.command_id,
                            user_id,
                            persona_id=persona_id,
                        )
                        command_name = cmd.name if cmd else None
                    if not command_name:
                        command_name = parsed.intent.action_config.get("action") or parsed.intent.action_type.value

                    record_voice_command_event(
                        db,
                        command_id=parsed.intent.command_id,
                        command_name=command_name,
                        user_id=user_id,
                        action_type=result.action_type,
                        success=result.success,
                        response_time_ms=result.execution_time_ms,
                        session_id=session.session_id,
                    )
                    save_voice_session(db, session)
                except Exception as e:
                    logger.warning(f"Failed to record voice analytics: {e}")

            return result, session.session_id

        except Exception as e:
            logger.error(f"Error processing voice command: {e}")
            await self.session_manager.update_state(
                session.session_id, VoiceSessionState.ERROR
            )
            return ActionResult(
                success=False,
                action_type=ActionType.CUSTOM,
                response_text="I'm sorry, I encountered an error processing your request.",
                error_message=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            ), session.session_id

    async def match_registered_command(
        self,
        text: str,
        *,
        user_id: int,
        persona_id: str | None = None,
        db: Optional[Any] = None,
        include_disabled: bool = False,
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[ParsedIntent]:
        """Run the deterministic registered-command fast path without executing the action."""
        self.registry.load_defaults()
        if db:
            self.registry.refresh_user_commands(
                db,
                user_id,
                include_disabled=include_disabled,
                persona_id=persona_id,
            )
        return await self.parser.parse_registered_command(
            text,
            user_id=user_id,
            persona_id=persona_id,
            context=context,
            include_disabled=include_disabled,
        )

    async def _execute_intent(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Execute an intent and return the result."""

        # Check if confirmation is required
        if intent.requires_confirmation and session.state != VoiceSessionState.AWAITING_CONFIRMATION:
            await self.session_manager.set_pending_intent(session.session_id, intent)
            return ActionResult(
                success=True,
                action_type=intent.action_type,
                response_text=self._get_confirmation_prompt(intent),
            )

        # Route to appropriate handler based on action type
        if intent.action_type == ActionType.CUSTOM:
            return await self._execute_custom(intent, session)
        elif intent.action_type == ActionType.MCP_TOOL:
            return await self._execute_mcp_tool(intent, session)
        elif intent.action_type == ActionType.WORKFLOW:
            return await self._execute_workflow(intent, session)
        elif intent.action_type == ActionType.LLM_CHAT:
            return await self._execute_llm_chat(intent, session)
        else:
            return ActionResult(
                success=False,
                action_type=intent.action_type,
                response_text="I don't know how to handle that type of action.",
                error_message=f"Unknown action type: {intent.action_type}",
            )

    def _get_confirmation_prompt(self, intent: VoiceIntent) -> str:
        """Generate a confirmation prompt for an intent."""
        action_desc = intent.action_config.get("description", "this action")

        if intent.action_type == ActionType.MCP_TOOL:
            tool_name = intent.action_config.get("tool_name", "unknown tool")
            return f"Do you want me to execute {tool_name}? Say yes or no."

        if intent.action_type == ActionType.WORKFLOW:
            workflow_name = intent.action_config.get("workflow_name", "the workflow")
            return f"Should I start {workflow_name}? Say yes or no."

        return f"Should I proceed with {action_desc}? Say yes or no."

    async def _execute_custom(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Execute a custom action."""
        action = intent.action_config.get("action", "")

        handler = self._custom_handlers.get(action)
        if handler:
            return await handler(intent, session)

        return ActionResult(
            success=False,
            action_type=ActionType.CUSTOM,
            response_text="I don't recognize that command.",
            error_message=f"No handler for custom action: {action}",
        )

    async def _execute_mcp_tool(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Execute an MCP tool."""
        tool_name = intent.action_config.get("tool_name")
        if not tool_name:
            return ActionResult(
                success=False,
                action_type=ActionType.MCP_TOOL,
                response_text="I couldn't determine which tool to use.",
                error_message="No tool_name in action config",
            )

        try:
            # Import MCP protocol
            from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext

            # Build tool arguments from intent entities
            arguments = {
                k: v for k, v in intent.entities.items()
                if k not in ("tool_name",)
            }

            # Add any explicit arguments from config
            for key, value in intent.action_config.items():
                if key not in ("tool_name", "extract_query", "extract_content"):
                    arguments[key] = value

            # Create request context
            context = RequestContext(
                request_id=f"voice-{session.session_id}",
                user_id=str(session.user_id),
                client_id="voice_assistant",
                session_id=session.session_id,
            )

            # Get MCP protocol instance
            protocol = MCPProtocol()

            # Execute tool
            result = await protocol._handle_tools_call(
                params={"name": tool_name, "arguments": arguments},
                context=context,
            )

            # Format response based on tool result
            response_text = self._format_tool_result(tool_name, result)

            return ActionResult(
                success=True,
                action_type=ActionType.MCP_TOOL,
                result_data=result,
                response_text=response_text,
            )

        except ImportError:
            logger.warning("MCP protocol not available")
            return ActionResult(
                success=False,
                action_type=ActionType.MCP_TOOL,
                response_text="The tool system is not available right now.",
                error_message="MCP protocol not available",
            )
        except Exception as e:
            logger.error(f"MCP tool execution failed: {e}")
            return ActionResult(
                success=False,
                action_type=ActionType.MCP_TOOL,
                response_text=f"I couldn't complete that action. {str(e)}",
                error_message=str(e),
            )

    def _format_tool_result(self, tool_name: str, result: dict[str, Any]) -> str:
        """Format tool result for TTS response."""
        if not result:
            return "The action completed but returned no results."

        # Handle search results
        if "results" in result and isinstance(result["results"], list):
            count = len(result["results"])
            if count == 0:
                return "I didn't find any results."
            elif count == 1:
                item = result["results"][0]
                title = item.get("title", item.get("name", "one item"))
                return f"I found one result: {title}"
            else:
                # Summarize first few results
                titles = [
                    r.get("title", r.get("name", "untitled"))
                    for r in result["results"][:3]
                ]
                return f"I found {count} results. The top results are: {', '.join(titles)}"

        # Handle note creation
        if "note_id" in result or "id" in result:
            return "I've created the note for you."

        # Generic success message
        if result.get("success") or result.get("status") == "ok":
            return "Done."

        # Return a generic message for other results
        return "The action completed successfully."

    async def _execute_workflow(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Execute a workflow using the voice workflow handler."""
        workflow_id = intent.action_config.get("workflow_id")
        workflow_template = intent.action_config.get("workflow_template")
        workflow_definition = None

        # Check for workflow template (built-in voice workflow)
        if workflow_template:
            templates = self.workflow_handler.get_voice_workflow_templates()
            workflow_definition = templates.get(workflow_template)
            if not workflow_definition:
                return ActionResult(
                    success=False,
                    action_type=ActionType.WORKFLOW,
                    response_text=f"I don't recognize the workflow template: {workflow_template}.",
                    error_message=f"Unknown workflow template: {workflow_template}",
                )

        # If no template or ID, check for inline definition
        if not workflow_id and not workflow_definition:
            workflow_definition = intent.action_config.get("workflow_definition")

        if not workflow_id and not workflow_definition:
            return ActionResult(
                success=False,
                action_type=ActionType.WORKFLOW,
                response_text="I couldn't determine which workflow to run.",
                error_message="No workflow_id or workflow_definition in action config",
            )

        # Build workflow inputs from entities
        workflow_inputs = dict(intent.entities)

        # Add any explicit inputs from action config
        if "inputs" in intent.action_config:
            workflow_inputs.update(intent.action_config["inputs"])

        # Determine sync/async mode
        sync_mode = intent.action_config.get("sync", True)

        # Execute via workflow handler
        return await self.workflow_handler.execute_workflow(
            workflow_id=workflow_id,
            workflow_definition=workflow_definition,
            inputs=workflow_inputs,
            user_id=session.user_id,
            session=session,
            sync=sync_mode,
        )

    async def _execute_llm_chat(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Execute a general LLM chat response."""
        message = intent.action_config.get("message", intent.raw_text)

        try:
            from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Unified import chat_api_call_async

            # Build conversation context
            session.get_context_messages(max_turns=5)

            # System prompt for voice assistant
            system_prompt = """You are a helpful voice assistant. Keep your responses concise and natural-sounding for speech.
Avoid using markdown, code blocks, or special formatting.
Respond conversationally and get straight to the point."""

            response = await chat_api_call_async(
                input_data=message,
                custom_prompt=system_prompt,
                api_endpoint="openai",
                api_key=None,
                temp=0.7,
                max_tokens=150,
            )

            if not response:
                response = "I'm not sure how to respond to that."

            return ActionResult(
                success=True,
                action_type=ActionType.LLM_CHAT,
                result_data={"response": response},
                response_text=response,
            )

        except ImportError:
            return ActionResult(
                success=False,
                action_type=ActionType.LLM_CHAT,
                response_text="I'm having trouble connecting to my language model.",
                error_message="LLM API not available",
            )
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            return ActionResult(
                success=False,
                action_type=ActionType.LLM_CHAT,
                response_text="I encountered an error generating a response.",
                error_message=str(e),
            )

    # Built-in command handlers

    async def _handle_stop(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Handle stop command."""
        # Clear any pending operations
        await self.session_manager.set_pending_intent(session.session_id, None)
        return ActionResult(
            success=True,
            action_type=ActionType.CUSTOM,
            response_text="Stopped.",
        )

    async def _handle_cancel(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Handle cancel command."""
        # Clear pending intent if any
        pending = session.pending_intent
        await self.session_manager.set_pending_intent(session.session_id, None)

        if pending:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                response_text="Cancelled.",
            )
        return ActionResult(
            success=True,
            action_type=ActionType.CUSTOM,
            response_text="Nothing to cancel.",
        )

    async def _handle_help(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Handle help command."""
        commands = self.registry.get_all_commands(session.user_id)
        command_names = [cmd.name for cmd in commands[:5]]

        response = f"You can say things like: {', '.join(command_names)}. You can also ask me general questions."

        return ActionResult(
            success=True,
            action_type=ActionType.CUSTOM,
            result_data={"available_commands": [c.name for c in commands]},
            response_text=response,
        )

    async def _handle_repeat(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Handle repeat command."""
        last_result = session.last_action_result
        if last_result and "response_text" in last_result:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                response_text=last_result["response_text"],
            )

        # Find last assistant message
        for turn in reversed(session.conversation_history):
            if turn["role"] == "assistant":
                return ActionResult(
                    success=True,
                    action_type=ActionType.CUSTOM,
                    response_text=turn["content"],
                )

        return ActionResult(
            success=True,
            action_type=ActionType.CUSTOM,
            response_text="I don't have anything to repeat.",
        )

    async def _handle_confirmation(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Handle confirmation response."""
        confirmed = intent.action_config.get("confirmed", False)
        pending = session.pending_intent

        # Clear pending intent
        await self.session_manager.set_pending_intent(session.session_id, None)

        if not pending:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                response_text="There's nothing pending to confirm.",
            )

        if confirmed:
            # Execute the pending intent
            pending.requires_confirmation = False  # Prevent loop
            return await self._execute_intent(pending, session)
        else:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                response_text="Okay, I won't do that.",
            )

    async def _handle_empty(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Handle empty input."""
        return ActionResult(
            success=True,
            action_type=ActionType.CUSTOM,
            response_text="",  # No response for empty input
        )

    async def _handle_workflow_status(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Handle workflow status query."""
        # Check for active workflow in session metadata
        last_result = session.last_action_result
        if not last_result:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                response_text="I don't have any active workflows to check.",
            )

        run_id = None
        if isinstance(last_result, dict):
            run_id = last_result.get("data", {}).get("run_id")

        if not run_id:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                response_text="I couldn't find a workflow to check.",
            )

        status = await self.get_workflow_status(run_id, session.user_id)
        if not status:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                response_text="I couldn't find that workflow.",
            )

        workflow_status = status.get("status", "unknown")
        if workflow_status == "succeeded":
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                result_data=status,
                response_text="The workflow completed successfully.",
            )
        elif workflow_status == "failed":
            error = status.get("error", "unknown error")
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                result_data=status,
                response_text=f"The workflow failed: {error}",
            )
        elif workflow_status == "cancelled":
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                result_data=status,
                response_text="The workflow was cancelled.",
            )
        elif workflow_status in ("running", "pending"):
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                result_data=status,
                response_text=f"The workflow is still {workflow_status}.",
            )
        else:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                result_data=status,
                response_text=f"The workflow status is {workflow_status}.",
            )

    async def _handle_workflow_cancel(
        self,
        intent: VoiceIntent,
        session: VoiceSessionContext,
    ) -> ActionResult:
        """Handle workflow cancel request."""
        # Check for active workflow in session metadata
        last_result = session.last_action_result
        run_id = None
        if isinstance(last_result, dict):
            run_id = last_result.get("data", {}).get("run_id")

        if not run_id:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                response_text="I don't have any active workflows to cancel.",
            )

        cancelled = await self.cancel_workflow(run_id, session.user_id)
        if cancelled:
            return ActionResult(
                success=True,
                action_type=ActionType.CUSTOM,
                response_text="I've cancelled the workflow.",
            )
        else:
            return ActionResult(
                success=False,
                action_type=ActionType.CUSTOM,
                response_text="I couldn't cancel that workflow. It may have already completed.",
            )

    # Workflow helper methods

    async def get_workflow_status(
        self,
        run_id: str,
        user_id: int,
    ) -> Optional[dict[str, Any]]:
        """
        Get the status of a workflow run.

        Args:
            run_id: Workflow run ID
            user_id: User ID

        Returns:
            Status dict or None if not found/authorized
        """
        return await self.workflow_handler.get_workflow_status(run_id, user_id)

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
        return await self.workflow_handler.cancel_workflow(run_id, user_id)

    def stream_workflow_progress(
        self,
        run_id: str,
        user_id: int,
        poll_interval: float = 0.5,
        timeout_seconds: float = 300.0,
    ):
        """
        Stream workflow progress events.

        Args:
            run_id: Workflow run ID
            user_id: User ID
            poll_interval: How often to poll for events
            timeout_seconds: Maximum streaming duration

        Returns:
            AsyncGenerator yielding WorkflowProgressEvent objects
        """
        return self.workflow_handler.stream_workflow_progress(
            run_id=run_id,
            user_id=user_id,
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
        )


# Singleton instance
_router_instance: Optional[VoiceCommandRouter] = None


def get_voice_command_router() -> VoiceCommandRouter:
    """Get the singleton voice command router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = VoiceCommandRouter()
    return _router_instance


#
# End of VoiceAssistant/router.py
#######################################################################################################################
