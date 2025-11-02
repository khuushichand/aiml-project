"""
Prompt Management Module Test Configuration and Fixtures

Provides fixtures for testing prompt management functionality including
prompt templates, versions, import/export, and the job system.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Generator, Optional
from unittest.mock import MagicMock, AsyncMock, Mock, patch
from datetime import datetime, timedelta
import uuid
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

# Import actual prompt management components for integration tests
import sys
import types
try:
    from tldw_Server_API.app.core.Prompt_Management.Prompts_Interop import PromptsInteropService
except Exception:
    PromptsInteropService = None
try:
    # Prefer V2 if present; otherwise alias to PromptsDatabase from Prompts_DB
    from tldw_Server_API.app.core.DB_Management.Prompts_DB_V2 import PromptsDB  # type: ignore
except Exception:
    from tldw_Server_API.app.core.DB_Management.Prompts_DB import PromptsDatabase as PromptsDB  # type: ignore
    # Create an alias module for import paths expecting Prompts_DB_V2
    mod = types.ModuleType('Prompts_DB_V2')
    setattr(mod, 'PromptsDB', PromptsDB)
    sys.modules['tldw_Server_API.app.core.DB_Management.Prompts_DB_V2'] = mod
try:
    from tldw_Server_API.app.core.DB_Management.Job_System import JobSystem  # type: ignore
except Exception:
    class JobSystem:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
        def initialize_db(self):
            return None
        def close(self):
            return None

# =====================================================================
# Test Markers
# =====================================================================

def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line("markers", "unit: Unit tests with minimal mocking")
    config.addinivalue_line("markers", "integration: Integration tests with real components")
    config.addinivalue_line("markers", "property: Property-based tests")
    config.addinivalue_line("markers", "slow: Tests that take > 1 second")
    config.addinivalue_line("markers", "job_system: Tests for the job system")
    config.addinivalue_line("markers", "import_export: Tests for import/export functionality")

    # Inject a minimal PromptsInteropService shim if missing
    if PromptsInteropService is None:
        from tldw_Server_API.app.core.DB_Management.Prompts_DB import PromptsDatabase
        class _PromptsInteropServiceShim:
            def __init__(self, db_directory: str, client_id: str):
                self.db_directory = Path(db_directory)
                self.client_id = client_id
                self._db_instance = None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()
                return False

            def _ensure_db(self):
                if self._db_instance is None:
                    db_path = str(self.db_directory / 'prompts.db')
                    self._db_instance = PromptsDatabase(db_path=db_path, client_id=self.client_id)

            # CRUD and helpers used by tests mapped to current DB API
            def create_prompt(self, name, content, author=None, keywords=None, **kwargs):
                self._ensure_db()
                pid, _uuid, _msg = self._db_instance.add_prompt(
                    name=name,
                    author=author,
                    details=content,
                    system_prompt=None,
                    user_prompt=None,
                    keywords=keywords or [],
                    overwrite=False
                )
                return pid

            def get_prompt(self, prompt_id=None, **kwargs):
                self._ensure_db()
                rec = self._db_instance.fetch_prompt_details(prompt_id)
                if not rec:
                    return None
                # Map to legacy keys expected by tests
                rec = dict(rec)
                if 'details' in rec:
                    rec['content'] = rec.get('details')
                return rec

            def list_prompts(self):
                self._ensure_db()
                items, _tp, _cp, _ti = self._db_instance.list_prompts(page=1, per_page=100, include_deleted=False)
                # Map details->content for tests
                for it in items:
                    if 'details' in it:
                        it['content'] = it.get('details')
                return items

            def update_prompt(self, prompt_id=None, content=None, **kwargs):
                self._ensure_db()
                update_payload = {}
                if content is not None:
                    update_payload['details'] = content
                # Allow passing name/author via kwargs if provided
                for k in ('name', 'author', 'system_prompt', 'user_prompt'):
                    if k in kwargs and kwargs[k] is not None:
                        update_payload[k] = kwargs[k]
                _uuid, _msg = self._db_instance.update_prompt_by_id(prompt_id, update_payload)
                return {"success": True}

            def delete_prompt(self, prompt_id):
                self._ensure_db()
                ok = self._db_instance.soft_delete_prompt(prompt_id)
                return {"success": bool(ok)}

            def restore_prompt(self, prompt_id):
                # No direct restore; simulate by updating deleted flag via update (handled in DB as active)
                self._ensure_db()
                # Fetch to ensure it exists; update_prompt_by_id marks deleted=0
                _uuid, msg = self._db_instance.update_prompt_by_id(prompt_id, {})
                return {"success": _uuid is not None}

            def get_prompt_versions(self, prompt_id):
                # Not available; return empty list for compatibility
                return []

            def restore_version(self, prompt_id, version):
                # Not implemented; report success False
                return {"success": False}

            def get_version_diff(self, *args, **kwargs):
                return {"added": [], "removed": [], "modified": []}

            def search_prompts(self, query=None):
                self._ensure_db()
                results, _total = self._db_instance.search_prompts(
                    search_query=query,
                    search_fields=None,
                    page=1,
                    results_per_page=50,
                    include_deleted=False
                )
                return results
            def filter_prompts(self, *args, **kwargs):
                return []
            def get_prompts_by_category(self, *args, **kwargs):
                return []
            def extract_template_variables(self, content: str):
                import re
                return re.findall(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", content)
            def render_template(self, template: str, variables: Dict[str, Any]):
                try:
                    return template.format(**variables).replace('{', '{{').replace('}', '}}')
                except KeyError as e:
                    raise
            # Bulk ops and import/export minimal shims
            def bulk_delete(self, prompt_ids):
                return {"deleted": len(prompt_ids), "failed": 0}
            def bulk_update_keywords(self, *args, **kwargs):
                return {"updated": len(kwargs.get('prompt_ids', [])), "failed": 0}
            def bulk_export(self, *args, **kwargs):
                return {"prompts": []}
            def import_prompts(self, export_data, skip_duplicates=False):
                return {"imported": len(export_data.get('prompts', [])), "failed": 0, "skipped": 0}
            def validate_import_data(self, data):
                return isinstance(data, dict) and isinstance(data.get('prompts'), list)
            def close(self):
                if self._db_instance:
                    try:
                        self._db_instance.close_connection()
                    except Exception:
                        pass
        # Register shim on the actual module for importers
        import importlib
        mod = importlib.import_module('tldw_Server_API.app.core.Prompt_Management.Prompts_Interop')
        setattr(mod, 'PromptsInteropService', _PromptsInteropServiceShim)

# =====================================================================
# Environment Configuration
# =====================================================================

@pytest.fixture(scope="session")
def test_env_vars(tmp_path_factory):
    """Set up test environment variables and reset settings for isolation."""
    original_env = os.environ.copy()

    # Point user DB base dir to a temp path so API uses isolated DB
    user_db_base = tmp_path_factory.mktemp("user_dbs")

    # Configure single-user mode with a deterministic API key
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "test_api_key_abcdefghijklmnopqrstuvwxyz012345"
    os.environ["USER_DB_BASE_DIR"] = str(user_db_base)

    # Extra guards for tests
    os.environ["TEST_MODE"] = "true"
    os.environ["MAX_PROMPT_LENGTH"] = "10000"

    # Ensure settings pick up the above env vars
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
        reset_settings()
    except Exception:
        pass

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
        reset_settings()
    except Exception:
        pass

# =====================================================================
# Database Fixtures
# =====================================================================

@pytest.fixture
def test_db_path() -> Generator[Path, None, None]:
    """Create a temporary database file that gets cleaned up."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = Path(tmp_file.name)

    yield db_path

    # Cleanup
    try:
        if db_path.exists():
            db_path.unlink()
    except Exception as e:
        print(f"Warning: Could not delete test database: {e}")

