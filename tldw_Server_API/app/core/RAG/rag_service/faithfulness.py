"""Faithfulness evaluator for the RAG pipeline.

Provides LLM-based evaluation of faithfulness, measuring whether generated
answers are grounded in retrieved context using a claim-level approach:

1. Extract atomic factual claims from the LLM response
2. Verify each claim against the retrieved context
3. Score = supported_claims / total_claims

This complements the existing guardrails.py (which does hard-citation and
numeric fidelity checks) by providing a scored faithfulness metric with
per-claim breakdown, useful for debugging hallucinations.

Ported from RAGnarok-AI's faithfulness evaluator, adapted for tldw_server2.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from .rag_protocols import LLMProtocol

# Re-export for backwards compatibility
LLMCallable = LLMProtocol


@dataclass(frozen=True)
class ClaimVerification:
    """Verification result for a single extracted claim.

    Attributes:
        claim: The extracted atomic claim from the response.
        supported: Whether the claim is supported by the provided context.
        reasoning: Explanation for the verification decision.
    """

    claim: str
    supported: bool
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "supported": self.supported,
            "reasoning": self.reasoning,
        }


@dataclass(frozen=True)
class FaithfulnessResult:
    """Detailed result of faithfulness evaluation.

    Attributes:
        score: Faithfulness score between 0.0 and 1.0.
        claims: List of extracted claims with verification results.
        reasoning: Overall reasoning for the score.
    """

    score: float
    claims: list[ClaimVerification]
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "faithfulness_score": self.score,
            "total_claims": len(self.claims),
            "supported_claims": sum(1 for c in self.claims if c.supported),
            "unsupported_claims": sum(1 for c in self.claims if not c.supported),
            "reasoning": self.reasoning,
            "claim_verifications": [c.to_dict() for c in self.claims],
        }


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CLAIM_EXTRACTION_PROMPT = """Extract all factual claims from the following response.
A claim is a single, atomic statement that can be verified as true or false.

Response: {response}

Return a JSON array of claims. Example format:
["Paris is the capital of France", "The Eiffel Tower is 330 meters tall"]

Only return the JSON array, nothing else."""

CLAIM_VERIFICATION_PROMPT = """Verify if the following claim is supported by the given context.

Claim: {claim}

Context: {context}

Answer with a JSON object containing:
- "supported": true if the claim is clearly supported by the context, false otherwise
- "reasoning": brief explanation for your decision

