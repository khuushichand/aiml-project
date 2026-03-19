# tldw / VademHQ Marketing Pages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh the open-source `tldwproject.com` homepage and add a separate `VademHQ` hosted-offering landing page in the existing static marketing site.

**Architecture:** Keep the public marketing work in `Docs/Website/` instead of the Next.js app. Update the existing `Docs/Website/index.html`, add a sibling `Docs/Website/vademhq/index.html`, and move shared presentation rules into a reusable CSS asset so both pages can share a coherent system without sharing identical positioning.

**Tech Stack:** Static HTML, shared CSS, optional vanilla JS, Python `pytest`, `beautifulsoup4`, Bandit

---

### Task 1: Add marketing-page regression tests

**Files:**
- Create: `tests/website/test_marketing_pages.py`
- Test: `tests/website/test_marketing_pages.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
TLDW_PAGE = ROOT / "Docs/Website/index.html"
VADEM_PAGE = ROOT / "Docs/Website/vademhq/index.html"


def parse_html(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def test_tldw_homepage_keeps_open_source_positioning():
    soup = parse_html(TLDW_PAGE)
    text = soup.get_text(" ", strip=True)

    assert "Open-source research assistant" in soup.title.get_text()
    assert soup.find(id="whats-new") is not None
    assert "self-host" in text.lower()
    assert "VademHQ" in text


def test_vademhq_page_exists_with_hosted_trial_cta():
    assert VADEM_PAGE.exists()
    soup = parse_html(VADEM_PAGE)
    text = soup.get_text(" ", strip=True)

    assert "Start hosted trial" in text
    assert "built on open-source tldw" in text.lower()
    assert "in progress" in text.lower()


def test_pages_have_distinct_canonical_urls():
    tldw = parse_html(TLDW_PAGE)
    vadem = parse_html(VADEM_PAGE)

    assert tldw.find("link", rel="canonical")["href"] == "https://tldwproject.com"
    assert vadem.find("link", rel="canonical")["href"] == "https://vademhq.com"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- FAIL because `Docs/Website/vademhq/index.html` does not exist.
- FAIL because the current `Docs/Website/index.html` does not contain the new `whats-new` section or updated OSS positioning copy.

**Step 3: Write minimal implementation**

Create the `tests/website/` directory and add the test file exactly as above.

**Step 4: Run test to verify it fails for the right reasons**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- the suite runs
- failures point only at missing/old marketing-page content

**Step 5: Commit**

```bash
git add tests/website/test_marketing_pages.py
git commit -m "test: add marketing page regression coverage"
```

### Task 2: Refresh the open-source homepage

**Files:**
- Modify: `Docs/Website/index.html`
- Create: `Docs/Website/assets/marketing.css`
- Test: `tests/website/test_marketing_pages.py`

**Step 1: Write the failing test**

Extend the existing test file with assertions that force the new OSS structure:

```python
def test_tldw_homepage_surfaces_recent_progress_and_hosted_pointer():
    soup = parse_html(TLDW_PAGE)
    text = soup.get_text(" ", strip=True)

    assert soup.find(id="whats-new") is not None
    assert "OpenAI-compatible" in text
    assert "Unified RAG" in text
    assert "MCP Unified" in text
    assert "Visit VademHQ" in text
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- FAIL because the current homepage still uses the older structure and inline-only styling.

**Step 3: Write minimal implementation**

Create shared CSS and update the OSS homepage to use it.

```html
<!-- Docs/Website/index.html -->
<link rel="stylesheet" href="./assets/marketing.css" />

<section id="whats-new" class="section">
  <div class="container">
    <h2>What’s New</h2>
    <div class="feature-grid">
      <article class="card"><strong>OpenAI-compatible APIs</strong><p>Chat, audio, embeddings, and evals.</p></article>
      <article class="card"><strong>Unified RAG + evaluations</strong><p>Hybrid retrieval, reranking, and evaluation tools.</p></article>
      <article class="card"><strong>Expanded audio stack</strong><p>Real-time STT, streaming TTS, and voice catalog support.</p></article>
      <article class="card"><strong>MCP Unified</strong><p>JWT/RBAC-aware MCP tooling, metrics, and status surfaces.</p></article>
    </div>
  </div>
</section>

<section id="hosted" class="section section-muted">
  <div class="container callout">
    <div>
      <h2>Need hosted access instead of self-hosting?</h2>
      <p>VademHQ offers managed early-access trials built on the open-source tldw project.</p>
    </div>
    <a class="btn btn-secondary" href="https://vademhq.com">Visit VademHQ</a>
  </div>
</section>
```

