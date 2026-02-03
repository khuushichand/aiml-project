"""Workflow helpers for chained prompt execution."""

# Workflows.py
#
#########################################
# Workflow Library
# This library is used to facilitate chained prompt workflows
#
####
####################
# Function Categories
#
# Fixme
#
#
####################
# Function List
#
# 1. FIXME
#
####################
#
# Imports
import json
from pathlib import Path
from typing import Optional, Union

#
# 3rd-Party Imports
#
# Local Imports
from loguru import logger

from tldw_Server_API.app.core.Chat.chat_orchestrator import chat

#
#######################################################################################################################
#
# Function Definitions

# Load workflows from a JSON file
json_path = Path('./App_Function_Libraries/Workflows/Workflows.json')

# Load workflows from a JSON file
def load_workflows(json_path: Union[str, Path] = json_path) -> list[dict]:
    with Path(json_path).open('r') as f:
        return json.load(f)

# Initialize a workflow
def initialize_workflow(workflow_name: str, workflows: list[dict]) -> tuple[dict, str, list[tuple[Optional[str], str]]]:
    selected_workflow = next((wf for wf in workflows if wf['name'] == workflow_name), None)
    if selected_workflow:
        num_prompts = len(selected_workflow['prompts'])
        context = selected_workflow.get('context', '')
        first_prompt = selected_workflow['prompts'][0]
        initial_chat = [(None, f"{first_prompt}")]
        workflow_state = {"current_step": 0, "max_steps": num_prompts, "conversation_id": None}
        logger.info(f"Initializing workflow: {workflow_name} with {num_prompts} steps")
        return workflow_state, context, initial_chat
    else:
        logger.error(f"Selected workflow not found: {workflow_name}")
        return {"current_step": 0, "max_steps": 0, "conversation_id": None}, "", []


# Process a workflow step
def process_workflow_step(
        message: str,
        history: list[tuple[Optional[str], str]],
        context: str,
        workflow_name: str,
        workflows: list[dict],
        workflow_state: dict,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        save_conv: bool = False,
        temp: float = 0.7,
        system_message: Optional[str] = None,
        media_content: Optional[dict] = None,
        selected_parts: Optional[list[str]] = None
) -> tuple[list[tuple[Optional[str], str]], dict, bool]:
    """
    Process a single step in a chained prompt workflow.

    Args:
        message: Latest user message for the current step.
        history: Existing chat history (user/assistant pairs).
        context: Workflow-level context string prepended to each step.
        workflow_name: Name of the workflow to run.
        workflows: Loaded workflow definitions.
        workflow_state: Mutable state dict containing current_step/max_steps.
        api_endpoint: Optional provider endpoint override.
        api_key: Optional provider API key override.
        save_conv: Whether to persist conversation history.
        temp: Sampling temperature for the LLM call.
        system_message: Optional system prompt override.
        media_content: Optional media payload for the chat orchestrator.
        selected_parts: Optional list of selected media parts.

    Returns:
        A tuple of (updated_history, updated_workflow_state, continue_workflow).
    """
    logger.info(f"Process workflow step called with message: {message}")
    logger.info(f"Current workflow state: {workflow_state}")
    media_content = dict(media_content or {})
    selected_parts = list(selected_parts or [])

    try:
        selected_workflow = next((wf for wf in workflows if wf['name'] == workflow_name), None)
        if not selected_workflow:
            logger.error(f"Selected workflow not found: {workflow_name}")
            return history, workflow_state, True

        current_step = workflow_state["current_step"]
        max_steps = workflow_state["max_steps"]

        logger.info(f"Current step: {current_step}, Max steps: {max_steps}")

        if current_step >= max_steps:
            logger.info("Workflow completed")
            return history, workflow_state, False

        prompt = selected_workflow['prompts'][current_step]
        full_message = f"{context}\n\nStep {current_step + 1}: {prompt}\nUser: {message}"

        logger.info(f"Preparing to process message: {full_message[:100]}...")

        # Use the existing chat function
        bot_message = chat(
            full_message, history, media_content, selected_parts,
            api_endpoint, api_key, prompt, temp, system_message
        )

        logger.info(f"Received bot_message: {bot_message[:100]}...")

        new_history = history + [(message, bot_message)]
        next_step = current_step + 1
        new_workflow_state = {
            "current_step": next_step,
            "max_steps": max_steps,
            "conversation_id": workflow_state["conversation_id"]
        }

        if next_step >= max_steps:
            logger.info("Workflow completed after this step")
            return new_history, new_workflow_state, False
        else:
            next_prompt = selected_workflow['prompts'][next_step]
            new_history.append((None, f"Step {next_step + 1}: {next_prompt}"))
            logger.info(f"Moving to next step: {next_step}")
            return new_history, new_workflow_state, True

    except Exception as e:
        logger.error(f"Error in process_workflow_step: {str(e)}")
        return history, workflow_state, True


# Main function to run a workflow
def run_workflow(
        workflow_name: str,
        initial_context: str = "",
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        save_conv: bool = False,
        temp: float = 0.7,
        system_message: Optional[str] = None,
        media_content: Optional[dict] = None,
        selected_parts: Optional[list[str]] = None
) -> list[tuple[Optional[str], str]]:
    """
    Run an interactive workflow loop in the console.

    Args:
        workflow_name: Name of the workflow to run.
        initial_context: Additional context to prepend to the workflow context.
        api_endpoint: Optional provider endpoint override.
        api_key: Optional provider API key override.
        save_conv: Whether to persist conversation history.
        temp: Sampling temperature for the LLM call.
        system_message: Optional system prompt override.
        media_content: Optional media payload for the chat orchestrator.
        selected_parts: Optional list of selected media parts.

    Returns:
        The final conversation history accumulated during the workflow.
    """
    workflows = load_workflows()
    workflow_state, context, history = initialize_workflow(workflow_name, workflows)

    # Combine the initial_context with the workflow's context
    combined_context = f"{initial_context}\n\n{context}".strip()
    media_content = dict(media_content or {})
    selected_parts = list(selected_parts or [])

    while True:
        user_input = input("Your input (or 'quit' to exit): ")
        if user_input.lower() == 'quit':
            break

        history, workflow_state, continue_workflow = process_workflow_step(
            user_input, history, combined_context, workflow_name, workflows, workflow_state,
            api_endpoint, api_key, save_conv, temp, system_message, media_content, selected_parts
        )

        for _, message in history[-2:]:  # Print the last two messages (user input and bot response)
            print(message)

        if not continue_workflow:
            print("Workflow completed.")
            break

    return history

# Example usage
# if __name__ == "__main__":
#     workflow_name = "Example Workflow"
#     initial_context = "This is an example context."
#
#     final_history = run_workflow(
#         workflow_name,
#         initial_context,
#         api_endpoint="your_api_endpoint",
#         api_key="your_api_key",
#         save_conv=True,
#         temp=0.7,
#         system_message="You are a helpful assistant guiding through a workflow.",
#         media_content={},
#         selected_parts=[]
#     )
#
#     print("Final conversation history:")
#     for user_message, bot_message in final_history:
#         if user_message:
#             print(f"User: {user_message}")
#         print(f"Bot: {bot_message}")
#         print()

#
# End of Workflows.py
#######################################################################################################################
