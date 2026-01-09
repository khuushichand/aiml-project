# provider_config.py
# Description: Provider configuration for LLM API calls
"""
This module contains configuration mappings for various LLM providers,
including dispatch tables for handler functions and parameter mappings.
"""
#
# Imports
from typing import Dict, Any, Callable
#
# Local Imports - Import the actual handler functions
from tldw_Server_API.app.core.LLM_Calls.legacy_chat_calls import (
    chat_with_cohere,
    chat_with_groq, chat_with_openrouter, chat_with_deepseek,
    chat_with_mistral, chat_with_huggingface, chat_with_google,
    chat_with_qwen, chat_with_bedrock,
)
from tldw_Server_API.app.core.LLM_Calls.adapter_shims import (
    openai_chat_handler,
    anthropic_chat_handler,
    groq_chat_handler,
    openrouter_chat_handler,
    google_chat_handler,
    mistral_chat_handler,
    qwen_chat_handler,
    deepseek_chat_handler,
    huggingface_chat_handler,
    bedrock_chat_handler,
    custom_openai_chat_handler,
    custom_openai_2_chat_handler,
    mlx_chat_handler,
    openai_chat_handler_async,
    anthropic_chat_handler_async,
    groq_chat_handler_async,
    openrouter_chat_handler_async,
    qwen_chat_handler_async,
    deepseek_chat_handler_async,
    huggingface_chat_handler_async,
    bedrock_chat_handler_async,
    custom_openai_chat_handler_async,
    custom_openai_2_chat_handler_async,
    google_chat_handler_async,
    mistral_chat_handler_async,
    mlx_chat_handler_async,
    moonshot_chat_handler,
    zai_chat_handler,
    llama_cpp_chat_handler,
    kobold_chat_handler,
    ooba_chat_handler,
    tabbyapi_chat_handler,
    vllm_chat_handler,
    local_llm_chat_handler,
    ollama_chat_handler,
    aphrodite_chat_handler,
)
from tldw_Server_API.app.core.LLM_Calls.provider_metadata import (
    PROVIDER_CAPABILITIES,
    PROVIDER_REQUIRES_KEY,
)
from tldw_Server_API.app.core.LLM_Calls.deprecation import log_legacy_once

log_legacy_once(
    "provider_config",
    "provider_config is deprecated; use adapter registry and provider_metadata instead.",
)
#
####################################################################################################
#
# Provider Configuration
#

# 1. Dispatch table for handler functions
API_CALL_HANDLERS: Dict[str, Callable] = {
    'openai': openai_chat_handler,
    'bedrock': bedrock_chat_handler,
    'anthropic': anthropic_chat_handler,
    'cohere': chat_with_cohere,
    'groq': groq_chat_handler,
    'qwen': qwen_chat_handler,
    'openrouter': openrouter_chat_handler,
    'deepseek': deepseek_chat_handler,
    'mistral': mistral_chat_handler,
    'google': google_chat_handler,
    'huggingface': huggingface_chat_handler,
    'moonshot': moonshot_chat_handler,
    'zai': zai_chat_handler,
    'llama.cpp': llama_cpp_chat_handler,
    'kobold': kobold_chat_handler,
    'ooba': ooba_chat_handler,
    'tabbyapi': tabbyapi_chat_handler,
    'vllm': vllm_chat_handler,
    'local-llm': local_llm_chat_handler,
    'ollama': ollama_chat_handler,
    'aphrodite': aphrodite_chat_handler,
    'custom-openai-api': custom_openai_chat_handler,
    'custom-openai-api-2': custom_openai_2_chat_handler,
    'mlx': mlx_chat_handler,
}
"""
A dispatch table mapping API endpoint names (e.g., 'openai') to their
corresponding handler functions (e.g., `chat_with_openai`). This is used by
`chat_api_call` to route requests to the appropriate LLM provider.
"""

# Optional async handlers. When present, the orchestrator can invoke these without blocking threads.
ASYNC_API_CALL_HANDLERS: Dict[str, Callable] = {
    # Adapter-backed async shims with feature-flag fallback to legacy async handlers
    'openai': openai_chat_handler_async,
    'groq': groq_chat_handler_async,
    'anthropic': anthropic_chat_handler_async,
    'openrouter': openrouter_chat_handler_async,
    'qwen': qwen_chat_handler_async,
    'deepseek': deepseek_chat_handler_async,
    'huggingface': huggingface_chat_handler_async,
    'bedrock': bedrock_chat_handler_async,
    'custom-openai-api': custom_openai_chat_handler_async,
    'custom-openai-api-2': custom_openai_2_chat_handler_async,
    'google': google_chat_handler_async,
    'mistral': mistral_chat_handler_async,
    'mlx': mlx_chat_handler_async,
}

