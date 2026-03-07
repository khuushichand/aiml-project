# Autonomous UX Audit Prompt for tldw WebUI

> **Usage**: Paste this entire file as a prompt to Claude Code (or Codex) with both the backend (`:8000`) and frontend (`:8080`) servers running. The agent will autonomously collect data, analyze every route, and produce a structured report.

---

## 1. Role & Mission

You are a **Senior UX/Design Professional** with 15+ years of experience auditing complex web applications. Your specialty is research-oriented developer tools and data-heavy dashboards.

**Your mission**: Perform a comprehensive, autonomous UX audit of the **tldw WebUI** (a Next.js research assistant application) by:

1. Writing and running a Playwright data-collection script that captures screenshots and diagnostics for every route
2. Analyzing every screenshot against established UX heuristics, accessibility standards, and visual design principles
3. Producing a structured audit report with prioritized findings and actionable recommendations

**Delta awareness**: Previous UX audit baseline artifacts are:
- `Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_cross_cutting_stage1_route_matrix_baseline_v2.md`
- `Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_overarching_program_oversight_v2_2026_02_16.md`
- `Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_ux_audit_cross_cutting_themes_v2.md`
Read these before starting. Your report must note which v2 issues are **resolved**, **regressed**, or **unchanged**, and flag any **new** issues.

**Autonomy**: Complete this entire audit in a single session with zero manual intervention. If a route times out or crashes, log it and continue.

---

## 2. Technical Setup

### 2.1 Prerequisites

Both servers must already be running:

| Service | URL | Verify |
|---------|-----|--------|
| Backend (FastAPI) | `http://127.0.0.1:8000` | `curl http://127.0.0.1:8000/api/v1/health` |
| Frontend (Next.js) | `http://localhost:8080` | `curl http://localhost:8080` |

### 2.2 Output Directory

Create this structure inside `apps/tldw-frontend/`:

```
ux-audit-v3/
  screenshots/          # All PNGs: {route-slug}_{viewport}_{theme}.png
  data/                 # Per-route JSON diagnostics
  report.md             # Final audit report
```

### 2.3 Existing Infrastructure to Import

The project has mature Playwright infrastructure. **Do not rebuild from scratch** — import from these files:

| File | What to Import |
|------|----------------|
| `e2e/smoke/page-inventory.ts` | `PAGES` array (72 routes with categories), `getActivePages()` |
| `e2e/utils/helpers.ts` | `seedAuth()`, `dismissModals()`, `BENIGN_PATTERNS`, `isBenign()`, `waitForNetworkIdle()`, `TEST_CONFIG` |
| `e2e/smoke/smoke.setup.ts` | `DiagnosticsData` interface, `SMOKE_HARD_GATE_ALLOWLIST`, `classifySmokeIssues()`, `getCriticalIssues()` |
| `e2e/utils/fixtures.ts` | `WorkflowFixtures`, `authedPage` fixture pattern |

### 2.4 Auth Seeding

Use the existing `seedAuth()` function from `e2e/utils/helpers.ts`. It sets:

```js
localStorage.setItem("tldwConfig", JSON.stringify({
  serverUrl: "http://127.0.0.1:8000",
  authMode: "single-user",
}));
localStorage.setItem("__tldw_first_run_complete", "true");
localStorage.setItem("__tldw_allow_offline", "true");
```

This must be called via `page.addInitScript()` **before** navigating to any route.

---

## 3. Phase 1 — Data Collection Script

Create the file `apps/tldw-frontend/e2e/ux-audit/audit-v3.spec.ts`.

### 3.1 Route List

Import `PAGES` from `../smoke/page-inventory` (72 routes), then **append** these 11 additional routes that exist as page files but are missing from the inventory:

```typescript
const EXTRA_ROUTES: PageEntry[] = [
  { path: "/settings/guardian", name: "Guardian Settings", category: "settings" },
  { path: "/settings/splash", name: "Splash Settings", category: "settings" },
  { path: "/workspace-playground", name: "Workspace Playground", category: "workspace" },
  { path: "/document-workspace", name: "Document Workspace", category: "workspace" },
  { path: "/workflow-editor", name: "Workflow Editor", category: "workspace" },
  { path: "/audiobook-studio", name: "Audiobook Studio", category: "audio" },
  { path: "/model-playground", name: "Model Playground", category: "workspace" },
  { path: "/writing-playground", name: "Writing Playground", category: "workspace" },
  { path: "/acp-playground", name: "ACP Playground", category: "workspace" },
  { path: "/skills", name: "Skills", category: "workspace" },
  { path: "/chatbooks-playground", name: "Chatbooks Playground", category: "workspace" },
];

const ALL_ROUTES = [...PAGES, ...EXTRA_ROUTES]; // 83 routes
```