```css
/* Docs/Website/assets/marketing.css */
:root {
  --bg: #0c0f12;
  --panel: #12171c;
  --text: #f2f4f7;
  --muted: #a6b0bb;
  --accent: #5dd6c0;
  --accent-strong: #f0b44c;
  --border: rgba(255, 255, 255, 0.12);
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Segoe UI", system-ui, sans-serif;
}

.feature-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.card {
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--panel);
  padding: 20px;
}
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- OSS-page assertions pass
- VademHQ assertions still fail until the next task

**Step 5: Commit**

```bash
git add Docs/Website/index.html Docs/Website/assets/marketing.css tests/website/test_marketing_pages.py
git commit -m "feat: refresh tldw open-source homepage"
```

### Task 3: Create the VademHQ landing page

**Files:**
- Create: `Docs/Website/vademhq/index.html`
- Modify: `Docs/Website/assets/marketing.css`
- Test: `tests/website/test_marketing_pages.py`

**Step 1: Write the failing test**

Add structure-level expectations for the VademHQ page:

```python
def test_vademhq_page_has_trust_problem_and_cta_sections():
    soup = parse_html(VADEM_PAGE)

    assert soup.find(id="hero") is not None
    assert soup.find(id="trust") is not None
    assert soup.find(id="problem") is not None
    assert soup.find(id="how-it-works") is not None
    assert soup.find(id="roadmap") is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- FAIL because `Docs/Website/vademhq/index.html` still does not exist.

**Step 3: Write minimal implementation**

Create the new page with distinct commercial copy and separate metadata.

```html
<!-- Docs/Website/vademhq/index.html -->
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>VademHQ | Hosted tldw for people drowning in information</title>
  <meta name="description" content="Privacy-first hosted tldw for people who want a calmer way to work with transcripts, documents, notes, and research." />
  <link rel="canonical" href="https://vademhq.com" />
  <link rel="stylesheet" href="../assets/marketing.css" />
</head>
<body class="brand-vadem">
  <a class="skip" href="#main">Skip to content</a>
  <main id="main">
    <section id="hero" class="hero hero-vadem">
      <div class="container">
        <p class="eyebrow">Privacy-first managed cloud</p>
        <h1>A calmer way to work with too much information</h1>
        <p>Hosted tldw for people who need to collect, search, and reason across messy information without self-hosting the stack.</p>
        <div class="actions">
          <a class="btn btn-primary" href="#trial">Start hosted trial</a>
          <a class="btn btn-secondary" href="#how-it-works">See how it works</a>
        </div>
      </div>
    </section>

    <section id="trust" class="section">
      <div class="container trust-row">
        <span>Privacy-first</span>
        <span>Managed cloud</span>
        <span>Built on open-source tldw</span>
        <span>Early access</span>
      </div>
    </section>

    <section id="problem" class="section">
      <div class="container">
        <h2>Your work is scattered across tabs, files, recordings, notes, and half-finished threads.</h2>
      </div>
    </section>

    <section id="how-it-works" class="section">
      <div class="container">
        <h2>How it works</h2>
        <ol>
          <li>Bring in your sources</li>
          <li>Search, ask, and connect ideas</li>
          <li>Keep a working knowledge base instead of a pile of tabs</li>
        </ol>
      </div>
    </section>

    <section id="roadmap" class="section">
      <div class="container">
        <h2>Available now, with more on the way</h2>
        <p>Hosted trial and managed-cloud sign-up are available now. Sync and fuller hosted workspace features are in progress.</p>
      </div>
    </section>

    <section id="trial" class="section">
      <div class="container callout">
        <div>
          <h2>Start with hosted access now</h2>
          <p>Prefer to run everything yourself? Visit tldwproject.com for the open-source self-hosted project.</p>
        </div>
        <a class="btn btn-primary" href="https://vademhq.com/signup">Start hosted trial</a>
      </div>
    </section>
  </main>
</body>
</html>
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- all marketing-page assertions pass

**Step 5: Commit**

```bash
git add Docs/Website/vademhq/index.html Docs/Website/assets/marketing.css tests/website/test_marketing_pages.py
git commit -m "feat: add VademHQ hosted landing page"
```

### Task 4: Finalize metadata, accessibility, and verification

**Files:**
- Modify: `Docs/Website/index.html`
- Modify: `Docs/Website/vademhq/index.html`
- Modify: `tests/website/test_marketing_pages.py`

**Step 1: Write the failing test**

Add assertions for page separation and accessibility hooks:

```python
def test_pages_keep_distinct_primary_intents():
    tldw_text = parse_html(TLDW_PAGE).get_text(" ", strip=True).lower()
    vadem_text = parse_html(VADEM_PAGE).get_text(" ", strip=True).lower()

    assert "get started" in tldw_text
    assert "start hosted trial" in vadem_text
    assert "self-host" in tldw_text
    assert "managed cloud" in vadem_text


def test_both_pages_include_skip_links():
    assert parse_html(TLDW_PAGE).find("a", class_="skip") is not None
    assert parse_html(VADEM_PAGE).find("a", class_="skip") is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- FAIL until both pages have the finalized CTA hierarchy and skip links.

**Step 3: Write minimal implementation**

Make the final HTML adjustments:

- ensure distinct page titles and meta descriptions
- ensure skip links exist on both pages
- ensure cross-links point the right direction
- ensure VademHQ discloses early access / in-progress hosted workspace state
- ensure the OSS page mentions VademHQ lightly, not as a dominant CTA

**Step 4: Run tests and security validation**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
source .venv/bin/activate && python -m bandit -r tests/website -f json -o /tmp/bandit_marketing_pages.json
```

Expected:
- `pytest` PASS
- `bandit` completes without new actionable findings in the touched Python test scope

**Step 5: Commit**

```bash
git add Docs/Website/index.html Docs/Website/vademhq/index.html tests/website/test_marketing_pages.py
git commit -m "docs: polish marketing metadata and accessibility"
```
