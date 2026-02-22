# M2 Release Note Template: Route Recoverability

Status: Active Template  
Owner: WebUI + QA  
Date: February 13, 2026  
Related Contract: `Docs/Product/Completed/WebUI-related/M2_Route_Error_Boundary_Contract_2026_02.md`

## 1) When to Use

Use this template whenever a release includes:

- New route-level error-boundary coverage
- Changes to fallback copy, actions, or recovery destinations
- Fixes for blank screens, runtime overlays, or broken redirect recovery

## 2) Release Notes Snippet (User-Facing)

Copy/paste and edit bracketed fields.

```markdown
### Web UI reliability and recovery improvements

- Added route-level recovery handling for [route list], so unexpected page errors now show a guided recovery panel instead of a blank screen.
- Standardized recovery actions: **Try again**, **Go to Chat**, **Open Settings**, and **Reload page**.
- Improved fallback behavior for [404/redirect/alias] states so navigation recovery is more predictable.

If you encounter a page error after updating:
1. Use **Try again** first.
2. If the issue persists, use **Open Settings** to verify server/auth configuration.
3. Use **Go to Chat** to continue core work while troubleshooting.
```

## 3) Operator/Support Addendum (Internal)

```markdown
### Troubleshooting links

- Route boundary contract and route coverage map:
  `Docs/Product/Completed/WebUI-related/M2_Route_Error_Boundary_Contract_2026_02.md`
- Latest route health snapshot and smoke evidence:
  `Docs/Product/Completed/WebUI-related/M1_4_Route_Health_Snapshot_2026_02_12.md`
- Wayfinding and keyboard recovery QA script:
  `Docs/Product/Completed/WebUI-related/M1_3_Wayfinding_Manual_QA_Script_2026_02.md`

### Verification evidence (attach command output)

- `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - Route Error Boundaries" --reporter=line`
- `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding|Route Error Boundaries)" --reporter=line`
```

## 4) Minimal QA Acceptance for Release Notes Claim

Before publishing release notes that mention route recoverability, verify:

- The route-boundary smoke slice is green.
- Combined key-nav + wayfinding + route-boundary slice is green.
- At least one screenshot or artifact is attached for the changed route set.

## 5) Example (Filled)

```markdown
### Web UI reliability and recovery improvements

- Added route-level recovery handling for Collections, World Books, Dictionaries, Characters, Items, Document Workspace, and Speech Playground.
- Standardized recovery actions: Try again, Go to Chat, Open Settings, and Reload page.
- Expanded forced-error smoke coverage to verify recovery contract on 15 non-core routes.
```
