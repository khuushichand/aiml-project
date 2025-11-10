# Curl-Scraping-PRD

Author: tldw_server team
Status: In Progress
Last Updated: 2025-10-26

## 1. Summary

Introduce a curl_cffi-powered HTTP backend with browser impersonation, a rule-based custom scraper router, and centralized browser User-Agent (UA) spoofing. The goal is to improve scrape success on sites with basic anti-bot defenses, reduce reliance on heavy headless browsers, and make per-domain customization straightforward and safe. The solution must preserve existing security (egress/SSRF guard), logging, and error-handling patterns.

Scope includes:
- Optional curl_cffi backend (Chrome/Firefox/Safari impersonation, HTTP/2, TLS fingerprinting)
- Router that picks a scraper strategy by URL/domain/regex and optional “tech” clues
- Centralized browser-like header generation (UA + sec-ch-ua, Accept-Language, Sec-Fetch-*)
- Seamless fallback to Playwright for JS-heavy pages
- Consistent usage of UA spoofing across WebSearch providers and article scraping
- Config-driven per-domain overrides, with safe defaults
- Tests, metrics, and rollout plan

Non-goals:
- Building a full anti-bot bypass framework
- Replacing Playwright for JS-required flows
- Violating site policies; robots.txt handling remains configurable and respectful by default

## 2. Background & Motivation

Current stack mixes `requests` and Playwright for scraping. While Playwright renders JS, it is heavyweight and unnecessary for many sites. `requests` has a generic TLS/HTTP fingerprint and basic headers that can be flagged by anti-bot systems. We want a middle path: curl_cffi (curl-impersonate) offers realistic browser fingerprints and HTTP/2 defaults, improving success without browser overhead.

Additionally, we want a maintainable way to route URLs to custom handlers (e.g., Substack, Medium, YouTube) and unify UA spoofing across scraping and search providers.

## 3. Goals

- Higher success rates on commonly-cited content sites (e.g., Medium, Substack)
- Lower average scrape latency vs. Playwright for static pages
- Configurable per-domain behavior with clear fallbacks
- Centralized, realistic browser headers reused across modules
- Maintain security posture (egress/SSRF guard) and error transparency

## 4. User Stories

- Researcher: “When I run web searches and scrape top results, content from Medium and Substack should extract reliably without switching to full browsers unless necessary.”
- Admin: “I can add per-domain rules (backend, UA, headers) without code changes.”
- Developer: “I can register a new handler in a few lines and write focused tests.”

## 5. Requirements

### 5.1 Functional
- Provide an HTTP client abstraction supporting backends: `requests`, `curl_cffi`, `playwright`.
- Implement browser impersonation via curl_cffi (`impersonate=chrome120|safari17|firefox120` etc.).
- Centralize UA/header generation; expose profiles and rotation mode.
- Route URLs to handlers by domain and optional regex path patterns; default to a generic handler.
- Preserve and invoke centralized egress/SSRF policy checks before any network call.
- Fallback logic:
  - Try curl_cffi for static pages → on failure or JS-required detection, fallback to Playwright.
- Make UA spoofing consistent in WebSearch providers (e.g., Searx, Tavily) and scraping.
- Config surface:
  - YAML for custom rules; environment variables for global defaults.
  - Per-domain overrides for backend, UA, impersonation, headers, cookies.
- Logging & Metrics:
  - Log rule selections, backend choice, retries, fallbacks, and errors (no secrets).
  - Counters/histograms for scrape success, latency, content length.

### 5.2 Non-Functional
- Performance: For static pages, curl backend median latency < Playwright median (target ≥30% faster).
- Reliability: Retries with backoff; circuit breaker for repeated LLM steps unchanged; timeouts tunable.
- Security: Keep egress policy; validate inputs; never log sensitive header/cookie values.
- Compatibility: Default behavior remains unchanged if curl_cffi disabled; Playwright path still available.

## 6. Architecture & Design

### 6.1 Modules & Files

Modules (locations under `tldw_Server_API/app/core/`):
- `http_client.py` (existing, extended): Now exposes `fetch(...)` with pluggable backends (`curl_cffi`/httpx), impersonation, HTTP/2, and egress guard.

