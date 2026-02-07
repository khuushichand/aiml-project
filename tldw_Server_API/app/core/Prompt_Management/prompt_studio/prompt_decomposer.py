# prompt_decomposer.py
# Simple heuristic task/prompt decomposition utilities

import re


class PromptDecomposer:
    """Naive, heuristic decomposer used for early MCTS planning.

    Splits a combined task/instruction into segments:
    - context
    - instruction
    - constraints
    - examples
    """

    def decompose_text(self, text: str) -> list[str]:
        if not text:
            return []
        # Split by common delimiters/sections
        parts = re.split(r"\n\s*\n|Constraints:|Examples:|INSTRUCTIONS:|USER_PROMPT:", text)
        segments = [p.strip() for p in parts if p and p.strip()]
        # Cap to a small number of segments for MVP
        return segments[:6]