### 3.2 Screenshot Matrix

For each route, capture **4 screenshots** (2 viewports x 2 themes):

| Viewport | Width x Height | Label |
|----------|---------------|-------|
| Desktop | 1440 x 900 | `desktop` |
| Mobile | 375 x 812 | `mobile` |

| Theme | How to Toggle | Label |
|-------|--------------|-------|
| Light | `document.documentElement.classList.remove('dark')` | `light` |
| Dark | `document.documentElement.classList.add('dark')` | `dark` |

The project uses `darkMode: "class"` in Tailwind config, so toggling the `.dark` class on `<html>` is sufficient.

**File naming**: `{route-slug}_{viewport}_{theme}.png`
- Route slug: replace `/` with `-`, strip leading `-`, e.g. `/settings/rag` → `settings-rag`
- Example: `settings-rag_desktop_dark.png`

**Screenshot settings**: `fullPage: true` to capture below-the-fold content.

### 3.3 Per-Route Diagnostics

For each route, collect and save a JSON file at `ux-audit-v3/data/{route-slug}.json`:

```typescript
interface RouteAuditData {
  route: string;
  name: string;
  category: string;
  timestamp: string;
  // Navigation
  finalUrl: string;
  redirected: boolean;
  httpStatus: number | null;
  loadTimeMs: number;
  // Screenshots captured
  screenshots: string[];
  // Diagnostics (use DiagnosticsData pattern from smoke.setup.ts)
  consoleErrors: Array<{ type: string; text: string }>;
  pageErrors: Array<{ message: string }>;
  requestFailures: Array<{ url: string; errorText: string }>;
  // Filtered through allowlist
  unexpectedErrors: number;
  allowlistedErrors: number;
  // Performance
  performanceMetrics: {
    domContentLoaded: number;
    firstPaint: number | null;
    largestContentfulPaint: number | null;
  };
  // Accessibility quick-check
  ariaLandmarks: number;
  headingStructure: string[];   // e.g. ["h1", "h2", "h2", "h3"]
  imagesWithoutAlt: number;
  focusableElements: number;
}
```

### 3.4 Script Logic (Pseudocode)

