"""
Tests for the falsification trigger logic module.
"""

import pytest
from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.Claims_Extraction.falsification import (
    should_trigger_falsification,
    estimate_falsification_rate,
    FalsificationDecision,
    FalsificationReason,
    HIGH_RISK_CLAIM_TYPES,
    CONTROVERSIAL_INDICATORS,
)

# Import ClaimType for creating test claims
try:
    from tldw_Server_API.app.core.RAG.rag_service.types import ClaimType
except Exception:
    from enum import Enum

    class ClaimType(Enum):
        STATISTIC = "statistic"
        COMPARATIVE = "comparative"
        CAUSAL = "causal"
        RANKING = "ranking"
        GENERAL = "general"
        QUOTE = "quote"


@dataclass
class MockClaim:
    """Mock claim for testing."""
    id: str
    text: str
    claim_type: ClaimType = ClaimType.GENERAL
    extracted_values: dict = None

    def __post_init__(self):
        if self.extracted_values is None:
            self.extracted_values = {}


class TestShouldTriggerFalsification:
    """Tests for should_trigger_falsification function."""

    @pytest.mark.unit
    def test_force_falsification_always_triggers(self):
        """Force falsification should always trigger regardless of other factors."""
        claim = MockClaim(id="1", text="Simple claim", claim_type=ClaimType.GENERAL)
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.99,
            evidence_count=10,
            force_falsification=True,
        )
        assert decision.should_falsify is True
        assert decision.reason == FalsificationReason.USER_REQUESTED
        assert decision.priority == 10

    @pytest.mark.unit
    def test_low_confidence_triggers_falsification(self):
        """Low verification confidence should trigger falsification."""
        claim = MockClaim(id="1", text="Some claim")
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.5,
            evidence_count=3,
        )
        assert decision.should_falsify is True
        assert decision.reason == FalsificationReason.LOW_CONFIDENCE
        # Priority should be higher for lower confidence
        assert decision.priority == 5  # int(10 - 0.5 * 10)

    @pytest.mark.unit
    def test_very_low_confidence_high_priority(self):
        """Very low confidence should have high priority."""
        claim = MockClaim(id="1", text="Some claim")
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.1,
            evidence_count=1,
        )
        assert decision.should_falsify is True
        assert decision.reason == FalsificationReason.LOW_CONFIDENCE
        assert decision.priority == 9  # int(10 - 0.1 * 10)

    @pytest.mark.unit
    def test_high_confidence_no_trigger(self):
        """High confidence with sufficient evidence should not trigger."""
        claim = MockClaim(id="1", text="A verified fact")
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.95,
            evidence_count=5,
        )
        assert decision.should_falsify is False
        assert decision.reason is None
        assert decision.priority == 0

    @pytest.mark.unit
    @pytest.mark.parametrize("claim_type", list(HIGH_RISK_CLAIM_TYPES))
    def test_high_risk_claim_types_trigger(self, claim_type):
        """High-risk claim types should trigger falsification."""
        claim = MockClaim(id="1", text="Some claim", claim_type=claim_type)
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.8,  # Above threshold
            evidence_count=5,
        )
        assert decision.should_falsify is True
        assert decision.reason == FalsificationReason.HIGH_RISK_TYPE
        assert decision.priority == 6

    @pytest.mark.unit
    def test_general_claim_type_no_trigger(self):
        """GENERAL claim type with good confidence should not trigger."""
        claim = MockClaim(id="1", text="Some general claim", claim_type=ClaimType.GENERAL)
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.9,
            evidence_count=3,
        )
        assert decision.should_falsify is False

    @pytest.mark.unit
    def test_quote_claim_type_no_trigger(self):
        """QUOTE claim type (not in HIGH_RISK) with good confidence should not trigger."""
        claim = MockClaim(id="1", text="He said 'hello'", claim_type=ClaimType.QUOTE)
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.9,
            evidence_count=3,
        )
        assert decision.should_falsify is False

    @pytest.mark.unit
    @pytest.mark.parametrize("indicator", CONTROVERSIAL_INDICATORS[:5])
    def test_controversial_indicators_trigger(self, indicator):
        """Claims with controversial language should trigger."""
        claim = MockClaim(id="1", text=f"This is {indicator} about climate")
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.8,
            evidence_count=5,
        )
        assert decision.should_falsify is True
        assert decision.reason == FalsificationReason.CONTROVERSIAL_TOPIC
        assert decision.priority == 5

    @pytest.mark.unit
    def test_controversial_case_insensitive(self):
        """Controversial indicators should be case-insensitive."""
        claim = MockClaim(id="1", text="Scientists ALWAYS agree on this")
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.8,
            evidence_count=5,
        )
        assert decision.should_falsify is True
        assert decision.reason == FalsificationReason.CONTROVERSIAL_TOPIC

    @pytest.mark.unit
    def test_weak_evidence_triggers(self):
        """Few evidence sources with moderate confidence should trigger."""
        claim = MockClaim(id="1", text="Some claim")
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.8,  # Below weak_evidence_threshold (0.85)
            evidence_count=1,  # Less than 2
        )
        assert decision.should_falsify is True
        assert decision.reason == FalsificationReason.WEAK_EVIDENCE
        assert decision.priority == 4

    @pytest.mark.unit
    def test_weak_evidence_sufficient_count_no_trigger(self):
        """Sufficient evidence count should not trigger weak evidence."""
        claim = MockClaim(id="1", text="Some claim")
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.8,
            evidence_count=3,  # >= 2
        )
        assert decision.should_falsify is False

    @pytest.mark.unit
    def test_custom_confidence_threshold(self):
        """Custom confidence threshold should be respected."""
        claim = MockClaim(id="1", text="Some claim")

        # Default threshold (0.7) - should trigger
        decision1 = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.65,
            evidence_count=5,
        )
        assert decision1.should_falsify is True

        # Higher threshold - still triggers
        decision2 = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.75,
            evidence_count=5,
            confidence_threshold=0.8,
        )
        assert decision2.should_falsify is True

        # Lower threshold - no trigger
        decision3 = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.65,
            evidence_count=5,
            confidence_threshold=0.5,
        )
        assert decision3.should_falsify is False

    @pytest.mark.unit
    def test_priority_bounds(self):
        """Priority should be bounded between 1 and 10."""
        claim = MockClaim(id="1", text="Some claim")

        # Very low confidence
        decision1 = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.0,
            evidence_count=0,
        )
        assert 1 <= decision1.priority <= 10

        # Edge case confidence
        decision2 = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.69,
            evidence_count=0,
        )
        assert 1 <= decision2.priority <= 10

    @pytest.mark.unit
    def test_reason_priority_ordering(self):
        """Different reasons should have expected priority ordering."""
        # User requested has highest priority
        claim = MockClaim(id="1", text="Some claim", claim_type=ClaimType.STATISTIC)
        decision = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.5,
            evidence_count=1,
            force_falsification=True,
        )
        assert decision.priority == 10

        # Low confidence can have high priority
        decision2 = should_trigger_falsification(
            claim=claim,
            verification_confidence=0.1,
            evidence_count=5,
        )
        assert decision2.priority >= 6  # Higher than HIGH_RISK_TYPE


