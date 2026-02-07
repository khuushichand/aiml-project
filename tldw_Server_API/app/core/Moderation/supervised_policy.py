"""
supervised_policy.py

Layers guardian-configured supervised policies on top of the existing
ModerationService. Evaluates supervised block/notify rules for dependent
users and routes alerts to guardians.

Integration point: called by the chat pipeline after standard moderation
to apply guardian-imposed rules on supervised accounts.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Character_Chat.regex_safety import validate_regex_safety
from tldw_Server_API.app.core.DB_Management.Guardian_DB import (
    GuardianDB,
    SupervisedPolicy,
)
from tldw_Server_API.app.core.Moderation.moderation_service import (
    ModerationService,
    ModerationPolicy,
    PatternRule,
    get_moderation_service,
)

_SUPERVISED_NONCRITICAL_EXCEPTIONS = (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    AttributeError,
    re.error,
)


@dataclass
class SupervisedCheckResult:
    """Result from evaluating supervised policies for a dependent user."""
    action: str = "pass"  # pass | block | redact | warn | notify
    matched_policy_id: str | None = None
    matched_category: str = ""
    matched_pattern: str = ""
    severity: str = "info"
    message_to_dependent: str | None = None
    notify_guardian: bool = False
    notify_context: str = "topic_only"
    context_snippet: str | None = None
    redacted_text: str | None = None


class SupervisedPolicyEngine:
    """Evaluates supervised policies for a dependent user.

    Compiles patterns from GuardianDB policies and checks text
    in both input and output phases. Caches compiled patterns
    per-dependent for efficiency.
    """

    _DEFAULT_BLOCK_MESSAGE = (
        "This content has been restricted by your account administrator. "
        "If you have questions, please speak with your parent or guardian."
    )

    def __init__(self, guardian_db: GuardianDB) -> None:
        self._db = guardian_db
        self._lock = threading.RLock()
        # Cache: dependent_user_id -> list of (policy, compiled_regex)
        self._compiled_cache: dict[str, list[tuple[SupervisedPolicy, re.Pattern]]] = {}
        self._cache_timestamps: dict[str, float] = {}
        self._cache_ttl_seconds = 60.0  # refresh every minute

    def invalidate_cache(self, dependent_user_id: str | None = None) -> None:
        with self._lock:
            if dependent_user_id:
                self._compiled_cache.pop(str(dependent_user_id), None)
                self._cache_timestamps.pop(str(dependent_user_id), None)
            else:
                self._compiled_cache.clear()
                self._cache_timestamps.clear()

    def _get_compiled_policies(
        self,
        dependent_user_id: str,
    ) -> list[tuple[SupervisedPolicy, re.Pattern]]:
        uid = str(dependent_user_id)
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            cached_at = self._cache_timestamps.get(uid, 0.0)
            if uid in self._compiled_cache and (now - cached_at) < self._cache_ttl_seconds:
                return self._compiled_cache[uid]

        # Fetch and compile outside the lock
        policies = self._db.list_active_policies_for_dependent(uid)
        compiled: list[tuple[SupervisedPolicy, re.Pattern]] = []
        for pol in policies:
            if not pol.pattern:
                continue
            try:
                if pol.pattern_type == "regex":
                    is_safe, reason = validate_regex_safety(pol.pattern)
                    if not is_safe:
                        logger.warning(f"Unsafe supervised policy regex '{pol.pattern}': {reason}")
                        continue
                    regex = re.compile(pol.pattern, re.IGNORECASE)
                else:
                    regex = re.compile(re.escape(pol.pattern), re.IGNORECASE)
                compiled.append((pol, regex))
            except re.error as e:
                logger.warning(f"Invalid supervised policy pattern '{pol.pattern}': {e}")
                continue

        with self._lock:
            self._compiled_cache[uid] = compiled
            self._cache_timestamps[uid] = now
        return compiled

    def check_text(
        self,
        text: str,
        dependent_user_id: str,
        phase: str = "input",
    ) -> SupervisedCheckResult:
        """Check text against supervised policies for a dependent user.

        Returns the highest-priority result (block > redact > warn > notify > pass).
        """
        if not text or not text.strip():
            return SupervisedCheckResult()

        compiled_policies = self._get_compiled_policies(dependent_user_id)
        if not compiled_policies:
            return SupervisedCheckResult()

        # Priority: block=4, redact=3, warn=2, notify=1
        action_priority = {"block": 4, "redact": 3, "warn": 2, "notify": 1}
        best_result = SupervisedCheckResult()
        best_priority = 0

        for pol, regex in compiled_policies:
            # Phase filtering
            if pol.phase != "both" and pol.phase != phase:
                continue
            # Check for match
            match = regex.search(text)
            if not match:
                continue

            priority = action_priority.get(pol.action, 0)
            if priority <= best_priority:
                continue

            best_priority = priority
            snippet = self._build_snippet(text, match, pol)
            best_result = SupervisedCheckResult(
                action=pol.action,
                matched_policy_id=pol.id,
                matched_category=pol.category,
                matched_pattern=regex.pattern,
                severity=pol.severity,
                message_to_dependent=pol.message_to_dependent or self._DEFAULT_BLOCK_MESSAGE,
                notify_guardian=pol.notify_guardian,
                notify_context=pol.notify_context,
                context_snippet=snippet,
            )

            # If we hit a block, can't do worse — early exit
            if pol.action == "block":
                break

        # If action is redact, compute redacted text
        if best_result.action == "redact":
            redacted = text
            for pol, regex in compiled_policies:
                if pol.phase != "both" and pol.phase != phase:
                    continue
                if pol.action != "redact":
                    continue
                try:
                    redacted = regex.sub("[REDACTED]", redacted)
                except re.error:
                    continue
            best_result.redacted_text = redacted

        return best_result

    @staticmethod
    def _build_snippet(
        text: str,
        match: re.Match,
        policy: SupervisedPolicy,
    ) -> str | None:
        if policy.notify_context == "full_message":
            return text[:500] if len(text) > 500 else text
        if policy.notify_context == "snippet":
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            snippet = text[start:end].strip()
            return snippet[:200] if len(snippet) > 200 else snippet
        # topic_only — return just the category, no content
        return None

    def build_moderation_policy_overlay(
        self,
        dependent_user_id: str,
        base_policy: ModerationPolicy,
    ) -> ModerationPolicy:
        """Create a ModerationPolicy that merges supervised rules with the base policy.

        This allows the standard moderation pipeline to enforce supervised
        rules without special-casing the check path.
        """
        compiled_policies = self._get_compiled_policies(dependent_user_id)
        if not compiled_policies:
            return base_policy

        # Merge supervised patterns into the base policy's block_patterns
        extra_rules: list[PatternRule] = []
        for pol, regex in compiled_policies:
            rule_action = pol.action if pol.action in ("block", "redact", "warn") else "warn"
            extra_rules.append(
                PatternRule(
                    regex=regex,
                    action=rule_action,
                    replacement="[REDACTED]" if pol.action == "redact" else None,
                    categories={pol.category} if pol.category else {"supervised"},
                )
            )

        merged_patterns = list(base_policy.block_patterns or []) + extra_rules
        return ModerationPolicy(
            enabled=True,  # force enabled for supervised accounts
            input_enabled=base_policy.input_enabled,
            output_enabled=base_policy.output_enabled,
            input_action=base_policy.input_action,
            output_action=base_policy.output_action,
            redact_replacement=base_policy.redact_replacement,
            per_user_overrides=base_policy.per_user_overrides,
            block_patterns=merged_patterns,
            categories_enabled=base_policy.categories_enabled,
        )


class GuardianModerationProxy:
    """Wraps ModerationService to overlay guardian policies on get_effective_policy()."""

    def __init__(self, base: Any, engine: SupervisedPolicyEngine, dependent_user_id: str) -> None:
        self._base = base
        self._engine = engine
        self._dep_uid = dependent_user_id

    def get_effective_policy(self, user_id: str | None = None) -> ModerationPolicy:
        base_policy = self._base.get_effective_policy(user_id)
        try:
            return self._engine.build_moderation_policy_overlay(self._dep_uid, base_policy)
        except _SUPERVISED_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"Guardian policy overlay skipped in proxy: {e}")
            return base_policy

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


# ── Factory accessor ──────────────────────────────────────────


def get_supervised_policy_engine(guardian_db: GuardianDB) -> SupervisedPolicyEngine:
    """Create a SupervisedPolicyEngine bound to the given DB.

    A new instance is returned each call so that multi-user deployments
    always query the correct per-user database.
    """
    return SupervisedPolicyEngine(guardian_db)
