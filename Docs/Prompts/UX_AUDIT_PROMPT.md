# UX Audit Prompt for tldw WebUI

> **Usage**: Open a fresh Claude Code session, paste or reference this prompt, then let Claude Code
> execute all four phases autonomously. Ensure the backend and frontend are running first.

---

## Role & Persona

You are a **Senior UX/Design Professional** with 15+ years of experience spanning product design,
interaction design, usability engineering, WCAG 2.2 accessibility compliance, responsive design,
and design systems. You have deep expertise in Nielsen's 10 usability heuristics and have conducted
hundreds of UX audits for production web applications.

Your task is to perform a comprehensive, professional UX audit of the tldw WebUI by automating
screenshot capture across all routes, analyzing each screenshot visually, and producing a structured
report with prioritized findings.

---

## Prerequisites Checklist

Before starting, verify these are running:

1. **Backend** running at `http://127.0.0.1:8000`
   - Start with: `python -m uvicorn tldw_Server_API.app.main:app --reload`
2. **Frontend** running at `http://localhost:8080`
   - Start with: `cd apps/tldw-frontend && bun run dev -- -p 8080`
3. **Puppeteer** available at `apps/tldw-frontend/node_modules/puppeteer` (v24+, already installed)
4. **Google Chrome** at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`

> **IMPORTANT**: The frontend runs on port **8080**, not 3000. The backend runs on port 8000.

Replace `YOUR_API_KEY_HERE` in the script below with a real API key from your backend
(default single-user key is printed at backend startup, or check your `.env`).

---

## Phase 1 --- Write the Puppeteer Audit Script

Create the file `ux-audit/audit-v2.mjs` with the following content. Copy this script verbatim
to disk using the Write tool:

```js
#!/usr/bin/env node
/**
 * tldw WebUI UX Audit Script v2
 *
 * Navigates all known routes, captures desktop + mobile screenshots,
 * records console errors, and outputs a JSON manifest.
 *
 * Usage:  cd apps/tldw-frontend && node ../../ux-audit/audit-v2.mjs
 *    or:  node ux-audit/audit-v2.mjs  (from repo root, with PUPPETEER_EXECUTABLE_PATH set)
 */
import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// ── Configuration ──────────────────────────────────────────────────────────
const BASE_URL = 'http://localhost:8080';
const API_KEY = process.env.TLDW_API_KEY || 'YOUR_API_KEY_HERE';
const CHROME_PATH = process.env.PUPPETEER_EXECUTABLE_PATH
  || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOTS_DIR = path.join(__dirname, 'screenshots-v2');
const DESKTOP = { width: 1440, height: 900 };
const MOBILE  = { width: 375,  height: 812 };
const NAV_TIMEOUT = 20_000;      // 20s per page
const SETTLE_DELAY = 1500;       // wait for JS rendering
const INTER_PAGE_DELAY = 300;    // rate-limit between navigations

// ── Auth Seeding ───────────────────────────────────────────────────────────
// Pattern from apps/tldw-frontend/e2e/smoke/smoke.setup.ts
async function seedAuth(page) {
  await page.evaluateOnNewDocument((apiKey) => {
    try {
      localStorage.setItem('tldwConfig', JSON.stringify({
        serverUrl: 'http://127.0.0.1:8000',
        authMode: 'single-user',
        apiKey: apiKey,
      }));
    } catch {}
    try { localStorage.setItem('__tldw_first_run_complete', 'true'); } catch {}
    try { localStorage.setItem('__tldw_allow_offline', 'true'); } catch {}
  }, API_KEY);
}

