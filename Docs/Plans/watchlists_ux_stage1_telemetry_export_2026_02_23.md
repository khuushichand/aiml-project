# Watchlists UX Stage 1 Telemetry Export (2026-02-23)

**Generated at (UTC):** 2026-02-23T05:39:25.048720+00:00

## Dataset

- Source scan: `Databases/**/Media_DB_v2.db`
- Database files scanned: `91`
- Active watchlists users (derived): `71`

## Funnel Baselines

| Funnel Metric | Numerator | Denominator | Percent / Value |
|---|---:|---:|---:|
| UC1-F1 First source setup | 66 | 71 | 92.96% |
| UC1-F2 Time-to-first-review (median) | n/a | samples=1 | 567.49s (0.16h) |
| UC1-F3 Triage completion (>=20/day) | 0 | 2 | 0.00% |
| UC2-F1 Pipeline completion (source->job->run) | 38 | 67 | 56.72% |
| UC2-F2 Text output success | 2 | 3182 completed runs | 0.06% |
| UC2-F3 Audio output success | 1 | 3182 completed runs | 0.03% |

## Export Method

- First-session proxy: source setup within 24 hours of first watchlists activity timestamp in each database snapshot.
- Review signal: `content_items.read_at` preferred; `scraped_items.reviewed` with `created_at` fallback.
- Text/audio classification: `outputs.type`, `outputs.format`, and `outputs.storage_path` extension.
- Run success baseline: `scrape_runs.status` in `{completed, succeeded, success, done, finished}`.

## Raw Local Export Artifacts

These were generated during Stage 1 and used to compute the values above:

- `Docs/Plans/watchlists_ux_stage1_telemetry_export_raw_2026_02_23.csv` (ignored by repo rules)
- `Docs/Plans/watchlists_ux_stage1_telemetry_export_summary_2026_02_23.json` (ignored by repo rules)