# 2. Parameter mapping for each provider
# Maps generic chat_api_call param name to provider-specific param name
PROVIDER_PARAM_MAP: Dict[str, Dict[str, str]] = {
    'bedrock': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        # Accept normalized top-p generic param and legacy 'maxp'
        'topp': 'maxp',
        'maxp': 'maxp',
        'model': 'model',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'logprobs': 'logprobs',
        'top_logprobs': 'top_logprobs',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'user_identifier': 'user',
        'extra_headers': 'extra_headers',
        'extra_body': 'extra_body',
    },
    'openai': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        # Accept normalized top-p generic param and legacy 'maxp'
        'topp': 'topp',
        'maxp': 'topp',
        'model': 'model',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'logprobs': 'logprobs',
        'top_logprobs': 'top_logprobs',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'user_identifier': 'user',
    },
    'anthropic': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_prompt',
        'streaming': 'streaming',
        'model': 'model',
        'topp': 'topp',
        'topk': 'topk',
        'tools': 'tools',
        #'tool_choice': 'tool_choice',
        'max_tokens': 'max_tokens',  # Anthropic uses max_tokens
        'stop': 'stop_sequences',  # Anthropic uses stop_sequences
    },
    'cohere': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_prompt',
        'streaming': 'streaming',
        'model': 'model',
        'topp': 'topp',
        'topk': 'topk',
        'tools': 'tools',
        # Cohere's legacy /v1/chat handler signature does not accept tool_choice
        # and passing it causes a TypeError. Only apply when a dedicated adapter
        # path supports it.
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop_sequences',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
    },
    'groq': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'topp',
        'model':'model',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'user_identifier': 'user',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'logprobs': 'logprobs',
        'top_logprobs': 'top_logprobs',
        'http_client_factory': 'http_client_factory',
        'http_fetcher': 'http_fetcher',
    },
    'qwen': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'maxp',
        'maxp': 'maxp',
        'model': 'model',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'logprobs': 'logprobs',
        'top_logprobs': 'top_logprobs',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'user_identifier': 'user',
    },
    'openrouter': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        # OpenRouter uses top_p/top_k/min_p naming
        'topp': 'top_p',
        'maxp': 'top_p',
        'topk': 'top_k',
        'minp': 'min_p',
        'model':'model',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'n': 'n',
    },
    'moonshot': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'maxp',
        'maxp': 'maxp',
        'model': 'model',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'user_identifier': 'user',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
    },
    'zai': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'maxp',
        'maxp': 'maxp',
        'model': 'model',
        'tools': 'tools',
        'max_tokens': 'max_tokens',
        'stop': 'stop',
        'response_format': 'response_format',
    },
    'deepseek': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'topp',
        'model':'model',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'logprobs': 'logprobs',
        'top_logprobs': 'top_logprobs',  # if supported
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
    },
    'mistral': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'topp',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'model': 'model',
        'max_tokens': 'max_tokens',
        'seed': 'random_seed',  # Mistral uses random_seed
        'topk': 'top_k',  # Mistral uses top_k
    },
    'google': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'topp',
        'topk': 'topk',
        'tools': 'tools',
        #'tool_choice': 'tool_choice',
        'model':'model',
        'max_tokens': 'max_output_tokens',
        'stop': 'stop_sequences',  # List of strings
        'n': 'candidate_count',
    },
    'huggingface': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'model':'model',
        'max_tokens': 'max_new_tokens',  # Common for TGI
        'topp': 'top_p',
        'topk': 'top_k',
        'seed': 'seed',
        'stop': 'stop',  # often 'stop_sequences'
    },
    'llama.cpp': { # Has api_url as a positional argument which needs special handling if not None
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt',
        'temp': 'temperature',
        'system_message': 'system_prompt',
        'streaming': 'stream',
        'topp': 'top_p', 'topk': 'top_k',
        'minp': 'min_p',
        'model':'model',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'max_tokens': 'n_predict', # Common for llama.cpp server
        'seed': 'seed',
        'stop': 'stop', # list of strings
        'response_format': 'response_format', # if OpenAI compatible endpoint
        'logit_bias': 'logit_bias',
        'n': 'n',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'http_client_factory': 'http_client_factory',
        'http_fetcher': 'http_fetcher',
    },
    'kobold': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_input',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'top_p',
        'topk': 'top_k',
        'model':'model',
        'max_tokens': 'max_length',  # or 'max_context_length'
        'stop': 'stop_sequence',  # Often a list
        'n': 'num_responses',
        'seed': 'seed',
    },
    'ooba': { # api_url also a consideration like llama.cpp
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt',
        'temp': 'temperature',
        'system_message': 'system_prompt', # often part of messages or specific param
        'streaming': 'stream',
        'topp': 'top_p',
        'model':'model',
        'topk': 'top_k',
        'minp': 'min_p',
        'max_tokens': 'max_tokens', # or 'max_new_tokens'
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'user_identifier': 'user',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'http_client_factory': 'http_client_factory',
        'http_fetcher': 'http_fetcher',
    },
    'tabbyapi': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_input',
        'temp': 'temperature',
        'system_message': 'system_message',
        'streaming': 'stream',
        'topp': 'top_p',
        'topk': 'top_k',
        'minp': 'min_p',
        'model':'model',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'http_client_factory': 'http_client_factory',
        'http_fetcher': 'http_fetcher',
    },
    'vllm': { # vllm_api_url consideration
                'app_config': 'app_config',
                'api_key': 'api_key', 'messages_payload': 'input_data', 'prompt': 'custom_prompt_input',
        'temp': 'temperature', 'system_message': 'system_prompt', 'streaming': 'stream',
        'topp': 'top_p', 'topk': 'top_k', 'minp': 'min_p', 'model': 'model',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'logprobs': 'logprobs',
        # vLLM supports OpenAI-style tool calling
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'user_identifier': 'user',
        'http_client_factory': 'http_client_factory',
        'http_fetcher': 'http_fetcher',
    },
    # Note: Local OpenAI-compatible providers support a strict filtering mode enabled via
    # `strict_openai_compat` in their config sections. When enabled, the request payload is
    # filtered to standard OpenAI Chat Completions keys. See:
    # Docs/Deployment/OpenAI_Compat_Strict_Mode.md
    'local-llm': {
        'app_config': 'app_config',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temperature',
        'system_message': 'system_message',
        'streaming': 'stream',
        'topp': 'top_p',
        'topk': 'top_k',
        'minp': 'min_p',
        'model':'model',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        # Support full OpenAI-compatible options where local servers accept them
        'response_format': 'response_format',
        'n': 'n',
        'user_identifier': 'user_identifier',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'logprobs': 'logprobs',
        'top_logprobs': 'top_logprobs',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'http_client_factory': 'http_client_factory',
        'http_fetcher': 'http_fetcher',
    },
    'ollama': { # api_url consideration
        'app_config': 'app_config',
        'api_key': 'api_key', # api_key is not used by ollama directly, url is more important
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt', # This is 'prompt' for generate, 'messages' for chat
        'temp': 'temperature',
        # Use the adapter's expected kwarg; the adapter inserts the system
        # prompt into messages for OpenAI-compatible chat.
        'system_message': 'system_message',
        'streaming': 'stream',
        'topp': 'top_p',
        'topk': 'top_k',
        'model': 'model',
        'max_tokens': 'num_predict', # For generate endpoint, chat might be different
        'seed': 'seed',
        'stop': 'stop', # list of strings
        # Adapter expects 'format_str' and can translate 'json' to OpenAI dict
        'response_format': 'format_str',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'http_client_factory': 'http_client_factory',
        'http_fetcher': 'http_fetcher',
    },
    'aphrodite': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt',
        'temp': 'temperature',
        'system_message': 'system_message',
        'streaming': 'stream',
        'topp': 'top_p',
        'topk': 'top_k',
        'minp': 'min_p',
        'model': 'model',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'logprobs': 'logprobs',
        'user_identifier': 'user',
        'http_client_factory': 'http_client_factory',
        'http_fetcher': 'http_fetcher',
    },
    'mlx': {
        'app_config': 'app_config',
        'messages_payload': 'input_data',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'topp',
        'topk': 'topk',
        'model': 'model',
        'max_tokens': 'max_tokens',
        'stop': 'stop',
        'response_format': 'response_format',
        'user_identifier': 'user',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'prompt_template': 'prompt_template',
        'custom_prompt_arg': 'custom_prompt_arg',
    },
    'custom-openai-api': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'topp',
        'model':'model',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'user_identifier': 'user',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'logprobs': 'logprobs',
        'top_logprobs': 'top_logprobs',
        'http_client_factory': 'http_client_factory',
        'http_fetcher': 'http_fetcher',
    },
    'custom-openai-api-2': {
        'app_config': 'app_config',
        'api_key': 'api_key',
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt_arg',
        'temp': 'temp',
        'system_message': 'system_message',
        'streaming': 'streaming',
        'topp': 'topp',
        'model':'model',
        'tools': 'tools',
        'tool_choice': 'tool_choice',
        'max_tokens': 'max_tokens',
        'seed': 'seed',
        'stop': 'stop',
        'response_format': 'response_format',
        'n': 'n',
        'user_identifier': 'user',
        'logit_bias': 'logit_bias',
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
        'logprobs': 'logprobs',
        'top_logprobs': 'top_logprobs',
    },
}
"""
Parameter mapping for each provider. Maps generic parameter names used in
the chat_api_call function to provider-specific parameter names.
"""

def get_provider_handler(provider: str) -> Callable:
    """
    Get the handler function for a specific provider.

    Args:
        provider: The provider name

    Returns:
        The handler function for the provider

    Raises:
        KeyError: If the provider is not supported
    """
    if provider not in API_CALL_HANDLERS:
        raise KeyError(f"Unsupported provider: {provider}")
    return API_CALL_HANDLERS[provider]

def get_provider_params(provider: str) -> Dict[str, str]:
    """
    Get the parameter mapping for a specific provider.

    Args:
        provider: The provider name

    Returns:
        The parameter mapping dictionary for the provider

    Raises:
        KeyError: If the provider is not supported
    """
    if provider not in PROVIDER_PARAM_MAP:
        raise KeyError(f"No parameter mapping for provider: {provider}")
    return PROVIDER_PARAM_MAP[provider]

#
# End of provider_config.py
####################################################################################################
