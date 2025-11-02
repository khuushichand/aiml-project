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
from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import (
    chat_with_openai, chat_with_anthropic, chat_with_cohere,
    chat_with_groq, chat_with_openrouter, chat_with_deepseek,
    chat_with_mistral, chat_with_huggingface, chat_with_google,
    chat_with_qwen, chat_with_bedrock, chat_with_moonshot, chat_with_zai,
    chat_with_openai_async, chat_with_groq_async, chat_with_anthropic_async, chat_with_openrouter_async,
)
from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local import (
    chat_with_aphrodite, chat_with_local_llm, chat_with_ollama,
    chat_with_kobold, chat_with_llama, chat_with_oobabooga,
    chat_with_tabbyapi, chat_with_vllm, chat_with_custom_openai,
    chat_with_custom_openai_2
)
#
####################################################################################################
#
# Provider Configuration
#

# 1. Dispatch table for handler functions
API_CALL_HANDLERS: Dict[str, Callable] = {
    'openai': chat_with_openai,
    'bedrock': chat_with_bedrock,
    'anthropic': chat_with_anthropic,
    'cohere': chat_with_cohere,
    'groq': chat_with_groq,
    'qwen': chat_with_qwen,
    'openrouter': chat_with_openrouter,
    'deepseek': chat_with_deepseek,
    'mistral': chat_with_mistral,
    'google': chat_with_google,
    'huggingface': chat_with_huggingface,
    'moonshot': chat_with_moonshot,
    'zai': chat_with_zai,
    'llama.cpp': chat_with_llama,
    'kobold': chat_with_kobold,
    'ooba': chat_with_oobabooga,
    'tabbyapi': chat_with_tabbyapi,
    'vllm': chat_with_vllm,
    'local-llm': chat_with_local_llm,
    'ollama': chat_with_ollama,
    'aphrodite': chat_with_aphrodite,
    'custom-openai-api': chat_with_custom_openai,
    'custom-openai-api-2': chat_with_custom_openai_2,
}
"""
A dispatch table mapping API endpoint names (e.g., 'openai') to their
corresponding handler functions (e.g., `chat_with_openai`). This is used by
`chat_api_call` to route requests to the appropriate LLM provider.
"""

# Optional async handlers. When present, the orchestrator can invoke these without blocking threads.
ASYNC_API_CALL_HANDLERS: Dict[str, Callable] = {
    'openai': chat_with_openai_async,
    'groq': chat_with_groq_async,
    'anthropic': chat_with_anthropic_async,
    'openrouter': chat_with_openrouter_async,
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
        'tool_choice': 'tool_choice',
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
    },
    'ollama': { # api_url consideration
        'app_config': 'app_config',
        'api_key': 'api_key', # api_key is not used by ollama directly, url is more important
        'messages_payload': 'input_data',
        'prompt': 'custom_prompt', # This is 'prompt' for generate, 'messages' for chat
        'temp': 'temperature',
        'system_message': 'system', # Part of request body
        'streaming': 'stream',
        'topp': 'top_p',
        'topk': 'top_k',
        'model': 'model',
        'max_tokens': 'num_predict', # For generate endpoint, chat might be different
        'seed': 'seed',
        'stop': 'stop', # list of strings
        'response_format': 'format', # 'json' string
        'presence_penalty': 'presence_penalty',
        'frequency_penalty': 'frequency_penalty',
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
# 3. Provider capability flags
# Whether a provider requires an API key (True) or can operate without one (False)
PROVIDER_REQUIRES_KEY: Dict[str, bool] = {
    'openai': True,
    'bedrock': True,
    'anthropic': True,
    'cohere': True,
    'groq': True,
    'qwen': True,
    'openrouter': True,
    'deepseek': True,
    'mistral': True,
    'google': True,
    'huggingface': True,   # HF Inference API typically requires a key
    'moonshot': True,
    'zai': True,
    'llama.cpp': False,
    'kobold': False,
    'ooba': False,
    'tabbyapi': False,
    'vllm': False,
    'local-llm': False,
    'ollama': False,
    'aphrodite': False,
    'custom-openai-api': True,
    'custom-openai-api-2': True,
}

# 4. Provider capabilities (surface minimal, extend as needed)
# Default timeouts are conservative; adjust per provider characteristics
PROVIDER_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    'openai': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 60,
        'max_output_tokens_default': 4096,
    },
    'anthropic': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 60,
        'max_output_tokens_default': 8192,
    },
    'google': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 90,
        'max_output_tokens_default': None,
    },
    'mistral': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 60,
        'max_output_tokens_default': 8192,
    },
    'cohere': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 60,
        'max_output_tokens_default': 4096,
    },
    'groq': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 60,
        'max_output_tokens_default': 4096,
    },
    'openrouter': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 90,
        'max_output_tokens_default': 8192,
    },
    'qwen': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 90,
        'max_output_tokens_default': 8192,
    },
    'deepseek': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 90,
        'max_output_tokens_default': 8192,
    },
    'huggingface': {
        'supports_streaming': True,
        'supports_tools': False,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 2048,
    },
    'moonshot': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 90,
        'max_output_tokens_default': 8192,
    },
    'zai': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 90,
        'max_output_tokens_default': 8192,
    },
    'llama.cpp': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 2048,
    },
    'kobold': {
        'supports_streaming': True,
        'supports_tools': False,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 2048,
    },
    'ooba': {
        'supports_streaming': True,
        'supports_tools': False,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 2048,
    },
    'tabbyapi': {
        'supports_streaming': True,
        'supports_tools': False,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 2048,
    },
    'vllm': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 8192,
    },
    'local-llm': {
        'supports_streaming': True,
        'supports_tools': False,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 2048,
    },
    'ollama': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 2048,
    },
    'aphrodite': {
        'supports_streaming': True,
        'supports_tools': False,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 2048,
    },
    'bedrock': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 120,
        'max_output_tokens_default': 8192,
    },
    'custom-openai-api': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 60,
        'max_output_tokens_default': 4096,
    },
    'custom-openai-api-2': {
        'supports_streaming': True,
        'supports_tools': True,
        'default_timeout_seconds': 60,
        'max_output_tokens_default': 4096,
    },
}