```typescript
import { test } from '@playwright/test';
import { PAGES, type PageEntry } from '../smoke/page-inventory';
import { seedAuth, dismissModals, waitForNetworkIdle, isBenign } from '../utils/helpers';
import { SMOKE_HARD_GATE_ALLOWLIST, classifySmokeIssues, getCriticalIssues } from '../smoke/smoke.setup';
import * as fs from 'fs';
import * as path from 'path';

// Merge inventory + extra routes
const ALL_ROUTES = [...PAGES, ...EXTRA_ROUTES];

// Output dirs
const SCREENSHOT_DIR = path.resolve(__dirname, '../../ux-audit-v3/screenshots');
const DATA_DIR = path.resolve(__dirname, '../../ux-audit-v3/data');

test.beforeAll(() => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  fs.mkdirSync(DATA_DIR, { recursive: true });
});

for (const route of ALL_ROUTES) {
  test(`audit: ${route.name} (${route.path})`, async ({ page }) => {
    // 1. Seed auth
    await seedAuth(page);

    // 2. Set up diagnostics collection (console, pageError, requestFailed listeners)
    const diagnostics = collectDiagnostics(page);

    // 3. Navigate with timing
    const startTime = Date.now();
    const response = await page.goto(`http://localhost:8080${route.path}`, {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    });
    await waitForNetworkIdle(page, 10_000);
    const loadTimeMs = Date.now() - startTime;

    // 4. Dismiss error overlays
    await dismissModals(page);
    // Also dismiss chrome.storage.local overlay if present
    await dismissChromeStorageOverlay(page);

    // 5. Capture 4 screenshots (desktop-light, desktop-dark, mobile-light, mobile-dark)
    for (const viewport of VIEWPORTS) {
      await page.setViewportSize(viewport.size);
      for (const theme of THEMES) {
        await page.evaluate(theme.apply);
        await page.waitForTimeout(300); // Let CSS transitions settle
        const slug = routeSlug(route.path);
        const filename = `${slug}_${viewport.label}_${theme.label}.png`;
        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, filename),
          fullPage: true,
        });
      }
    }

    // 6. Collect performance metrics
    const perfMetrics = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      const paint = performance.getEntriesByType('paint');
      const lcp = performance.getEntriesByType('largest-contentful-paint');
      return {
        domContentLoaded: nav?.domContentLoadedEventEnd ?? 0,
        firstPaint: paint.find(e => e.name === 'first-paint')?.startTime ?? null,
        largestContentfulPaint: lcp.length ? lcp[lcp.length - 1].startTime : null,
      };
    });

    // 7. Collect accessibility quick-check
    const a11y = await page.evaluate(() => ({
      ariaLandmarks: document.querySelectorAll('[role="main"],[role="navigation"],[role="banner"],[role="contentinfo"],main,nav,header,footer').length,
      headingStructure: Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6')).map(h => h.tagName.toLowerCase()),
      imagesWithoutAlt: document.querySelectorAll('img:not([alt])').length,
      focusableElements: document.querySelectorAll('a[href],button,input,select,textarea,[tabindex]').length,
    }));

    // 8. Save diagnostics JSON
    const auditData: RouteAuditData = {
      route: route.path,
      name: route.name,
      category: route.category,
      timestamp: new Date().toISOString(),
      finalUrl: page.url(),
      redirected: !page.url().includes(route.path),
      httpStatus: response?.status() ?? null,
      loadTimeMs,
      screenshots: [...captured filenames],
      consoleErrors: diagnostics.console.filter(c => c.type === 'error'),
      pageErrors: diagnostics.pageErrors,
      requestFailures: diagnostics.requestFailures,
      unexpectedErrors: classifySmokeIssues(route.path, getCriticalIssues(diagnostics)).unexpectedConsoleErrors.length,
      allowlistedErrors: classifySmokeIssues(route.path, getCriticalIssues(diagnostics)).allowlistedConsoleErrors.length,
      performanceMetrics: perfMetrics,
      ...a11y,
    };
    fs.writeFileSync(
      path.join(DATA_DIR, `${routeSlug(route.path)}.json`),
      JSON.stringify(auditData, null, 2)
    );
  });
}
```

### 3.5 Edge Cases to Handle

| Scenario | Handling |
|----------|---------|
| `/content-review`, `/claims-review` | Known infinite re-render loops — use 10s timeout, capture whatever renders |
| `chrome.storage.local` error overlay | After `dismissModals()`, also check for `.ant-notification` or error boundary div and click dismiss |
| Routes returning 404 | Still capture screenshot (the 404 page itself is part of the audit), log in diagnostics |
| Redirect routes (e.g. `/search` → `/knowledge`) | Record `redirected: true` and `finalUrl`, capture screenshots of the destination |
| Routes that timeout | Catch error, save partial diagnostics, set `httpStatus: null`, continue to next route |

### 3.6 Running the Script

```bash
cd apps/tldw-frontend

# Set env to prevent auto-starting the dev server (it's already running)
TLDW_WEB_AUTOSTART=false npx playwright test e2e/ux-audit/audit-v3.spec.ts \
  --project=chromium \
  --timeout=120000 \
  --reporter=list \
  --workers=1
