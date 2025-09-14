# config_info.py - Endpoint for serving configuration information for documentation
"""
API endpoint to provide configuration information for auto-populating documentation.
Only exposes non-sensitive configuration suitable for documentation.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from typing import Dict, List, Optional
import configparser
import os
from pathlib import Path

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_user
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.config import load_comprehensive_config
from loguru import logger

router = APIRouter()


def get_config_path() -> Path:
    """Get the path to the config file."""
    # Try environment variable first
    config_path = os.getenv("TLDW_CONFIG_PATH")
    if config_path:
        return Path(config_path)
    
    # Default location
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    return Path(project_root) / "Config_Files" / "config.txt"


def load_safe_config() -> Dict:
    """
    Load configuration that is safe to expose for documentation.
    Excludes sensitive information like actual API keys.
    """
    config_path = get_config_path()
    
    if not config_path.exists():
        logger.warning(f"Config file not found at {config_path}")
        return {
            "configured": False,
            "message": "Configuration file not found"
        }
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Get authentication mode
    auth_mode = config.get('Authentication', 'auth_mode', fallback='single_user')
    
    # Determine what to expose based on auth mode
    safe_config = {
        "configured": True,
        "auth_mode": auth_mode,
        "server": {
            "host": config.get('Server', 'host', fallback='127.0.0.1'),
            "port": config.getint('Server', 'port', fallback=8000)
        }
    }
    
    # In single-user mode, we can expose the API key for documentation
    if auth_mode == 'single_user':
        api_key = config.get('Authentication', 'single_user_api_key', 
                           fallback='default-secret-key-for-single-user')
        safe_config["api_key_for_docs"] = api_key
    else:
        # In multi-user mode, provide a placeholder
        safe_config["api_key_for_docs"] = "YOUR_API_KEY_HERE"
    
    # Check which LLM providers are configured (without exposing keys)
    configured_providers = []
    if config.has_section('API'):
        provider_keys = {
            'openai_api_key': 'OpenAI',
            'anthropic_api_key': 'Anthropic',
            'groq_api_key': 'Groq',
            'google_api_key': 'Google',
            'cohere_api_key': 'Cohere',
            'mistral_api_key': 'Mistral',
            'deepseek_api_key': 'DeepSeek',
            'huggingface_api_key': 'HuggingFace',
            'openrouter_api_key': 'OpenRouter'
        }
        
        for key_name, provider_name in provider_keys.items():
            value = config.get('API', key_name, fallback='')
            if value and value not in ['', 'your_api_key_here', 'YOUR_API_KEY_HERE']:
                configured_providers.append(provider_name)
    
    safe_config["configured_llm_providers"] = configured_providers
    
    return safe_config


@router.get("/config/docs-info")
async def get_documentation_config():
    """
    Get configuration information suitable for auto-populating documentation.
    
    This endpoint returns non-sensitive configuration that can be used to:
    - Auto-populate API keys in documentation (single-user mode only)
    - Show which LLM providers are configured
    - Provide the correct base URL for examples
    
    Returns:
        Dict with configuration information safe for documentation
    """
    config = load_safe_config()
    
    # Build base URL
    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 8000)
    
    # Convert 0.0.0.0 to localhost for documentation
    if host == "0.0.0.0":
        host = "localhost"
    
    base_url = f"http://{host}:{port}"
    
    return {
        "configured": config.get("configured", False),
        "auth_mode": config.get("auth_mode", "single_user"),
        "api_key": config.get("api_key_for_docs", "default-secret-key-for-single-user"),
        "base_url": base_url,
        "configured_providers": config.get("configured_llm_providers", []),
        "examples": {
            "python": generate_python_example(
                config.get("api_key_for_docs", "default-secret-key-for-single-user"),
                base_url
            ),
            "curl": generate_curl_example(
                config.get("api_key_for_docs", "default-secret-key-for-single-user"),
                base_url
            ),
            "javascript": generate_js_example(
                config.get("api_key_for_docs", "default-secret-key-for-single-user"),
                base_url
            )
        }
    }


def generate_python_example(api_key: str, base_url: str) -> str:
    """Generate a Python code example with the provided configuration."""
    return f"""import requests

