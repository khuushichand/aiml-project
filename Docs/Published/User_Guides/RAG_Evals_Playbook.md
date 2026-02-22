# RAG Evals Playbook

Status: Active
Last Updated: 2026-02-13
Audience: RAG engineers, evaluation owners, release managers

## Purpose

Use this playbook to run repeatable RAG evaluations, compare retrieval/generation variants, and decide whether a change is safe to ship.

This is the canonical process for:
- Retrieval strategy changes
- Chunking/context expansion changes
- Reranker changes
- Prompt/model changes
- Guardrail and abstention behavior changes

## Core Rule

Never ship a RAG pipeline change without a baseline comparison on the same dataset and scoring protocol.

## Required Datasets

Maintain three dataset buckets and report results for each bucket separately.

1. In-corpus answerable
- Questions expected to be answerable from indexed content.
- Goal: detect regressions in relevance/faithfulness when evidence exists.

2. Messy real-user style
- Informal, noisy, shorthand, typo-heavy, and underspecified queries.
- Goal: test robustness to real query phrasing.

3. Out-of-corpus / no-answer
- Questions likely missing from corpus.
- Goal: test abstention behavior and avoid confident fabrication.

Recommended minimums for stable signal:
- 50 samples per bucket for routine checks
- 200+ per bucket for release gating

## Mandatory A/B Comparison

For any context-expansion change, run both variants on identical samples.

- Variant A: `seed-only`
- Variant B: `seed+expansion` (siblings/parent/neighbor expansion)

Required output:
- Per-bucket delta table for all metrics
- Worst 5-10 regressions with query-level traces
- Decision note: keep, rollback, or iterate

## Metrics

Use both generation and retrieval metrics. Report mean, median, and p10.

Generation metrics:
- Faithfulness
- Relevance
- Answer similarity (if gold answer present)
- Hallucination/unsupported-claim rate
- Abstention correctness on no-answer bucket

Retrieval metrics:
- Context precision/relevance
- Context recall/coverage (when labels exist)
- MRR/nDCG (when relevant IDs exist)
- Source diversity

Source diversity formula (required):

`source_diversity_at_k = distinct_source_ids_in_top_k / k`

Interpretation:
- `0.1` for `k=10`: all hits from one source
- `1.0` for `k=10`: all hits from different sources

## Judge Strategy

LLM-as-a-judge is useful but biased. Mitigate with policy:

- Do not use the exact same model as both generator and judge.
- Prefer a different provider for the primary judge on release gates.
- Re-run a fixed subset (10-20%) with a second judge model and track variance.
- Treat large judge disagreement as "needs manual review," not pass/fail.

## Logging Contract (Per Query)

Store enough detail to debug failures.

Required fields:
- `query_id`, `dataset_bucket`, `query_text`
- Pipeline variant/config hash
- Retrieved seed chunks (IDs, scores, source IDs)
- Retrieved expanded chunks (IDs, scores, source IDs)
- Final context sent to generator
- Model/provider identifiers
- Prompt/template version
- Generated answer
- Metric scores + judge rationale
- Latency and token/cost usage

## Failure Triage Workflow

For each run:

1. Review regressions first
- Compare against last accepted baseline.

2. Inspect worst offenders
- Manually inspect bottom 5-10 samples per bucket.

3. Tag root cause for each failure
- Retrieval miss
- Retrieval noise overload
- Reranker failure
- Generation error
- Judge artifact
- Dataset labeling issue

4. Decide action
- Fix retrieval
- Tune generation/guardrails
- Improve dataset labels
- Adjust metrics/weights

## Release Gates

Use delta-based gates, not absolute-only gates.

Required default gates (adjust per product needs):
- No statistically meaningful drop in in-corpus faithfulness
- No statistically meaningful drop in in-corpus relevance
- No increase in hallucination rate on no-answer bucket
- No regression in abstention correctness on no-answer bucket
- Latency/cost within agreed budget envelope

If any gate fails:
- Do not promote candidate
- File a regression note with offending sample IDs and root-cause tags

## Run Cadence

- Nightly: run a reduced set for trend monitoring
- Pre-merge (high-risk RAG changes): run bucket smoke set
- Pre-release: full gate set with A/B comparison

## Implementation Notes for This Repo

Use existing unified evaluations and rag_pipeline workflow:

1. Create datasets
- `POST /api/v1/evaluations/datasets`

2. Define evals
- `POST /api/v1/evaluations`
- For pipeline sweeps: `eval_type=model_graded`, `sub_type=rag_pipeline`

3. Start run
- `POST /api/v1/evaluations/{eval_id}/runs`

4. Poll status/results
- `GET /api/v1/evaluations/runs/{run_id}`

5. Persist winning preset
- `POST /api/v1/evaluations/rag/pipeline/presets`

See also:
- `Docs/User_Guides/Media_to_RAG_Evals_Workflow.md`
- `Docs/Design/RAG_Pipeline_Evaluation.md`
- `Docs/Design/RAG-Benchmarking.md`
- `Docs/RAG/Benchmarks/Benchmark_Corpus_Workflow.md`

## Checklist (Copy/Paste)

- [ ] Dataset buckets updated (in-corpus, messy, no-answer)
- [ ] Baseline and candidate run on identical samples
- [ ] `seed-only` vs `seed+expansion` comparison completed (when expansion changes)
- [ ] Source diversity reported (`distinct_source_ids / k`)
- [ ] Judge cross-check run completed
- [ ] Worst-offender triage documented
- [ ] Release gates passed
- [ ] Winning config/preset saved