```

Use `--workers=1` to avoid race conditions on viewport/theme toggling and to produce sequential console output for debugging.

After the script completes, verify:
- `ux-audit-v3/screenshots/` contains ~332 PNG files (83 routes x 4 screenshots, minus any timeouts)
- `ux-audit-v3/data/` contains ~83 JSON files

---

## 4. Navigation Protocol

### 4.1 Route Discovery

The script already covers 83 known routes. After running it, perform a **sidebar link extraction** to catch any routes not in the inventory:

```typescript
// Navigate to home, expand all sidebar sections, extract hrefs
const sidebarLinks = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('nav a, aside a, [data-testid*="sidebar"] a'))
    .map(a => (a as HTMLAnchorElement).pathname)
    .filter((v, i, arr) => arr.indexOf(v) === i);
});
```

Compare `sidebarLinks` against `ALL_ROUTES` paths. If any new routes are found, visit and screenshot them as well.

### 4.2 Key User Flows to Evaluate

Beyond per-route screenshots, evaluate these critical workflows for coherence and usability:

1. **First-run onboarding**: `/setup` → server config → first chat
2. **Media ingestion**: URL input → processing → appears in library → view detail
3. **Search & RAG**: Enter query → results displayed → open result → RAG context shown
4. **Chat interaction**: Send message → response streams → conversation history persists
5. **Character chat**: Select character → start session → multi-turn conversation
6. **Notes workflow**: Create note → edit → search notes
7. **Settings navigation**: Sidebar navigation between 20+ settings sub-pages
8. **Admin dashboard**: Admin landing → sub-pages → server stats

### 4.3 State Variations to Capture

Where possible, note the behavior of:
- **Empty states**: Pages with no data (first-run appearance)
- **Error states**: What happens when backend returns 500 or is unreachable
- **Loading states**: Skeleton loaders, spinners — do they resolve or hang?
- **Overflow**: Long text, many items in lists, wide tables on mobile

---

## 5. Evaluation Framework

### 5.1 Nielsen's Heuristics + Modern Additions

Score each heuristic 1-5 (1 = critical failures, 5 = exemplary) across the application:

| # | Heuristic | What to Evaluate |
|---|-----------|-----------------|
| H1 | Visibility of system status | Loading indicators, progress bars, connection status, save confirmations |
| H2 | Match between system and real world | Terminology, icons, mental models — appropriate for technical/research audience? |
| H3 | User control and freedom | Undo, cancel, back navigation, escape from modals, destructive action guards |
| H4 | Consistency and standards | Component patterns, naming conventions, layout grids across pages |
| H5 | Error prevention | Form validation, confirmation dialogs, input constraints |
| H6 | Recognition rather than recall | Labels, tooltips, breadcrumbs, contextual help |
| H7 | Flexibility and efficiency | Keyboard shortcuts, bulk actions, power-user features |
| H8 | Aesthetic and minimalist design | Visual noise, information density, whitespace usage |
| H9 | Help users recognize and recover from errors | Error message clarity, recovery paths, retry options |
| H10 | Help and documentation | Inline help, tooltips, `/documentation` page quality |
| H11 | **Accessibility** (WCAG 2.2 AA) | Color contrast, keyboard navigation, screen reader support, focus indicators |
| H12 | **Responsive design** | Mobile usability, touch targets, layout adaptation, readable text at all sizes |
| H13 | **Performance perception** | Perceived speed, skeleton loaders vs spinners, optimistic updates |

### 5.2 Visual Design Review

Evaluate against the project's design system:

**Typography**:
- Body font: Inter (14px/20px)
- Display font: Space Grotesk
- Monospace: Arimo
- Check: consistent usage, hierarchy, readability

**Color System** (CSS custom properties):
- Light theme: warm parchment bg (`244 242 238`), white surfaces, blue primary (`47 111 237`), teal accent (`31 181 159`)
- Dark theme: deep charcoal bg (`15 17 19`), dark surfaces, bright blue primary (`92 141 255`), mint accent (`79 209 176`)
- Check: sufficient contrast ratios (4.5:1 for text, 3:1 for UI), consistent token usage, no raw hex values bypassing the system

**Component Library**: Ant Design 6.x with Tailwind utilities
- Check: consistent use of AntD components vs custom implementations, theme token adherence

**Spacing & Layout**:
- Check: consistent padding/margins, grid alignment, responsive breakpoints

**Iconography**: Lucide icons + Heroicons
- Check: consistent icon style, appropriate sizing, meaningful labels

### 5.3 Information Architecture

- Is the sidebar navigation logical and well-organized?
- Are related features grouped sensibly?
- Can users find what they need within 3 clicks?
- Is the hierarchy clear (categories → subcategories → items)?

### 5.4 Severity Scale

| Level | Name | Definition |
|-------|------|------------|
| 0 | Not a problem | No usability issue detected |
| 1 | Cosmetic | Minor visual inconsistency, fix only if time permits |
| 2 | Minor | Causes slight confusion or extra steps, but user can complete task |
| 3 | Major | Significantly impairs usability, workarounds exist but are non-obvious |
| 4 | Catastrophic | Prevents task completion, blocks critical user flow, or causes data loss |

---

## 6. Report Output Format

Write the report to `ux-audit-v3/report.md` with exactly these 9 sections:

### Section 1: Executive Summary

- Total routes tested, screenshots captured, date, methodology
- Overall health score (1-10)
- Top 5 critical issues (table: issue, severity, impact)
- **Delta vs v2**: Issues resolved, issues regressed, new issues found
- Key metrics comparison table (v2 vs v3)

### Section 2: Sitemap & Flow Inventory

- Complete route table: path, name, category, status (200/404/redirect/timeout), final URL
- Visual grouping by category
- Navigation flow diagram (text-based) showing primary user journeys

### Section 3: Prioritized Issues List

A master table of ALL findings sorted by severity (descending) then effort (ascending):

| ID | Issue | Severity (0-4) | Effort (Low/Med/High) | Category | Routes Affected | v2 Status |
|----|-------|----------------|----------------------|----------|-----------------|-----------|

Where `v2 Status` is one of: `New`, `Unchanged`, `Regressed`, `Resolved`, `Improved`.

### Section 4: Heuristic Scorecard

Table of all 13 heuristics with scores and brief justification:

| Heuristic | Score (1-5) | Key Observations |
|-----------|-------------|------------------|

Include an overall weighted average.

### Section 5: Detailed Findings by Page/Flow

For each category (chat, media, settings, admin, workspace, knowledge, audio, connectors, other), provide:

- Route-by-route findings with screenshot references: `![alt](screenshots/filename.png)`
- Specific issues with severity tags
- Positive observations (what works well)
- Dark mode specific issues
- Mobile-specific issues

### Section 6: Cross-Cutting Themes

Patterns that appear across multiple pages:

- Consistency issues (different button styles, inconsistent empty states)
- Common error patterns (overlay issues, unresolved templates)
- Navigation problems (dead links, wrong redirects)
- Performance patterns (slow routes, hanging loaders)
- Design system adherence (where the design tokens are/aren't used consistently)

### Section 7: Accessibility Audit (WCAG 2.2 AA)

Organized by WCAG principle:

- **Perceivable**: Color contrast, text alternatives, content structure
- **Operable**: Keyboard access, focus management, touch targets (mobile)
- **Understandable**: Labels, error messages, consistent behavior
- **Robust**: Semantic HTML, ARIA usage, heading hierarchy

Include data from the automated `a11y` checks (images without alt, heading structure, landmarks, focusable elements).

### Section 8: Top 10 Quick Wins

The 10 highest-impact improvements that require the least effort. For each:

- **What**: Specific change needed
- **Why**: User impact
- **How**: Implementation hint (specific file or component if identifiable)
- **Effort**: Hours estimate (S/M/L)

### Section 9: Strategic Recommendations

3-5 larger initiatives for long-term UX improvement:

- **Title**: Initiative name
- **Problem**: What user pain it addresses
- **Approach**: High-level implementation strategy
- **Impact**: Expected improvement
- **Dependencies**: What needs to happen first

---

## 7. Project-Specific Technical Context

### 7.1 Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | Next.js (Pages Router) | — |
| UI Library | Ant Design | 6.x |
| Styling | Tailwind CSS | 3.4 |
| State (client) | Zustand | — |
| State (server) | React Query (@tanstack/react-query) | — |
| Icons | Lucide + Heroicons | — |
| Router shim | Custom `react-router-dom` → Next.js router | `extension/shims/react-router-dom.tsx` |
| Browser shim | Custom `wxt-browser` → localStorage | `extension/shims/wxt-browser.ts` |

### 7.2 Design Tokens

All colors use CSS custom properties with RGB triplets for Tailwind alpha support:

```css
/* Light */
--color-bg: 244 242 238;      /* Warm parchment */
--color-surface: 255 255 255;  /* White cards */
--color-primary: 47 111 237;   /* Blue actions */
--color-accent: 31 181 159;    /* Teal highlights */
--color-text: 31 35 40;        /* Near-black text */
--color-border: 226 221 211;   /* Warm grey borders */