New modules (under `tldw_Server_API/app/core/Web_Scraping/`):
- `ua_profiles.py`: UA profiles and header builder that produce realistic browser request headers.
- `scraper_router.py`: Rule engine to map URL → `ScrapePlan` (handler, backend, headers, cookies).
- `handlers.py`: Focused handlers (generic HTML→trafilatura, Playwright render, provider-specific like YouTube/Medium/Substack when needed).

Config:
- `tldw_Server_API/Config_Files/custom_scrapers.yaml`: Rule registry for domains and patterns.

Integration:
- `Article_Extractor_Lib.scrape_article(...)`: Use router→plan→client to fetch HTML before extraction; fallback to Playwright.
- `WebSearch_APIs.py`: Replace ad-hoc headers with `ua_profiles.build_browser_headers(...)` where applicable (e.g., Searx, Tavily).

### 6.2 HTTP Client Abstraction

Interface (illustrative):
```python
# http_client.py
class HttpResponse(TypedDict):
    status: int
    headers: Dict[str, str]
    text: str
    url: str

def fetch(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    backend: str = "auto",  # auto|curl|requests|playwright
    impersonate: Optional[str] = None,  # chrome120|safari17|firefox120
    http2: bool = True,
    timeout: float = 15.0,
    allow_redirects: bool = True,
) -> HttpResponse: ...
```

Behavior:
- `auto`: prefer `curl` if installed/configured; otherwise `requests`; detect JS-required then elevate to `playwright`.
- Domain-scoped session pool with cookie jars.
- Mandatory egress policy check before any network call.
- Retries/backoff for idempotent GETs; reasonable defaults configurable.

### 6.3 UA Spoofing

- `ua_profiles.py` exposes:
  - `build_browser_headers(profile: str, accept_lang: str) -> Dict[str, str]`
  - `pick_ua_profile(mode: str, domain: Optional[str]) -> str` (fixed vs rotate)
- Profiles include matching `sec-ch-ua*`, `Accept`, `Accept-Language`, `Sec-Fetch-*`, `Accept-Encoding` with gzip/br/zstd.
- Align curl_cffi `impersonate` value with UA profile version where possible.

### 6.4 Router & Rules

Data model:
```yaml
# custom_scrapers.yaml
domains:
  medium.com:
    backend: curl
    handler: tldw_Server_API.app.core.Web_Scraping.handlers:handle_generic_html
    ua_profile: chrome_120_win
    impersonate: chrome120
    extra_headers:
      Referer: https://www.google.com
  substack.com:
    backend: curl
    handler: tldw_Server_API.app.core.Web_Scraping.handlers:handle_generic_html
    ua_profile: chrome_120_win
    impersonate: chrome120
    url_patterns:
      - ".*\\?output=1$"
```

Router responsibilities:
- Match by exact domain, wildcard, or regex patterns.
- Build `ScrapePlan` with backend, UA profile, impersonation, and extra headers/cookies.
- Default: generic handler with curl backend; fallback to Playwright on JS detection/failure.

### 6.5 Security

- All outbound requests go through centralized egress policy (`evaluate_url_policy`) before dialing.
- Robots integration: fetchers consult robots.txt (via a standard parser) when `respect_robots=true` (default); admins may override via config with explicit acknowledgement.
- Handler import allowlist: YAML `handler` references must start with approved module prefixes (e.g., `tldw_Server_API.app.core.Web_Scraping.handlers:`). Non-allowlisted handlers are ignored in favor of a safe default.
- Structured redaction: client-level header redaction removes `Authorization`, `Cookie`, `Set-Cookie`, `X-API-KEY`, and similar keys from logs.

## 7. Configuration

All settings are configured via `Config_Files/config.txt` (loaded by `load_and_log_configs()`); this PRD does not use environment variables.

Relevant `config.txt` keys (section: `Web-Scraper`):
- `custom_scrapers_yaml_path`: Path to `custom_scrapers.yaml` (default: `tldw_Server_API/Config_Files/custom_scrapers.yaml`).
- `web_scraper_default_backend`: `auto|curl|httpx|playwright` (applied when a rule resolves to `auto`).
- `web_scraper_ua_mode`: `fixed|rotate` (default: `fixed`).
- `web_scraper_respect_robots`: `True|False` (default: `True`).

