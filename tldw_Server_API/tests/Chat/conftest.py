"""Simplified test configuration that works with the existing system."""

import pytest
import tempfile
import os
import json
import threading
import time
import atexit
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
import datetime

# Set environment variables BEFORE any tldw imports
os.environ["OPENAI_API_KEY"] = "sk-mock-key-12345"
os.environ["OPENAI_API_BASE"] = "http://localhost:8080/v1"

# IMPORTANT: Ensure API_BEARER is not set - it causes wrong authentication path in single-user mode
if "API_BEARER" in os.environ:
    del os.environ["API_BEARER"]

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import (
    get_chacha_db_for_user,
    DEFAULT_CHARACTER_NAME,
)
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user


# Global state to track mock server
_mock_server_state = {"server": None, "thread": None, "base_url": None}

# Global variable to store original dependency overrides
_original_dependency_overrides = None


def cleanup_mock_server():
    """Cleanup function to ensure mock server is stopped."""
    server = _mock_server_state.get("server")
    thread = _mock_server_state.get("thread")

    if server:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass

    if thread and thread.is_alive():
        thread.join(timeout=5)

    _mock_server_state["server"] = None
    _mock_server_state["thread"] = None
    _mock_server_state["base_url"] = None


# Register cleanup function
atexit.register(cleanup_mock_server)


@pytest.fixture(scope="session", autouse=True)
def preserve_app_state():
    """Preserve the original app dependency overrides across all tests."""
    global _original_dependency_overrides
    
    # Store the original state at the beginning of the test session
    _original_dependency_overrides = app.dependency_overrides.copy()
    
    yield
    
    # Restore the original state at the end of the test session
    app.dependency_overrides = _original_dependency_overrides.copy()


@pytest.fixture(autouse=True)
def reset_app_overrides():
    """Reset app dependency overrides before each test."""
    global _original_dependency_overrides
    
    # Reset to original state before each test
    if _original_dependency_overrides is not None:
        app.dependency_overrides = _original_dependency_overrides.copy()
    else:
        app.dependency_overrides.clear()
    
    yield
    
    # Clean up after each test
    if _original_dependency_overrides is not None:
        app.dependency_overrides = _original_dependency_overrides.copy()
    else:
        app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def mock_openai_server():
    """Start the mock OpenAI server for testing."""
    if _mock_server_state["server"]:
        yield _mock_server_state["base_url"]
        return

    class _MockOpenAIHandler(BaseHTTPRequestHandler):
        mock_completion = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "mock-gpt",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "This is a test response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }

        def _send_json(self, payload, status_code=200):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 - http.server naming
            if self.path == "/v1/models":
                self._send_json({"data": [{"id": "mock-gpt"}]})
            else:
                self._send_json({"error": "Not found"}, status_code=404)

        def do_POST(self):  # noqa: N802 - http.server naming
            if self.path == "/v1/chat/completions":
                content_length = int(self.headers.get("Content-Length") or 0)
                if content_length:
                    # Consume request body to keep the socket healthy
                    self.rfile.read(content_length)
                response = dict(self.mock_completion)
                response["created"] = int(time.time())
                self._send_json(response)
            else:
                self._send_json({"error": "Not found"}, status_code=404)

        def log_message(self, format, *args):  # noqa: D401 - silence default logging
            return

    server = HTTPServer(("127.0.0.1", 0), _MockOpenAIHandler)
    thread = threading.Thread(target=server.serve_forever, name="mock-openai-server", daemon=True)
    thread.start()

    # Store state for reuse
    _mock_server_state["server"] = server
    _mock_server_state["thread"] = thread
    _mock_server_state["base_url"] = f"http://127.0.0.1:{server.server_port}"

    # Give server moment to start
    time.sleep(0.1)

    yield _mock_server_state["base_url"]

    cleanup_mock_server()


