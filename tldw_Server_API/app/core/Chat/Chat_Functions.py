# Chat_Functions.py
# Description: Chat functions for interacting with the LLMs as chatbots
"""
This module now acts as a compatibility shim around the refactored chat stack.
Prefer importing from `chat_orchestrator`, `chat_history`, `chat_dictionary`, or
`chat_characters` directly. These exports are retained for legacy integrations
and will be deprecated once downstream callers migrate.
"""
#
# Imports
from typing import List, Dict, Any, Tuple, Optional, Union
#
# 3rd-party Libraries

#
# Local Imports
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import ResponseFormat
from tldw_Server_API.app.core.Chat.Chat_Deps import (
    ChatBadRequestError,
    ChatConfigurationError,
    ChatAPIError,
    ChatProviderError,
    ChatRateLimitError,
    ChatAuthenticationError,
)
# Note: Provider handler maps are now centralized in provider_config.
# Authoritative provider mappings (avoid drift):
from tldw_Server_API.app.core.Chat.provider_config import API_CALL_HANDLERS as _PROVIDER_API_CALL_HANDLERS
from tldw_Server_API.app.core.Chat.provider_config import PROVIDER_PARAM_MAP as _PROVIDER_PARAM_MAP
import tldw_Server_API.app.core.Chat.chat_orchestrator as _chat_orchestrator_module
import tldw_Server_API.app.core.Chat.chat_history as _chat_history_module
import tldw_Server_API.app.core.Chat.chat_characters as _chat_characters_module
from tldw_Server_API.app.core.Chat.chat_orchestrator import (
    chat as _orchestrator_chat,
    chat_api_call as _orchestrator_chat_api_call,
    approximate_token_count as _orchestrator_approximate_token_count,
)
from tldw_Server_API.app.core.Chat.chat_history import (
    save_chat_history_to_db_wrapper,
    save_chat_history,
    get_conversation_name,
    generate_chat_history_content,
    extract_media_name,
    update_chat_content,
)
from tldw_Server_API.app.core.Chat.chat_characters import (
    save_character,
    load_characters,
    get_character_names,
)
import tldw_Server_API.app.core.Chat.chat_dictionary as _chat_dictionary_module
from tldw_Server_API.app.core.Chat.chat_dictionary import (
    ChatDictionary,
    TokenBudgetExceededWarning,
    alert_token_budget_exceeded,
    apply_replacement_once,
    apply_strategy,
    apply_timed_effects,
    calculate_token_usage,
    enforce_token_budget,
    filter_by_probability,
    group_scoring,
    match_whole_words,
    parse_user_dict_markdown_file,
    process_user_input,
)
from tldw_Server_API.app.core.config import load_and_log_configs
#
####################################################################################################
#
# Functions:

approximate_token_count = _orchestrator_approximate_token_count

"""Provider mappings now live in provider_config; this module no longer exports them."""

def chat_api_call(
    api_endpoint: str,
    messages_payload: List[Dict[str, Any]], # CHANGED from input_data, prompt
    api_key: Optional[str] = None,
    temp: Optional[float] = None,
    system_message: Optional[str] = None, # Still passed separately, some providers might use it, others expect it in messages_payload
    streaming: Optional[bool] = None,
    minp: Optional[float] = None,
    maxp: Optional[float] = None, # Often maps to top_p
    model: Optional[str] = None,
    topk: Optional[int] = None,
    topp: Optional[float] = None, # Often maps to top_p
    logprobs: Optional[bool] = None,
    top_logprobs: Optional[int] = None,
    logit_bias: Optional[Dict[str, float]] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,  # Expects {'type': 'text' | 'json_object'}
    n: Optional[int] = None,
    user_identifier: Optional[str] = None,  # Renamed from 'user' to avoid conflict with 'user' role in messages
    extra_headers: Optional[Dict[str, str]] = None,
    extra_body: Optional[Dict[str, Any]] = None,
    app_config: Optional[Dict[str, Any]] = None,
    ):
    """
    Deprecated shim.
    - Default: forwards to chat_orchestrator.chat_api_call to avoid drift.
    - Test compatibility: if API_CALL_HANDLERS has been patched on this module
      (object identity differs from provider_config), perform local dispatch
      using the patched mapping so existing tests that monkeypatch this symbol
      continue to work without changes.
    """
    # Forward to orchestrator (single source of truth)
    return _orchestrator_chat_api_call(
        api_endpoint=api_endpoint,
        messages_payload=messages_payload,
        api_key=api_key,
        temp=temp,
        system_message=system_message,
        streaming=streaming,
        minp=minp,
        maxp=maxp,
        model=model,
        topk=topk,
        topp=topp,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        logit_bias=logit_bias,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
        seed=seed,
        stop=stop,
        response_format=response_format,
        n=n,
        user_identifier=user_identifier,
        extra_headers=extra_headers,
        extra_body=extra_body,
        app_config=app_config,
        )


