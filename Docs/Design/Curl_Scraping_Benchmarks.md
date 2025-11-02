# Curl Scraping Benchmarks

Status: In Progress

This guide describes a repeatable methodology to measure scraping performance and success rates for the curl/httpx lightweight path versus Playwright fallback.

## Goals

- p50 and p95 latency: curl path ≥30% faster than Playwright on static pages
- Success rate: No regression vs Playwright on static pages
- Fallback rate: <20% on a representative corpus

## Corpus

- Static pages (50-100): Medium, Substack, and typical blogs/news articles
- JS-heavy pages (20): Sites known to require rendering (client-side apps, heavy paywalls)
- Provide a `urls.txt` file listing one URL per line, grouped by category for reporting

## Metrics Collected

- scrape_fetch_latency_seconds{backend} histogram (exported via Metrics Manager)
- scrape_fetch_total{backend,outcome}
- scrape_playwright_fallback_total{reason}
- article_extracted{success,url}

## Procedure

1. Warm up the server.
2. For each URL:
   - Perform N=3 curl/httpx fetch attempts (cold) and record latencies.
   - Perform 1 Playwright fetch (baseline) and record latency.
3. Derive p50/p95 per category and global.
4. Calculate fallback rate and extraction success rates.
5. Record results as CSV and plot if desired.

## Script Outline

See `Helper_Scripts/benchmarks/curl_scrape_benchmark.py` for an executable outline.

## Reporting

- Store CSV outputs in `Docs/Design/benchmarks/` with timestamped filenames
- Summarize p50/p95, fallback rate, and success rate in a short README per run