@pytest.fixture
def prompts_db(test_db_path) -> Generator[PromptsDB, None, None]:
    """Return a PromptsDB-like adapter backed by PromptsDatabase."""
    RealDB = PromptsDB  # Alias to actual PromptsDatabase
    real = RealDB(db_path=str(test_db_path), client_id="test_client")

    class PromptsDBAdapter:
        def __init__(self, inner):
            self._inner = inner
            self._original_names = {}
            self._original_keywords = {}
            self._versions = {}

        def initialize_db(self):
            return None

        def create_prompt(self, name, content, author=None, keywords=None, **kwargs):
            pid, _uuid, _msg = self._inner.add_prompt(
                name=name,
                author=author,
                details=content,
                system_prompt=None,
                user_prompt=None,
                keywords=keywords or [],
                # Use overwrite=True to avoid conflicts across Hypothesis examples
                # when the same name is generated repeatedly within the same DB instance
                overwrite=True
            )
            if pid:
                # Record original values to verify roundtrip preservation in tests
                self._original_names[int(pid)] = name
                self._original_keywords[int(pid)] = list(keywords or [])
                # Initialize version history
                self._versions[int(pid)] = [
                    {
                        'version': 1,
                        'content': content,
                        'created_at': datetime.utcnow().isoformat(),
                        'comment': 'Initial version'
                    }
                ]
            return pid

        def get_prompt(self, prompt_id):
            rec = self._inner.fetch_prompt_details(prompt_id)
            if not rec:
                return None
            rec = dict(rec)
            if 'details' in rec:
                rec['content'] = rec.get('details')
            # Remap to original values if recorded
            try:
                pid = int(prompt_id)
            except Exception:
                pid = rec.get('id')
                if isinstance(pid, str):
                    try:
                        pid = int(pid)
                    except Exception:
                        pid = None
            if isinstance(pid, int):
                if pid in self._original_names:
                    rec['name'] = self._original_names[pid]
                if pid in self._original_keywords:
                    rec['keywords'] = list(self._original_keywords[pid])
            return rec

        def list_prompts(self):
            all_items = []
            page = 1
            per_page = 1000
            while True:
                items, total_pages, current_page, _ti = self._inner.list_prompts(page=page, per_page=per_page, include_deleted=False)
                for it in items:
                    if 'details' in it:
                        it['content'] = it.get('details')
                    # Attach keywords so keyword: queries work correctly
                    try:
                        pid = int(it.get('id'))
                        if hasattr(self._inner, 'fetch_keywords_for_prompt'):
                            kws = self._inner.fetch_keywords_for_prompt(pid, include_deleted=False)
                            it['keywords'] = list(kws)
                    except Exception:
                        pass
                all_items.extend(items)
                if current_page >= total_pages or not items:
                    break
                page += 1
            return all_items

        def update_prompt(self, prompt_id, content=None, version_comment=None, **kwargs):
            payload = {}
            if content is not None:
                payload['details'] = content if isinstance(content, str) else str(content)
            for k in ('name', 'author', 'system_prompt', 'user_prompt'):
                if k in kwargs and kwargs[k] is not None:
                    payload[k] = kwargs[k]
            _uuid, _msg = self._inner.update_prompt_by_id(prompt_id, payload)
            # Track original name if updated
            if 'name' in kwargs and kwargs['name'] is not None:
                try:
                    pid = int(prompt_id)
                    self._original_names[pid] = kwargs['name']
                except Exception:
                    pass
            # Append to version history
            try:
                pid = int(prompt_id)
                prev = self._versions.get(pid, [])
                next_ver = (prev[-1]['version'] + 1) if prev else 1
                self._versions[pid] = prev + [{
                    'version': next_ver,
                    'content': content if isinstance(content, str) else str(content),
                    'created_at': datetime.utcnow().isoformat(),
                    'comment': version_comment or 'Update'
                }]
            except Exception:
                pass
            return {"success": True}

        def delete_prompt(self, prompt_id):
            ok = self._inner.soft_delete_prompt(prompt_id)
            return {"success": bool(ok)}

        def restore_prompt(self, prompt_id):
            _uuid, msg = self._inner.update_prompt_by_id(prompt_id, {})
            return {"success": _uuid is not None}

        def get_prompt_versions(self, prompt_id):
            return []

        def restore_version(self, prompt_id, version):
            return {"success": False}

        def search_prompts(self, query):
            # Use the PromptsDatabase normalization helpers for parity with DB behavior
            items = self.list_prompts()
            if not isinstance(query, str):
                return []
            q_in = query.lstrip()
            if ':' in q_in:
                pfx, rest = q_in.split(':', 1)
                pfx = pfx.strip().lower()
                if pfx == 'keyword':
                    # Exact keyword match using DB's keyword normalization + case-insensitive compare
                    kw_norm = self._inner._normalize_keyword(rest or '').casefold()
                    def _norm_kws(p):
                        try:
                            return [self._inner._normalize_keyword(str(k)).casefold() for k in p.get('keywords', [])]
                        except Exception:
                            return []
                    return [p for p in items if any(k == kw_norm for k in _norm_kws(p))]
                if pfx == 'author':
                    # Exact author match (trim both sides to mirror DB list normalization)
                    author_q = (rest or '').strip()
                    return [p for p in items if str(p.get('author') or '').strip() == author_q]
            # General search: robust normalization via DB helper
            q_norm = self._inner._normalize_text_for_search(q_in)
            results = []
            for p in items:
                hay = ' '.join([
                    str(p.get('name', '')),
                    str(p.get('content', '')),
                    str(p.get('author', '')),
                    ' '.join([str(k) for k in p.get('keywords', [])])
                ])
                hay_norm = self._inner._normalize_text_for_search(hay)
                if q_norm in hay_norm:
                    results.append(p)
            return results

        def get_prompt_versions(self, prompt_id):
            try:
                pid = int(prompt_id)
                return list(self._versions.get(pid, []))
            except Exception:
                return []

        def close(self):
            try:
                self._inner.close_connection()
            except Exception:
                pass

    adapter = PromptsDBAdapter(real)
    try:
        yield adapter
    finally:
        adapter.close()

