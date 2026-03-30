# RAG Retrieval Tuning Recipe Design

## Summary

This design introduces a new evaluation recipe, `RAG Retrieval Tuning`, for comparing retrieval and indexing configurations against a specific data corpus or media collection inside tldw.

The recipe is intentionally retrieval-focused. Its job is to answer:

- which retrieval setup works best for this corpus
- whether the best setup changes at media-level versus chunk-level relevance
- which candidate is the best overall, best quality, best cheap, and best local option

The recipe should support both:

- `labeled` mode, where users provide queries plus relevance targets
- `weak-supervision` mode, where the system bootstraps queries and provisional relevance judgments, then reserves a human review sample

The primary user path should optimize around already-ingested tldw media collections, while still supporting standalone dataset snapshots for reproducibility and offline workflows.

This recipe should be the first half of a future two-recipe RAG family:

- `RAG Retrieval Tuning`
- `RAG Answer Quality`

The first version explicitly does not try to solve both at once.

## Goals

- Give users a corpus-specific way to tune retrieval for RAG without requiring deep eval expertise.
- Keep the recipe aligned with the new recipe framework and shared WebUI wizard.
- Support both media-level and chunk-level relevance targets as first-class options.
- Support both manually supplied candidates and a bounded auto-generated tuning sweep.
- Work with both labeled datasets and weakly supervised datasets.
- Make already-ingested media collections the primary happy path.
- Produce recommendation-first reports with confidence and failure examples.
- Preserve reproducibility through dataset snapshots, normalized candidate configs, and stored artifacts.

## Non-Goals

- Evaluating end-to-end answer quality and generation faithfulness in V1.
- Building a general hyperparameter search engine for retrieval.
- Running a large blind sweep across many unrelated knobs without explainability.
- Treating weak labels or judge outputs as trustworthy by default without review.
- Replacing the existing unified RAG evaluator or existing recipe framework abstractions.

## Current State

### Existing Recipe Foundation

The recipe framework already has:

- a built-in recipe registry under `tldw_Server_API/app/core/Evaluations/recipes/registry.py`
- concrete recipes for `embeddings_model_selection` and `summarization_quality`
- recipe run persistence, Jobs execution, CLI support, launch readiness, and report fetching
- a shared `Recipes` tab in the WebUI with guided controls and advanced JSON fallback

This means the new RAG recipe should be added as another built-in recipe rather than a parallel subsystem.

### Existing RAG Evaluation Capability

The backend already includes a standalone RAG evaluator in:

- `tldw_Server_API/app/core/Evaluations/rag_evaluator.py`
- `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`

That evaluator is useful for scoring a single `query + contexts + response (+ optional ground truth)` tuple, but it is not a retrieval tuning workflow. It should remain available for future answer-quality recipes, while the new recipe focuses on retrieval and indexing quality.

### Skill Review Takeaways

Before finalizing this design, the following external eval skills were installed and reviewed from `hamelsmu/evals-skills`:

- `evaluate-rag`
- `generate-synthetic-data`
- `eval-audit`
- `validate-evaluator`
- `write-judge-prompt`
- `error-analysis`
- `build-review-interface`

The most important design constraints reinforced by those skills are:

- separate retrieval evaluation from generation evaluation
- optimize first-pass retrieval primarily for `Recall@k`
- use `Precision@k`, `MRR`, and `NDCG@k` as complementary ranking metrics
- prefer real queries and traces over synthetic data when available
- use synthetic data to fill gaps, not to replace real corpus behavior
- treat weak-label judges as untrusted until validated against human labels
- reserve human review as a first-class part of weak-supervision workflows

## Requirements Confirmed With User

- The recipe should tune the RAG system against a specific corpus or media collection.
- The V1 goal is retrieval pipeline tuning, not end-to-end answer quality.
- The recipe should support both labeled and weak-supervision modes, defaulting to labeled when available and weak supervision otherwise.
- Competing candidates should support both manual configuration and auto-generated sweeps, with a small auto-generated sweep as the default path.
- Both media-level and chunk-level relevance should be supported from day one.
- The corpus should support both already-ingested tldw media and standalone dataset snapshots, with the primary path optimized around ingested media collections.

## Approaches Considered

### Approach 1: Retrieval Tuning Recipe

Compare retrieval and indexing candidates on a shared query set using relevance targets and retrieval metrics.

