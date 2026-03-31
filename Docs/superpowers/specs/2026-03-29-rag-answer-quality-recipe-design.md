# RAG Answer Quality Recipe Design

## Summary

This design introduces a new evaluation recipe, `RAG Answer Quality`, for measuring how well a RAG system answers user queries once retrieval is already acceptable.

The recipe is intentionally downstream of retrieval tuning. Its job is to answer:

- which answer-generation setup works best once retrieval is fixed or mostly fixed
- whether the winner changes when generation is measured against frozen context versus live end-to-end RAG
- which candidate is the best overall, best quality, best cheap, and best local option

The recipe should support:

- `fixed-context` mode as the default, where generation candidates are compared against frozen retrieved context snapshots
- `live end-to-end` mode as an advanced option, where a small number of retrieval baselines can be compared alongside generation candidates
- multiple supervision modes, including rubric judging, reference answers, pairwise winner judgments, and mixed runs

The recipe should explicitly score abstention behavior. A model that safely answers, hedges, or abstains when context is insufficient should outperform one that hallucinates.

This recipe is the second half of the planned two-recipe RAG family:

- `RAG Retrieval Tuning`
- `RAG Answer Quality`

It also depends on a shared synthetic dataset generation and review workflow, which is specified separately.

## Goals

- Give users a reliable way to compare answer-generation candidates after retrieval quality is good enough.
- Separate answer-generation measurement from retrieval tuning by default.
- Make grounding a hard gate so unsupported answers cannot win overall.
- Treat abstention and insufficient-evidence handling as a first-class quality dimension.
- Support both fixed-context and live end-to-end evaluation modes.
- Support multiple supervision signals without fragmenting the final report shape.
- Reuse the recipe-first framework, WebUI flow, and recommendation contract already established for other eval recipes.
- Preserve reproducibility through explicit retrieval baseline references, context snapshot references, and stored answer artifacts.

## Non-Goals

- Replacing the retrieval tuning recipe with a single combined RAG mega-recipe.
- Treating live end-to-end RAG as the default mode.
- Allowing arbitrary generation configuration search in V1.
- Treating synthetic or judge-generated labels as equally trustworthy as real reviewed data.
- Building the shared synthetic generation workflow inside this recipe instead of depending on it.

## Current State

### Existing Recipe Framework

The recipe framework already exposes:

- recipe manifests and launch readiness
- recipe-run persistence
- Jobs-based execution
- shared recommendation slots
- shared WebUI recipe launcher and report surface

Relevant files include:

- `tldw_Server_API/app/api/v1/schemas/evaluation_recipe_schemas.py`
- `tldw_Server_API/app/core/Evaluations/recipe_runs_service.py`
- `tldw_Server_API/app/core/Evaluations/recipe_runs_jobs_worker.py`
- `apps/packages/ui/src/components/Option/Evaluations/tabs/RecipesTab.tsx`

The framework is now also capable of exposing safe non-launchable stub manifests for future recipes.

### Existing RAG Evaluation Surface

The backend already has a RAG evaluator and unified evaluation service:

- `tldw_Server_API/app/core/Evaluations/rag_evaluator.py`
- `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`

Those components are useful building blocks for scoring one `query + contexts + answer` tuple, but they are not a recipe workflow. They do not currently define:

- fixed context snapshot artifacts
- retrieval baseline references
- abstention-aware recommendation policy
- candidate comparison workflows for answer-generation presets

### Existing RAG Request Surface

The current RAG request schema already exposes many adaptive knobs such as:

- intent routing
- rewrite loops
- adaptive reruns
- reranking strategies
- retrieval-source selection

Relevant schema surface:

- `tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py`

That flexibility is useful for product runtime behavior, but it is a design risk for answer-quality evaluation. Live answer-quality runs must freeze retrieval behavior strongly enough that generation comparisons remain interpretable.

## Requirements Confirmed With User

- This recipe should be designed after retrieval tuning, not as a replacement for it.
- V1 should optimize a weighted rubric across:
  - grounding / faithfulness
  - answer relevance
  - format / style compliance
  - abstention / insufficient-evidence handling
- Grounding should remain a hard gate.
- The recipe should support both:
  - fixed retrieved context snapshots
  - live end-to-end RAG runs
- Fixed-context should be the default; live end-to-end should be advanced.
- Competing candidates in V1 should vary across:
  - generation model
  - prompt variant
  - formatting / citation mode
- Runs should anchor to one retrieval baseline by default, with a small number of baselines allowed in advanced mode.
- Supervision should support:
  - reference answers
  - pairwise winner judgments
  - rubric judging
  - mixed user-chosen modes
- Synthetic support for this recipe should eventually provide draft items that include:
  - query
  - retrieval baseline ref or context snapshot ref
  - draft reference answer
  - expected behavior label: `answer`, `hedge`, `abstain`

## Approaches Considered

### Approach 1: Fixed-Context-First Recipe

Default to frozen retrieved contexts and compare only answer-generation candidates there, with live end-to-end available as advanced confirmation.

Pros:

- cleanest signal for generation quality
- easiest mode to reproduce
- minimizes retrieval noise
- best fit for rubric-based evaluation

Cons:

- less realistic than live full-RAG execution
- requires first-class context snapshot artifacts

### Approach 2: Live End-to-End Recipe

Default to full RAG runs and treat fixed-context as secondary.

Pros:

- closest to user-visible runtime behavior
- easier to explain as “real answer quality”

Cons:

- retrieval variance muddies generation comparisons
- adaptive retrieval features can change the test itself
- harder to diagnose failures

### Approach 3: Two Separate Answer Recipes

Create one recipe for fixed-context generation quality and another for live end-to-end answer quality.

