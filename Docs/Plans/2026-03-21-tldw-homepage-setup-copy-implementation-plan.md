# tldw Homepage Setup Copy Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh the old live-style `tldwproject.com` homepage copy so the displayed version and setup instructions match the current repository guidance.

**Architecture:** Update `Docs/Website/index.html` to use the currently deployed old homepage structure as the baseline, then make narrowly scoped copy changes for versioning and quickstart guidance. Keep `Docs/Website/vademhq/index.html` untouched and update homepage regression tests to enforce the old structure with current setup copy.

**Tech Stack:** Static HTML, inline CSS/JS, pytest, BeautifulSoup, Bandit

---

### Task 1: Rewrite homepage regression tests for the old live structure

**Files:**
- Modify: `tests/website/test_marketing_pages.py`
- Test: `tests/website/test_marketing_pages.py`

**Step 1: Write the failing test**

```python
def test_tldw_homepage_keeps_old_live_section_structure():
    soup = parse_html(TLDW_PAGE)

    assert soup.find(id="cta") is not None
    assert soup.find(id="about") is not None
    assert soup.find(id="features") is not None
    assert soup.find(id="community") is not None
    assert soup.find(id="whats-new") is None


def test_tldw_homepage_setup_copy_matches_current_repo_guidance():
    text = parse_html(TLDW_PAGE).get_text(" ", strip=True)

    assert "v0.1.26" in text
    assert "make quickstart" in text
    assert "make quickstart-docker" in text
    assert "make quickstart-install" in text
    assert "make quickstart-prereqs" in text
    assert "pip install tldw_server" not in text
    assert "docker compose up" not in text
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- FAIL because the current local homepage still uses the newer redesign structure and quickstart copy.

**Step 3: Write minimal implementation**

Update the homepage test file to assert the old structure plus current setup guidance.

**Step 4: Run test to verify it fails for the right reasons**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- homepage assertions fail
- failures point at structure and stale setup copy only

**Step 5: Commit**

```bash
git add tests/website/test_marketing_pages.py
git commit -m "test: update homepage setup-copy expectations"
```

### Task 2: Restore the old homepage structure and refresh setup/version copy

**Files:**
- Modify: `Docs/Website/index.html`
- Test: `tests/website/test_marketing_pages.py`

**Step 1: Write the failing test**

Use the Task 1 tests as the active failing contract.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- FAIL until `Docs/Website/index.html` is rewritten against the old live structure.

**Step 3: Write minimal implementation**

Patch the old live homepage structure with current setup truth:

```html
<div class="pill"><span class="dot" aria-hidden="true"></span> v0.1.26 · Beta · Inspired by <em>The Diamond Age</em></div>
```

```html
<div class="code-block">
  <div class="code-header">
    <span>Recommended: Docker + WebUI</span>
    <button class="copy-btn" data-code="make quickstart-prereqs&#10;git clone https://github.com/rmusser01/tldw_server.git&#10;cd tldw_server&#10;make quickstart">Copy</button>
  </div>
  <pre><code>make quickstart-prereqs
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server
make quickstart</code></pre>
</div>
```

Add separate blocks for `make quickstart-docker` and `make quickstart-install`, and add a text link to `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md`.

Also update the JSON-LD `softwareVersion` to `0.1.26`.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- PASS

**Step 5: Commit**

```bash
git add Docs/Website/index.html tests/website/test_marketing_pages.py
git commit -m "docs: refresh homepage setup and version copy"
```

### Task 3: Run security and deployment-readiness verification

**Files:**
- Modify: `tests/website/test_marketing_pages.py` if Bandit suppression comments are needed

**Step 1: Write the failing test**

No new behavior test; use the existing regression suite.

**Step 2: Run verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
source .venv/bin/activate && python -m bandit -r tests/website -f json -o /tmp/bandit_tldw_homepage_setup_copy.json
```

Expected:
- `pytest` PASS
- Bandit completes without actionable findings in the touched test scope

**Step 3: Write minimal implementation**

If Bandit reports pytest `assert` findings, suppress them explicitly with inline `# nosec B101` comments.

**Step 4: Run verification again**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
source .venv/bin/activate && python -m bandit -r tests/website -f json -o /tmp/bandit_tldw_homepage_setup_copy.json
```

Expected:
- `pytest` PASS
- Bandit JSON contains zero results

**Step 5: Commit**

```bash
git add Docs/Website/index.html tests/website/test_marketing_pages.py
git commit -m "test: verify homepage setup copy refresh"
```