// ── Route Inventory ────────────────────────────────────────────────────────
// Authoritative list from e2e/smoke/page-inventory.ts + route-registry.tsx
const ROUTES = [
  // ── Chat ──
  { path: '/', name: 'home', category: 'other' },
  { path: '/login', name: 'login', category: 'other' },
  { path: '/setup', name: 'setup', category: 'other' },
  { path: '/chat', name: 'chat', category: 'chat' },
  { path: '/chat/agent', name: 'chat-agent', category: 'chat' },
  { path: '/persona', name: 'persona', category: 'chat' },
  { path: '/chat/settings', name: 'chat-settings-page', category: 'chat' },

  // ── Media ──
  { path: '/media', name: 'media', category: 'media' },
  { path: '/media-multi', name: 'media-multi', category: 'media' },
  { path: '/media-trash', name: 'media-trash', category: 'media' },
  { path: '/media/123/view', name: 'media-view-redirect', category: 'media' },

  // ── Settings ──
  { path: '/settings', name: 'settings', category: 'settings' },
  { path: '/settings/tldw', name: 'settings-tldw', category: 'settings' },
  { path: '/settings/model', name: 'settings-model', category: 'settings' },
  { path: '/settings/chat', name: 'settings-chat', category: 'settings' },
  { path: '/settings/prompt', name: 'settings-prompt', category: 'settings' },
  { path: '/settings/knowledge', name: 'settings-knowledge', category: 'settings' },
  { path: '/settings/rag', name: 'settings-rag', category: 'settings' },
  { path: '/settings/speech', name: 'settings-speech', category: 'settings' },
  { path: '/settings/evaluations', name: 'settings-evaluations', category: 'settings' },
  { path: '/settings/chatbooks', name: 'settings-chatbooks', category: 'settings' },
  { path: '/settings/characters', name: 'settings-characters', category: 'settings' },
  { path: '/settings/world-books', name: 'settings-world-books', category: 'settings' },
  { path: '/settings/chat-dictionaries', name: 'settings-chat-dicts', category: 'settings' },
  { path: '/settings/health', name: 'settings-health', category: 'settings' },
  { path: '/settings/processed', name: 'settings-processed', category: 'settings' },
  { path: '/settings/about', name: 'settings-about', category: 'settings' },
  { path: '/settings/share', name: 'settings-share', category: 'settings' },
  { path: '/settings/quick-ingest', name: 'settings-quick-ingest', category: 'settings' },
  { path: '/settings/prompt-studio', name: 'settings-prompt-studio', category: 'settings' },
  { path: '/settings/ui', name: 'settings-ui', category: 'settings' },
  { path: '/settings/splash', name: 'settings-splash', category: 'settings' },
  { path: '/settings/image-generation', name: 'settings-image-gen', category: 'settings' },
  { path: '/settings/guardian', name: 'settings-guardian', category: 'settings' },

  // ── Admin ──
  { path: '/admin', name: 'admin', category: 'admin' },
  { path: '/admin/server', name: 'admin-server', category: 'admin' },
  { path: '/admin/llamacpp', name: 'admin-llamacpp', category: 'admin' },
  { path: '/admin/mlx', name: 'admin-mlx', category: 'admin' },
  { path: '/admin/orgs', name: 'admin-orgs', category: 'admin' },
  { path: '/admin/data-ops', name: 'admin-data-ops', category: 'admin' },
  { path: '/admin/watchlists-items', name: 'admin-watchlists-items', category: 'admin' },
  { path: '/admin/watchlists-runs', name: 'admin-watchlists-runs', category: 'admin' },
  { path: '/admin/maintenance', name: 'admin-maintenance', category: 'admin' },

  // ── Workspace / Tools ──
  { path: '/flashcards', name: 'flashcards', category: 'workspace' },
  { path: '/quiz', name: 'quiz', category: 'workspace' },
  { path: '/moderation-playground', name: 'moderation-playground', category: 'workspace' },
  { path: '/kanban', name: 'kanban', category: 'workspace' },
  { path: '/data-tables', name: 'data-tables', category: 'workspace' },
  { path: '/content-review', name: 'content-review', category: 'workspace' },
  { path: '/claims-review', name: 'claims-review', category: 'workspace' },
  { path: '/watchlists', name: 'watchlists', category: 'workspace' },
  { path: '/chatbooks', name: 'chatbooks', category: 'workspace' },
  { path: '/notes', name: 'notes', category: 'workspace' },
  { path: '/collections', name: 'collections', category: 'workspace' },
  { path: '/evaluations', name: 'evaluations', category: 'workspace' },
  { path: '/search', name: 'search', category: 'workspace' },
  { path: '/review', name: 'review', category: 'workspace' },
  { path: '/reading', name: 'reading', category: 'workspace' },
  { path: '/items', name: 'items', category: 'workspace' },
  { path: '/chunking-playground', name: 'chunking-playground', category: 'workspace' },
  { path: '/writing-playground', name: 'writing-playground', category: 'workspace' },
  { path: '/workspace-playground', name: 'workspace-playground', category: 'workspace' },
  { path: '/model-playground', name: 'model-playground', category: 'workspace' },
  { path: '/document-workspace', name: 'document-workspace', category: 'workspace' },
  { path: '/audiobook-studio', name: 'audiobook-studio', category: 'workspace' },
  { path: '/workflow-editor', name: 'workflow-editor', category: 'workspace' },
  { path: '/acp-playground', name: 'acp-playground', category: 'workspace' },
  { path: '/chatbooks-playground', name: 'chatbooks-playground', category: 'workspace' },
  { path: '/skills', name: 'skills', category: 'workspace' },

  // ── Knowledge ──
  { path: '/knowledge', name: 'knowledge', category: 'knowledge' },
  { path: '/world-books', name: 'world-books', category: 'knowledge' },
  { path: '/dictionaries', name: 'dictionaries', category: 'knowledge' },
  { path: '/characters', name: 'characters', category: 'knowledge' },
  { path: '/prompts', name: 'prompts', category: 'knowledge' },
  { path: '/prompt-studio', name: 'prompt-studio', category: 'knowledge' },

  // ── Audio ──
  { path: '/tts', name: 'tts', category: 'audio' },
  { path: '/stt', name: 'stt', category: 'audio' },
  { path: '/speech', name: 'speech', category: 'audio' },
  { path: '/audio', name: 'audio', category: 'audio' },

  // ── Connectors ──
  { path: '/connectors', name: 'connectors', category: 'connectors' },
  { path: '/connectors/browse', name: 'connectors-browse', category: 'connectors' },
  { path: '/connectors/jobs', name: 'connectors-jobs', category: 'connectors' },
  { path: '/connectors/sources', name: 'connectors-sources', category: 'connectors' },

  // ── Other / Core ──
  { path: '/config', name: 'config', category: 'other' },
  { path: '/documentation', name: 'documentation', category: 'other' },
  { path: '/profile', name: 'profile', category: 'other' },
  { path: '/privileges', name: 'privileges', category: 'other' },
  { path: '/quick-chat-popout', name: 'quick-chat-popout', category: 'other' },
  { path: '/onboarding-test', name: 'onboarding-test', category: 'other' },
  { path: '/for/journalists', name: 'for-journalists', category: 'other' },
  { path: '/for/osint', name: 'for-osint', category: 'other' },
  { path: '/for/researchers', name: 'for-researchers', category: 'other' },
  { path: '/__debug__/authz.spec', name: 'debug-authz', category: 'other' },
  { path: '/__debug__/sidepanel-error-boundary', name: 'debug-error-boundary', category: 'other' },

  // ── 404 test ──
  { path: '/nonexistent-page-404-test', name: '404-test', category: 'other' },
];

