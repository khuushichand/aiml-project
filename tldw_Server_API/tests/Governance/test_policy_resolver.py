from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.core.Governance import CandidateAction, resolve_effective_action

pytestmark = pytest.mark.unit


def test_action_precedence_deny_beats_warn():
    result = resolve_effective_action(
        [
            CandidateAction(action="warn", priority=10, scope_level=2),
            CandidateAction(action="deny", priority=1, scope_level=2),
        ]
    )
    assert result.action == "deny"


def test_scope_precedence_workspace_beats_org():
    result = resolve_effective_action(
        [
            CandidateAction(action="allow", priority=100, scope_level=1),  # org
            CandidateAction(action="require_approval", priority=1, scope_level=4),  # workspace
        ]
    )
    assert result.action == "require_approval"


def test_priority_breaker_same_action_and_scope():
    result = resolve_effective_action(
        [
            CandidateAction(action="warn", priority=1, scope_level=2, source_id="low-priority"),
            CandidateAction(action="warn", priority=9, scope_level=2, source_id="high-priority"),
        ]
    )
    assert result.winning_candidate.source_id == "high-priority"


def test_updated_at_breaker_when_action_scope_priority_equal():
    now = datetime.now(timezone.utc)
    older = now - timedelta(minutes=5)
    newer = now - timedelta(minutes=1)
    result = resolve_effective_action(
        [
            CandidateAction(action="warn", priority=5, scope_level=2, updated_at=older, source_id="older"),
            CandidateAction(action="warn", priority=5, scope_level=2, updated_at=newer, source_id="newer"),
        ]
    )
    assert result.winning_candidate.source_id == "newer"


def test_empty_candidates_raises_value_error():
    with pytest.raises(ValueError, match="at least one candidate"):
        resolve_effective_action([])

