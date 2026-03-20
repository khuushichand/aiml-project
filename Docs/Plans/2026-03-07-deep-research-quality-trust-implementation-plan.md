# Deep Research Quality And Trust Implementation Plan

## Stage 1: Verification Contracts
**Goal**: Define and test machine-readable trust artifacts for synthesis and packaging.
**Success Criteria**: Red tests pin `verification_summary.json`, `contradictions.json`, `unsupported_claims.json`, and trust fields in the final bundle.
**Tests**: `tldw_Server_API/tests/Research/test_research_synthesizer.py`, `tldw_Server_API/tests/Research/test_research_jobs_worker.py`, `tldw_Server_API/tests/Research/test_research_exporter.py`
**Status**: Complete

## Stage 2: Backend Trust Artifacts
**Goal**: Implement claim verification, contradiction extraction, source trust derivation, and bundle inclusion.
**Success Criteria**: Synthesis writes trust artifacts, packaging includes them, and claim outputs expose support strength and warnings.
**Tests**: `tldw_Server_API/tests/Research/test_research_synthesizer.py`, `tldw_Server_API/tests/Research/test_research_jobs_worker.py`, `tldw_Server_API/tests/e2e/test_deep_research_runs.py`
**Status**: Complete

## Stage 3: Regression Fixtures
**Goal**: Add stable fixture-style tests for support coverage, contradiction capture, and unsupported-claim surfacing.
**Success Criteria**: Research quality is regression-tested on evidence invariants instead of only phase completion.
**Tests**: `tldw_Server_API/tests/Research/test_research_synthesizer.py`, `tldw_Server_API/tests/e2e/test_deep_research_runs.py`
**Status**: Complete

## Stage 4: Verification And Finish
**Goal**: Run targeted backend verification and security checks, then record a clean commit.
**Success Criteria**: Research trust suites pass, Bandit stays clean on touched backend files, and the branch is ready for review.
**Tests**: targeted pytest, research/e2e pytest subset, Bandit on touched research backend paths
**Status**: Complete

## Verification
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_synthesizer.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_exporter.py -q`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research tldw_Server_API/tests/e2e/test_deep_research_runs.py -k 'not test_arxiv_ingest_success' -q`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research/exporter.py tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/app/core/Research/models.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/core/Research/synthesizer.py -f json -o /tmp/bandit_deep_research_quality_trust.json`
