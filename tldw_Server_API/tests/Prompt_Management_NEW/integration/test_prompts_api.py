"""
Integration tests for Prompt Management API endpoints.

Tests the complete API flow with real components, no mocking.
"""

import pytest
pytestmark = pytest.mark.integration
import json
from datetime import datetime
from fastapi.testclient import TestClient

# ========================================================================
# Prompt CRUD Endpoint Tests
# ========================================================================

class TestPromptCRUDEndpoints:
    """Test prompt CRUD operations through API."""

    @pytest.mark.integration
    def test_create_prompt_endpoint(self, test_client, auth_headers, sample_prompt):
        """Test creating a prompt via API."""
        payload = {
            'name': sample_prompt['name'],
            'author': sample_prompt.get('author'),
            'details': sample_prompt.get('content'),
            'keywords': sample_prompt.get('keywords', [])
        }
        response = test_client.post(
            "/api/v1/prompts",
            json=payload,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert 'id' in data and data['id'] > 0
        assert data['name'] == payload['name']

    @pytest.mark.integration
    def test_get_prompt_endpoint(self, test_client, auth_headers):
        """Test getting a prompt via API."""
        create_response = test_client.post(
            "/api/v1/prompts",
            json={
                'name': 'API Test Prompt',
                'details': 'Test content {{variable}}',
                'author': 'api_test',
                'keywords': ['test', 'api']
            },
            headers=auth_headers
        )
        prompt_id = create_response.json()['id']

        # Then get it
        response = test_client.get(
            f"/api/v1/prompts/{prompt_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['name'] == 'API Test Prompt'
        assert data.get('details') == 'Test content {{variable}}'
        assert 'test' in data.get('keywords', [])

    @pytest.mark.integration
    def test_list_prompts_endpoint(self, test_client, auth_headers):
        """Test listing prompts via API."""
        # Seed a couple prompts
        for i in range(2):
            test_client.post(
                "/api/v1/prompts",
                json={'name': f'List Seed {i}', 'author': 'seed', 'details': f'Details {i}'},
                headers=auth_headers
            )
        response = test_client.get(
            "/api/v1/prompts",
            params={'page': 1, 'per_page': 2},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert 'items' in data
        assert len(data['items']) <= 2

    @pytest.mark.integration
    def test_update_prompt_endpoint(self, test_client, auth_headers):
        """Test updating a prompt via API."""
        # Create prompt
        create_response = test_client.post(
            "/api/v1/prompts",
            json={'name': 'Update Test', 'details': 'Original content', 'author': 'test'},
            headers=auth_headers
        )
        prompt = create_response.json()
        prompt_id = prompt['id']

        # Update it: PromptCreate schema requires name; keep name, change details
        update_response = test_client.put(
            f"/api/v1/prompts/{prompt_id}",
            json={
                'name': prompt['name'],
                'author': prompt.get('author'),
                'details': 'Updated content {{new_var}}',
                'system_prompt': prompt.get('system_prompt'),
                'user_prompt': prompt.get('user_prompt'),
                'keywords': prompt.get('keywords', [])
            },
            headers=auth_headers
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data['id'] == prompt_id
        assert data.get('details') == 'Updated content {{new_var}}'

    @pytest.mark.integration
    def test_delete_prompt_endpoint(self, test_client, auth_headers):
        """Test deleting a prompt via API."""
        create_response = test_client.post(
            "/api/v1/prompts",
            json={'name': 'Delete Test', 'details': 'To be deleted', 'author': 'test'},
            headers=auth_headers
        )
        prompt_id = create_response.json()['id']

        delete_response = test_client.delete(
            f"/api/v1/prompts/{prompt_id}",
            headers=auth_headers
        )

        assert delete_response.status_code == 204

        # Verify it's deleted (soft delete)
        get_response = test_client.get(
            f"/api/v1/prompts/{prompt_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404

# ========================================================================
# Version Management Endpoint Tests
# ========================================================================

class TestVersionEndpoints:
    """Versioning endpoints are not available in current API."""

    @pytest.mark.integration
    def test_versions_endpoints_skipped(self):
        pytest.skip("Prompt version and restore endpoints not implemented in current API.")

# ========================================================================
# Search and Filter Endpoint Tests
# ========================================================================

class TestSearchEndpoints:
    """Test search and filter endpoints."""

    @pytest.mark.integration
    def test_search_prompts_endpoint(self, test_client, auth_headers):
        """Test searching prompts via API."""
        # Seed a prompt
        test_client.post(
            "/api/v1/prompts",
            json={'name': 'Assistant Prompt', 'author': 'test', 'details': 'You are a helpful assistant.'},
            headers=auth_headers
        )
        response = test_client.post(
            "/api/v1/prompts/search",
            params={'search_query': 'assistant', 'search_fields': ['details']},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert 'items' in data and data['total_matches'] >= 1

    @pytest.mark.integration
    def test_search_by_keywords(self, test_client, auth_headers):
        """Search using keywords field via FTS."""
        # Seed a prompt with keywords by creating then updating keywords through create payload
        test_client.post(
            "/api/v1/prompts",
            json={'name': 'Keyword Prompt', 'author': 'test', 'details': 'Has keywords', 'keywords': ['test', 'assistant']},
            headers=auth_headers
        )
        response = test_client.post(
            "/api/v1/prompts/search",
            params={'search_query': 'assistant', 'search_fields': ['keywords']},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['total_matches'] >= 1

    @pytest.mark.integration
    def test_search_by_author(self, test_client, auth_headers):
        """Search by author via search endpoint."""
        test_client.post(
            "/api/v1/prompts",
            json={'name': 'Author Prompt', 'author': 'author_user', 'details': 'foobar'},
            headers=auth_headers
        )
        response = test_client.post(
            "/api/v1/prompts/search",
            params={'search_query': 'author_user', 'search_fields': ['author']},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['total_matches'] >= 1

# ========================================================================
# Import/Export Endpoint Tests
# ========================================================================

class TestImportExportEndpoints:
    """Test export endpoints; import endpoints not present in current API."""

    @pytest.mark.integration
    def test_export_prompts_endpoint(self, test_client, auth_headers):
        """Test exporting prompts via API (CSV or Markdown)."""
        # Seed a prompt
        test_client.post(
            "/api/v1/prompts",
            json={'name': 'Export Prompt', 'author': 'test', 'details': 'Export me', 'keywords': ['exp']},
            headers=auth_headers
        )
        response = test_client.get(
            "/api/v1/prompts/export",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert 'message' in data
        # file_content_b64 may be None if no prompts, but here we seeded one
        assert 'file_content_b64' in data

    @pytest.mark.integration
    def test_import_endpoints_skipped(self):
        pytest.skip("Prompts import endpoints not implemented in current API.")

# ========================================================================
# Template Processing Endpoint Tests
# ========================================================================

class TestTemplateEndpoints:
    """Template-specific endpoints are not available in current API."""

    @pytest.mark.integration
    def test_template_endpoints_skipped(self):
        pytest.skip("Template render/variable endpoints not implemented in current API.")

# ========================================================================
# Bulk Operations Endpoint Tests
# ========================================================================

class TestBulkOperationsEndpoints:
    """Bulk endpoints not present in current API."""

    @pytest.mark.integration
    def test_bulk_endpoints_skipped(self):
        pytest.skip("Bulk delete/keyword endpoints not implemented in current API.")

# ========================================================================
# Collection Management Endpoint Tests
# ========================================================================

class TestCollectionEndpoints:
    """Test collection management endpoints."""

    @pytest.mark.integration
    def test_create_collection_endpoint(self, test_client, auth_headers):
        """Test creating a collection via API."""
        # Create prompts for collection
        prompt_ids = []
        for i in range(3):
            response = test_client.post(
                "/api/v1/prompts/create",
                json={
                    'name': f'Collection Item {i}',
                    'content': f'Content {i}',
                    'author': 'test'
                },
                headers=auth_headers
            )
            prompt_ids.append(response.json()['prompt_id'])

        # Create collection
        collection_response = test_client.post(
            "/api/v1/prompts/collections/create",
            json={
                'name': 'Test Collection',
                'description': 'A test collection',
                'prompt_ids': prompt_ids
            },
            headers=auth_headers
        )

        assert collection_response.status_code == 200
        data = collection_response.json()
        assert 'collection_id' in data
        assert data['collection_id'] > 0

    @pytest.mark.integration
    def test_get_collection_endpoint(self, test_client, auth_headers):
        """Test getting a collection via API."""
        # Create collection
        create_response = test_client.post(
            "/api/v1/prompts/collections/create",
            json={
                'name': 'Get Test',
                'description': 'Test',
                'prompt_ids': []
            },
            headers=auth_headers
        )
        collection_id = create_response.json()['collection_id']

        # Get collection
        get_response = test_client.get(
            f"/api/v1/prompts/collections/{collection_id}",
            headers=auth_headers
        )

        assert get_response.status_code == 200
        data = get_response.json()
        assert data['name'] == 'Get Test'
        assert data['description'] == 'Test'

# ========================================================================
# Error Handling Endpoint Tests
# ========================================================================

class TestErrorHandling:
    """Test API error handling."""

    @pytest.mark.integration
    def test_not_found_error(self, test_client, auth_headers):
        """Test 404 for non-existent prompt."""
        response = test_client.get(
            "/api/v1/prompts/99999",
            headers=auth_headers
        )

        assert response.status_code == 404
        data = response.json()
        assert 'detail' in data

    @pytest.mark.integration
    def test_validation_error(self, test_client, auth_headers):
        """Test 422 for invalid data."""
        response = test_client.post(
            "/api/v1/prompts",
            json={
                'name': '',  # Empty name
                'details': 'Content'
            },
            headers=auth_headers
        )

        assert response.status_code == 422
        data = response.json()
        assert 'detail' in data

    @pytest.mark.integration
    def test_unauthorized_error(self, test_client):
        """Test 401 for missing auth."""
        response = test_client.get("/api/v1/prompts")

        assert response.status_code in [401, 403]

    @pytest.mark.integration
    def test_duplicate_prompt_error(self, test_client, auth_headers):
        """Test handling duplicate prompt names."""
        # Create first prompt
        first_response = test_client.post(
            "/api/v1/prompts",
            json={
                'name': 'Unique Name',
                'details': 'Content 1',
                'author': 'test'
            },
            headers=auth_headers
        )
        # Creation may return 201 (Created) or 200 depending on API semantics
        assert first_response.status_code in [200, 201]

        # Try to create duplicate
        duplicate_response = test_client.post(
            "/api/v1/prompts",
            json={
                'name': 'Unique Name',
                'details': 'Content 2',
                'author': 'test'
            },
            headers=auth_headers
        )

        assert duplicate_response.status_code in [400, 409]

# ========================================================================
# Pagination and Filtering Tests
# ========================================================================

class TestPaginationAndFiltering:
    """Test pagination and filtering in endpoints."""

    @pytest.mark.integration
    def test_pagination_endpoint(self, test_client, auth_headers):
        """Test pagination in list endpoint."""
        # Seed a few prompts
        for i in range(4):
            test_client.post(
                "/api/v1/prompts",
                json={'name': f'Paginate {i}', 'author': 'test', 'details': f'Details {i}'},
                headers=auth_headers
            )
        # Get first page
        page1_response = test_client.get(
            "/api/v1/prompts",
            params={'page': 1, 'per_page': 2},
            headers=auth_headers
        )

        assert page1_response.status_code == 200
        page1_data = page1_response.json()
        assert len(page1_data['items']) <= 2

        # Get second page
        page2_response = test_client.get(
            "/api/v1/prompts",
            params={'page': 2, 'per_page': 2},
            headers=auth_headers
        )

        assert page2_response.status_code == 200
        page2_data = page2_response.json()

        # Ensure different results
        if page1_data['items'] and page2_data['items']:
            assert page1_data['items'][0]['id'] != page2_data['items'][0]['id']

    @pytest.mark.integration
    def test_sorting_endpoint(self, test_client, auth_headers):
        """Test sorting in list endpoint."""
        # Sorting is not implemented in current API list endpoint
        pytest.skip("Sorting parameters not implemented in current list endpoint.")