Pros:

- clear conceptual split
- easy to reason about evaluation scope

Cons:

- more product surface
- more user confusion
- more recipe duplication

## Recommendation

Use Approach 1.

Implement one `RAG Answer Quality` recipe that supports both modes, but defaults to `fixed-context` and treats `live end-to-end` as advanced confirmation. This keeps the beginner path reliable while still supporting more realistic follow-up comparisons.

## Proposed Architecture

### Recipe Purpose

The recipe should compare answer-generation candidates against a fixed retrieval baseline and return recommendation slots such as:

- `best_overall`
- `best_quality`
- `best_cheap`
- `best_local`

It should answer a plain-language user question such as:

- “Given this retrieval setup, which answer model and prompt should I use?”

### Required Anchors

Every answer-quality run must include one of:

- `retrieval_baseline_ref`
- `context_snapshot_ref`

For V1:

- `retrieval_baseline_ref` should point to an approved retrieval tuning winner, preset, or explicit retrieval baseline artifact
- `context_snapshot_ref` should point to immutable retrieved contexts captured for a fixed-context benchmark set

These should be first-class concepts in the recipe domain model, not implicit metadata blobs.

### Evaluation Modes

#### Fixed-Context Mode

This is the default mode.

Each sample should include:

- `sample_id`
- `query`
- `context_snapshot_ref`
- `retrieved_contexts`
- optional `reference_answer`
- optional pairwise or rubric annotations
- `expected_behavior`: `answer`, `hedge`, or `abstain`

Generation candidates receive exactly the same context and are judged only on what they do with it.

#### Live End-to-End Mode

This is advanced mode.

Each sample should include:

- `sample_id`
- `query`
- `retrieval_baseline_ref`
- optional `reference_answer`
- optional pairwise or rubric annotations
- `expected_behavior`

The run may compare:

- one retrieval baseline by default
- a small number of retrieval baselines in advanced mode

In live mode, generation candidates must not be allowed to drift retrieval behavior. The recipe should execute against an immutable retrieval preset hash derived from the chosen baseline.

By default, live-mode answer evaluation should disable or freeze adaptive retrieval features that would otherwise blur the boundary between retrieval and generation, including:

- intent-routing-driven retrieval changes
- query rewrite loops
- adaptive reruns
- generation-coupled retrieval retries

### Candidate Model

V1 candidates should vary across:

- generation model
- prompt variant
- formatting / citation mode

These are the only first-class candidate dimensions in V1. The recipe should not allow arbitrary full-generation configuration search.

Optional candidate metadata may still include:

- local vs hosted
- estimated cost
- latency policy

### Supervision Modes

The recipe should support:

- `reference-answer` scoring
- `pairwise` winner judgments
- `rubric` judging
- `mixed`

Users should be able to select the supervision mode per run. However, the report output should normalize all of them into the same recommendation shell.

### Scoring Model

The default rubric should include:

- `grounding`
- `answer_relevance`
- `format_style_compliance`
- `abstention_behavior`

#### Grounding Gate

Grounding is a hard gate. A candidate that fails the grounding threshold cannot win `best_overall`.

#### Abstention Behavior

Abstention should be a first-class scored dimension, not just a hidden safety rule.

Expected behavior per sample:

- `answer`: the context is sufficient for a direct answer
- `hedge`: the answer should acknowledge uncertainty or partial evidence
- `abstain`: the answer should decline to answer directly because context is insufficient

This allows the system to reward safe behavior rather than treating every non-answer as failure.

### Artifacts

Per run, the recipe should persist:

- `retrieval_baseline_ref`
- `context_snapshot_ref` where applicable
- immutable retrieval preset hash for live mode
- candidate list and normalized candidate configs
- answers per candidate and per sample
- scoring artifacts:
  - reference comparisons
  - pairwise winner records
  - rubric outputs
- failure labels such as:
  - `hallucinated`
  - `missed_answer`
  - `bad_abstention`
  - `format_failure`

### Recommendation Policy

The recipe should emit:

- `best_overall`
- `best_quality`
- `best_cheap`
- `best_local`

Supporting evidence should include:

- recommendation rationale
- key tradeoffs
- confidence summary
- failure examples

The mandatory shared slots from the framework still apply. Optional recipe-specific slots should not replace them.

## Dependency On Shared Synthetic Dataset Generation

This recipe depends on a separate shared capability for synthetic dataset generation and review.

That capability must be able to create draft answer-quality items shaped like:

- `query`
- `retrieval_baseline_ref` or `context_snapshot_ref`
- draft `reference_answer`
- `expected_behavior`: `answer`, `hedge`, `abstain`
- provenance metadata
- review state

Synthetic items must not influence recommendations until reviewed and promoted into active eval datasets.

## UI And Workflow Expectations

The user-facing wizard should ask:

1. which retrieval baseline to use
2. whether to run `fixed-context` or `live end-to-end`
3. which answer candidates should compete
4. which supervision mode to use
5. whether abstention handling matters for this run

The results page should open with:

- recommended answer setup
- why it won
- whether the winner changes between fixed and live mode
- failure cases and bad abstention examples

## Testing Expectations

The future implementation should include:

- recipe unit tests for dataset validation and scoring
- report tests for grounding-gate behavior
- tests for abstention-aware scoring
- service and worker tests for artifact persistence
- API tests for recipe launch and report retrieval
- UI tests for fixed-context vs live mode branching

## Rollout Notes

- Implement this only after retrieval tuning is real, runnable, and produces stable retrieval baseline artifacts.
- Do not block current retrieval-tuning implementation on this recipe.
- The shared synthetic dataset generation spec should follow next and satisfy the dependency contract defined here.