Pros:

- Directly answers the user’s corpus-specific tuning question
- Keeps the signal focused and reproducible
- Cheaper and less noisy than generation-inclusive evals
- Fits the installed `evaluate-rag` guidance well

Cons:

- Does not directly measure final answer quality
- Requires a second recipe later for generation-quality assurance

### Approach 2: Full RAG Configuration Recipe

Compare indexing, retrieval, and generation together in one recipe.

Pros:

- More end-to-end in principle
- Easier to market as “RAG quality”

Cons:

- Generation variance can hide retrieval problems
- Harder for users to debug and interpret
- More expensive and less reproducible

### Approach 3: Two-Recipe Family

Make `RAG Retrieval Tuning` the first recipe, then add a later `RAG Answer Quality` recipe that consumes strong retrieval candidates.

Pros:

- Keeps each recipe focused and understandable
- Maps well to how RAG systems are actually debugged
- Allows answer-quality evaluation to reuse retrieval winners later

Cons:

- Requires users to understand that retrieval tuning and answer evaluation are separate tasks

## Recommendation

Use Approach 3 and implement the retrieval half first.

The new recipe should be `RAG Retrieval Tuning`, focused on retrieval and indexing quality against a specific corpus. Future answer-quality evaluation should be a separate recipe, not mixed into this one.

## Proposed Architecture

### Recipe Purpose

The recipe should compare candidate retrieval configurations against one corpus and produce recommendation slots such as:

- `best_overall`
- `best_quality`
- `best_cheap`
- `best_local`

The recipe should not require users to understand ranking metrics up front. The beginner question should be closer to:

- “Which retrieval setup should I use for this collection?”

### Corpus Sources

The recipe should support two corpus source modes:

1. `Ingested corpus` as the primary path
   - selected by media ids
   - or selected by saved collection id

2. `Dataset snapshot` as a secondary path
   - uploaded or referenced snapshot containing the benchmark payload

The report should always persist the effective corpus scope so a run remains reproducible even if the live collection changes later.

### Supervision Modes

The recipe should support:

- `labeled`
- `weak_supervision`

#### Labeled Mode

Users provide queries plus one or both of:

- `relevant_media_ids`
- `relevant_chunk_ids`

This is the preferred mode when users already know what the retriever should find.

#### Weak-Supervision Mode

The system bootstraps:

- candidate queries
- provisional media-level and/or chunk-level relevance judgments
- a reserved human review slice

The weak-supervision flow should follow these rules:

- prefer real queries and traces if they exist
- use synthetic query generation only to fill coverage gaps
- use dimension-based generation instead of generic freeform prompting
- reserve a human review sample in every run
- explicitly lower confidence when labels are synthetic or judge-derived

### Dataset Contract

The recipe should use the existing recipe framework pattern of a common envelope plus task-specific payload.

Each retrieval sample should conceptually include:

- `sample_id`
- `query`
- `corpus_scope`
- `targets`
- `metadata`

`corpus_scope` should support:

- `media_ids`
- `collection_id`
- optional retrieval filters where supported

`targets` should support:

- `relevant_media_ids`
- `relevant_chunk_ids`

This allows four valid dataset shapes:

- media-level only
- chunk-level only
- both
- weak-supervision with missing targets initially

### Candidate Model

Candidate configs should normalize into two layers:

1. `indexing_config`
   - chunking strategy
   - chunk size
   - overlap
   - heading/title augmentation flags if supported
   - embedding model
   - optional reranker model

2. `retrieval_config`
   - search mode
   - `top_k`
   - `hybrid_alpha`
   - filters
   - reranker enabled/disabled plus params

This separation matters because some candidate changes require a fresh index while others can reuse the same index.

### Candidate Creation

The recipe should support both:

- `auto_sweep`
- `manual_candidates`

Default path:

- build a small bounded sweep from a base config
- vary only a few explainable knobs
- keep the number of candidates intentionally small

Examples of safe auto-sweep axes:

- `top_k`
- `hybrid_alpha`
- reranker on/off
- one or two chunking presets

The system should not default to large unbounded tuning grids.

### Execution Flow

Recommended execution flow:

1. resolve corpus scope
2. validate dataset mode and target completeness
3. generate or normalize candidate configs
4. materialize indexes only for candidates whose indexing config differs
5. run retrieval for every query/candidate pair
6. capture retrieved media ids, retrieved chunk ids, ranks, scores, and latency
7. compute media-level and chunk-level metrics separately
8. combine into recommendation slots and confidence summary
9. reserve or present review samples where required

