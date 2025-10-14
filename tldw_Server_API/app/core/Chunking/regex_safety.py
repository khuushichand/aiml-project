"""
Shared regex safety helpers for boundary and classifier patterns.

Provides lightweight checks to reject obviously dangerous constructs
and normalize flags consistently across modules.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple, Set


# Pre-compiled heuristics to catch catastrophic backtracking risks
_DANGEROUS_CHECKS = [
    re.compile(r"\([^)]*[+*]\)[+*?]"),        # (a+)+, (a*)*, (a+)?
    re.compile(r"\([^)]*[+*]\){"),            # (a+){n,m}
    re.compile(r"\(\w+\+\)\+"),             # (word+)+
    re.compile(r"\(\w+\*\)\*"),             # (word*)*
    re.compile(r"\(\w+\?\)\?"),             # (word?)?
]


def check_pattern(pattern: str, *, max_len: int = 256) -> Optional[str]:
    """Return an error message if pattern appears dangerous/invalid, else None.

    - Enforces a maximum length.
    - Applies nested-quantifier heuristics to reduce ReDoS risk.
    - Ensures the pattern compiles under Python's re.
    """
    try:
        pat = str(pattern or "")
    except Exception:
        return "Pattern must be a string"
    if not pat:
        return None
    if len(pat) > max_len:
        return f"Pattern too long (max {max_len})"
    try:
        for chk in _DANGEROUS_CHECKS:
            if chk.search(pat):
                return "Pattern contains potentially dangerous regex constructs (nested quantifiers/alternations)"
    except Exception:
        # Non-fatal, continue to compile test
        pass
    try:
        re.compile(pat)
    except Exception as e:
        return f"Invalid regex: {e}"
    return None


def compile_flags(flags_str: str, *, allowed: Set[str] | None = None, max_len: int = 10) -> Tuple[int, Optional[str]]:
    """Map a flags string (e.g., "im") to re flags, enforcing an allowlist.

    Returns (flags_value, error_message). error_message is None if ok.
    """
    allowed = allowed or {"i", "m"}
    try:
        s = str(flags_str or "").lower()
    except Exception:
        return (0, "Flags must be a string")
    if len(s) > max_len:
        return (0, f"Flags too long (max {max_len})")
    flags = 0
    for f in s:
        if f not in allowed:
            return (0, "Only 'i' and 'm' flags are allowed")
        if f == 'i':
            flags |= re.IGNORECASE
        elif f == 'm':
            flags |= re.MULTILINE
    return (flags, None)


def warn_ambiguity(pattern: str) -> Optional[str]:
    """Return a warning string for patterns that are valid but ambiguous.

    Heuristics:
    - Pattern not anchored with ^ and contains a wide wildcard like ".*" or ".+".
    """
    try:
        pat = str(pattern or "")
    except Exception:
        return None
    if not pat:
        return None
    # crude detection of ".*" or ".+" outside of character classes
    if "^" not in pat and (".*" in pat or ".+" in pat):
        return "Unanchored pattern with wide wildcard may overmatch"
    return None

