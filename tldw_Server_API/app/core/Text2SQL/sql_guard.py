"""SQL policy guardrails for Text2SQL execution."""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp


class SqlPolicyViolation(ValueError):
    """Raised when SQL violates Text2SQL read-only policy."""


@dataclass(frozen=True)
class GuardedSql:
    """Validated SQL plus rewrite metadata."""

    sql: str
    limit_injected: bool
    limit_clamped: bool


class SqlGuard:
    """Validate generated SQL and enforce deterministic row limits."""

    def __init__(self, default_limit: int, max_limit: int) -> None:
        if default_limit <= 0:
            raise ValueError("default_limit must be positive")
        if max_limit <= 0:
            raise ValueError("max_limit must be positive")
        if default_limit > max_limit:
            raise ValueError("default_limit must be <= max_limit")
        self.default_limit = default_limit
        self.max_limit = max_limit

    def validate_and_rewrite(self, sql: str) -> GuardedSql:
        """Validate SQL is single-statement read-only and enforce LIMIT policy."""
        text = str(sql).strip()
        if not text:
            raise SqlPolicyViolation("SQL must not be empty")

        try:
            statements = sqlglot.parse(text)
        except sqlglot.errors.ParseError as exc:
            raise SqlPolicyViolation("Invalid SQL syntax") from exc

        if len(statements) != 1:
            raise SqlPolicyViolation("Multiple statements are not allowed")

        tree = statements[0]
        if not isinstance(tree, exp.Query):
            raise SqlPolicyViolation("Only SELECT/WITH queries are allowed")

        limit = tree.args.get("limit")
        limit_injected = False
        limit_clamped = False

        if limit is None:
            tree = tree.limit(self.default_limit)
            limit_injected = True
        else:
            limit_value = _extract_literal_limit(limit)
            if limit_value is None:
                raise SqlPolicyViolation("LIMIT must be a numeric literal")
            if limit_value > self.max_limit:
                tree = tree.limit(self.max_limit)
                limit_clamped = True

        return GuardedSql(
            sql=tree.sql(),
            limit_injected=limit_injected,
            limit_clamped=limit_clamped,
        )


def _extract_literal_limit(limit_expr: exp.Expression) -> int | None:
    """Return integer LIMIT literal value, or None for non-literal expressions."""
    expression = limit_expr.expression
    if not isinstance(expression, exp.Literal) or not expression.is_int:
        return None
    try:
        value = int(expression.this)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value
