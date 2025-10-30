# program_evaluator.py
# Feature-flagged, minimal program evaluator (non-executing MVP)

import os
from typing import Dict


class ProgramEvaluator:
    """Minimal evaluator for code-like outputs, gated by feature flag.

    MVP does NOT execute code. It evaluates text using simple heuristics and
    returns a reward in [−1..10]. Execution sandbox will be added in Phase 2.
    """

    @staticmethod
    def is_enabled() -> bool:
        return str(os.getenv("PROMPT_STUDIO_ENABLE_CODE_EVAL", "false")).strip().lower() in {"1", "true", "yes"}

    def evaluate_text_output(self, text: str) -> float:
        if not self.is_enabled():
            return 0.0
        if not text:
            return -1.0
        t = text.lower()
        reward = 0.0
        # Heuristic signals of code structure
        if "def " in text or "class " in text:
            reward += 3.0
        if "import " in text:
            reward += 1.5
        if "if __name__ == '__main__'" in text or "if __name__ == \"__main__\"" in text:
            reward += 1.0
        # Structured libraries (non-executing hints)
        for lib in ("numpy", "pandas", "cvxpy", "scipy"):
            if f"import {lib}" in t:
                reward += 0.5
        # Basic style: no obvious forbidden ops hints
        forbidden = ["os.system(", "subprocess.", "open(", "requests."]
        if any(x in t for x in forbidden):
            reward -= 2.0
        # Clamp
        return float(max(-1.0, min(10.0, reward)))