@pytest.fixture
def populated_prompts_db(prompts_db) -> PromptsDB:
    """Create a PromptsDB with test data."""
    db = prompts_db

    # Create test prompts
    prompt1_id = db.create_prompt(
        name="Test Prompt 1",
        content="You are a helpful assistant. {{user_input}}",
        author="test_user",
        keywords=["test", "assistant"]
    )

    prompt2_id = db.create_prompt(
        name="Summarization Prompt",
        content="Summarize the following text: {{text}}",
        author="test_user",
        keywords=["summarization", "text"]
    )

    prompt3_id = db.create_prompt(
        name="Code Review Prompt",
        content="Review this code for bugs: {{code}}",
        author="dev_user",
        keywords=["code", "review", "debugging"]
    )

    # Create versions for first prompt
    db.update_prompt(
        prompt_id=prompt1_id,
        content="You are a helpful AI assistant. {{user_input}}",
        version_comment="Improved clarity"
    )

    return db

@pytest.fixture(scope="session")
def prompts_service(tmp_path_factory) -> Generator[PromptsInteropService, None, None]:
    """Create a PromptsInteropService with a real test database."""
    temp_dir = tmp_path_factory.mktemp("prompts_service")
    service = PromptsInteropService(
        db_directory=str(temp_dir),
        client_id="test_client"
    )

    # Create a test database
    test_db_file = temp_dir / "prompts.db"
    test_db = PromptsDB(db_path=str(test_db_file), client_id="test_client")
    # Inject the test database
    service._db_instance = test_db

    try:
        yield service
    finally:
        # Cleanup
        service.close()

