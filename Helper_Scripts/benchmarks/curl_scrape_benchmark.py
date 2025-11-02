#!/usr/bin/env python3
"""
curl_scrape_benchmark.py - quick benchmarking harness for curl/httpx vs Playwright

Usage:
  python Helper_Scripts/benchmarks/curl_scrape_benchmark.py urls.txt --runs 3 --timeout 15

Notes:
- Requires the tldw_Server_API package environment (dependencies installed).
- This script exercises the internal fetch path and measures latency.
- Results are printed as CSV and can be redirected to a file for analysis.
"""
from __future__ import annotations

import argparse
import time
import sys
from typing import List, Dict

from tldw_Server_API.app.core.Web_Scraping.ua_profiles import build_browser_headers, pick_ua_profile
from tldw_Server_API.app.core.http_client import fetch as http_fetch


def load_urls(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]


def bench_curl(url: str, headers: Dict[str, str], runs: int, timeout: float) -> List[float]:
    lat = []
    for _ in range(runs):
        t0 = time.time()
        try:
            http_fetch(url, method="GET", headers=headers, backend="curl", http2=True, timeout=timeout, allow_redirects=True)
        except Exception:
            pass
        lat.append(max(0.0, time.time() - t0))
    return lat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url_file", help="Text file with one URL per line")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()

    urls = load_urls(args.url_file)
    if not urls:
        print("No URLs loaded", file=sys.stderr)
        sys.exit(1)

    profile = pick_ua_profile("fixed")
    headers = build_browser_headers(profile, accept_lang="en-US,en;q=0.9")

    print("url,backend,run,latency_seconds")
    for url in urls:
        lats = bench_curl(url, headers, args.runs, args.timeout)
        for i, v in enumerate(lats, 1):
            print(f"{url},curl,{i},{v:.6f}")

        # Note: Playwright timing can be added in a separate script or integrated here
        # via direct usage of playwright. Kept out to avoid requiring browser downloads here.

if __name__ == "__main__":
    main()