@pytest.fixture
def configure_for_mock_server(mock_openai_server, monkeypatch):
    """Configure the application to use the mock OpenAI server."""
    # Ensure environment variables are set
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key-12345")
    monkeypatch.setenv("OPENAI_API_BASE", f"{mock_openai_server}/v1")
    
    # Also set custom endpoint variables
    monkeypatch.setenv("CUSTOM_OPENAI_API_IP", f"{mock_openai_server}/v1/chat/completions")
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", "sk-mock-key-12345")
    
    # Reload the schemas module to pick up the new environment variables
    import importlib
    import tldw_Server_API.app.api.v1.schemas.chat_request_schemas as chat_schemas
    importlib.reload(chat_schemas)
    
    # Update API_KEYS using monkeypatch for automatic cleanup
    monkeypatch.setitem(chat_schemas.API_KEYS, 'openai', 'sk-mock-key-12345')
    # Sync the chat endpoint's imported API_KEYS without leaving global residue
    from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint
    if hasattr(chat_endpoint, 'API_KEYS'):
        monkeypatch.setattr(chat_endpoint, 'API_KEYS', chat_schemas.API_KEYS, raising=False)
    
    # Patch the OpenAI API URL in the config
    from tldw_Server_API.app.core.config import load_and_log_configs
    config = load_and_log_configs()
    if 'openai_api' not in config:
        config['openai_api'] = {}
    config['openai_api']['api_key'] = 'sk-mock-key-12345'
    config['openai_api']['api_base_url'] = f'{mock_openai_server}/v1'
    
    # Patch the load_and_log_configs function to return our patched config
    def mock_load_and_log_configs():
        return config
    
    monkeypatch.setattr('tldw_Server_API.app.core.config.load_and_log_configs', mock_load_and_log_configs)
    monkeypatch.setattr('tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs', mock_load_and_log_configs)
    
    yield


@pytest.fixture
def test_user():
    """Create a test user object."""
    return User(
        id=1,
        username="test_user",
        email="test@example.com",
        is_active=True
    )


@pytest.fixture
def auth_token(test_user):
    """Generate a valid JWT token for the test user."""
    settings = get_settings()
    
    if settings.AUTH_MODE == "multi_user":
        jwt_service = get_jwt_service()
        # Use the correct method signature
        access_token = jwt_service.create_access_token(
            user_id=test_user.id,
            username=test_user.username,
            role="user"
        )
        return f"Bearer {access_token}"
    else:
        # For single-user mode - return the actual API key from settings
        # This should match what's in the environment
        api_key = settings.SINGLE_USER_API_KEY
        if not api_key:
            # Fallback to the test key if not set
            api_key = "test-api-key-12345"
        return api_key


@pytest.fixture
def mock_user_db(test_user):
    """Mock the user database to return our test user."""
    mock_db = MagicMock()
    
    # Mock get_user_by_id to return test user data
    async def mock_get_user_by_id(user_id):
        if user_id == test_user.id:
            return {
                "id": test_user.id,
                "username": test_user.username,
                "email": test_user.email,
                "is_active": test_user.is_active
            }
        return None
    
    # Patch the actual function
    import tldw_Server_API.app.core.DB_Management.Users_DB as users_db_module
    if hasattr(users_db_module, 'get_user_by_id'):
        users_db_module.get_user_by_id = mock_get_user_by_id
    
    return mock_db


