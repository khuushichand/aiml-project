# Evaluations Recipe Framework Design

## Summary

This design introduces a beginner-friendly evaluations framework built around reusable recipe definitions rather than one-off benchmark pages. The first two built-in recipes are:

- `Embeddings Model Selection`
- `Summarization Quality`

The core product is a guided WebUI wizard backed by stable API parity. Users should be able to run reliable evaluations in two modes:

- `labeled`: they provide references, labels, or preference pairs
- `unlabeled`: the system uses weak supervision, judge-based scoring, and human spot checks

The design is intentionally recipe-oriented so the same workflow can later support additional evaluations such as rerankers, OCR quality, transcription quality, classification, and RAG answer quality.

This is not a proposal to replace the existing evaluations backend wholesale. It is a proposal to add a recipe layer on top of the current evaluations backbone, while avoiding direct dependence on the currently unstable parts of the shared evaluations UI.

## Goals

- Give non-expert users a reliable, low-friction way to evaluate models on their own data.
- Make the primary user flow a guided wizard in the shared WebUI, with API parity underneath.
- Support both labeled and unlabeled evaluation paths as first-class options.
- Let users define what "best" means per run instead of forcing one global metric.
- Produce recommendations with evidence, tradeoffs, and confidence rather than raw metric dumps.
- Reuse the same workflow design for future evaluation recipes.
- Preserve reproducibility through dataset versioning, run snapshots, and stored artifacts.
- Use the existing evaluations storage and execution foundation where it is sound.

## Non-Goals

- Building a generic public benchmark hub centered on MTEB, STS, or leaderboard-style cross-corpus rankings.
- Requiring users to understand eval terminology before they can get value.
- Treating intrinsic embedding benchmarks as the main decision signal in V1.
- Building a general-purpose pipeline builder in V1.
- Rewriting the entire existing evaluations module before shipping the recipe framework.
- Making the current generic tabs the primary V1 experience without a stabilization pass.

## Current State

### Existing Evaluations Backbone

The backend already exposes a broad unified evaluations surface with CRUD, datasets, benchmarks, webhooks, history, embeddings A/B testing, and RAG evaluation functionality. Relevant entry points include:

- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_crud.py`
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_datasets.py`
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_webhooks.py`
- `tldw_Server_API/app/core/Evaluations/`

The shared frontend and extension already use a common evaluations surface under:

- `apps/packages/ui/src/components/Option/Evaluations/`

Both the Next.js web page and the extension route share that implementation.

### Review Findings That Affect This Design

The current shared evaluations UI has several concrete issues that make it a weak foundation for the new recipe-first workflow:

- The webhooks tab does not match backend response and delete contracts.
- The history tab uses the wrong filter concept and renders mismatched field names.
- Dataset sample pagination is presented in the UI, but the backend dataset detail route does not support the paging parameters the UI relies on.
- A shared frontend service calls a non-existent global runs endpoint.
- The broad backend evaluations test sweep is not fully green today; a focused rerun confirmed a reproducible failure in the embeddings A/B retrieval tests due to Chroma initialization on the hybrid path.

These issues do not invalidate the existing evaluations backend as a foundation, but they do mean the new user-facing recipe workflow should not be built as a thin wrapper around the current generic tabs.

## Requirements Confirmed With User

- The workflow should support both labeled and unlabeled evaluation modes.
- The product should support both API/CLI and WebUI usage, but the WebUI wizard is the primary experience.
- For embeddings, users should choose what "best" means per run rather than being forced into one default task.
- For summarization, the default recipe should use a weighted rubric across:
  - factual grounding
  - coverage
  - concise usefulness
- The workflow design should be reusable for future evaluation recipes, not just embeddings and summarization.
- The default system should support both local-first operation and optional stronger external judge models.

## Approaches Considered

### Approach 1: Generic Benchmark Hub

Center the product on benchmark suites and public-style metric packs.

Pros:

- Easy to explain in abstract terms
- Reuses familiar eval vocabulary
- Useful for benchmarking demos

Cons:

- Weak signal for a user's own dataset
- Encourages cargo-cult metric selection
- Makes it harder to answer the user's actual question: "what should I use on my data?"

### Approach 2: Dataset-Native Recipe System

Use reusable recipe definitions that run against the user's own data, task, constraints, and preferred decision criteria.

Pros:

- Best fit for real user decisions
- Works for both labeled and unlabeled data
- Extensible to many future recipe types
- Beginner-friendly if wrapped in a wizard

Cons:

- Requires stronger product structure up front
- Needs clearer dataset contracts and scoring policies

### Approach 3: Power-User Pipeline Builder

Expose a highly composable graph of metrics, judges, chunkers, prompts, and aggregation steps.

Pros:

- Maximal flexibility
- Strong long-term expert potential

Cons:

- Too complex for V1
- Poor fit for users unfamiliar with evals
- High risk of noise and invalid comparisons

## Recommendation

Use Approach 2.

Build a recipe registry with a shared wizard-driven workflow. Embeddings and summarization are the first built-in recipes, but the product abstraction is the recipe system itself.

## Proposed Architecture

### Core Product Shape

The user-facing product should be a guided wizard with stable recipe APIs underneath.

The canonical beginner flow is:

1. Choose recipe.
2. Choose goal in plain language.
3. Choose data mode: `labeled` or `unlabeled`.
4. Select or upload a dataset.
5. Choose candidate models and runtime constraints.
6. Review defaults and optional advanced settings.
7. Run the evaluation.
8. Receive recommendation cards plus detailed evidence.

The API should expose the same capabilities so CLI and external integrations can create runs, inspect status, and fetch reports without going through the UI.

### Recipe Registry

The system should revolve around a registry of recipe definitions. Each recipe contributes:

- `manifest`
- `wizard schema`
- `dataset validator`
- `execution adapter`
- `scoring adapter`
- `recommendation policy`
- `report builder`

This keeps the workflow reusable while allowing each recipe to define its own metrics and data rules.

### Beginner-First UX Contract

Every recipe should support:

- `Simple mode` by default
- `Advanced` controls for weights, judge settings, sample sizes, and thresholds
- plain-language descriptions of when to use the recipe
- starter templates and examples
- recommendation-first results pages

The first screen should answer "What do you want to learn?" rather than "What metric do you want to compute?"

## Scoring Framework

All recipes should share a common scoring contract:

- `raw metrics`
- `normalized metrics` on a common `0-100` scale
- `weights`
- `hard gates`
- `confidence`
- `recommendation set`

### Recommendation Set

Every recipe report should produce these mandatory recommendation slots:

- `best overall`
- `best cheap`
- `best local`

Recipes may also expose optional recipe-specific recommendation slots such as:

- `best quality`
- `best fast`
- `best grounded`

This keeps the report shell stable while still allowing recipe-specific emphasis.

If no candidate qualifies for a mandatory slot, or if the data needed to compute that slot is unavailable, the report must emit `null` for that slot plus a machine-readable `reason_code` and user-facing explanation. The system must not fabricate a winner for `best overall`, `best cheap`, or `best local`.

### Confidence Model

Recommendations should include confidence derived from:

- sample count
- variance or bootstrap spread
- margin between top candidates
- judge agreement where applicable

The system should explicitly warn when the winner is statistically close or the sample is too small.

### Hard Gates

Recipes should be able to disqualify candidates that cross unacceptable thresholds even if their composite scores are high. For example:

- summarization candidates that fail grounding thresholds
- candidates that exceed latency or cost caps
- candidates that violate formatting or completeness requirements

## Dataset Model

Every recipe should use a common canonical dataset envelope plus a recipe-specific payload schema.

The shared layer should not try to flatten all recipe data into one generic row shape. Instead:

- the common envelope defines identity, provenance, and reproducibility
- the recipe payload defines the task-specific structure

### Core Envelope

Recommended common fields:

- `dataset_id`
- `dataset_version`
- `recipe_id`
- `schema_version`
- `metadata`
- `split`
- `items` or `payload`

Each item should support shared metadata such as:

- `item_id`
- `input`
- `source` or `context`
- `reference` or `labels` when available
- `metadata`

### Recipe-Specific Payload

Each recipe then validates an explicit task schema on top of the core envelope.

Examples:

- embeddings retrieval labeled:
  - `queries[]`
  - `query_id`
  - `expected_doc_ids` or `expected_chunk_ids`
- embeddings clustering labeled:
  - `item_id`
  - `cluster_id` or pairwise labels
- summarization labeled:
  - `document_id`
  - `source_text`
  - `reference_summaries[]`
  - optional `preference_pairs[]`
- summarization unlabeled:
  - `document_id`
  - `source_text`
  - optional `importance_annotations`
  - optional `review_samples`

This avoids turning the shared model into an untyped metadata bucket.

Each run should snapshot:

- recipe id and version
- dataset id and version
- dataset content hash or immutable snapshot reference
- candidate model list
- prompts and judge configuration
- scoring weights and thresholds
- retrieval and chunking settings where relevant
- local or hosted execution policy

This is required for reproducibility and auditability.

Dataset versioning should therefore use a two-layer model:

- the shared dataset record owns the logical `dataset_id` and `dataset_version`
- each recipe run owns an immutable snapshot reference or content hash captured at run creation time

This keeps reusable datasets possible while still making individual runs reproducible even if the source dataset is later edited.

## Built-In V1 Recipes

### Recipe 1: Embeddings Model Selection

This recipe is a task selector, not a single metric pack.

The recipe framework should eventually support four embeddings goals, but the first implementation milestone should ship `retrieval / RAG` as the only fully supported path. `Clustering / dedup` and `classification` are future or experimental work and should not be part of the first delivery milestone.

The wizard should ask:

1. What are embeddings for in this run?
2. Is the dataset labeled?
3. What corpus or examples are being evaluated?
4. Which models should compete?
5. What constraints matter?

Future framework goal set:

- `retrieval / RAG`
- `weighted scorecard` layered on retrieval metrics

Future or experimental goals, explicitly out of scope for the first milestone:

- `clustering / dedup`
- `classification`

#### Retrieval Mode

Labeled mode:

- user provides `query -> relevant chunk/doc ids`
- score with `Recall@k`, `MRR`, `nDCG`
- also record cost, latency, and index/storage metrics

Unlabeled mode:

- user provides corpus and optionally example queries
- system can synthesize candidate queries
- weak labels come from relevance judging plus human spot checks

In unlabeled mode, every run should automatically reserve a human spot-check sample. The run may auto-complete when confidence is above threshold, but low-confidence runs or close-call winners should remain marked as requiring review until that spot-check sample is completed.

Important design rule:

For retrieval, the product must support both:

- `embedding-only comparison`
- `retrieval-stack comparison`

Otherwise users may choose a "best embedding model" under unrealistic chunking or retrieval settings.

#### Clustering / Dedup Mode

Labeled mode:

- accept cluster ids or positive/negative pairs

Unlabeled mode:

- sample likely pairs and use weak judging or light human review

Primary outputs should stay beginner-oriented. Advanced diagnostics like ARI or NMI can exist, but should not dominate the first report.

#### Classification Mode

Labeled mode:

- use a simple probe or kNN baseline
- score macro F1 and balanced accuracy

Unlabeled mode:

- keep as advanced and low-confidence in V1

#### Embeddings Output Contract

The report should include:

- `best overall`
- `best cheap`
- `best local`
- optional `best quality`
- optional `best fast`
- weighted leaderboard
- notable failure cases
- exportable run configuration

#### Embeddings V1 Acceptance Criteria

- Users can run a retrieval-focused embeddings comparison on their own dataset through the wizard.
- The system supports both labeled and unlabeled retrieval runs.
- The report returns `best overall`, `best cheap`, and `best local`.
- The run captures enough configuration to be rerun on the same dataset version.
- Clustering and classification are either deferred or clearly marked experimental.

### Recipe 2: Summarization Quality

This recipe should always optimize a weighted rubric rather than a single metric.

The wizard should ask:

1. What kind of source material is being summarized?
2. Does the user have references or preference data?
3. What kind of summary is desired?
4. Which candidate models should compete?
5. What matters most?

Default rubric dimensions:

- `grounding / factuality`
- `coverage of important points`
- `concise usefulness`

#### Labeled Mode

If the user has references or preference pairs:

- use them as supporting evidence
- do not let lexical overlap alone decide winners

#### Unlabeled Mode

Use source-grounded judging by default, then pairwise comparison among the strongest candidates.

In unlabeled mode, every run should automatically reserve a human spot-check sample. The run may auto-complete when confidence is above threshold, but low-confidence runs or close-call winners should remain marked as requiring review until that spot-check sample is completed.

Recommended V1 execution pattern:

1. run all candidates on a stratified sample
2. score with source-grounded judging
3. do pairwise comparisons among top candidates
4. produce a ranked recommendation with confidence

The system should keep prompt and formatting instructions fixed across candidates inside a run.

#### Source Normalization And Context Policy

Summarization runs must define a single preprocessing and context-budget policy before any candidate is executed.

That policy should freeze:

- source normalization rules
- segmentation or chunking rules
- ordering rules
- map-reduce or single-pass strategy
- aggregation prompts
- maximum source budget per stage

All candidates in the run must receive equivalent normalized inputs under that same policy. The system must not silently compare one model on the full source and another on a truncated or differently segmented source.

If a candidate cannot satisfy the run-wide context policy, it should be excluded up front or clearly marked ineligible rather than being compared on a weaker input.

#### Summarization Output Contract

The report should include:

- `best overall`
- `best cheap`
- `best local`
- optional `best quality`
- rubric breakdown by candidate
- side-by-side example summaries
- flagged failure cases

Candidates that fail a grounding threshold must not win overall.

#### Summarization V1 Acceptance Criteria

- Users can run a rubric-based summarization comparison on their own source documents.
- The system supports both labeled and unlabeled summarization runs.
- A run-wide source normalization and context policy is captured and reused for every candidate in that run.
- Candidates that fail grounding thresholds cannot win overall.
- The report returns `best overall`, `best cheap`, and `best local`, with `best quality` when the recipe exposes it.

## Repo Integration

### Backend

Add a recipe registry layer under:

- `tldw_Server_API/app/core/Evaluations/`

with one module per recipe plus shared interfaces for manifests, validation, execution, scoring, and reports.

Reuse the existing evaluations persistence and lower-level run concepts where sound, but add stable recipe-oriented endpoints such as:

- `GET /api/v1/evaluations/recipes`
- `GET /api/v1/evaluations/recipes/{recipe_id}`
- `POST /api/v1/evaluations/recipes/{recipe_id}/validate-dataset`
- `POST /api/v1/evaluations/recipes/{recipe_id}/runs`
- `GET /api/v1/evaluations/recipe-runs/{run_id}`
- `GET /api/v1/evaluations/recipe-runs/{run_id}/report`

Per the repo's scheduler vs jobs guidance, recipe execution should use `Jobs` because:

- it is user-facing
- it may be long-running
- it benefits from visible progress and cancellation
- it needs stable status/report endpoints

The existing low-level eval run machinery can remain implementation detail under the user-facing recipe run abstraction.

The user-facing recipe run should be the parent object. A single recipe run may fan out into multiple internal eval runs or candidate executions, but only the recipe-run id should be the public orchestration identity exposed to the wizard and reports.

Recipe runs should reuse the existing evaluations run status model of `pending`, `running`, `completed`, `failed`, and `cancelled` rather than inventing a second status enum. Any post-run human review requirement should be represented through separate review metadata such as `review_state` or report flags, not through a conflicting lifecycle status vocabulary.

Recipe runs should also have explicit idempotency and reuse semantics:

- each run request should produce a deterministic config hash from recipe version, dataset version, resolved immutable model identifiers, versioned judge configuration, prompts, weights, and execution policy
- identical submissions should be able to reuse cached artifacts or return the prior completed run unless the caller sets `force_rerun`
- partial or failed runs should be resumable only when their intermediate artifacts are valid for reuse

This matters immediately for expensive judge-based runs and for embeddings preprocessing that can be reused across repeated comparisons.

### Frontend

The shared WebUI implementation should live under:

- `apps/packages/ui/src/components/Option/Evaluations/`

so both the web page and extension continue sharing a single experience.

The recipe wizard should become the primary entry path.

The existing generic tabs should remain secondary and should not be the foundation for the new UX until they are stabilized.

In the first implementation milestone, generic history and runs pages should remain secondary and explicitly out of scope for recipe-aware parity. The first ship target is the guided wizard plus report flow.

### Migration Strategy

The recipe framework should be introduced incrementally:

1. add registry, schemas, and report contracts
2. add the wizard and report views
3. ship embeddings and summarization recipes
4. stabilize or refactor generic tabs separately
5. add more recipes later without changing the workflow shell

## Error Handling And Safety

- Mark low-confidence runs clearly rather than presenting weak winners as authoritative.
- Preserve source-grounding failures as blocking signals for summarization.
- Persist artifacts for auditability.
- In `Simple mode`, unlabeled runs should always create a human-review sample automatically. Labeled runs do not require manual review by default, but may still surface optional review samples or require review when confidence falls below threshold.
- Make local-first and hosted-judge choices explicit in the run configuration.
- Warn when retrieval-stack settings differ across candidates in ways that would invalidate comparisons.

## Testing Strategy

The design should be implemented with coverage at three levels:

### Recipe Unit Tests

- dataset validation
- metric normalization
- recommendation logic
- hard-gate behavior
- confidence calculation

### Backend Integration Tests

- recipe manifest endpoints
- run creation and status
- dataset validation APIs
- report retrieval
- user scoping and permission handling

### Frontend Tests

- wizard branching for labeled vs unlabeled flows
- task selection and conditional fields
- recommendation card rendering
- failure and low-confidence states
- shared route parity between web page and extension

The existing evaluations UI gaps make frontend coverage particularly important for the new workflow.

## Risks And Tradeoffs

- Judge-based unlabeled evals can look precise while still being noisy. Confidence and spot checks are mandatory.
- Retrieval evaluation can become misleading if embeddings are compared under non-equivalent stack settings.
- Summarization scoring is vulnerable to over-trusting single-judge outputs. Pairwise judging and grounding gates are more stable than a single absolute score.
- Supporting both local-first and hosted judging improves flexibility, but increases the configuration surface. `Simple mode` must keep this manageable.

## Open Questions Deferred To Planning

- How much of the existing embeddings A/B infrastructure can be safely reused without carrying forward current Chroma-related instability.
- Whether generic history and runs pages should be upgraded to understand recipe runs in V1 or remain secondary.

## Implementation Recommendation

The implementation plan should treat the work as a recipe-framework project with two built-in recipes, not as "just add an embeddings wizard" or "just improve the evals page."

The plan should also separate:

- recipe framework and APIs
- wizard/report UX
- embeddings recipe
- summarization recipe
- generic eval UI stabilization

That separation keeps the first plan coherent and avoids mixing new product flows with unrelated cleanup work.