API_KEY = "{api_key}"
BASE_URL = "{base_url}"

# Create evaluation
eval_data = {{
    "name": "test_evaluation",
    "eval_type": "exact_match",
    "eval_spec": {{"threshold": 1.0}},
    "dataset": [
        {{"input": {{"output": "test"}}, "expected": {{"output": "test"}}}}
    ]
}}

response = requests.post(
    f"{{BASE_URL}}/api/v1/evals",
    json=eval_data,
    headers={{"Authorization": f"Bearer {{API_KEY}}"}}
)

print(f"Created evaluation: {{response.json()['id']}}")"""


def generate_curl_example(api_key: str, base_url: str) -> str:
    """Generate a cURL example with the provided configuration."""
    return f"""curl -X POST {base_url}/api/v1/evals \\
  -H "Authorization: Bearer {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "name": "test_eval",
    "eval_type": "exact_match",
    "eval_spec": {{"threshold": 1.0}},
    "dataset": [
      {{"input": {{"output": "test"}}, "expected": {{"output": "test"}}}}
    ]
  }}'"""


def generate_js_example(api_key: str, base_url: str) -> str:
    """Generate a JavaScript example with the provided configuration."""
    return f"""const API_KEY = '{api_key}';
const BASE_URL = '{base_url}';

const evalData = {{
    name: 'test_evaluation',
    eval_type: 'exact_match',
    eval_spec: {{ threshold: 1.0 }},
    dataset: [
        {{ input: {{ output: 'test' }}, expected: {{ output: 'test' }} }}
    ]
}};

const response = await fetch(`${{BASE_URL}}/api/v1/evals`, {{
    method: 'POST',
    headers: {{
        'Authorization': `Bearer ${{API_KEY}}`,
        'Content-Type': 'application/json'
    }},
    body: JSON.stringify(evalData)
}});

const data = await response.json();
console.log('Created evaluation:', data.id);"""


@router.get("/config/quickstart")
async def get_quickstart_redirect():
    """
    Redirect to a Quickstart URL defined in config.txt or environment.

    Precedence:
    1) Environment variable QUICKSTART_URL
    2) Config [WebUI] quickstart_url
    3) Config [Docs] quickstart_url
    4) Default: /webui/
    
    Behavior:
    - If the target starts with http(s)://, redirect there.
    - If the target starts with '/', redirect to that path (same origin).
    - Otherwise, treat as WebUI-relative file and redirect to /webui/<target>.
    """
    try:
        # 1) Environment override
        url = os.getenv("QUICKSTART_URL")

        # 2/3) Config file
        if not url:
            try:
                cfg = load_comprehensive_config()
                if cfg.has_section('WebUI') and cfg.has_option('WebUI', 'quickstart_url'):
                    url = cfg.get('WebUI', 'quickstart_url').strip()
                elif cfg.has_section('Docs') and cfg.has_option('Docs', 'quickstart_url'):
                    url = cfg.get('Docs', 'quickstart_url').strip()
            except Exception as e:
                logger.warning(f"Quickstart redirect: could not read config, using default. Error: {e}")

        # 4) Default
        if not url:
            url = "/webui/"

        # Normalize
        if url.startswith("http://") or url.startswith("https://"):
            target = url
        elif url.startswith("/"):
            target = url
        else:
            # Treat as WebUI-relative file
            target = f"/webui/{url}"

        logger.info(f"Redirecting /api/v1/config/quickstart to: {target}")
        return RedirectResponse(url=target, status_code=307)
    except Exception as e:
        logger.error(f"Quickstart redirect failed: {e}")
        # Fallback to a minimal built-in HTML page with a link to /webui/
        fallback_html = """
        <!DOCTYPE html>
        <html><head><meta charset='utf-8'><title>Quickstart</title></head>
        <body>
          <p>Quickstart is not configured. Continue to the WebUI:</p>
          <a href="/webui/">Open WebUI</a>
        </body></nhtml>
        """
        return HTMLResponse(content=fallback_html, status_code=200)
