"""
category_taxonomy.py

Built-in category taxonomy for content governance rules.
Provides keyword lists and regex patterns for common content categories
so that guardians and self-monitoring users can create rules from
predefined categories without manually entering patterns.

Usage:
    from category_taxonomy import get_category_patterns, get_all_categories
    patterns = get_category_patterns("violence")  # list[re.Pattern]
    all_cats = get_all_categories()  # dict of category metadata
"""
from __future__ import annotations

import re
from typing import Any

CATEGORY_TAXONOMY: dict[str, dict[str, Any]] = {
    "violence": {
        "description": "Content related to violence, weapons, or physical harm",
        "severity_default": "warning",
        "keywords": [
            "kill", "murder", "weapon", "gun", "knife", "stab", "shoot",
            "assault", "attack", "bomb", "explosive", "fight", "violence",
        ],
        "regex_patterns": [
            r"\b(?:kill|murder|assault|stab|shoot)\w*\b",
            r"\b(?:weapon|gun|knife|bomb|explosive)s?\b",
        ],
    },
    "self_harm": {
        "description": "Content related to self-harm, suicide, or self-injury",
        "severity_default": "critical",
        "keywords": [
            "suicide", "self-harm", "self harm", "cutting", "overdose",
            "end my life", "kill myself", "want to die", "hurt myself",
        ],
        "regex_patterns": [
            r"\b(?:suicid\w*|self[- ]?harm\w*)\b",
            r"\b(?:kill|hurt|end)\s+(?:my\s*self|my\s+life)\b",
            r"\b(?:want|wish)\s+to\s+die\b",
            r"\b(?:overdos\w*|cutting)\b",
        ],
    },
    "profanity": {
        "description": "Profanity, vulgar language, and strong expletives",
        "severity_default": "info",
        "keywords": [
            "damn", "hell", "crap",
        ],
        "regex_patterns": [
            r"\b(?:damn|hell|crap)\b",
        ],
    },
    "pii": {
        "description": "Personally identifiable information (SSN, credit cards, phone numbers)",
        "severity_default": "warning",
        "keywords": [
            "social security", "credit card", "ssn",
        ],
        "regex_patterns": [
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",  # Credit card
            r"\b(?:\+?1[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b",  # US phone
        ],
    },
    "drugs_alcohol": {
        "description": "Content related to illegal drugs, drug use, or alcohol",
        "severity_default": "warning",
        "keywords": [
            "marijuana", "cocaine", "heroin", "meth", "fentanyl",
            "weed", "cannabis", "drug", "alcohol", "beer", "wine",
            "vodka", "whiskey", "drunk", "high", "stoned",
        ],
        "regex_patterns": [
            r"\b(?:marijuana|cocaine|heroin|meth|fentanyl|cannabis|weed)\b",
            r"\b(?:drug|alcohol|beer|wine|vodka|whiskey)s?\b",
            r"\b(?:drunk|stoned|high|intoxicated)\b",
        ],
    },
    "sexual_content": {
        "description": "Sexually explicit or suggestive content",
        "severity_default": "warning",
        "keywords": [
            "sex", "porn", "nude", "naked", "erotic",
            "explicit", "xxx", "nsfw",
        ],
        "regex_patterns": [
            r"\b(?:porn\w*|nude\w*|naked|erotic\w*|xxx|nsfw)\b",
        ],
    },
    "hate_speech": {
        "description": "Hate speech, discrimination, or slurs targeting protected groups",
        "severity_default": "critical",
        "keywords": [
            "racist", "racism", "sexist", "sexism", "homophobic",
            "bigot", "discrimination", "hate speech",
        ],
        "regex_patterns": [
            r"\b(?:racist|racism|sexist|sexism|homophob\w*|bigot\w*)\b",
            r"\bhate\s+speech\b",
        ],
    },
    "gambling": {
        "description": "Content related to gambling, betting, or wagering",
        "severity_default": "info",
        "keywords": [
            "gambling", "bet", "wager", "casino", "poker",
            "slot machine", "roulette", "blackjack", "lottery",
        ],
        "regex_patterns": [
            r"\b(?:gambl\w*|bet(?:ting)?|wager\w*|casino|poker)\b",
            r"\b(?:slot\s+machine|roulette|blackjack|lottery)\b",
        ],
    },
}


def get_category_patterns(category: str) -> list[re.Pattern]:
    """Compile and return regex patterns for a given category.

    Returns an empty list if the category is not found.
    """
    cat = CATEGORY_TAXONOMY.get(category)
    if not cat:
        return []
    compiled: list[re.Pattern] = []
    for pat_str in cat.get("regex_patterns", []):
        try:
            compiled.append(re.compile(pat_str, re.IGNORECASE))
        except re.error:
            continue
    return compiled


def get_category_keywords(category: str) -> list[str]:
    """Return keyword list for a given category."""
    cat = CATEGORY_TAXONOMY.get(category)
    if not cat:
        return []
    return list(cat.get("keywords", []))


def get_all_categories() -> dict[str, dict[str, Any]]:
    """Return metadata for all categories (name, description, severity_default).

    Does not include patterns/keywords — use get_category_patterns() for those.
    """
    return {
        name: {
            "name": name,
            "description": info["description"],
            "severity_default": info["severity_default"],
            "keyword_count": len(info.get("keywords", [])),
            "pattern_count": len(info.get("regex_patterns", [])),
        }
        for name, info in CATEGORY_TAXONOMY.items()
    }
