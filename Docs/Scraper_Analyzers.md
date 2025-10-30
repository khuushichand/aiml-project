# Scraper Analyzers

This repository now exposes a reusable collection of anti-bot analyzers that were
ported from the open-source `caniscrape` project.  They help you profile a target
domain before running a scraper by checking for JavaScript rendering, CAPTCHAs,
rate limits, WAFs, and TLS fingerprinting.

## Installation

The analyzers rely on optional dependencies.  Install them with extras when you
need the feature set:

```bash
pip install ".[scrape-analyzers]"
# Optional wafw00f support
pip install ".[scrape-analyzers-waf]"
# Playwright requires browser binaries
playwright install chromium
```

If you prefer using the wafw00f CLI through pipx:

```bash
python -m pip install --user pipx
pipx install wafw00f
```

## Quick Start

```python
from tldw_Server_API.app.core.Web_Scraping.scraper_analyzers import run_analysis

result = run_analysis(
    "https://example.com",
    find_all=False,  # pass True to use `wafw00f -a`
    impersonate=True,  # use curl_cffi impersonation for rate-limit checks
    scan_depth="thorough",  # honeypot scan depth: default|thorough|deep
)

print(result["score"])  # {'score': 3, 'label': 'Medium'}
print(result["recommendations"])  # {'tools': [...], 'strategy': [...]}
```

For async environments (e.g. FastAPI handlers) import `gather_analysis` and
await it directly:

```python
from tldw_Server_API.app.core.Web_Scraping.scraper_analyzers import gather_analysis

analysis = await gather_analysis("https://example.com")
```

## Error Handling

Every analyzer returns a dictionary with a `status` key.  When optional
dependencies are missing you will receive an `error_code` set to
`missing_dependency` and a human-readable message.  The orchestrator preserves
those payloads so callers can gracefully degrade or surface actionable guidance
to operators.
