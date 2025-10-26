# Custom Scrapers Router

Status: In Progress

This document describes the YAML schema and usage for the per-domain scraper router. The router selects a fetch backend, handler, and headers on a per-domain basis and feeds that into the article scraping pipeline.

File locations:
- Config: `tldw_Server_API/Config_Files/custom_scrapers.yaml` (user-managed)
- Example: `tldw_Server_API/Config_Files/custom_scrapers.example.yaml`

The router validates and normalizes the YAML at load time. Unknown keys are dropped; invalid regex patterns are ignored.

## YAML Schema

Top-level keys:
- `domains` (object): Mapping of domain or wildcard domain to rule.

Rule keys (per domain):

| Key             | Type            | Example                                                         | Notes |
|-----------------|-----------------|-----------------------------------------------------------------|-------|
| `backend`       | string          | `curl`, `httpx`, `playwright`, `auto`                           | Default `auto`. `curl` uses curl_cffi impersonation when available. |
| `handler`       | string          | `tldw_Server_API.app.core.Web_Scraping.handlers:handle_generic_html` | Must begin with an allowlisted module prefix. Unknown handlers fallback to safe default. |
| `ua_profile`    | string          | `chrome_120_win`                                                | Maps to UA + sec-ch-ua* headers and Accept-Language/Sec-Fetch-*. |
| `impersonate`   | string          | `chrome120`, `safari17`, `firefox120`                           | Used by curl_cffi; defaults to mapping for `ua_profile`. |
| `extra_headers` | object<string>  | `{ Referer: https://www.google.com }`                           | Merged into base headers built from UA profile. |
| `cookies`       | object<string>  | `{ sessionid: abc123 }`                                         | Simple name→value cookie map. |
| `respect_robots`| boolean         | `true`                                                          | Default `true`. If `false`, robots.txt is not enforced. |
| `url_patterns`  | array<string>   | `[".*\\?output=1$"]`                                          | Regex patterns to further scope the rule; all non-compiling patterns are ignored. |
| `proxies`       | object<string>  | `{ http: http://localhost:8080, https: http://localhost:8080 }`| Per-domain proxies passed to the fetch client. |

Domains may be:
- Exact, e.g., `example.com`
- Wildcard, e.g., `*.example.com` (applies to subdomains)

Precedence:
1. Exact domain
2. Wildcard (longest suffix wins)
3. Regex `url_patterns` within the matched domain rule

If no rule matches, defaults are used: `backend=auto`, a safe generic handler, and default UA profile.

## Enabling and Editing

1. Copy the example file:
   - `cp tldw_Server_API/Config_Files/custom_scrapers.example.yaml tldw_Server_API/Config_Files/custom_scrapers.yaml`
2. Edit `custom_scrapers.yaml` and add/modify your domains.
3. Restart the server to reload configs if running in production mode.

## Security

- Handler import strings must start with an allowlisted package prefix; otherwise they are ignored.
- Egress/SSRF policy is enforced before any outbound connection.
- Robots.txt is enforced by default. You can set `respect_robots: false` per domain with explicit acknowledgement of policy.

## config.txt example (Web-Scraper section)

Place in `tldw_Server_API/Config_Files/config.txt` under the `[Web-Scraper]` section:

```
[Web-Scraper]
# Optional: override path to router YAML
custom_scrapers_yaml_path = tldw_Server_API/Config_Files/custom_scrapers.yaml

# Default backend for 'auto' rules: auto|curl|httpx|playwright
web_scraper_default_backend = auto

# UA profile selection mode: fixed|rotate
web_scraper_ua_mode = fixed

# Enforce robots by default (per-rule overrides allowed)
web_scraper_respect_robots = True

# Existing keys (for reference)
web_scraper_retry_count = 3
web_scraper_retry_timeout = 60
web_scraper_stealth_playwright = False
```