The execution path should stay retrieval-only in V1. It should not call answer generation for the main scoring loop.

### Scoring Framework

Primary metrics:

- `Recall@k`
- `MRR`
- `NDCG@k`
- `Precision@k` when labels support it

Secondary metrics:

- median and p95 retrieval latency
- indexing/build time when indexing changes are part of the candidate
- storage/index footprint when available
- estimated hosted cost where relevant

The recipe should compute:

- `media_relevance_score`
- `chunk_relevance_score`
- `retrieval_quality_score`
- `overall_score`

The default weighting should be configurable, but the report should keep media-level and chunk-level performance visible rather than collapsing them too early.

If only one relevance level exists in the dataset, the scoring model should degrade cleanly to that level.

### Hard Gates

Candidates should be disqualified or heavily penalized for:

- frequent empty retrievals
- catastrophic regressions in one relevance level
- latency beyond configured caps
- invalid or incomplete retrieval outputs

Hard gates should be explicit in the report so users understand why a candidate did not win.

### Confidence Model

Confidence should be derived from:

- sample count
- spread between candidates
- winner margin
- weak-label versus labeled mode
- agreement between weak labels and reviewed samples, when available

Weak-supervision runs should carry lower default confidence than labeled runs unless validated human review evidence materially increases trust.

### UI And Results Contract

The WebUI should expose a recipe card like `RAG Retrieval Tuning`.

Beginner wizard steps:

1. choose corpus source
2. choose goal emphasis:
   - media retrieval
   - chunk retrieval
   - balanced
3. choose supervision mode
4. choose candidate creation mode:
   - recommended sweep
   - manual candidates
5. review runtime constraints
6. run

The results page should lead with:

- `Recommended config`
- `Why it won`
- `Best cheap`
- `Best local`
- `Failure cases to inspect`

Then show:

- leaderboard
- per-metric breakdown
- media-level versus chunk-level split
- candidate config diffs
- review sample links

The page should avoid opening with raw metric tables only.

### Manifest And Framework Extension

This recipe is likely to need richer manifest metadata than the current framework exposes. The recipe manifest should eventually support wizard-oriented hints such as:

- supported corpus source types
- supported candidate generation modes
- supported metric families
- whether human review is required or optional

That should be handled as an intentional framework improvement rather than hardcoded inside the tab.

## Weak-Supervision And Human Review

Weak supervision should not be presented as equivalent to gold labels.

The recipe should make this explicit in both run status and reports:

- labels were synthetic, judge-derived, or user-supplied
- a human review sample was reserved
- confidence was adjusted accordingly

If the system later uses LLM judges for relevance or realism checks, the workflow should encourage:

- binary criteria where possible
- separate validators for separate failure modes
- later validation against human labels before those judges become trusted decision signals

The first version does not need to solve full judge validation inside the recipe itself, but it should not hide the distinction between judged labels and trusted labels.

## Testing Strategy

### Backend

Add:

- unit tests for dataset validation across media-level, chunk-level, mixed, and weak-supervision cases
- unit tests for candidate normalization and bounded auto-sweep generation
- unit tests for score aggregation and recommendation slot selection
- worker/service tests covering index reuse versus rebuild behavior
- integration tests for recipe run creation, readiness, and report retrieval

### Frontend

Add:

- wizard tests for corpus source selection
- tests for labeled versus weak-supervision UI branches
- tests for auto-sweep generation defaults
- tests for media-level versus chunk-level emphasis handling
- report rendering tests for recommendation cards and failure sample presentation

### Browser

Add at least one guided smoke flow that:

- selects an ingested corpus
- chooses retrieval tuning
- validates a dataset
- launches a bounded candidate sweep
- renders a completed report with recommendation slots

## Future Expansion

This recipe should be the first half of a broader RAG evaluation family.

Future follow-on work should include:

- `RAG Answer Quality` as a separate recipe using retrieval winners as candidate inputs
- optional review interface support for trace-level labeling and weak-label auditing
- later judge-validation tooling for subjective relevance or realism checks
- integration with real trace sampling and error-analysis workflows

Keeping retrieval tuning and answer-quality evaluation separate is a design feature, not a temporary limitation.