// ── Helpers ────────────────────────────────────────────────────────────────
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

async function takeScreenshot(page, name, viewport) {
  const tag = viewport.width > 500 ? 'desktop' : 'mobile';
  const filename = `${name}_${tag}.png`;
  await page.setViewport(viewport);
  await delay(400);
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, filename),
    fullPage: true,
  });
  return filename;
}

// Dismiss Next.js dev error overlay if present
async function dismissErrorOverlay(page) {
  try {
    await page.evaluate(() => {
      // Next.js dev overlay dismiss button
      const overlay = document.querySelector('nextjs-portal');
      if (overlay?.shadowRoot) {
        const dismissBtn = overlay.shadowRoot.querySelector('button[aria-label="Close"]')
          || overlay.shadowRoot.querySelector('[data-nextjs-errors-dialog-left-right-close-button]');
        if (dismissBtn) dismissBtn.click();
      }
      // Also try pressing Escape
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    await delay(300);
  } catch {}
}

// ── Main ───────────────────────────────────────────────────────────────────
async function run() {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: CHROME_PATH,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--window-size=1440,900',
    ],
  });

  const page = await browser.newPage();

  // Seed auth BEFORE any navigation
  await seedAuth(page);

  // Console error capture (NOT suppressed)
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push({
        route: page.url(),
        type: 'console.error',
        text: msg.text().slice(0, 500),
        location: msg.location(),
        timestamp: new Date().toISOString(),
      });
    }
  });
  page.on('pageerror', (err) => {
    consoleErrors.push({
      route: page.url(),
      type: 'pageerror',
      text: err.message?.slice(0, 500) || String(err).slice(0, 500),
      stack: err.stack?.slice(0, 300) || '',
      timestamp: new Date().toISOString(),
    });
  });

  const results = [];
  let idx = 0;

  // ── Navigate all routes ──────────────────────────────────────────────
  for (const route of ROUTES) {
    idx++;
    const url = `${BASE_URL}${route.path}`;
    const pct = Math.round((idx / ROUTES.length) * 100);
    process.stdout.write(`[${String(pct).padStart(3)}%] ${route.name} (${route.path})...`);

    const routeConsolesBefore = consoleErrors.length;

    try {
      const response = await page.goto(url, {
        waitUntil: 'networkidle2',
        timeout: NAV_TIMEOUT,
      });

      const status = response?.status() ?? 0;
      const finalUrl = page.url();
      const title = await page.title();

      await delay(SETTLE_DELAY);

      // Try dismissing Next.js dev error overlay
      await dismissErrorOverlay(page);

      // Desktop screenshot
      const desktopFile = await takeScreenshot(page, route.name, DESKTOP);
      // Mobile screenshot
      const mobileFile = await takeScreenshot(page, route.name, MOBILE);

      // Body text preview for error/empty detection
      const bodyText = await page.evaluate(
        () => document.body?.innerText?.slice(0, 500) || ''
      );
      const hasError = /error|exception|500|not found/i.test(bodyText);
      const isEmpty = bodyText.trim().length < 50;

      // Console errors collected during this route
      const routeConsoles = consoleErrors.slice(routeConsolesBefore);

      results.push({
        route: route.path,
        name: route.name,
        category: route.category,
        status,
        finalUrl,
        title,
        desktopScreenshot: desktopFile,
        mobileScreenshot: mobileFile,
        hasError,
        isEmpty,
        bodyPreview: bodyText.slice(0, 300),
        redirected: finalUrl !== url && !finalUrl.startsWith(url + '?'),
        redirectTarget: finalUrl !== url ? finalUrl : null,
        consoleErrorCount: routeConsoles.length,
        consoleErrors: routeConsoles.slice(0, 5), // first 5
      });

      process.stdout.write(` ${status} OK\n`);
    } catch (err) {
      process.stdout.write(` FAILED: ${err.message.slice(0, 80)}\n`);
      results.push({
        route: route.path,
        name: route.name,
        category: route.category,
        status: 0,
        error: err.message.slice(0, 300),
        desktopScreenshot: null,
        mobileScreenshot: null,
        consoleErrorCount: 0,
        consoleErrors: [],
      });
    }

    await delay(INTER_PAGE_DELAY);
  }

  // ── Interaction Tests ────────────────────────────────────────────────
  process.stdout.write('\n--- Interaction Tests ---\n');
  const interactionResults = [];

  // 1. Chat: type in input
  try {
    await page.goto(`${BASE_URL}/chat`, { waitUntil: 'networkidle2', timeout: NAV_TIMEOUT });
    await delay(SETTLE_DELAY);
    await dismissErrorOverlay(page);
    const chatInput = await page.$('textarea, input[type="text"]');
    if (chatInput) {
      await chatInput.click();
      await chatInput.type('Hello, this is a test message');
      await delay(500);
      await takeScreenshot(page, 'interaction-chat-typed', DESKTOP);
      interactionResults.push({ test: 'Chat input', result: 'PASS', note: 'Textarea found, typed' });
      process.stdout.write('  Chat input: PASS\n');
    } else {
      interactionResults.push({ test: 'Chat input', result: 'FAIL', note: 'No textarea found' });
      process.stdout.write('  Chat input: FAIL (no input found)\n');
    }
  } catch (e) {
    interactionResults.push({ test: 'Chat input', result: 'ERROR', note: e.message.slice(0, 100) });
    process.stdout.write(`  Chat input: ERROR ${e.message.slice(0, 60)}\n`);
  }

  // 2. Search/Knowledge: type query and submit
  try {
    await page.goto(`${BASE_URL}/search`, { waitUntil: 'networkidle2', timeout: NAV_TIMEOUT });
    await delay(SETTLE_DELAY);
    await dismissErrorOverlay(page);
    const searchInput = await page.$('input[type="text"], input[type="search"], textarea');
    if (searchInput) {
      await searchInput.click();
      await searchInput.type('test query');
      await delay(300);
      await takeScreenshot(page, 'interaction-search-typed', DESKTOP);
      await page.keyboard.press('Enter');
      await delay(2000);
      await takeScreenshot(page, 'interaction-search-results', DESKTOP);
      interactionResults.push({ test: 'Search submit', result: 'PASS', note: 'Typed and submitted' });
      process.stdout.write('  Search submit: PASS\n');
    } else {
      interactionResults.push({ test: 'Search submit', result: 'FAIL', note: 'No search input found' });
      process.stdout.write('  Search submit: FAIL\n');
    }
  } catch (e) {
    interactionResults.push({ test: 'Search submit', result: 'ERROR', note: e.message.slice(0, 100) });
    process.stdout.write(`  Search submit: ERROR ${e.message.slice(0, 60)}\n`);
  }

  // 3. Settings: verify sidebar navigation
  try {
    await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle2', timeout: NAV_TIMEOUT });
    await delay(SETTLE_DELAY);
    await dismissErrorOverlay(page);
    await takeScreenshot(page, 'interaction-settings-loaded', DESKTOP);
    const navLinks = await page.$$('nav a, aside a, [role="navigation"] a');
    if (navLinks.length > 0) {
      await navLinks[0].click();
      await delay(1500);
      await takeScreenshot(page, 'interaction-settings-nav-clicked', DESKTOP);
      interactionResults.push({
        test: 'Settings nav',
        result: 'PASS',
        note: `${navLinks.length} links found, first clicked`,
      });
      process.stdout.write(`  Settings nav: PASS (${navLinks.length} links)\n`);
    } else {
      interactionResults.push({ test: 'Settings nav', result: 'FAIL', note: 'No nav links found' });
      process.stdout.write('  Settings nav: FAIL\n');
    }
  } catch (e) {
    interactionResults.push({ test: 'Settings nav', result: 'ERROR', note: e.message.slice(0, 100) });
    process.stdout.write(`  Settings nav: ERROR ${e.message.slice(0, 60)}\n`);
  }

  // 4. Command palette (Cmd+K)
  try {
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle2', timeout: NAV_TIMEOUT });
    await delay(SETTLE_DELAY);
    await dismissErrorOverlay(page);
    await page.keyboard.down('Meta');
    await page.keyboard.press('k');
    await page.keyboard.up('Meta');
    await delay(800);
    await takeScreenshot(page, 'interaction-command-palette', DESKTOP);
    interactionResults.push({ test: 'Command palette', result: 'PASS', note: 'Cmd+K triggered' });
    process.stdout.write('  Command palette: PASS\n');
    // Close palette
    await page.keyboard.press('Escape');
    await delay(300);
  } catch (e) {
    interactionResults.push({ test: 'Command palette', result: 'ERROR', note: e.message.slice(0, 100) });
    process.stdout.write(`  Command palette: ERROR ${e.message.slice(0, 60)}\n`);
  }

  // 5. Dark/light mode toggle
  try {
    await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle2', timeout: NAV_TIMEOUT });
    await delay(SETTLE_DELAY);
    await dismissErrorOverlay(page);
    const themeBtn = await page.$(
      '[aria-label*="theme" i], [aria-label*="dark" i], [aria-label*="light" i], '
      + 'button:has(svg[class*="moon"]), button:has(svg[class*="sun"])'
    );
    if (themeBtn) {
      await themeBtn.click();
      await delay(800);
      await takeScreenshot(page, 'interaction-theme-toggled', DESKTOP);
      interactionResults.push({ test: 'Theme toggle', result: 'PASS', note: 'Button found and clicked' });
      process.stdout.write('  Theme toggle: PASS\n');
    } else {
      interactionResults.push({ test: 'Theme toggle', result: 'SKIP', note: 'No toggle button found' });
      process.stdout.write('  Theme toggle: SKIP (button not found)\n');
    }
  } catch (e) {
    interactionResults.push({ test: 'Theme toggle', result: 'ERROR', note: e.message.slice(0, 100) });
    process.stdout.write(`  Theme toggle: ERROR ${e.message.slice(0, 60)}\n`);
  }

  // 6. Empty form submission on media
  try {
    await page.goto(`${BASE_URL}/media`, { waitUntil: 'networkidle2', timeout: NAV_TIMEOUT });
    await delay(SETTLE_DELAY);
    await dismissErrorOverlay(page);
    const submitBtn = await page.$(
      'button[type="submit"], button:has-text("Submit"), button:has-text("Process"), button:has-text("Ingest")'
    );
    if (submitBtn) {
      await submitBtn.click();
      await delay(1500);
      await takeScreenshot(page, 'interaction-media-empty-submit', DESKTOP);
      interactionResults.push({ test: 'Media empty submit', result: 'PASS', note: 'Submitted empty form' });
      process.stdout.write('  Media empty submit: PASS\n');
    } else {
      interactionResults.push({ test: 'Media empty submit', result: 'SKIP', note: 'No submit button found' });
      process.stdout.write('  Media empty submit: SKIP\n');
    }
  } catch (e) {
    interactionResults.push({ test: 'Media empty submit', result: 'ERROR', note: e.message.slice(0, 100) });
    process.stdout.write(`  Media empty submit: ERROR ${e.message.slice(0, 60)}\n`);
  }

  await browser.close();

  // ── Write manifest ───────────────────────────────────────────────────
  const manifest = {
    timestamp: new Date().toISOString(),
    baseUrl: BASE_URL,
    apiKeyProvided: API_KEY !== 'YOUR_API_KEY_HERE',
    totalRoutes: ROUTES.length,
    successful: results.filter((r) => r.status >= 200 && r.status < 400).length,
    failed: results.filter((r) => r.status === 0 || r.status >= 400).length,
    redirected: results.filter((r) => r.redirected).length,
    withErrors: results.filter((r) => r.hasError).length,
    empty: results.filter((r) => r.isEmpty).length,
    totalConsoleErrors: consoleErrors.length,
    interactionTests: interactionResults,
    routes: results,
    consoleErrors: consoleErrors.slice(0, 200), // cap at 200
  };

  fs.writeFileSync(
    path.join(SCREENSHOTS_DIR, 'manifest.json'),
    JSON.stringify(manifest, null, 2),
  );

  // ── Summary ──────────────────────────────────────────────────────────
  console.log('\n=== AUDIT SUMMARY ===');
  console.log(`Total routes:      ${manifest.totalRoutes}`);
  console.log(`Successful:        ${manifest.successful}`);
  console.log(`Failed/Error:      ${manifest.failed}`);
  console.log(`Redirected:        ${manifest.redirected}`);
  console.log(`Has error text:    ${manifest.withErrors}`);
  console.log(`Empty pages:       ${manifest.empty}`);
  console.log(`Console errors:    ${manifest.totalConsoleErrors}`);
  console.log(`Screenshots dir:   ${SCREENSHOTS_DIR}`);
  console.log(`Manifest:          ${path.join(SCREENSHOTS_DIR, 'manifest.json')}`);

  const redirects = results.filter((r) => r.redirected);
  if (redirects.length) {
    console.log('\nRedirects:');
    redirects.forEach((r) => console.log(`  ${r.route} -> ${r.redirectTarget}`));
  }

  const errors = results.filter((r) => r.hasError || r.status >= 400 || r.error);
  if (errors.length) {
    console.log('\nErrors/Issues:');
    errors.forEach((r) =>
      console.log(`  ${r.route}: ${r.error || `status=${r.status}, hasError=${r.hasError}`}`),
    );
  }

  console.log('\nInteraction Tests:');
  interactionResults.forEach((t) =>
    console.log(`  ${t.test}: ${t.result} - ${t.note}`),
  );
}

