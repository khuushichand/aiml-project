## admin-ui Release Checklist

This checklist covers release readiness for the admin UI (Next.js). Treat it as a living document and trim/expand based on scope.

---

## 1. Versioning & Metadata

- [ ] Bump the version in `admin-ui/package.json` and confirm release tags/notes match.
- [ ] Update `admin-ui/README.md` with user-visible changes and setup steps.
- [ ] Document new environment variables in `admin-ui/README.md` (and `.env.example` if present).
- [ ] Verify any UI-visible version strings or “What’s New” notes are current.

---

## 2. Documentation Health

- [ ] Walk through the `admin-ui/README.md` setup from a clean clone (install → dev → build).
- [ ] Verify screenshots, feature lists, and links are current.
- [ ] Update any admin UI notes or audit docs to reflect major changes.

---

## 3. Code Review & Hygiene

- [ ] Remove debug code, temporary flags, and unused feature toggles.
- [ ] Ensure components follow existing patterns for hooks, layout, and state handling.
- [ ] Confirm type coverage and lint rules are satisfied.
- [ ] Review accessibility annotations (aria labels, focus states, keyboard navigation).
- [ ] Validate client-only code is gated appropriately for Next.js.

---

## 4. Build & Install

- [ ] Run `npm install` (or the chosen package manager) from `admin-ui/`.
- [ ] Run `npm run lint` and address warnings.
- [ ] Run `npm run build` and confirm the build completes without errors.
- [ ] Start the production build (`npm run start`) and confirm pages load correctly.

---

## 5. Test Matrix (Frontend)

- [ ] Run unit tests (for example `npx vitest run` or configured test script).
- [ ] Confirm React Testing Library coverage for new UI flows and error states.
- [ ] If snapshots are used, review and update them intentionally.
- [ ] Verify key pages (dashboard, monitoring, auth/config views) render without console errors.

---

## 6. Backend Integration

- [ ] Verify admin auth and role gating against the current backend (single-user and multi-user if supported).
- [ ] Confirm API base URL configuration works in dev and prod (`NEXT_PUBLIC_API_URL`).
- [ ] Validate common admin flows (users, orgs, teams, monitoring) against the backend.
- [ ] Check for breaking changes in API schemas or routes and update UI accordingly.

---

## 7. Performance & UX

- [ ] Check Lighthouse or basic performance metrics for key pages.
- [ ] Verify tables/lists scale without regressions.
- [ ] Confirm loading, empty, and error states are consistent.
- [ ] Validate mobile and tablet layouts for primary flows.

---

## 8. Accessibility & Visual QA

- [ ] Keyboard navigation works for primary flows (tabs, dialogs, dropdowns).
- [ ] Focus states are visible and consistent.
- [ ] Color contrast meets WCAG AA for critical UI elements.
- [ ] Verify dialogs, toasts, and alerts are accessible.

---

## 9. Security & Privacy

- [ ] Ensure no secrets are exposed in client bundles (API keys, tokens).
- [ ] Validate auth token storage and logout flow.
- [ ] Confirm security headers (if managed at the frontend level) are intact.
- [ ] Review any new third-party dependencies for risk and license compatibility.

---

## 10. Release Hygiene

- [ ] Update changelog/release notes with UI changes and fixes.
- [ ] Close or update related issues/PRs and document known issues.
- [ ] Tag the release and verify CI/CD artifacts (if applicable).

---

### Using This Checklist

- Use a subset for small fixes and expand for major releases.
- Keep the checklist current as the admin UI evolves.