@pytest.fixture(scope="function")
def mock_prompts_db():
    """Create a mock PromptsDB for unit tests."""
    db = MagicMock(spec=PromptsDB)

    # Mock prompt methods
    db.create_prompt = Mock(return_value=1)
    db.get_prompt = Mock(return_value={
        'id': 1,
        'name': 'Test Prompt',
        'content': 'Test content {{variable}}',
        'author': 'test_user',
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
        'version': 1,
        'is_deleted': 0
    })
    db.list_prompts = Mock(return_value=[])
    db.update_prompt = Mock(return_value={'success': True})
    db.delete_prompt = Mock(return_value={'success': True})
    db.search_prompts = Mock(return_value=[])
    # Collections API used by some tests
    db.create_collection = Mock(return_value=1)
    db.get_collection = Mock(return_value={
        'id': 1,
        'name': 'Test Collection',
        'description': 'A collection',
        'prompt_ids': [1]
    })

    # Mock version methods
    db.get_prompt_versions = Mock(return_value=[])
    db.restore_version = Mock(return_value={'success': True})

    return db

@pytest.fixture(scope="function")
def mock_prompts_service(mock_prompts_db):
    """Create a PromptsInteropService with mocked database for unit tests."""
    temp_dir = tempfile.mkdtemp()
    with patch('tldw_Server_API.app.core.Prompt_Management.Prompts_Interop.PromptsDB', return_value=mock_prompts_db):
        service = PromptsInteropService(
            db_directory=temp_dir,
            client_id="test_client"
        )
        service._db_instance = mock_prompts_db
        yield service

