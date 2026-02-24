## Summary

- What changed:
- Why:

## Validation

- [ ] Tests added/updated for behavior changes
- [ ] Relevant unit/integration tests pass locally
- [ ] Docs updated (if behavior, routes, or config changed)

## UX Audit Checklist (v2 Stage 5)

- [ ] `npm run e2e:smoke:stage5` passes
- [ ] `npx playwright test e2e/smoke/all-pages.spec.ts --reporter=line` passes (or failures documented)
- [ ] No listed AntD deprecations in console output: `Drawer.width`, `Space.direction`, `Alert.message`, `List`
- [ ] No `Maximum update depth exceeded` warnings on audited routes
- [ ] No unresolved `{{...}}` placeholders on audited routes
- [ ] WebUI/extension parity validated for shared UI fixes
- [ ] For Flashcards UI changes: tabs remain `Study` / `Manage` / `Transfer` and secondary create CTAs route through manager create-entry path
- [ ] For Flashcards drawer changes: use `FLASHCARDS_DRAWER_WIDTH_PX` and keep footer action order `Cancel -> secondary -> primary`
- [ ] For Flashcards help/copy/import UX changes: update `Docs/User_Guides/Flashcards_Study_Guide.md` and keep in-app help links pointed at guide section anchors

## Watchlists Accessibility Checklist (Group 09 Stage 5)

- [ ] If Watchlists UI behavior changed: `cd apps/packages/ui && bun run test:watchlists:a11y` passes locally
- [ ] If Watchlists UI behavior changed: keyboard-only path still works for Overview -> Feeds -> Monitors -> Activity -> Articles -> Reports
- [ ] If Watchlists UI behavior changed: list/table labels and live-region copy remain localized (no new hardcoded assistive text)
- [ ] If Watchlists UI behavior changed: monitor/feed active state is not color-only (explicit text or icon signal is present)
- [ ] If Watchlists UI behavior changed: known assistive-tech constraints reviewed in `Docs/Plans/WATCHLISTS_ASSISTIVE_TECH_AUDIT_2026_02_24.md`

## Risk & Rollback

- Risk level: Low / Medium / High
- Rollback plan:
