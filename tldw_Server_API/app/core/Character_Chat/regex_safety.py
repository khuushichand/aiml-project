# regex_safety.py
"""
Shared regex safety utilities for the Character_Chat module.

This module provides functions to validate and compile regex patterns safely,
protecting against ReDoS (Regular Expression Denial of Service) attacks.
"""

import re
import time as _time_module
from typing import Tuple

import regex  # Third-party regex engine with timeout support
from loguru import logger

from tldw_Server_API.app.core.Character_Chat.constants import (
    MAX_REGEX_LENGTH,
    MAX_REGEX_COMPILE_TIME_MS,
)

# Maximum allowed time (in milliseconds) for the validation test match
MAX_REGEX_VALIDATE_TIME_MS = 50


# =============================================================================
# ReDoS Protection Constants
# =============================================================================

# Dangerous regex patterns that could cause catastrophic backtracking
DANGEROUS_REGEX_PATTERNS = [
    # Nested quantifiers with groups
    r"\(\.\*\)\+",  # (.*)+
    r"\(\.\+\)\+",  # (.+)+
    r"\(\.\*\)\*",  # (.*)*
    r"\(\.\+\)\*",  # (.+)*
    r"\(\[.*?\]\+\)\+",  # ([...]+)+
    r"\(\[.*?\]\*\)\+",  # ([...]*)+
    r"\(\?:.*\)\+\??\(",  # nested quantifiers with groups
    # Alternation with overlapping patterns
    r"\(\w\|\w\)\+",  # (a|a)+ style
    r"\(\.\|\.\)\+",  # (.|.)+ style
    # Nested groups with quantifiers
    r"\(\([^)]+\)\+\)\+",  # ((...)+ )+
    r"\(\([^)]+\)\*\)\+",  # ((...)* )+
    # Backreference with quantifier (can cause exponential time)
    r"\\1\+",  # \1+
    r"\\1\*",  # \1*
    # Additional dangerous patterns from world_book_manager
    r'(\+\+|\*\*|\{\d+,\d*\}\+)',  # Nested quantifiers like a++, a**, a{1,}+
    r'\([^)]*\+[^)]*\)\+',  # (a+)+ style patterns
    r'\([^)]*\*[^)]*\)\+',  # (a*)+ style patterns
    r'\([^)]*\{[^}]*\}[^)]*\)\+',  # (a{1,2})+ style patterns
]

# Maximum nesting depth for groups
MAX_GROUP_NESTING_DEPTH = 5

# Maximum number of quantifiers in a pattern
MAX_QUANTIFIER_COUNT = 10

# Test input size for bounded matching test
SAFE_TEST_INPUT_SIZE = 100


# =============================================================================
# Helper Functions
# =============================================================================

def count_quantifiers(pattern: str) -> int:
    """Count the number of quantifiers in a pattern.

    Args:
        pattern: The regex pattern to analyze

    Returns:
        Number of quantifiers found
    """
    # Match *, +, ?, {n}, {n,}, {n,m} but not escaped ones
    quantifier_pattern = r'(?<!\\)[*+?]|(?<!\\)\{[0-9,]+\}'
    return len(re.findall(quantifier_pattern, pattern))


def get_group_nesting_depth(pattern: str) -> int:
    """Calculate the maximum nesting depth of groups in a pattern.

    Args:
        pattern: The regex pattern to analyze

    Returns:
        Maximum nesting depth of groups
    """
    max_depth = 0
    current_depth = 0
    escaped = False

    for char in pattern:
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if char == '(':
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif char == ')':
            current_depth = max(0, current_depth - 1)

    return max_depth


# =============================================================================
# Main Validation Functions
# =============================================================================

def is_dangerous_regex(pattern: str) -> Tuple[bool, str]:
    """Check if a regex pattern contains potentially dangerous constructs.

    Args:
        pattern: The regex pattern to validate

    Returns:
        Tuple of (is_dangerous, reason). If is_dangerous is True, reason explains why.
    """
    # Check for known dangerous patterns
    for dangerous in DANGEROUS_REGEX_PATTERNS:
        try:
            if re.search(dangerous, pattern):
                return True, "Pattern contains known dangerous construct"
        except re.error as e:
            # Log the error for debugging but continue checking other patterns
            logger.debug(f"Regex error while checking dangerous pattern '{dangerous}': {e}")

    # Check group nesting depth
    nesting_depth = get_group_nesting_depth(pattern)
    if nesting_depth > MAX_GROUP_NESTING_DEPTH:
        return True, f"Group nesting depth ({nesting_depth}) exceeds limit ({MAX_GROUP_NESTING_DEPTH})"

    # Check quantifier count
    quantifier_count = count_quantifiers(pattern)
    if quantifier_count > MAX_QUANTIFIER_COUNT:
        return True, f"Too many quantifiers ({quantifier_count}) exceeds limit ({MAX_QUANTIFIER_COUNT})"

    return False, ""