@pytest.fixture
def mock_chacha_db(test_user):
    """Create a mock ChaChaNotes database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    db = CharactersRAGDB(db_path, f"user_{test_user.id}")
    
    # Add default character with the expected name
    char_id = db.add_character_card({
        "name": DEFAULT_CHARACTER_NAME,
        "description": "A helpful AI assistant",
        "personality": "Helpful",
        "scenario": "General",
        "system_prompt": "You are a helpful AI assistant."
    })
    print(f"Created default character with ID: {char_id}")
    
    yield db
    
    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def mock_media_db(test_user):
    """Create a mock media database."""
    mock_db = MagicMock()
    mock_db.client_id = f"user_{test_user.id}"
    return mock_db


@pytest.fixture
def setup_dependencies(test_user, mock_user_db, mock_chacha_db, mock_media_db):
    """Override all dependencies for testing."""
    settings = get_settings()
    
    # Override authentication
    if settings.AUTH_MODE == "multi_user":
        # For multi-user mode, override to return test user
        async def mock_get_request_user(api_key=None, token=None):
            return test_user
        app.dependency_overrides[get_request_user] = mock_get_request_user
    
    # Override databases
    app.dependency_overrides[get_chacha_db_for_user] = lambda: mock_chacha_db
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_media_db
    
    yield
    
    # Cleanup - don't clear, let the autouse fixture handle it


@pytest.fixture
def client():
    """Create test client with CSRF handling."""
    # Make sure we're using the same app instance
    from tldw_Server_API.app.main import app as main_app
    with TestClient(main_app) as test_client:
        # Get CSRF token
        response = test_client.get("/api/v1/health")
        csrf_token = response.cookies.get("csrf_token", "")
        test_client.csrf_token = csrf_token
        test_client.cookies = {"csrf_token": csrf_token}
        
        # Add helper method
        def post_with_auth(url, auth_token, **kwargs):
            headers = kwargs.pop("headers", {})
            headers["X-CSRF-Token"] = csrf_token
            
            settings = get_settings()
            if settings.AUTH_MODE == "multi_user":
                headers["Authorization"] = auth_token
            else:
                # Use X-API-KEY header for single-user mode
                headers["X-API-KEY"] = auth_token
            
            return test_client.post(url, headers=headers, **kwargs)
        
        test_client.post_with_auth = post_with_auth
        
        yield test_client


@pytest.fixture
def authenticated_client(client, auth_token):
    """Create an authenticated test client."""
    settings = get_settings()
    
    # Add authentication to all requests
    original_post = client.post
    
    def authenticated_post(url, **kwargs):
        headers = kwargs.pop("headers", {})
        
        if settings.AUTH_MODE == "multi_user":
            headers["Authorization"] = auth_token
        else:
            # Use Token header with Bearer format for chat endpoint
            token_with_bearer = auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}"
            headers["Token"] = token_with_bearer
        
        return original_post(url, headers=headers, **kwargs)
    
    client.post = authenticated_post
    return client


def get_auth_headers(auth_token, csrf_token=""):
    """Helper function to get authentication headers."""
    settings = get_settings()
    headers = {"X-CSRF-Token": csrf_token}
    
    if settings.AUTH_MODE == "multi_user":
        headers["Authorization"] = auth_token
    else:
        # Use X-API-KEY header for single-user mode
        headers["X-API-KEY"] = auth_token
    
    return headers


# Additional fixtures for unit tests
@pytest.fixture
def isolated_db():
    """Create an isolated database for each test."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    db = CharactersRAGDB(db_path, f"test_client_{id(tmp)}")
    
    # Enable WAL mode for better concurrency
    conn = db.get_connection()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.close()
    
    # Add default character
    char_id = db.add_character_card({
        "name": DEFAULT_CHARACTER_NAME,
        "description": "A helpful AI assistant",
        "personality": "Helpful",
        "scenario": "General",
        "system_prompt": "You are a helpful AI assistant."
    })
    
    yield db
    
    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def sample_chat_request():
    """Create a sample chat completion request."""
    from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import (
        ChatCompletionRequest,
        ChatCompletionUserMessageParam
    )
    
    return ChatCompletionRequest(
        model="test-model",
        messages=[
            ChatCompletionUserMessageParam(role="user", content="Test message")
        ],
        api_provider="openai"
    )


@pytest.fixture(autouse=True)
def ensure_no_api_bearer():
    """Ensure API_BEARER is not set for chat tests."""
    import os
    # Remove API_BEARER if it exists - it causes wrong authentication path
    if "API_BEARER" in os.environ:
        del os.environ["API_BEARER"]
    yield
    # Clean up after test as well
    if "API_BEARER" in os.environ:
        del os.environ["API_BEARER"]


@pytest.fixture
def unit_test_client(client, auth_token, isolated_db):
    """Create a test client configured for unit tests."""
    from unittest.mock import patch
    
    settings = get_settings()
    
    # Create test user
    test_user = User(
        id=1,
        username="test_user",
        email="test@example.com",
        is_active=True
    )
    
    # Override dependencies
    async def mock_get_request_user(api_key=None, token=None):
        return test_user
    
    app.dependency_overrides[get_request_user] = mock_get_request_user
    app.dependency_overrides[get_chacha_db_for_user] = lambda: isolated_db
    
    # Mock LLM responses
    mock_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "test-model",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": "This is a test response"},
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
    }
    
    # Add helper method for authenticated requests
    def post_with_auth(url, json_data, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["X-CSRF-Token"] = client.csrf_token
        
        if settings.AUTH_MODE == "multi_user":
            headers["Authorization"] = auth_token
        else:
            # Use Token header with Bearer format for chat endpoint
            token_with_bearer = auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}"
            headers["Token"] = token_with_bearer
        
        # Mock the LLM call
        with patch("tldw_Server_API.app.core.Chat.Chat_Functions.chat_api_call") as mock_llm, \
             patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call") as mock_perform:
            mock_llm.return_value = mock_response
            mock_perform.return_value = mock_response
            
            return client.post(url, json=json_data, headers=headers, **kwargs)
    
    client.post_with_auth = post_with_auth
    
    yield client
    
    # Cleanup
    app.dependency_overrides.clear()
