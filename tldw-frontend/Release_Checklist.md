## tldw-frontend Release Checklist

This checklist covers frontend-only release readiness for the Next.js web UI. Use it as a living document and trim/expand based on the scope of the release.

---

## 1. Versioning & Metadata

- [ ] Bump the version in `tldw-frontend/package.json` and verify it matches any release notes or tags.
- [ ] Update `tldw-frontend/README.md` with user-visible changes and new setup steps.
- [ ] Ensure any new environment variables are documented in `tldw-frontend/README.md` (and `.env.example` if present).
- [ ] Confirm any UI-visible version strings or “What’s New” sections reflect the release notes.

---

## 2. Documentation Health

- [ ] Walk through the `tldw-frontend/README.md` setup from a clean clone (install → dev → build).
- [ ] Verify screenshots, feature lists, and links are current.
- [ ] Update any feature docs or audit notes (for example `tldw-frontend/FRONTEND_AUDIT.md`) to reflect major changes.

---

## 3. Code Review & Hygiene

- [ ] Remove debug code, temporary flags, and unused feature toggles.
- [ ] Ensure new components follow existing patterns for hooks, layout, and state management.
- [ ] Confirm types are explicit where needed and linting rules are satisfied.
- [ ] Review accessibility annotations (aria labels, focus states, keyboard navigation).
- [ ] Validate that client-only code is gated properly (no SSR/SSG errors in Next.js).

---

## 4. Build & Install

- [ ] Run `npm install` (or the project’s package manager) from `tldw-frontend/`.
- [ ] Run `npm run lint` (or the configured lint command) and address warnings.
- [ ] Run `npm run build` and confirm the build completes without warnings or errors.
- [ ] Start the production build (`npm run start`) and confirm pages load correctly.

---

## 5. Test Matrix (Frontend)

- [ ] Run unit tests (for example `npm run test` or `npx vitest run`) and confirm they pass.
- [ ] Confirm React Testing Library tests cover new UI flows and error states.
- [ ] If snapshots are used, review and update them intentionally.
- [ ] Verify critical pages (dashboard, chat, media library, settings) render without console errors.

---

## 6. Backend Integration

- [ ] Verify the frontend can authenticate against the current backend (single-user and multi-user if supported).
- [ ] Confirm API base URL configuration works in dev and prod (`NEXT_PUBLIC_API_URL`).
- [ ] Validate that common flows (search, chat, ingest, RAG features) still work against the current backend.
- [ ] Check for breaking changes in API schemas or routes and update UI accordingly.

---

## 7. Performance & UX

- [ ] Check Lighthouse or basic performance metrics for key pages.
- [ ] Verify large list/streaming views do not regress in performance.
- [ ] Confirm loading states, empty states, and error states are present and consistent.
- [ ] Validate mobile and tablet layouts for primary flows.

---

## 8. Accessibility & Visual QA

- [ ] Keyboard navigation works for primary flows (tabs, dialogs, dropdowns).
- [ ] Focus states are visible and consistent.
- [ ] Color contrast meets WCAG AA for critical UI elements.
- [ ] Verify that dialogs, toasts, and alerts are announced or discoverable for assistive tech.

---

## 9. Security & Privacy

- [ ] Ensure no secrets are exposed in client bundles (API keys, tokens).
- [ ] Validate auth token storage and logout flow.
- [ ] Confirm CSP / security headers (if managed at the frontend level) are intact.
- [ ] Review any new third-party dependencies for risk and license compatibility.

---

## 10. Release Hygiene

- [ ] Update `CHANGELOG.md` (if used for frontend releases) with UI changes and fixes.
- [ ] Close or update related issues/PRs and document known issues.
- [ ] Tag the release and verify artifacts in CI/CD outputs (if applicable).

---

### Using This Checklist

- Treat this as a guide, not a strict contract. Use a subset for small fixes.
- Keep it updated as the frontend grows and architecture changes.