DEFAULT_CHARACTER_NAME = _chat_history_module.DEFAULT_CHARACTER_NAME

# Legacy compatibility shim: chat forwards to chat_orchestrator.chat.
def chat(
    message: str,
    history: List[Dict[str, Any]],
    media_content: Optional[Dict[str, str]],
    selected_parts: List[str],
    api_endpoint: str,
    api_key: Optional[str],
    custom_prompt: Optional[str],
    temperature: float,
    system_message: Optional[str] = None,
    streaming: bool = False,
    minp: Optional[float] = None,
    maxp: Optional[float] = None,
    model: Optional[str] = None,
    topp: Optional[float] = None,
    topk: Optional[int] = None,
    chatdict_entries: Optional[List[Any]] = None,  # Should be List[ChatDictionary]
    max_tokens: int = 500,
    strategy: str = "sorted_evenly",
    current_image_input: Optional[Dict[str, str]] = None,
    image_history_mode: str = "tag_past",
    llm_max_tokens: Optional[int] = None,
    llm_seed: Optional[int] = None,
    llm_stop: Optional[Union[str, List[str]]] = None,
    llm_response_format: Optional[ResponseFormat] = None,
    llm_n: Optional[int] = None,
    llm_user_identifier: Optional[str] = None,
    llm_logprobs: Optional[bool] = None,
    llm_top_logprobs: Optional[int] = None,
    llm_logit_bias: Optional[Dict[str, float]] = None,
    llm_presence_penalty: Optional[float] = None,
    llm_frequency_penalty: Optional[float] = None,
    llm_tools: Optional[List[Dict[str, Any]]] = None,
    llm_tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
) -> Union[str, Any]:
    """Compatibility shim that forwards to `chat_orchestrator.chat`."""
    original_chat_api_call = _chat_orchestrator_module.chat_api_call
    original_load_and_log_configs = _chat_orchestrator_module.load_and_log_configs
    try:
        if _chat_orchestrator_module.chat_api_call is not chat_api_call:
            _chat_orchestrator_module.chat_api_call = chat_api_call
        if _chat_orchestrator_module.load_and_log_configs is not load_and_log_configs:
            _chat_orchestrator_module.load_and_log_configs = load_and_log_configs
        return _orchestrator_chat(
            message=message,
            history=history,
            media_content=media_content,
            selected_parts=selected_parts,
            api_endpoint=api_endpoint,
            api_key=api_key,
            custom_prompt=custom_prompt,
            temperature=temperature,
            system_message=system_message,
            streaming=streaming,
            minp=minp,
            maxp=maxp,
            model=model,
            topp=topp,
            topk=topk,
            chatdict_entries=chatdict_entries,
            max_tokens=max_tokens,
            strategy=strategy,
            current_image_input=current_image_input,
            image_history_mode=image_history_mode,
            llm_max_tokens=llm_max_tokens,
            llm_seed=llm_seed,
            llm_stop=llm_stop,
            llm_response_format=llm_response_format,
            llm_n=llm_n,
            llm_user_identifier=llm_user_identifier,
            llm_logprobs=llm_logprobs,
            llm_top_logprobs=llm_top_logprobs,
            llm_logit_bias=llm_logit_bias,
            llm_presence_penalty=llm_presence_penalty,
            llm_frequency_penalty=llm_frequency_penalty,
            llm_tools=llm_tools,
            llm_tool_choice=llm_tool_choice,
        )
    finally:
        _chat_orchestrator_module.chat_api_call = original_chat_api_call
        _chat_orchestrator_module.load_and_log_configs = original_load_and_log_configs



#
# End of Chat functions
#######################################################################################################################


#######################################################################################################################
#
# Chat Dictionary Functions (see chat_dictionary module; symbols re-exported below)
#

#######################################################################################################################
#
# Character Card Functions (re-exported from chat_characters for compatibility)
#

save_character = _chat_characters_module.save_character
load_characters = _chat_characters_module.load_characters
get_character_names = _chat_characters_module.get_character_names

__all__ = [
    "chat",
    "chat_api_call",
    "DEFAULT_CHARACTER_NAME",
    "approximate_token_count",
]

#
# End of Chat_Functions.py
##########################################################################################################################