/* Dark */
--color-bg: 15 17 19;          /* Deep charcoal */
--color-surface: 23 26 31;     /* Dark cards */
--color-primary: 92 141 255;   /* Bright blue */
--color-accent: 79 209 176;    /* Mint green */
--color-text: 231 233 238;     /* Off-white text */
--color-border: 43 49 59;      /* Dark grey borders */
```

Defined in `packages/ui/src/assets/tailwind-shared.css`, mapped to Tailwind classes in `tailwind.config.js`.

### 7.3 Fonts

| Role | Font | Tailwind Class |
|------|------|---------------|
| Body text | Inter (14px/20px) | `font-body` |
| Display/headings | Space Grotesk | `font-display` |
| Alternative | Arimo | `font-arimo` |

### 7.4 Dark Mode Strategy

- Tailwind `darkMode: "class"` — toggled by adding/removing `.dark` on `<html>`
- All components should use semantic tokens (`bg-bg`, `text-text`, `border-border`)
- Watch for: hardcoded colors that don't respect dark mode, contrast issues in dark theme

### 7.5 Known v2 Issues to Track

These were identified in the v2 audit. Note whether each is resolved, unchanged, or regressed:

| Issue | v2 Severity | Status |
|-------|-------------|--------|
| `chrome.storage.local` error overlay on 84/86 routes | 4 | Check |
| 9 admin/connector routes render wrong page content | 4 | Check |
| 7 sidebar links lead to 404 pages | 3 | Check |
| Unresolved template variables (`{{percentage}}`, `{{model}}`) | 3 | Check |
| Permanently loading skeleton states (admin stats, TTS voices) | 3 | Check |
| antd deprecation console warnings on 85/86 routes | 2 | Check |
| Missing mobile responsive layouts | 2 | Check |
| Inconsistent empty state designs | 2 | Check |

### 7.6 Target User

The primary audience is **technical, research-oriented users** (journalists, OSINT analysts, academic researchers). They expect:
- Information-dense interfaces (not oversimplified)
- Keyboard-navigable workflows
- Clear terminology (NLP, RAG, embeddings — domain terms are fine)
- Reliable, predictable behavior over flashy animations

---

## 8. Execution Checklist

Run these steps in order. Each step should complete before moving to the next.

### Step 1: Verify Servers

```bash
curl -s http://127.0.0.1:8000/api/v1/health | head -c 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080
```

Both must return 200. If not, stop and report.

### Step 2: Read v2 Baseline Artifacts

```
Read Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_cross_cutting_stage1_route_matrix_baseline_v2.md
Read Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_overarching_program_oversight_v2_2026_02_16.md
Read Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_ux_audit_cross_cutting_themes_v2.md
```

Internalize the findings so you can compare.

### Step 3: Create the Data Collection Script

Write `apps/tldw-frontend/e2e/ux-audit/audit-v3.spec.ts` following Section 3.

### Step 4: Run the Script

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false npx playwright test e2e/ux-audit/audit-v3.spec.ts \
  --project=chromium \
  --timeout=120000 \
  --reporter=list \
  --workers=1
```

