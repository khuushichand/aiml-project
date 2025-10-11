## Stage 1: Foundations (Aggregators + OA)
Goal: Add OpenAlex, Crossref, and Unpaywall clients; shared normalization helpers; base schemas.
Success Criteria: Able to search by venue/publisher and resolve OA PDF by DOI; unit tests pass.
Tests: Unit tests for param building, normalization, OA resolution (mocked).
Status: Not Started

## Stage 2: IEEE Xplore Adapter
Goal: Implement `IEEE_Xplore.py` + `/api/v1/paper-search/ieee` endpoints and by-doi/by-id.
Success Criteria: Paginated IEEE search, by-id/doi fetch; error mapping; tests pass.
Tests: Unit + integration (mock HTTP). Rate-limit and 4xx/5xx behaviors.
Status: Not Started

## Stage 3: Springer Nature Adapter
Goal: Implement `Springer_Nature.py` + `/api/v1/paper-search/springer` and by-doi.
Success Criteria: Metadata search with filters; by-doi fetch; tests pass.
Tests: Unit + integration (mock HTTP). Timeout/HTTP error mapping.
Status: Not Started

## Stage 4: Elsevier/Scopus Adapter
Goal: Implement `Elsevier_Scopus.py` + `/api/v1/paper-search/scopus` and by-doi.
Success Criteria: Scopus search, by-doi; handle API keys/inst tokens; tests pass.
Tests: Unit + integration (mock HTTP). 401/403/429 handling.
Status: Not Started

## Stage 5: ACM & Wiley via Aggregators
Goal: Endpoints `/api/v1/paper-search/acm`, `/api/v1/paper-search/wiley` using OpenAlex/Crossref constraints.
Success Criteria: Venue/publisher-filtered results; by-doi fetch; tests pass.
Tests: Unit + integration (mock HTTP). Normalization correctness.
Status: Not Started

