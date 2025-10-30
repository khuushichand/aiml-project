# prompt_quality.py
# Cheap heuristic prompt quality scoring for Prompt Studio

from typing import Optional
import re


class PromptQualityScorer:
    """Lightweight, deterministic heuristic scorer in [0..10].

    Heuristics considered:
    - Reasonable length of system prompt (not too short/long)
    - Presence of action verbs / clarity markers
    - Variable coverage: user prompt placeholders are referenced in system/user
    - Penalize ambiguous directives (e.g., "maybe", "perhaps")
    """

    def score_prompt(self, *, system_text: str, user_text: str) -> float:
        score = 5.0

        sys_len = len(system_text.strip())
        usr_len = len(user_text.strip())

        # Length heuristics
        if 60 <= sys_len <= 800:
            score += 2.0
        elif sys_len < 20:
            score -= 1.0
        elif sys_len > 1200:
            score -= 1.0

        if 20 <= usr_len <= 2000:
            score += 1.0
        elif usr_len < 5:
            score -= 1.0

        # Clarity/action words
        action_terms = [
            "provide", "return", "output", "ensure", "follow", "validate",
            "step-by-step", "json", "format", "constraints",
        ]
        hits = sum(1 for t in action_terms if t in system_text.lower())
        score += min(2.0, hits * 0.4)

        # Ambiguity penalties
        ambiguity = ["maybe", "perhaps", "guess", "try to", "sort of"]
        amb_hits = sum(1 for t in ambiguity if t in system_text.lower())
        score -= min(1.5, amb_hits * 0.5)

        # Variable coverage (simple placeholder check)
        vars_user = set(re.findall(r"\{(\w+)\}", user_text))
        vars_sys = set(re.findall(r"\{(\w+)\}", system_text))
        if vars_user:
            overlap = len(vars_user & vars_sys)
            score += min(1.5, overlap * 0.5)

        return float(max(0.0, min(10.0, score)))