YAML (`custom_scrapers.yaml`) controls per-domain overrides (backend, UA, impersonate, headers, cookies, proxies, patterns).

## 8. Dependencies & Changes

- Add optional dependency: `curl_cffi`.
- Optional: `playwright_stealth` (already conditionally used).
- Add decompressors to match Accept-Encoding: `brotli`, `zstandard` (Python decoding), though curl backend can auto-decode.
- Update pyproject extras accordingly; ensure imports are optional with clear errors or fallbacks.

## 9. Detailed Integration Plan

1) Scaffold modules: `http_client.py`, `ua_profiles.py`, `scraper_router.py`, `handlers.py`.
2) Article scraping:
   - In `scrape_article(...)`, resolve `ScrapePlan` via router.
   - If plan.backend == `curl` → `http_client.fetch(...)` with impersonation and plan headers; extract via `trafilatura`.
   - On failure or JS-required page → fallback to Playwright path.
3) Web search providers:
   - Replace ad-hoc headers with `build_browser_headers(...)` in Searx/Tavily and other direct HTTP paths.
4) Config & docs:
   - Ship `custom_scrapers.yaml` with examples (Medium/Substack).
   - Document environment variables and rule schema.
5) Metrics & logging:
   - Counters: `html_fetched`, `html_fetch_error`, `article_extracted` (existing), plus `curl_fetch`, `playwright_fallback`.
   - Histograms: scrape latency, content length.

## 10. Testing Strategy

Follow existing pytest markers and patterns.

- Unit (no network):
  - Router: URL → rule match → `ScrapePlan` correctness (domain/pattern precedence, defaults).
  - UA: `build_browser_headers` returns expected keys; impersonate aligns with UA profile.
  - Client: backend selection behavior when `curl_cffi` missing (falls back to `requests`).

- Integration (external_api):
  - curl backend fetch succeeds on static pages; honors UA/headers.
  - Generic handler extracts content via `trafilatura`.
  - Playwright fallback path still scrapes JS-heavy pages.

- Security:
  - Egress-denied URL raises/returns policy error consistently.

Coverage target: ≥80% for new modules; deterministic tests with mocks where feasible.

## 11. Rollout Plan

- Phase 1 (opt-in):
  - Ship modules disabled by default; backend `auto` uses `requests` if `curl_cffi` absent.
  - Provide example `custom_scrapers.yaml` and enable for select domains.

- Phase 2 (graduated rollout):
  - Enable curl backend by default for generic handler if `curl_cffi` present.
  - Monitor metrics (success rate, latency, fallback rate).

- Phase 3 (hardening):
  - Expand rule set with additional domains.
  - Tune header profiles and timeouts.

Rollback: Set `WEB_SCRAPER_HTTP_BACKEND=playwright` or `requests` and/or remove domain rules.

## 12. Risks & Mitigations

- Anti-bot escalation: Some sites may still block. Mitigate with Playwright fallback and conservative retries.
- Legal/compliance: Respect site terms and robots by default; provide config to require explicit override.
- Fingerprint drift: Update UA profiles and `impersonate` values periodically.
- Environment variance: Ensure behavior without `curl_cffi` remains correct; clear warnings when disabled.

## 13. Milestones & Success Criteria

### M1: Foundations (1-2 weeks)
- Modules scaffolded; UA profiles and router operational; unit tests passing.
- Success: Router selects handlers; curl backend fetch works in CI with mocks.

### M2: Integration (1-2 weeks)
- `scrape_article` routed; WebSearch providers use UA helper; example rules for Medium/Substack.
- Success: Improved success rate on selected domains (≥20% vs baseline); Playwright fallback intact.

### M3: Hardening & Docs (1 week)
- Metrics, docs, and example configs complete; coverage ≥80% on new code.
- Success: Performance gain (≥30% lower median latency for static pages), no regression in error rates.

## 14. Acceptance Criteria

- Optional curl backend integrated with impersonation and HTTP/2.
- Router-driven per-domain behavior with YAML overrides.
- Centralized UA spoofing; consistent headers in scraping and WebSearch.
- Egress guard enforced before any network.
- Playwright fallback reliable for JS-heavy pages.
- Tests and docs updated; example config provided.