def validate_regex_safety(pattern: str) -> Tuple[bool, str]:
    """Validate a regex pattern for potential ReDoS vulnerabilities.

    This is the main validation function that checks all safety criteria.

    Args:
        pattern: The regex pattern to validate

    Returns:
        Tuple of (is_safe, reason). If is_safe is False, reason explains why.
    """
    # Check length
    if len(pattern) > MAX_REGEX_LENGTH:
        return False, f"Pattern too long ({len(pattern)} > {MAX_REGEX_LENGTH} chars)"

    # Check for dangerous patterns
    is_dangerous, reason = is_dangerous_regex(pattern)
    if is_dangerous:
        return False, reason

    # Try to compile with a basic test to catch obvious issues
    try:
        # Use the third-party regex module so we can enforce a timeout on the test search.
        compiled = regex.compile(pattern)
        # Quick sanity test with a bounded string
        test_input = "a" * SAFE_TEST_INPUT_SIZE
        start_time = _time_module.perf_counter()
        try:
            compiled.search(
                test_input,
                timeout=MAX_REGEX_VALIDATE_TIME_MS / 1000.0,
            )
        except regex.TimeoutError:
            elapsed_ms = (_time_module.perf_counter() - start_time) * 1000
            return False, f"Pattern too slow (timeout): test match exceeded {elapsed_ms:.2f}ms"
        elapsed_ms = (_time_module.perf_counter() - start_time) * 1000

        if elapsed_ms > MAX_REGEX_COMPILE_TIME_MS:
            return False, f"Pattern too slow: test match took {elapsed_ms:.2f}ms"
    except regex.error as e:
        return False, f"Invalid regex: {e}"
        # Catch-all to avoid unexpected exceptions from breaking validation.
        logger.debug(f"Unexpected error during regex validation: {e}")
    except Exception as e:
        return False, f"Regex validation error: {e}"

    return True, ""


def safe_compile_regex(
    pattern: str,
    flags: int = 0,
    timeout_ms: int = MAX_REGEX_COMPILE_TIME_MS
) -> re.Pattern:
    """Compile a regex pattern with safety checks to prevent ReDoS.

    Args:
        pattern: The regex pattern to compile
        flags: Regex flags to apply
        timeout_ms: Maximum time allowed for compilation (best-effort)

    Returns:
        Compiled regex pattern

    Raises:
        re.error: If pattern is invalid or potentially dangerous
    """
    if len(pattern) > MAX_REGEX_LENGTH:
        raise re.error(f"Regex pattern exceeds maximum length of {MAX_REGEX_LENGTH} characters")

    is_dangerous, reason = is_dangerous_regex(pattern)
    if is_dangerous:
        raise re.error(f"Regex pattern rejected: {reason}")

    # Attempt compilation with timing (best-effort since Python doesn't support compile timeouts)
    start_time = _time_module.perf_counter()
    try:
        compiled = re.compile(pattern, flags)
    except re.error:
        raise

    elapsed_ms = (_time_module.perf_counter() - start_time) * 1000
    if elapsed_ms > timeout_ms:
        logger.warning(f"Regex compilation took {elapsed_ms:.2f}ms (threshold: {timeout_ms}ms)")

    # Perform a bounded test match to catch patterns that compile fast but match slow
    test_input = "a" * SAFE_TEST_INPUT_SIZE
    match_start = _time_module.perf_counter()
    try:
        compiled.search(test_input)
    except Exception as e:
        # Log but don't fail - we primarily care about detecting slow patterns
        logger.debug(f"Exception during regex test match for pattern '{pattern[:50]}...': {e}")
    match_elapsed_ms = (_time_module.perf_counter() - match_start) * 1000

    if match_elapsed_ms > timeout_ms:
        raise re.error(
            f"Regex pattern too slow: test match took {match_elapsed_ms:.2f}ms "
            f"(threshold: {timeout_ms}ms)"
        )

    return compiled