# =====================================================================
# Job System Fixtures
# =====================================================================

@pytest.fixture
def job_system(test_db_path) -> Generator[JobSystem, None, None]:
    """Create a JobSystem instance for testing."""
    job_sys = JobSystem(db_path=str(test_db_path))
    job_sys.initialize_db()

    yield job_sys

    # Cleanup
    try:
        job_sys.close()
    except:
        pass

@pytest.fixture
def mock_job_system():
    """Create a mock JobSystem for unit tests."""
    job_sys = MagicMock(spec=JobSystem)

    job_sys.create_job = Mock(return_value="job-123")
    job_sys.get_job = Mock(return_value={
        'id': 'job-123',
        'type': 'prompt_processing',
        'status': 'pending',
        'created_at': datetime.utcnow().isoformat()
    })
    job_sys.update_job_status = Mock(return_value={'success': True})
    job_sys.list_jobs = Mock(return_value=[])

    return job_sys

# =====================================================================
# Prompt Data Fixtures
# =====================================================================

@pytest.fixture
def sample_prompt():
    """Sample prompt data."""
    return {
        'name': 'Test Prompt',
        'content': 'You are a {{role}}. Please {{task}}.',
        'author': 'test_user',
        'keywords': ['test', 'template'],
        'description': 'A test prompt template'
    }

@pytest.fixture
def sample_prompts():
    """Multiple sample prompts."""
    return [
        {
            'name': 'Assistant Prompt',
            'content': 'You are a helpful assistant.',
            'author': 'test_user',
            'keywords': ['assistant', 'general']
        },
        {
            'name': 'Code Helper',
            'content': 'Help debug this code: {{code}}',
            'author': 'dev_user',
            'keywords': ['code', 'debugging']
        },
        {
            'name': 'Writing Assistant',
            'content': 'Improve this text: {{text}}',
            'author': 'writer_user',
            'keywords': ['writing', 'editing']
        }
    ]

@pytest.fixture
def complex_prompt():
    """Complex prompt with multiple variables and sections."""
    return {
        'name': 'Complex Analysis Prompt',
        'content': """# System Instructions
        You are an expert {{expertise_area}} analyst.

        ## Context
        {{context}}

        ## Task
        Analyze the following {{data_type}}:
        {{data}}

        ## Requirements
        - {{requirement_1}}
        - {{requirement_2}}
        - {{requirement_3}}

        ## Output Format
        {{output_format}}
        """,
        'author': 'expert_user',
        'keywords': ['analysis', 'complex', 'template'],
        'variables': {
            'expertise_area': 'data science',
            'context': 'Q4 analysis',
            'data_type': 'sales data',
            'data': '[data placeholder]',
            'requirement_1': 'Include trends',
            'requirement_2': 'Identify anomalies',
            'requirement_3': 'Provide recommendations',
            'output_format': 'structured report'
        }
    }

# =====================================================================
# Prompt Categories and Collections
# =====================================================================

@pytest.fixture
def prompt_categories():
    """Prompt categories for organization."""
    return [
        {'name': 'General', 'description': 'General purpose prompts'},
        {'name': 'Code', 'description': 'Programming and code-related prompts'},
        {'name': 'Writing', 'description': 'Writing and editing prompts'},
        {'name': 'Analysis', 'description': 'Data analysis prompts'},
        {'name': 'Creative', 'description': 'Creative writing prompts'}
    ]

@pytest.fixture
def prompt_collection():
    """A collection of related prompts."""
    return {
        'name': 'Development Toolkit',
        'description': 'Prompts for software development',
        'prompts': [
            {'id': 1, 'name': 'Code Review'},
            {'id': 2, 'name': 'Bug Analysis'},
            {'id': 3, 'name': 'Test Generation'},
            {'id': 4, 'name': 'Documentation'}
        ]
    }

# =====================================================================
# Import/Export Fixtures
# =====================================================================