run().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
```

After writing the script to disk, verify it was written correctly by reading the first and last 5 lines.

---

## Phase 2 --- Execute the Script

Run the audit script from the **repo root**:

```bash
cd /path/to/tldw_server2 && node ux-audit/audit-v2.mjs
```

If Puppeteer cannot resolve Chrome, try running from the frontend directory where `node_modules` is:

```bash
cd apps/tldw-frontend && node ../../ux-audit/audit-v2.mjs
```

**Expected output**: Progress lines for each route, a summary table at the end, and a populated
`ux-audit/screenshots-v2/` directory with ~190 PNG files and a `manifest.json`.

**Verify** the screenshots directory was populated:

```bash
ls ux-audit/screenshots-v2/ | wc -l   # Should be ~190 files
ls -la ux-audit/screenshots-v2/manifest.json
```

If the script fails, diagnose the error (wrong port, Chrome not found, auth not configured)
and fix it before proceeding to Phase 3.

---

## Phase 3 --- Batched Screenshot Analysis

This is the core of the audit. Process screenshots in **10 category batches** to avoid context
overflow. For each batch, use the **Read tool** to view the screenshot images, then write your
findings to a scratch section of the report.

### Evaluation Framework

For **every page**, evaluate against:

1. **Nielsen's 10 Usability Heuristics** (severity 0-4 scale)
   - H1: Visibility of system status
   - H2: Match between system and real world
   - H3: User control and freedom
   - H4: Consistency and standards
   - H5: Error prevention
   - H6: Recognition rather than recall
   - H7: Flexibility and efficiency of use
   - H8: Aesthetic and minimalist design
   - H9: Help users recognize, diagnose, and recover from errors
   - H10: Help and documentation
2. **Accessibility** (WCAG 2.2 AA)
   - Color contrast ratios
   - Keyboard navigation indicators
   - Focus management
   - Screen reader compatibility (aria-labels, roles, alt text)
   - Touch target sizes (min 44x44px)
3. **Responsive Design**
   - Compare desktop vs mobile screenshots for each route
   - Layout adaptation, text truncation, touch targets
4. **Performance Perception**
   - Loading states, skeleton screens, progress indicators
   - Perceived speed and feedback
5. **Information Architecture**
   - Navigation clarity, wayfinding, breadcrumbs
   - Discoverability of features
6. **Interaction Design**
   - Forms, buttons, feedback loops, error states
   - Empty states, onboarding, first-use experience
7. **Visual Design**
   - Typography hierarchy, color consistency, spacing, iconography
   - Brand consistency across pages

### Batch Processing Order

Process screenshots in this order. For each batch, read ALL desktop and mobile screenshots
for the routes listed, analyze them, and write findings to `Docs/UX_AUDIT_REPORT_v2.md`
incrementally (append each batch's findings).

Also read `ux-audit/screenshots-v2/manifest.json` first to understand status codes,
redirects, console errors, and body previews for all routes.

| Batch | Category | Routes | ~Screenshots |
|-------|----------|--------|--------------|
| 1 | Chat + Core (home, login, setup) | `/`, `/login`, `/setup`, `/chat`, `/chat/agent`, `/persona`, `/chat/settings` | 14 |
| 2 | Media | `/media`, `/media-multi`, `/media-trash`, `/media/123/view` | 8 |
| 3 | Knowledge | `/knowledge`, `/world-books`, `/dictionaries`, `/characters`, `/prompts`, `/prompt-studio` | 12 |
| 4 | Settings A | `/settings`, `/settings/tldw`, `/settings/model`, `/settings/chat`, `/settings/prompt`, `/settings/knowledge`, `/settings/rag` | 14 |
| 5 | Settings B | `/settings/speech`, `/settings/evaluations`, `/settings/chatbooks`, `/settings/characters`, `/settings/world-books`, `/settings/chat-dictionaries`, `/settings/prompt-studio` | 14 |
| 6 | Settings C + Misc | `/settings/ui`, `/settings/splash`, `/settings/image-generation`, `/settings/guardian`, `/settings/health`, `/settings/processed`, `/settings/about`, `/settings/share`, `/settings/quick-ingest` | 18 |
| 7 | Workspace A | `/flashcards`, `/quiz`, `/notes`, `/collections`, `/kanban`, `/data-tables`, `/content-review`, `/claims-review` | 16 |
| 8 | Workspace B | `/chatbooks`, `/evaluations`, `/search`, `/reading`, `/items`, `/chunking-playground`, `/writing-playground`, `/workspace-playground`, `/model-playground`, `/document-workspace` | 20 |
| 9 | Audio + Connectors + Workspace C | `/tts`, `/stt`, `/speech`, `/audio`, `/connectors`, `/connectors/*`, `/audiobook-studio`, `/workflow-editor`, `/acp-playground`, `/skills`, `/chatbooks-playground`, `/moderation-playground` | 24 |
| 10 | Admin + Other | `/admin`, `/admin/*`, `/config`, `/documentation`, `/profile`, `/privileges`, `/quick-chat-popout`, `/onboarding-test`, `/for/*`, `/__debug__/*`, `/review`, `/nonexistent-page-404-test` | ~30 |

### Per-Batch Workflow

For each batch:

1. Read all desktop screenshots for the batch routes (use the Read tool on each `.png` file)
2. Read all mobile screenshots for the same routes
3. Cross-reference with `manifest.json` data (status codes, console errors, redirects)
4. For each page, write a structured finding:

```markdown
### [Page Name] (`/route`)
- **Screenshots**: `name_desktop.png`, `name_mobile.png`
- **Status**: [200/404/redirect/timeout]
- **Console Errors**: [count] ([summary of errors if any])
- **Strengths**: [2-3 bullet points on what works well]
- **Issues**:
  - [H#/Sev-N] [Description of issue]
  - [H#/Sev-N] [Description of issue]
- **Accessibility**: [Key a11y observations]
- **Responsive**: [Desktop vs mobile comparison]
- **Recommendation**: [Specific, actionable fix]
```

5. Append the batch findings to `Docs/UX_AUDIT_REPORT_v2.md`

---

## Phase 4 --- Write the Final Report

After all 10 batches are analyzed, compile the final report at `Docs/UX_AUDIT_REPORT_v2.md`
with this structure:

### Report Structure

```markdown
# tldw WebUI - Comprehensive UX Audit Report v2

**Date**: [today's date]
**Auditor**: Senior UX Review (automated Puppeteer + Claude Code visual analysis)
**Target**: http://localhost:8080 (Next.js + Turbopack, dev mode)
**Backend**: http://127.0.0.1:8000 (FastAPI)
**Routes tested**: [N] | **Screenshots captured**: [N] (desktop 1440x900 + mobile 375x812)
**Screenshots directory**: `ux-audit/screenshots-v2/`

---

## 1. Executive Summary
[3-5 paragraph overview: overall quality, critical blockers, top 3 issues, bright spots]

## 2. Sitemap & Flow Inventory
### 2.1 Route Status Summary
[Table: Status | Count | Percentage]
### 2.2 All Routes Tested
[Full table: #, Route, Name, Category, Status, Notes, Screenshot Ref]

## 3. Prioritized Issues List
[Table: #, Page/Flow, Issue, Heuristic Violated, Severity (0-4), Effort (S/M/L), Recommendation]
- Severity 4 = Catastrophic (blocks core task)
- Severity 3 = Major (significant user friction)
- Severity 2 = Minor (annoying but workaround exists)
- Severity 1 = Cosmetic (visual polish)
- Severity 0 = Enhancement (nice-to-have)

## 4. Heuristic Scorecard
[Table: 13 rows (10 Nielsen + Accessibility + Responsive + Performance), 1-5 scale, justification]

## 5. Detailed Findings by Page/Flow
[One subsection per page or page group, with the per-page template from Phase 3]

## 6. Cross-Cutting Themes
[5-8 themes observed across multiple pages: error patterns, nav issues, visual consistency, etc.]

## 7. Accessibility Audit Summary (WCAG 2.2 AA)
### Perceivable
### Operable
### Understandable
### Robust

## 8. Top 10 Quick Wins
[Table: #, What to Fix, Before, After, Impact, Effort]

## 9. Strategic Recommendations
[5-7 longer-term recommendations with priority levels]

## 10. Appendix
### A. Methodology
### B. Interaction Test Results
### C. Redirect Map
### D. Console Error Summary
### E. Full Route Manifest (reference to manifest.json)
```

### Quality Standards for the Report

- Every finding must reference a **specific screenshot file** (e.g., `chat_desktop.png`)
- Every issue must cite a **specific heuristic** and **severity level**
- Recommendations must be **actionable** (not "improve this" but "add a tooltip to the sidebar icons with `title` and `aria-label` attributes")
- The executive summary should be readable by a non-technical stakeholder
- The prioritized issues list should let a PM create tickets directly from it
- Cross-reference console errors from `manifest.json` with visual findings

---

## Known Gotchas & Edge Cases

Read this section carefully before executing. These are lessons learned from the v1 audit:

1. **Port 8080, not 3000**: The frontend dev server runs on `http://localhost:8080`. Using port 3000 will fail.

2. **Auth seeding is mandatory**: Without `evaluateOnNewDocument()` setting `tldwConfig`, `__tldw_first_run_complete`, and `__tldw_allow_offline` in localStorage before the first navigation, every page will show a `chrome.storage.local` error overlay or redirect to onboarding.

3. **`__tldw_first_run_complete` flag**: Without this flag, the app redirects to the onboarding wizard instead of showing the actual page content.

4. **`__tldw_allow_offline` flag**: Without this flag, pages may show a "server unreachable" overlay even when the backend is running, due to timing issues with the initial health check.

5. **Next.js dev mode error overlays**: In development mode, Next.js shows a red error overlay for any uncaught exceptions. The script includes a `dismissErrorOverlay()` function that tries to close it. If it persists, press Escape.

6. **`/content-review` may timeout**: This page can take >15s to load. The script uses a 20s timeout, but it may still fail. This is a known issue.

7. **Rate limiting**: Navigating all 95 routes rapidly can trigger rate limiting on the backend. The script includes a 300ms inter-page delay. If you see 429 errors, increase `INTER_PAGE_DELAY`.

8. **Some beta routes return 404**: Routes like `/model-playground`, `/audiobook-studio`, `/acp-playground`, `/chatbooks-playground`, `/skills`, `/settings/ui`, `/settings/image-generation` may return 404. This is expected and should be noted in the report as a finding (registered in navigation but not implemented).

9. **Known redirects**:
   - `/search` may redirect to `/knowledge`
   - `/review` redirects to `/media-multi`
   - `/profile` and `/config` redirect to `/settings`
   - `/prompt-studio` redirects to `/prompts?tab=studio`
   - `/connectors/*` may redirect to `/settings`
   - `/admin/data-ops`, `/admin/watchlists-*` may redirect to `/admin/server`

10. **Run script from correct directory**: For Puppeteer's `node_modules` to resolve, either run from `apps/tldw-frontend/` or ensure `PUPPETEER_EXECUTABLE_PATH` is set.

11. **Full-page screenshots can be very tall**: Settings pages with many options may produce screenshots 5000+ pixels tall. This is expected and useful for the audit.

12. **Console errors should be captured, not suppressed**: The v1 script suppressed all console output (`page.on('console', () => {})`). The v2 script captures `console.error` and `pageerror` events and includes them in the manifest. This data is critical for identifying runtime issues.

13. **API key placeholder**: The script uses `YOUR_API_KEY_HERE` as a placeholder. Replace it with a real API key before running, or set the `TLDW_API_KEY` environment variable. The default single-user key is printed when the backend starts up.

---

## Summary of Improvements over v1

| Issue in v1 | Fix in v2 |
|---|---|
| Wrong port (3000) | Correct port (8080) |
| No auth seeding | `seedAuth()` with `evaluateOnNewDocument()` |
| Missing `__tldw_first_run_complete` | Set in localStorage before navigation |
| Missing `__tldw_allow_offline` | Set in localStorage before navigation |
| Console errors suppressed | Full console error capture with per-route attribution |
| No interaction tests for command palette | Cmd+K test added |
| No error overlay dismissal | `dismissErrorOverlay()` function |
| No per-route console error tracking | Console errors attributed to specific routes in manifest |
| Missing routes from route-registry | Complete 95-route inventory from both sources |
| No category metadata | Routes tagged with category for batched analysis |
| Missing routes: `/persona`, `/writing-playground`, `/workspace-playground`, etc. | All routes from `route-registry.tsx` included |
