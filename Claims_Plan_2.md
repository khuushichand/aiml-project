## Stage 1: Analytics Expansion (Trends + Hotspots)
**Goal**: Extend review analytics with trend dashboards and hotspot analytics for clustered claims.
**Success Criteria**: Trend/hotspot analytics are available via API endpoints and dashboards; review analytics include trend windows beyond nightly delta reporting.
**Tests**: API integration tests for trend/hotspot endpoints; UI smoke tests for dashboards.
**Status**: Complete

## Stage 2: Extractor Catalog + Multilingual Support
**Goal**: Expand extractor catalog (multilingual heuristics, lightweight local LLMs) and improve scheduling heuristics.
**Success Criteria**: New extractors are configurable and selectable; multilingual handling improves accuracy in non-English samples; scheduling heuristics updated and documented.
**Tests**: Unit tests for extractor selection logic; integration tests for multilingual extraction paths.
**Status**: Not Started

## Stage 3: Evidence Span Alignment + Correction Workflows
**Goal**: Improve evidence span alignment in longer documents and enhance correction workflows.
**Success Criteria**: Evidence span alignment accuracy improves for long-form content; correction flows preserve and propagate reviewer edits reliably.
**Tests**: Unit tests for alignment logic; integration tests for review corrections and re-embedding behavior.
**Status**: Not Started

## Stage 4: Per-Job Budget Guardrails + Cost/Latency Dashboards
**Goal**: Add per-job budget guardrails and provider latency/cost dashboards with adaptive throttling.
**Success Criteria**: Budgets enforce per-job caps; dashboards report provider latency/cost; adaptive throttling responds to budget/latency signals.
**Tests**: Unit tests for budget enforcement; integration tests for dashboard metrics and throttling behavior.
**Status**: Not Started
