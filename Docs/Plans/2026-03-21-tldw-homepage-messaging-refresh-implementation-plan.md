# tldw Homepage Messaging Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the broader `tldwproject.com` homepage messaging on the existing old structure so it reads as serious self-hosted OSS infrastructure while keeping `The Young Lady's Illustrated Primer` as the central project goal.

**Architecture:** Keep `Docs/Website/index.html` on the restored old live layout and update only the copy hierarchy in the hero, quickstart intro, about section, proof panel, features, and FAQ. Extend `tests/website/test_marketing_pages.py` so the Primer-forward, OSS/hackerish messaging is enforced alongside the already-updated setup/version guidance.

**Tech Stack:** Static HTML, inline CSS/JS, pytest, BeautifulSoup, Bandit

---

### Task 1: Add failing tests for the practical-first homepage messaging

**Files:**
- Modify: `tests/website/test_marketing_pages.py`
- Test: `tests/website/test_marketing_pages.py`

**Step 1: Write the failing test**

Add assertions for new messaging outcomes such as:

```python
def test_tldw_homepage_leads_with_primer_goal_and_direct_job():
    text = parse_html(TLDW_PAGE).get_text(" ", strip=True)

    assert "Ingest, transcribe, search, and talk to your source material." in text
    assert "The Young Lady's Illustrated Primer" in text
    assert "self-hosted step toward" in text
    assert "OpenAI-compatible Chat / Audio / Embeddings / Evals" in text
    assert "Your personal research assistant. Self-hosted. Privacy-first." not in text
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- FAIL because the current homepage still uses the rejected generic-practical copy.

**Step 3: Write minimal implementation**

Update the test file with the new messaging assertions while preserving the existing structure/setup assertions.

**Step 4: Run test to verify it fails for the right reason**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- FAIL only because the homepage HTML still has the rejected copy.

**Step 5: Commit**

```bash
git add tests/website/test_marketing_pages.py
git commit -m "test: define practical homepage messaging expectations"
```

### Task 2: Rewrite homepage messaging on the existing structure

**Files:**
- Modify: `Docs/Website/index.html`
- Test: `tests/website/test_marketing_pages.py`

**Step 1: Use the failing tests as the contract**

Keep the phase-1 setup/version tests plus the new messaging assertions active.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
```

Expected:
- FAIL until the homepage copy is updated.

**Step 3: Write minimal implementation**

Patch the homepage copy only:

- hero headline and lead
- quickstart intro sentence
- about copy
- proof panel bullets
- feature card headings and blurbs
- FAQ wording where it benefits clarity

Do not change:

- layout
- section IDs
- setup commands
- `VademHQ`

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
git commit -m "docs: tighten homepage messaging"
```

### Task 3: Run security and deployment-readiness verification

**Files:**
- Modify: `tests/website/test_marketing_pages.py` if additional `# nosec B101` comments are needed

**Step 1: Run verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
source .venv/bin/activate && python -m bandit -r tests/website -f json -o /tmp/bandit_tldw_homepage_messaging_refresh.json
```

Expected:
- `pytest` PASS
- Bandit completes without actionable findings in the touched scope

**Step 2: Write minimal implementation**

If Bandit reports pytest assert findings, annotate only the affected assertions with inline `# nosec B101`.

**Step 3: Run verification again**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/website/test_marketing_pages.py -v
source .venv/bin/activate && python -m bandit -r tests/website -f json -o /tmp/bandit_tldw_homepage_messaging_refresh.json
```

Expected:
- `pytest` PASS
- Bandit JSON contains zero results

**Step 4: Commit**

```bash
git add Docs/Website/index.html tests/website/test_marketing_pages.py
git commit -m "test: verify homepage messaging refresh"
```
