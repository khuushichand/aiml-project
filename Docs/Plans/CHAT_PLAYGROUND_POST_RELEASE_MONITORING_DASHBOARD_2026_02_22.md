# Chat Playground Post-Release Monitoring Dashboard (2026-02-22)

## Objective

Track adoption and regression signals for the chat-page UX remediation set during the 30-day stabilization window.

## Owners

- Product owner: Chat UX lead
- Engineering owner: WebUI maintainers
- QA owner: Frontend UX gate maintainers

## Adoption Signals

| Metric | Source | Target | Alert Condition |
|---|---|---|---|
| Starter mode activation rate (`compare`, `character`, `rag`, `voice`) | `tldw:playground-starter-selected` event stream | Increase from baseline week | Any mode drops below 50% of baseline for 3 days |
| Compare continuation completion | compare flow telemetry + branch return events | Stable or improving | >15% week-over-week drop |
| Share-link usage with TTL | share-link create/revoke logs | Stable growth | 0 create events for 7 days after release |
| Template usage before first send | startup template apply events | Increasing trend | >20% week-over-week drop |

## Regression Signals

| Metric | Source | Target | Alert Condition |
|---|---|---|---|
| Composer misconfiguration warnings per send | composer conflict signals | Non-increasing | >25% spike over 7-day average |
| Stream failure recovery success | error-recovery action completion | Stable | >10% drop in retry success |
| Accessibility gate pass rate | `ui-playground-quality-gates.yml` | 100% on protected branches | Any CI accessibility gate failure |
| Device matrix gate pass rate | `ui-playground-quality-gates.yml` | 100% on protected branches | Any device-matrix gate failure |
| Share-role contract tests | `Header.share-links.integration.test.tsx` | 100% | Any failing run |

## Operational Views

- CI view:
  - `.github/workflows/ui-playground-quality-gates.yml`
- Plan/evidence view:
  - `Docs/Plans/CHAT_PLAYGROUND_FINDING_EVIDENCE_LEDGER_2026_02_22.md`
  - group implementation plan files (`Group 01` through `Group 08`)
- QA checklists:
  - composer, device matrix, accessibility, discoverability, share/automation artifacts in `Docs/Plans/`

## Release Gate Commands

```bash
bun run test:playground:composer --reporter=dot
bun run test:playground:device-matrix --reporter=dot
bun run test:playground:a11y --reporter=dot
bunx vitest run src/components/Layouts/__tests__/chat-share-links.test.ts src/components/Layouts/__tests__/Header.share-links.integration.test.tsx --reporter=dot
```

## 30-Day Checkpoint Cadence

1. Daily: gate failures triage + rollback risk assessment.
2. Weekly: adoption trend review and threshold tuning.
3. Day 30: stabilization closeout and ownership handoff to routine monitoring.
