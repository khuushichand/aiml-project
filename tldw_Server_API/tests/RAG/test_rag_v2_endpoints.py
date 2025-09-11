"""
Integration tests for Unified RAG endpoints.

Covers the primary Unified API surface with light fixtures and no heavy mocking.
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.api.v1.endpoints.rag_unified import router as rag_router
from tldw_Server_API.app.core.config import settings


class TestRAGUnifiedEndpoints:
    """Integration tests for Unified RAG endpoints."""
    
    @classmethod
    def setup_class(cls):
        """Set up test fixtures."""
        # Disable CSRF for testing
        cls.original_csrf = settings.get("CSRF_ENABLED", None)
        settings["CSRF_ENABLED"] = False
        
        cls.client = TestClient(app)
        cls.test_user = User(
            id=0,  # Using 0 for single-user mode
            username="test_user",
            email="test@example.com",
            is_active=True
        )
        cls.auth_headers = {"X-API-KEY": "default-secret-key-for-single-user"}
        
        # Create temp directory for test databases
        cls.test_dir = tempfile.mkdtemp(prefix="rag_v2_test_")
        cls.user_base_dir = Path(cls.test_dir) / "user_databases"
        cls.user_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup test databases in the expected location
        cls.setup_test_databases()
    
    @classmethod
    def teardown_class(cls):
        """Clean up test fixtures."""
        # Restore CSRF setting
        if cls.original_csrf is not None:
            settings["CSRF_ENABLED"] = cls.original_csrf
        else:
            settings.pop("CSRF_ENABLED", None)
        
        # Clean up test directory
        shutil.rmtree(cls.test_dir, ignore_errors=True)
        
        # No special cleanup required for unified endpoints
        pass
    
    @classmethod
    def setup_test_databases(cls):
        """Set up test databases with sample data."""
        # Create user directory structure
        user_dir = cls.user_base_dir / "0"
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Create media database
        media_db_path = user_dir / "user_media_library.sqlite"
        media_db = MediaDatabase(str(media_db_path), client_id="0")
        
        # Add sample media
        sample_media = [
            {
                "title": "RAG Overview",
                "content": "Retrieval-Augmented Generation (RAG) combines retrieval and generation.",
                "url": "https://example.com/rag",
                "media_type": "article",
                "author": "AI Expert",
                "ingestion_date": datetime.now().isoformat()
            },
            {
                "title": "Machine Learning Concepts",
                "content": "Machine learning enables systems to learn from data.",
                "url": "https://example.com/ml",
                "media_type": "article",
                "author": "ML Expert",
                "ingestion_date": datetime.now().isoformat()
            }
        ]
        
        for item in sample_media:
            media_db.add_media_with_keywords(**item)
        
        media_db.close_connection()
        
        # Create ChaChaNotes database
        chacha_dir = user_dir / "chachanotes_user_dbs"
        chacha_dir.mkdir(parents=True, exist_ok=True)
        chacha_db_path = chacha_dir / "user_chacha_notes_rag.sqlite"
        chacha_db = CharactersRAGDB(str(chacha_db_path), client_id="0")
        
        # Add sample character and conversation
        char_data = {
            'name': 'Test Assistant',
            'description': 'A helpful AI assistant',
            'personality': 'Professional',
            'tags': json.dumps(['test']),
            'creator': 'test',
            'client_id': '0'
        }
        char_id = chacha_db.add_character_card(char_data)
        
        # Add conversation
        conv_id = str(uuid4())
        conv_data = {
            'id': conv_id,
            'character_id': char_id,
            'title': 'Test Conversation',
            'client_id': '0'
        }
        chacha_db.add_conversation(conv_data)
        
        # Add messages
        messages = [
            {"conversation_id": conv_id, "sender": "user", "content": "Previous question"},
            {"conversation_id": conv_id, "sender": "assistant", "content": "Previous answer"}
        ]
        for msg in messages:
            chacha_db.add_message(msg)
        
        chacha_db.close_connection()
        
        # Store the conversation ID for later use
        cls.test_conversation_id = conv_id
    
    # ============= Unified Endpoints =============

    def test_unified_search_basic(self):
        """POST /api/v1/rag/search with minimal params."""
        payload = {
            "query": "machine learning concepts",
            "sources": ["media_db"],
            "search_mode": "hybrid",
            "top_k": 5
        }
        resp = self.client.post("/api/v1/rag/search", headers=self.auth_headers, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("query") == payload["query"]
        assert isinstance(data.get("documents", []), list)

    def test_unified_search_with_citations_and_generation(self):
        """Enable citations and generation flags and verify response shape."""
        payload = {
            "query": "what is rag?",
            "sources": ["media_db"],
            "enable_citations": True,
            "enable_generation": True,
            "top_k": 3
        }
        resp = self.client.post("/api/v1/rag/search", headers=self.auth_headers, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "documents" in data
        assert "citations" in data
        # generated_answer may be empty; ensure key exists
        assert "generated_answer" in data

    def test_unified_simple_and_advanced(self):
        # Simple GET
        resp_simple = self.client.get("/api/v1/rag/simple", params={"query": "neural networks", "top_k": 2}, headers=self.auth_headers)
        assert resp_simple.status_code == 200
        ds = resp_simple.json()
        assert "documents" in ds

        # Advanced GET
        resp_adv = self.client.get("/api/v1/rag/advanced", params={"query": "deep learning", "with_citations": True}, headers=self.auth_headers)
        assert resp_adv.status_code == 200
        da = resp_adv.json()
        assert "documents" in da

    def test_unified_batch_and_health(self):
        # Batch POST
        batch = {
            "queries": ["ai", "ml"],
            "sources": ["media_db"],
            "top_k": 2
        }
        rb = self.client.post("/api/v1/rag/batch", headers=self.auth_headers, json=batch)
        assert rb.status_code == 200
        bd = rb.json()
        assert bd.get("total_queries") == 2
        assert isinstance(bd.get("results", []), list)

        # Health GET
        rh = self.client.get("/api/v1/rag/health", headers=self.auth_headers)
        assert rh.status_code == 200
        hd = rh.json()
        assert "status" in hd

    def test_unified_validation_error(self):
        # Missing required query
        resp = self.client.post("/api/v1/rag/search", headers=self.auth_headers, json={"top_k": 1})
        assert resp.status_code == 422
        assert "detail" in resp.json()


# Agent-specific tests have been removed in favor of unified search/generation flags.
