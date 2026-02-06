"""
Tests for FVA (Falsification-Verification Alignment) API endpoint.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Schema imports
from tldw_Server_API.app.api.v1.schemas.claims_schemas import (
    FVAClaimInput,
    FVAConfigRequest,
    FVAVerifyRequest,
    FVAVerifyResponse,
    FVASettingsResponse,
)


# -------------------------------------------------------------------------
# Schema Tests
# -------------------------------------------------------------------------

class TestFVASchemas:
    """Test FVA Pydantic schemas."""

    def test_fva_claim_input_minimal(self):
        """Test FVAClaimInput with minimal required fields."""
        claim = FVAClaimInput(text="The sky is blue.")
        assert claim.text == "The sky is blue."
        assert claim.claim_type is None
        assert claim.span_start is None
        assert claim.span_end is None

    def test_fva_claim_input_full(self):
        """Test FVAClaimInput with all fields."""
        claim = FVAClaimInput(
            text="Paris is the capital of France.",
            claim_type="existence",
            span_start=10,
            span_end=50,
        )
        assert claim.text == "Paris is the capital of France."
        assert claim.claim_type == "existence"
        assert claim.span_start == 10
        assert claim.span_end == 50

    def test_fva_config_request_defaults(self):
        """Test FVAConfigRequest with default values."""
        config = FVAConfigRequest()
        assert config.enabled is True
        assert config.confidence_threshold == 0.7
        assert config.contested_threshold == 0.4
        assert config.max_concurrent_falsifications == 5
        assert config.timeout_seconds == 30.0
        assert config.force_claim_types is None
        assert config.max_budget_usd is None

    def test_fva_config_request_custom(self):
        """Test FVAConfigRequest with custom values."""
        config = FVAConfigRequest(
            enabled=False,
            confidence_threshold=0.8,
            contested_threshold=0.3,
            max_concurrent_falsifications=10,
            timeout_seconds=60.0,
            force_claim_types=["statistic", "causal"],
            max_budget_usd=0.50,
        )
        assert config.enabled is False
        assert config.confidence_threshold == 0.8
        assert config.contested_threshold == 0.3
        assert config.max_concurrent_falsifications == 10
        assert config.timeout_seconds == 60.0
        assert config.force_claim_types == ["statistic", "causal"]
        assert config.max_budget_usd == 0.50

    def test_fva_verify_request_minimal(self):
        """Test FVAVerifyRequest with minimal fields."""
        request = FVAVerifyRequest(
            claims=[FVAClaimInput(text="Test claim")],
            query="Test query",
        )
        assert len(request.claims) == 1
        assert request.query == "Test query"
        assert request.sources is None
        assert request.top_k == 10
        assert request.fva_config is None

    def test_fva_verify_request_full(self):
        """Test FVAVerifyRequest with all fields."""
        request = FVAVerifyRequest(
            claims=[
                FVAClaimInput(text="Claim 1"),
                FVAClaimInput(text="Claim 2", claim_type="statistic"),
            ],
            query="Original query for retrieval",
            sources=["media_db", "notes_db"],
            top_k=20,
            fva_config=FVAConfigRequest(enabled=True, confidence_threshold=0.6),
        )
        assert len(request.claims) == 2
        assert request.query == "Original query for retrieval"
        assert request.sources == ["media_db", "notes_db"]
        assert request.top_k == 20
        assert request.fva_config is not None
        assert request.fva_config.confidence_threshold == 0.6

    def test_fva_verify_request_claim_limit(self):
        """Test FVAVerifyRequest enforces max claim limit."""
        # Should accept up to 50 claims
        claims_50 = [FVAClaimInput(text=f"Claim {i}") for i in range(50)]
        request = FVAVerifyRequest(claims=claims_50, query="test")
        assert len(request.claims) == 50

        # Should reject >50 claims
        claims_51 = [FVAClaimInput(text=f"Claim {i}") for i in range(51)]
        with pytest.raises(ValueError):
            FVAVerifyRequest(claims=claims_51, query="test")

    def test_fva_settings_response(self):
        """Test FVASettingsResponse model."""
        settings = FVASettingsResponse(
            enabled=True,
            confidence_threshold=0.7,
            contested_threshold=0.4,
            max_concurrent_falsifications=5,
            timeout_seconds=30.0,
            force_claim_types=["statistic"],
            anti_context_cache_size=100,
        )
        assert settings.enabled is True
        assert settings.confidence_threshold == 0.7
        assert settings.anti_context_cache_size == 100


# -------------------------------------------------------------------------
# Service Function Tests
# -------------------------------------------------------------------------

class TestFVAServiceFunctions:
    """Test FVA service layer functions."""

    def test_get_fva_settings(self):
        """Test get_fva_settings returns default config."""
        from tldw_Server_API.app.core.Claims_Extraction import claims_service

        settings = claims_service.get_fva_settings()

        assert "enabled" in settings
        assert "confidence_threshold" in settings
        assert "contested_threshold" in settings
        assert "max_concurrent_falsifications" in settings
        assert "timeout_seconds" in settings
        assert "force_claim_types" in settings
        assert "anti_context_cache_size" in settings

    def test_fva_batch_result_dataclass(self):
        """Test FVABatchResult dataclass structure."""
        from tldw_Server_API.app.core.Claims_Extraction.fva_pipeline import FVABatchResult

        result = FVABatchResult(
            results=[],
            total_claims=5,
            falsification_triggered_count=2,
            status_changes={"verified->contested": 1},
            total_time_ms=100.0,
            budget_exhausted=True,
        )

        assert result.total_claims == 5
        assert result.falsification_triggered_count == 2
        assert result.status_changes == {"verified->contested": 1}
        assert result.total_time_ms == 100.0
        assert result.budget_exhausted is True

    def test_fva_config_dataclass(self):
        """Test FVAConfig dataclass structure."""
        from tldw_Server_API.app.core.Claims_Extraction.fva_pipeline import FVAConfig

        config = FVAConfig(
            enabled=True,
            confidence_threshold=0.8,
            contested_threshold=0.35,
            max_concurrent_falsifications=10,
            falsification_timeout_seconds=45.0,
            force_falsification_claim_types=["statistic", "causal"],
        )

        assert config.enabled is True
        assert config.confidence_threshold == 0.8
        assert config.contested_threshold == 0.35
        assert config.max_concurrent_falsifications == 10
        assert config.falsification_timeout_seconds == 45.0
        assert config.force_falsification_claim_types == ["statistic", "causal"]

    def test_fva_result_dataclass(self):
        """Test FVAResult dataclass structure."""
        from tldw_Server_API.app.core.Claims_Extraction.fva_pipeline import FVAResult
        from tldw_Server_API.app.core.Claims_Extraction.claims_engine import (
            Claim,
            ClaimVerification,
        )

        # Create minimal claim and verification for testing
        claim = Claim(id="test", text="Test claim")
        verification = ClaimVerification(claim=claim)

        result = FVAResult(
            original_verification=verification,
            falsification_triggered=True,
            falsification_decision=None,
            anti_context_found=3,
            adjudication=None,
            final_verification=verification,
            processing_time_ms=50.0,
        )

        assert result.falsification_triggered is True
        assert result.anti_context_found == 3
        assert result.processing_time_ms == 50.0


# -------------------------------------------------------------------------
# Integration-style Tests (with mocked HTTP client)
# -------------------------------------------------------------------------

class TestFVAEndpointIntegration:
    """Integration tests for FVA endpoint using test client."""

    @pytest.fixture
    def mock_auth(self):
        """Mock authentication dependencies."""
        mock_principal = MagicMock()
        mock_principal.user_id = "test_user"
        mock_user = MagicMock()
        mock_user.username = "test_user"
        mock_user.id = 1
        mock_db = MagicMock()
        return mock_principal, mock_user, mock_db

    def test_fva_verify_request_validation(self, mock_auth):
        """Test request validation for FVA verify endpoint."""
        # Test empty claims list rejection
        with pytest.raises(ValueError):
            FVAVerifyRequest(claims=[], query="test")

        # Test empty query rejection
        with pytest.raises(ValueError):
            FVAVerifyRequest(
                claims=[FVAClaimInput(text="Test")],
                query="",
            )

        # Test top_k bounds
        with pytest.raises(ValueError):
            FVAVerifyRequest(
                claims=[FVAClaimInput(text="Test")],
                query="test",
                top_k=0,  # Below minimum
            )

        with pytest.raises(ValueError):
            FVAVerifyRequest(
                claims=[FVAClaimInput(text="Test")],
                query="test",
                top_k=101,  # Above maximum
            )

    def test_fva_config_validation(self):
        """Test FVA config parameter validation."""
        # Test confidence_threshold bounds
        with pytest.raises(ValueError):
            FVAConfigRequest(confidence_threshold=-0.1)

        with pytest.raises(ValueError):
            FVAConfigRequest(confidence_threshold=1.5)

        # Test contested_threshold bounds
        with pytest.raises(ValueError):
            FVAConfigRequest(contested_threshold=-0.1)

        with pytest.raises(ValueError):
            FVAConfigRequest(contested_threshold=1.5)

        # Test max_concurrent_falsifications bounds
        with pytest.raises(ValueError):
            FVAConfigRequest(max_concurrent_falsifications=0)

        with pytest.raises(ValueError):
            FVAConfigRequest(max_concurrent_falsifications=25)

        # Test timeout_seconds bounds
        with pytest.raises(ValueError):
            FVAConfigRequest(timeout_seconds=0.5)

        with pytest.raises(ValueError):
            FVAConfigRequest(timeout_seconds=150.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
