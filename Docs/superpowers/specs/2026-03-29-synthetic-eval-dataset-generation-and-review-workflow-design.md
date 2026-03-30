# Synthetic Eval Dataset Generation And Review Workflow Design

## Summary

This design introduces a shared, user-facing workflow for generating, reviewing, and promoting synthetic evaluation data across recipe-driven evals.

The first two direct consumers are:

- `RAG Retrieval Tuning`
- `RAG Answer Quality`

The workflow should not be hidden backend-only infrastructure. It should provide a real review surface from day one so users can inspect, edit, approve, or reject generated samples before those samples affect recipe recommendations.

The default system behavior should prefer real examples first, use synthetic generation to fill coverage gaps, and weight reviewed synthetic data lower than reviewed real data.

## Goals

- Provide a shared synthetic-data capability that multiple recipes can reuse.
- Keep synthetic generation corpus-specific and failure-oriented.
- Expose a real user-facing review workflow rather than silently trusting generated items.
- Preserve provenance and review state per sample.
- Support both retrieval-oriented and answer-quality-oriented dataset generation.
- Let recipes link into filtered views of the same review queue rather than each inventing separate review tools.
- Stratify synthetic generation across both `media_db` and `notes`.
- Support recommendation confidence that reflects sample provenance, not just sample count.

## Non-Goals

- Replacing real user traces when those are already abundant and representative.
- Treating synthetic drafts as trustworthy enough to skip review.
- Making synthetic generation a mandatory standalone workflow for every beginner.
- Building a generic annotation platform for every evaluation use case in V1.

## Current State

### Existing Recipe And Dataset Framework

The current framework already supports:

- recipe manifests
- recipe runs
- dataset snapshots and content hashes
- run-level review state

Relevant files include:

- `tldw_Server_API/app/api/v1/schemas/evaluation_recipe_schemas.py`
- `tldw_Server_API/app/core/Evaluations/recipe_runs_service.py`
- `apps/packages/ui/src/components/Option/Evaluations/tabs/RecipesTab.tsx`

What it does not yet have is a shared per-sample review queue with:

- provenance classes
- promotion states
- provenance-aware weighting
- recipe-specific filtered review views

### Existing Eval Guidance

The reviewed eval skills and the approved retrieval design both reinforce that:

- real traces should be preferred when available
- synthetic generation should fill gaps, not replace reality
- synthetic items must be reviewed before they count toward conclusions

### Existing UI Constraint

The current shared `RecipesTab` is already a large recipe launcher and results surface. A real day-one review workflow likely needs a shared eval sub-surface rather than more logic packed into the same launcher component.

## Requirements Confirmed With User

- Synthetic generation should be a shared capability, not just recipe-local prompt glue.
- It should not block the current retrieval-tuning implementation thread.
- It should have a real user-facing review workflow from day one.
- Default source precedence should be:
  1. real queries/examples
  2. user seed examples
  3. corpus-grounded synthetic generation
- Default synthetic output should include:
  - synthetic queries
  - expected relevant targets
  - a required review queue before they affect recommendations
- For answer-quality use cases, synthetic draft items should include both:
  - a draft reference answer
  - an expected behavior label: `answer`, `hedge`, `abstain`

## Approaches Considered

### Approach 1: Hidden Backend Capability

Keep generation and review internal and only expose final datasets through recipes.

Pros:

- lowest initial UI cost
- simpler backend-first rollout

Cons:

- users cannot inspect realism
- hard to trust
- does not satisfy the confirmed requirement for a user-facing review workflow

### Approach 2: Recipe-Local Review Flows

Each recipe owns its own synthetic generation and review surface.

Pros:

- recipe-specific workflows can be tailored tightly
- simpler to reason about within each recipe

Cons:

- duplicate logic across recipes
- inconsistent provenance semantics
- not reusable for future recipes

### Approach 3: Shared Generation + Shared Review Workflow

Build a shared synthetic generation and review capability, then let recipes link into filtered views of it.

Pros:

- consistent provenance and review semantics
- reusable across many recipes
- best fit for the recipe-first product model
- satisfies the user’s requirement for a real review workflow

Cons:

- more initial design work
- requires a clearer shared sample model

## Recommendation

Use Approach 3.

Build a shared synthetic generation and review workflow with recipe-specific entry points and filtered review views.

## Proposed Architecture

### Shared Capability Purpose

The capability should:

- generate draft eval samples from a selected corpus
- merge real and synthetic sources into one working dataset
- expose a review queue
- promote approved samples into active recipe datasets

The workflow should be reusable by multiple recipes while still preserving recipe-specific sample fields.

### Source Precedence

When building a draft dataset, the system should use this precedence:

1. real user queries/examples if available
2. user-provided seed tasks/examples
3. corpus-grounded synthetic generation for missing coverage

Synthetic generation should fill gaps in coverage rather than replace real data.

### Shared Dataset States

Each candidate sample should have a state such as:

- `draft`
- `approved`
- `rejected`
- `edited`

Only approved or explicitly promoted edited samples should count toward active eval datasets.

### Provenance Classes

Each sample should also record provenance such as:

- `real`
- `real_edited`
- `synthetic_from_corpus`
- `synthetic_from_seed_examples`
- `synthetic_human_edited`

Review state alone is not enough. Provenance is required for weighting and confidence interpretation.

### Weighting Policy

Approved samples should not all count equally by default.

Recommended weighting order:

- `real reviewed`
- `real edited`
- `synthetic human-edited`
- `approved synthetic`

This weighting policy should be explicit in recipe scoring and confidence models.

### Generation Pipeline

The shared generation pipeline should:

1. resolve corpus scope
2. inspect available real examples
3. identify coverage gaps and likely failure dimensions
4. generate structured tuples first
5. convert tuples into natural-language draft items
6. attach recipe-specific targets
7. place items into the review queue

Generation should be corpus-specific and failure-oriented, not generic “write many questions.”

### Stratification Requirements

Synthetic generation must be stratified across:

- source:
  - `media_db`
  - `notes`
- query intent:
  - lookup
  - synthesis
  - comparison
  - ambiguous / underspecified
- difficulty:
  - straightforward
  - distractor-heavy
  - multi-source
  - abstention-worthy

This prevents the generator from overfitting to whichever source dominates the corpus.

## Recipe-Specific Sample Shapes

### Retrieval Tuning Draft Items

For `RAG Retrieval Tuning`, draft items should support:

- `query`
- `relevant_media_ids`
- `relevant_note_ids`
- stable `relevant_spans`
- distractor metadata
- difficulty metadata
- provenance
- review state

### Answer Quality Draft Items

For `RAG Answer Quality`, draft items should support:

- `query`
- `retrieval_baseline_ref` or `context_snapshot_ref`
- draft `reference_answer`
- `expected_behavior`: `answer`, `hedge`, `abstain`
- provenance
- review state

This allows reviewers to approve or edit both:

- what a good answer should say
- what kind of answer behavior is appropriate

## Review Workflow

### Retrieval Review

Reviewers should confirm:

- query realism
- relevance targets
- span stability where needed
- distractor plausibility
- source coverage

### Answer-Quality Review

Reviewers should confirm:

- query realism
- the attached retrieval baseline or context snapshot
- the draft reference answer
- the expected behavior label:
  - direct answer
  - hedge
  - abstain

### Reviewer Actions

V1 reviewer actions should include:

- approve
- reject
- edit and approve
- reclassify difficulty or behavior label

## Shared UI Surface

This should be exposed as a shared evaluation review sub-surface, not only as extra controls inside `RecipesTab`.

Recipes should link into filtered views of the review workflow, for example:

- “Review synthetic retrieval drafts”
- “Review synthetic answer-quality drafts”

This keeps the workflow reusable and avoids turning the main recipe launcher into a monolith.

## Recipe Integration

### Retrieval Tuning Integration

`RAG Retrieval Tuning` should be able to:

- request synthetic coverage for missing query types
- link to filtered review items for retrieval
- consume only approved items in active eval runs

### Answer Quality Integration

`RAG Answer Quality` should be able to:

- request synthetic answer-quality drafts tied to a retrieval baseline or context snapshot
- link to filtered review items for answer behavior
- consume only approved items in active eval runs

## Testing Expectations

The future implementation should include:

- unit tests for provenance and state transitions
- generation tests for stratification logic
- review workflow tests for promotion and rejection behavior
- recipe integration tests that ensure only approved samples affect recommendations
- UI tests for filtered review queue behavior

## Rollout Notes

- This capability should be implemented after or alongside the `RAG Answer Quality` recipe, not before the current retrieval-tuning implementation finishes.
- The review workflow is part of the first version of this capability, not a deferred enhancement.
- The shared weighting and provenance model should be kept generic enough to serve future recipe types beyond RAG.
