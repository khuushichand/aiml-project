"""Service layer for synthetic evaluation draft generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from tldw_Server_API.app.api.v1.schemas.synthetic_eval_schemas import (
    SyntheticEvalProvenance,
    SyntheticEvalReviewState,
)
from tldw_Server_API.app.core.Evaluations.synthetic_eval_generation import (
    SyntheticEvalCorpusScope,
    SyntheticEvalCoverageSummary,
    SyntheticEvalGenerationPlan,
    SyntheticEvalStructuredTuple,
    convert_structured_tuples_to_draft_samples,
    generate_structured_tuples,
    ingest_examples,
    resolve_corpus_scope,
    summarize_coverage,
)
from tldw_Server_API.app.core.Evaluations.synthetic_eval_repository import (
    SyntheticEvalRepository,
)


@dataclass(slots=True)
class SyntheticEvalGenerationResult:
    """Structured result for a draft generation batch."""

    samples: list[dict[str, Any]] = field(default_factory=list)
    source_breakdown: dict[str, int] = field(default_factory=dict)
    coverage: dict[str, list[str]] = field(default_factory=dict)
    missing_coverage: dict[str, list[str]] = field(default_factory=dict)
    structured_tuples: list[SyntheticEvalStructuredTuple] = field(default_factory=list)
    corpus_scope: SyntheticEvalCorpusScope | None = None


class SyntheticEvalGenerationService:
    """Orchestrate corpus scope resolution, generation, and persistence."""

    def __init__(
        self,
        *,
        repository: SyntheticEvalRepository,
        tuple_generator: Callable[..., Sequence[SyntheticEvalStructuredTuple]] | None = None,
    ) -> None:
        self.repository = repository
        self.tuple_generator = tuple_generator or generate_structured_tuples

    def generate_draft_batch(
        self,
        *,
        recipe_kind: str,
        corpus_scope: SyntheticEvalCorpusScope | Sequence[str] | None = None,
        real_examples: Sequence[dict[str, Any]] | None = None,
        seed_examples: Sequence[dict[str, Any]] | None = None,
        target_sample_count: int = 0,
        tuple_generator: Callable[..., Sequence[SyntheticEvalStructuredTuple]] | None = None,
        created_by: str | None = None,
    ) -> SyntheticEvalGenerationResult:
        """Generate a mixed batch using real, seed, and synthetic examples."""

        resolved_scope = resolve_corpus_scope(corpus_scope)
        plan: SyntheticEvalGenerationPlan = ingest_examples(
            real_examples=real_examples,
            seed_examples=seed_examples,
            corpus_scope=resolved_scope,
        )
        synthetic_needed = max(
            0,
            int(target_sample_count) - self._count_examples(plan.examples),
        )
        generator = tuple_generator or self.tuple_generator
        structured_tuples = list(
            generator(
                coverage_gaps=plan.missing_coverage,
                corpus_scope=resolved_scope,
                corpus_examples=[example for example in plan.examples if example["example_category"] == "real"],
                seed_examples=[example for example in plan.examples if example["example_category"] == "seed_examples"],
                target_count=synthetic_needed,
            )
        )
        synthetic_samples = convert_structured_tuples_to_draft_samples(
            recipe_kind=recipe_kind,
            structured_tuples=structured_tuples,
        )

        persisted_samples: list[dict[str, Any]] = []
        for example in self._ordered_examples(plan.examples) + synthetic_samples:
            provenance = self._normalize_provenance(example.get("provenance"))
            sample_id = str(example.get("sample_id") or self._build_sample_id(recipe_kind, provenance, len(persisted_samples) + 1))
            draft_row = self.repository.create_draft_sample(
                sample_id=sample_id,
                recipe_kind=example.get("recipe_kind") or recipe_kind,
                sample_payload=dict(example.get("sample_payload") or {}),
                provenance=provenance,
                review_state=example.get("review_state") or SyntheticEvalReviewState.DRAFT.value,
                sample_metadata=self._build_sample_metadata(
                    example=example,
                    recipe_kind=recipe_kind,
                    created_by=created_by,
                ),
                source_kind=example.get("source_kind"),
                created_by=created_by,
            )
            persisted_samples.append(draft_row)

        coverage = summarize_coverage(persisted_samples)
        source_breakdown = self._build_source_breakdown(persisted_samples)
        return SyntheticEvalGenerationResult(
            samples=persisted_samples,
            source_breakdown=source_breakdown,
            coverage={
                "sources": coverage.sources,
                "query_intents": coverage.query_intents,
                "difficulties": coverage.difficulties,
                "failure_modes": coverage.failure_modes,
            },
            missing_coverage=plan.missing_coverage,
            structured_tuples=structured_tuples,
            corpus_scope=resolved_scope,
        )

    def _ordered_examples(self, examples: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        real_examples = [example for example in examples if self._normalize_provenance(example.get("provenance")) in {SyntheticEvalProvenance.REAL.value, SyntheticEvalProvenance.REAL_EDITED.value}]
        seed_examples = [example for example in examples if self._normalize_provenance(example.get("provenance")) == SyntheticEvalProvenance.SYNTHETIC_FROM_SEED_EXAMPLES.value]
        ordered = real_examples + seed_examples
        return ordered

    def _build_source_breakdown(self, samples: Sequence[dict[str, Any]]) -> dict[str, int]:
        breakdown = {
            "real": 0,
            "seed_examples": 0,
            "synthetic_from_corpus": 0,
        }
        for sample in samples:
            provenance = self._normalize_provenance(sample.get("provenance"))
            if provenance in {SyntheticEvalProvenance.REAL.value, SyntheticEvalProvenance.REAL_EDITED.value}:
                breakdown["real"] += 1
            elif provenance == SyntheticEvalProvenance.SYNTHETIC_FROM_SEED_EXAMPLES.value:
                breakdown["seed_examples"] += 1
            elif provenance == SyntheticEvalProvenance.SYNTHETIC_FROM_CORPUS.value:
                breakdown["synthetic_from_corpus"] += 1
        return breakdown

    def _build_sample_metadata(
        self,
        *,
        example: dict[str, Any],
        recipe_kind: str,
        created_by: str | None,
    ) -> dict[str, Any]:
        metadata = dict(example.get("sample_metadata") or {})
        metadata.setdefault("recipe_kind", recipe_kind)
        metadata.setdefault("source_kind", example.get("source_kind"))
        metadata.setdefault("query_intent", example.get("query_intent"))
        metadata.setdefault("difficulty", example.get("difficulty"))
        metadata.setdefault("created_by", created_by)
        metadata.setdefault("generation_stage", "generation_service")
        return metadata

    def _build_sample_id(self, recipe_kind: str, provenance: str, index: int) -> str:
        safe_provenance = provenance.replace(" ", "_")
        return f"{recipe_kind}-{safe_provenance}-{index}"

    def _count_examples(self, examples: Sequence[dict[str, Any]]) -> int:
        return len(self._ordered_examples(examples))

    def _normalize_provenance(self, provenance: Any) -> str:
        if isinstance(provenance, SyntheticEvalProvenance):
            return provenance.value
        if provenance == "seed_examples":
            return SyntheticEvalProvenance.SYNTHETIC_FROM_SEED_EXAMPLES.value
        return str(provenance or SyntheticEvalProvenance.SYNTHETIC_FROM_CORPUS.value)


__all__ = [
    "SyntheticEvalGenerationResult",
    "SyntheticEvalGenerationService",
]