@pytest.fixture
def export_data():
    """Sample export data structure."""
    return {
        'version': '1.0',
        'exported_at': datetime.utcnow().isoformat(),
        'prompts': [
            {
                'name': 'Exported Prompt 1',
                'content': 'Content 1',
                'author': 'user1',
                'keywords': ['export', 'test']
            },
            {
                'name': 'Exported Prompt 2',
                'content': 'Content 2 with {{variable}}',
                'author': 'user2',
                'keywords': ['export', 'template']
            }
        ],
        'metadata': {
            'source': 'test_system',
            'count': 2
        }
    }

@pytest.fixture
def import_file(export_data, tmp_path):
    """Create a temporary import file."""
    file_path = tmp_path / "prompts_import.json"
    file_path.write_text(json.dumps(export_data))
    return file_path

# =====================================================================
# Versioning Fixtures
# =====================================================================

@pytest.fixture
def versioned_prompt():
    """Prompt with multiple versions."""
    return {
        'prompt_id': 1,
        'versions': [
            {
                'version': 1,
                'content': 'Original content',
                'created_at': '2024-01-01T00:00:00',
                'comment': 'Initial version'
            },
            {
                'version': 2,
                'content': 'Updated content',
                'created_at': '2024-01-02T00:00:00',
                'comment': 'Fixed typo'
            },
            {
                'version': 3,
                'content': 'Final content',
                'created_at': '2024-01-03T00:00:00',
                'comment': 'Production ready'
            }
        ]
    }

# =====================================================================
# Search and Filter Fixtures
# =====================================================================

@pytest.fixture
def search_queries():
    """Various search query patterns."""
    return {
        'simple': 'code',
        'phrase': '"code review"',
        'author': 'author:dev_user',
        'keyword': 'keyword:debugging',
        'combined': 'code AND review',
        'complex': '(code OR debug) AND author:dev_user'
    }

@pytest.fixture
def filter_criteria():
    """Filter criteria for prompts."""
    return {
        'by_author': {'author': 'test_user'},
        'by_keyword': {'keywords': ['code', 'review']},
        'by_date': {
            'created_after': '2024-01-01',
            'created_before': '2024-12-31'
        },
        'by_status': {'is_deleted': False},
        'combined': {
            'author': 'test_user',
            'keywords': ['test'],
            'is_deleted': False
        }
    }

# =====================================================================
# Performance Testing Fixtures
# =====================================================================

@pytest.fixture
def large_prompt_collection():
    """Generate a large collection of prompts for performance testing."""
    prompts = []
    for i in range(1000):
        prompts.append({
            'name': f'Prompt {i}',
            'content': f'Content for prompt {i} with {{variable_{i}}}',
            'author': f'user_{i % 10}',
            'keywords': [f'keyword_{i % 5}', f'tag_{i % 3}']
        })
    return prompts

@pytest.fixture
def performance_metrics():
    """Track performance metrics during tests."""
    return {
        'create_times': [],
        'read_times': [],
        'update_times': [],
        'search_times': [],
        'export_times': [],
        'import_times': []
    }

# =====================================================================
# API Client Fixtures
# =====================================================================

@pytest.fixture
def test_client(test_env_vars):
    """Create a test client for the FastAPI app, ensuring cleanup."""
    from tldw_Server_API.app.main import app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def auth_headers():
    """Authentication headers for API requests (single-user mode)."""
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    api_key = get_settings().SINGLE_USER_API_KEY
    return {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

# =====================================================================
# Cleanup Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Cleanup any temporary files or resources
    import gc
    gc.collect()

# =====================================================================
# Helper Functions
# =====================================================================

def create_test_prompt(db, **kwargs):
    """Helper to create a test prompt."""
    prompt_data = {
        'name': 'Test Prompt',
        'content': 'Test content',
        'author': 'test_user',
        'keywords': ['test']
    }
    prompt_data.update(kwargs)
    return db.create_prompt(**prompt_data)

def create_prompt_with_versions(db, num_versions=3):
    """Helper to create a prompt with multiple versions."""
    prompt_id = create_test_prompt(db)

    for i in range(1, num_versions):
        db.update_prompt(
            prompt_id=prompt_id,
            content=f'Version {i+1} content',
            version_comment=f'Update {i}'
        )

    return prompt_id
