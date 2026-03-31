# End-to-End User Journey Audit — Design

**Date:** 2026-03-31
**Status:** Approved
**Scope:** Full user journey from install through watchlists/notifications/alerts
**Prior work:** PRs #938 and #944 addressed 46 FTUE onboarding issues

---

## Context

Comprehensive audit of the complete user journey identified 30 actionable issues across 6 phases, plus 7 deferred items requiring separate project design. Issues range from quick UI copy fixes (30 min) to multi-day notification infrastructure work.

## Summary

- **30 issues to implement** across 6 phases
- **7 items deferred** as separate projects (require backend design or new subsystems)
- **Estimated effort:** ~20 days total
- **1 P0** (notification bell), **14 P1**, **10 P2**, **5 P3**

## Phases

1. **Quick wins** (10 items, ~12 hours) — pure frontend, zero risk
2. **Post-onboarding LLM flow** (4 items, ~3 days) — provider setup CTAs, model refresh
3. **Chat UX** (4 items, ~3.5 days) — streaming indicator, error banners
4. **Watchlist onboarding** (2 items, ~3.5 days) — wizard surfacing, overview dashboard
5. **Notification infrastructure** (5 items, ~7 days) — bell, preferences, bridge, deep links
6. **Real-time updates** (2 items, ~2.5 days) — polling, WebSocket integration

## Deferred (separate projects)

- User-managed LLM provider keys (backend security design needed)
- Settings page tabbed refactor
- Extension notification infrastructure
- Watchlist-specific notification kinds
- Notification grouping/filtering
- Email/push delivery
- Alert rules/thresholds engine

Full issue list with file paths: see plan file.