Only return the JSON object, nothing else."""


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class FaithfulnessEvaluator:
    """LLM-based faithfulness evaluator.

    Measures if generated answers are grounded in retrieved context
    using a claim extraction + verification approach.

    The evaluation process:
    1. Extract atomic claims from the generated response
    2. Verify each claim against the provided context
    3. Calculate score as: supported_claims / total_claims

    This is designed to complement (not replace) the existing guardrails
    in ``guardrails.py``.

    Args:
        llm: Any object implementing the ``LLMCallable`` protocol (async generate).
        max_claims: Maximum number of claims to extract and verify.
    """

    def __init__(self, llm: LLMCallable, max_claims: int = 25) -> None:
        self.llm = llm
        self.max_claims = max_claims

    async def evaluate(
        self,
        response: str,
        context: str,
        query: Optional[str] = None,
    ) -> float:
        """Evaluate faithfulness, returning a single score.

        Args:
            response: The generated response to evaluate.
            context: The retrieved context used for generation.
            query: Optional original query (unused, for protocol compat).

        Returns:
            Faithfulness score between 0.0 and 1.0.
        """
        result = await self.evaluate_detailed(response, context)
        return result.score

    async def evaluate_detailed(
        self,
        response: str,
        context: str,
    ) -> FaithfulnessResult:
        """Evaluate faithfulness with detailed claim-level results.

        Args:
            response: The generated response to evaluate.
            context: The retrieved context used for generation.

        Returns:
            FaithfulnessResult with score, claims, and reasoning.
        """
        # Handle empty response
        if not response.strip():
            return FaithfulnessResult(
                score=1.0,
                claims=[],
                reasoning="Empty response has no claims to verify.",
            )

        # Handle empty context
        if not context.strip():
            return FaithfulnessResult(
                score=0.0,
                claims=[],
                reasoning="No context provided to verify claims against.",
            )

        # Extract claims from response
        try:
            claims = await self._extract_claims(response)
        except Exception as e:
            logger.warning(f"Faithfulness: claim extraction failed: {e}")
            return FaithfulnessResult(
                score=0.0,
                claims=[],
                reasoning=f"Claim extraction failed: {e}",
            )

        if not claims:
            return FaithfulnessResult(
                score=1.0,
                claims=[],
                reasoning="No verifiable claims found in the response.",
            )

        # Truncate to max_claims
        claims = claims[: self.max_claims]

        # Verify each claim against context
        verifications: list[ClaimVerification] = []
        for claim in claims:
            try:
                verification = await self._verify_claim(claim, context)
                verifications.append(verification)
            except Exception as e:
                logger.warning(f"Faithfulness: claim verification failed for '{claim[:50]}...': {e}")
                verifications.append(
                    ClaimVerification(
                        claim=claim,
                        supported=False,
                        reasoning=f"Verification failed: {e}",
                    )
                )

        # Calculate score
        supported_count = sum(1 for v in verifications if v.supported)
        score = supported_count / len(verifications) if verifications else 1.0

        # Generate overall reasoning
        if score == 1.0:
            reasoning = "All claims in the response are supported by the context."
        elif score == 0.0:
            reasoning = "None of the claims in the response are supported by the context."
        else:
            reasoning = (
                f"{supported_count} out of {len(verifications)} claims "
                f"are supported by the context."
            )

        return FaithfulnessResult(
            score=score,
            claims=verifications,
            reasoning=reasoning,
        )

    async def _extract_claims(self, response: str) -> list[str]:
        """Extract factual claims from a response."""
        prompt = CLAIM_EXTRACTION_PROMPT.format(response=response)
        llm_response = await self.llm.generate(prompt)
        claims = _parse_json_array(llm_response)
        return [str(claim) for claim in claims if claim]

    async def _verify_claim(self, claim: str, context: str) -> ClaimVerification:
        """Verify a single claim against context."""
        prompt = CLAIM_VERIFICATION_PROMPT.format(claim=claim, context=context)
        llm_response = await self.llm.generate(prompt)
        result = _parse_json_object(llm_response)

        supported = bool(result.get("supported", False))
        reasoning = str(result.get("reasoning", "No reasoning provided."))

        return ClaimVerification(
            claim=claim,
            supported=supported,
            reasoning=reasoning,
        )


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

_JSON_DECODER = json.JSONDecoder()


def _parse_json_array(text: str) -> list[str]:
    """Parse a JSON array from LLM response, with fallback extraction.

    Uses ``json.JSONDecoder.raw_decode`` so that trailing text after the
    JSON structure (common in LLM output) is tolerated.
    """
    text = text.strip()

    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try to extract the first valid JSON array by scanning for '['
    for match in re.finditer(r"\[", text):
        try:
            result, _ = _JSON_DECODER.raw_decode(text, match.start())
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, ValueError):
            continue

    return []


def _parse_json_object(text: str) -> dict[str, object]:
    """Parse a JSON object from LLM response, with fallback extraction.

    Uses ``json.JSONDecoder.raw_decode`` so that trailing text after the
    JSON structure (common in LLM output) is tolerated.
    """
    text = text.strip()

    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Try to extract the first valid JSON object by scanning for '{'
    for match in re.finditer(r"\{", text):
        try:
            result, _ = _JSON_DECODER.raw_decode(text, match.start())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            continue

    return {}