Expect ~15-25 minutes for 83 routes x 4 screenshots each.

### Step 5: Verify Data Collection

```bash
ls apps/tldw-frontend/ux-audit-v3/screenshots/ | wc -l   # Expect ~332
ls apps/tldw-frontend/ux-audit-v3/data/ | wc -l           # Expect ~83
```

### Step 6: Analyze All Screenshots

Read every screenshot in `ux-audit-v3/screenshots/`. For each route, examine:
- Desktop light + dark: layout, spacing, color, readability
- Mobile light + dark: responsive behavior, touch targets, overflow

Read the corresponding JSON in `ux-audit-v3/data/` for error counts, performance, and a11y data.

### Step 7: Write the Report

Write `ux-audit-v3/report.md` following the 9-section format in Section 6. Include:
- Inline screenshot references where helpful
- Data-driven observations (error counts, performance numbers)
- Delta comparison against v2 throughout

### Step 8: Final Verification

After writing the report, do a self-review:
- All 9 sections present and substantive
- Every route accounted for in Section 2
- Severity ratings are consistent
- Quick wins are genuinely quick
- Strategic recommendations are actionable

---

## 9. Quality Standards

- **Objectivity**: Ground every finding in observable evidence (screenshots, error logs, metrics). No speculation.
- **Specificity**: "The submit button on `/chat` has no loading state" > "Some buttons lack feedback"
- **Actionability**: Every issue should imply a clear fix. State what should change, not just what's wrong.
- **Proportionality**: Don't spend 500 words on a cosmetic issue. Match detail to severity.
- **Completeness**: Every route must appear in the report. No "and similar pages" hand-waving.
- **Delta tracking**: For every issue, state whether it's new or carried over from v2.