class TestEstimateFalsificationRate:
    """Tests for estimate_falsification_rate function."""

    @pytest.mark.unit
    def test_empty_claims_returns_zero(self):
        """Empty claims list should return 0.0."""
        rate = estimate_falsification_rate([], [], [])
        assert rate == 0.0

    @pytest.mark.unit
    def test_all_trigger_returns_one(self):
        """All claims triggering should return 1.0."""
        claims = [
            MockClaim(id="1", text="Low conf claim"),
            MockClaim(id="2", text="Another low conf"),
        ]
        confidences = [0.3, 0.4]
        evidence_counts = [1, 1]

        rate = estimate_falsification_rate(claims, confidences, evidence_counts)
        assert rate == 1.0

    @pytest.mark.unit
    def test_none_trigger_returns_zero(self):
        """No claims triggering should return 0.0."""
        claims = [
            MockClaim(id="1", text="High conf claim"),
            MockClaim(id="2", text="Another high conf"),
        ]
        confidences = [0.95, 0.98]
        evidence_counts = [5, 5]

        rate = estimate_falsification_rate(claims, confidences, evidence_counts)
        assert rate == 0.0

    @pytest.mark.unit
    def test_partial_trigger(self):
        """Partial triggering should return correct rate."""
        claims = [
            MockClaim(id="1", text="Low conf"),
            MockClaim(id="2", text="High conf"),
            MockClaim(id="3", text="Medium with statistic", claim_type=ClaimType.STATISTIC),
            MockClaim(id="4", text="High conf 2"),
        ]
        confidences = [0.3, 0.95, 0.8, 0.95]
        evidence_counts = [1, 5, 5, 5]

        rate = estimate_falsification_rate(claims, confidences, evidence_counts)
        # Claims 1 (low conf) and 3 (STATISTIC type) should trigger
        assert rate == 0.5  # 2 out of 4


class TestFalsificationDecision:
    """Tests for FalsificationDecision dataclass."""

    @pytest.mark.unit
    def test_decision_fields(self):
        """FalsificationDecision should have expected fields."""
        decision = FalsificationDecision(
            should_falsify=True,
            reason=FalsificationReason.LOW_CONFIDENCE,
            priority=5,
        )
        assert decision.should_falsify is True
        assert decision.reason == FalsificationReason.LOW_CONFIDENCE
        assert decision.priority == 5

    @pytest.mark.unit
    def test_decision_with_none_reason(self):
        """FalsificationDecision with None reason should work."""
        decision = FalsificationDecision(
            should_falsify=False,
            reason=None,
            priority=0,
        )
        assert decision.reason is None


class TestFalsificationReason:
    """Tests for FalsificationReason enum."""

    @pytest.mark.unit
    def test_all_reasons_are_strings(self):
        """All reason values should be strings."""
        for reason in FalsificationReason:
            assert isinstance(reason.value, str)

    @pytest.mark.unit
    def test_reason_values(self):
        """Reason values should match expected strings."""
        assert FalsificationReason.LOW_CONFIDENCE.value == "low_confidence"
        assert FalsificationReason.HIGH_RISK_TYPE.value == "high_risk_type"
        assert FalsificationReason.CONTROVERSIAL_TOPIC.value == "controversial_topic"
        assert FalsificationReason.WEAK_EVIDENCE.value == "weak_evidence"
        assert FalsificationReason.USER_REQUESTED.value == "user_requested"