## 15. Open Questions

- Robots policy defaults: enforce per environment (dev vs prod)?
- Proxy support: per-domain proxies in rule config?
- Cookie persistence: should domain sessions persist across runs or be ephemeral?
- Cache control: introduce local cache for static pages to reduce load?

## 16. Appendix

### A. Example Code Snippet (curl backend)
```python
from curl_cffi import requests as cfr
from tldw_Server_API.app.core.Web_Scraping.ua_profiles import build_browser_headers

headers = build_browser_headers(profile="chrome_120_win", accept_lang="en-US,en;q=0.9")
r = cfr.get(url, impersonate="chrome120", headers=headers, http2=True, timeout=15)
html = r.text
```

### B. Example YAML Rule
```yaml
domains:
  medium.com:
    backend: curl
    handler: tldw_Server_API.app.core.Web_Scraping.handlers:handle_generic_html
    ua_profile: chrome_120_win
    impersonate: chrome120
    extra_headers:
      Referer: https://www.google.com
```

## 17. Related Work

Sections on modular extraction strategies, LLM/block extraction, regex catalogs, clustering, and extended observability have been split into a dedicated document to keep this PRD focused on transport/UA/routing. See:

- Docs/Design/Extraction_Pipeline_PRD.md

## 19. Router YAML Schema (Short)

See full schema and examples in Docs/Design/Custom_Scrapers_Router.md. Allowed per-domain keys:
- `backend`: `auto|curl|httpx|playwright`
- `handler`: allowlisted import string
- `ua_profile`: e.g., `chrome_120_win`
- `impersonate`: e.g., `chrome120|safari17|firefox120`
- `extra_headers`: string map
- `cookies`: string map
- `respect_robots`: boolean
- `url_patterns`: list of regex strings
- `proxies`: string map for `http`/`https`

## 18. Implementation Status

Implemented (as of this update):
- UA/header builder with realistic browser headers and profile→impersonate mapping.
- Core HTTP client extended with `fetch()` supporting `curl_cffi` (impersonation, HTTP/2) and httpx fallback, plus header redaction and egress guard.
- Scraper Router with `ScrapePlan` (exact > wildcard > regex precedence), YAML loader, and handler import allowlist.
- Article fetch path updated to: resolve `ScrapePlan`, enforce robots.txt (fail-open if unreachable), try lightweight fetch first (curl/httpx) then fallback to Playwright; Playwright now uses centralized UA.
- WebSearch providers (Searx, Tavily) now use centralized UA builder instead of hard-coded User-Agent strings.
- Requirements updated to include `curl_cffi`, `brotli`, `zstandard`.
- Unit tests added: UA profiles/header shape, router precedence and allowlist, websearch header shape, robots enforcement behavior.
- Curl path non-blocking: lightweight fetch uses `asyncio.to_thread` to avoid blocking the event loop.
- Metrics instrumentation: counters/histograms for scrape fetch outcome and latency, plus fallback and robots-block events.
- Example rules file: `tldw_Server_API/Config_Files/custom_scrapers.example.yaml` added; YAML validation implemented in the router.

Remaining work (near-term):
- Async non-blocking integration for curl path in async contexts (wrap blocking fetch in `asyncio.to_thread` or provide async facade) to avoid event-loop blocking.
- Broaden WebSearch refactor: replace other hard-coded UAs across providers to use UA builder.
- Metrics: broaden instrumentation across all scraping paths and align names/labels with Metrics Manager conventions.
- Config surface: wire `WEB_SCRAPER_*` envs and config.txt to control UA mode (fixed/rotate), default backend, robots policy, and rule file path.
- Ship a default (disabled) `custom_scrapers.yaml` or clearly reference the example file and configuration steps in README/Docs.
- Proxy support (optional): per-domain proxies in rule config.
- JS-required detection heuristics beyond simple extraction-failure fallback (e.g., script density or known patterns) to trigger Playwright earlier.
- Ensure Accept-Encoding compatibility for code paths using `requests` (either switch to httpx/curl or manually decode br/zstd, or restrict accepted encodings there).

Out of scope (tracked separately; see Related Work):
- Modular extraction pipeline (schema/regex/LLM/cluster), PII masking, extended observability.
