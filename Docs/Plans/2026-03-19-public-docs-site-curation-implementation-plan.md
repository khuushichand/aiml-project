# Public Docs Site Curation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the public docs site pass `mkdocs build --strict -f Docs/mkdocs.yml` using the curated public docs set.

**Architecture:** Treat the curated docs tree under `Docs/Published` as the source of truth, shrink nav to match what actually exists, and repair only the broken links and anchors that remain in the retained public pages. Keep the OSS/private boundary checker in the loop so the docs cleanup does not reintroduce hosted/private material.

**Tech Stack:** MkDocs, Markdown, YAML, Python boundary checker, shell verification commands.

---

### Task 1: Baseline The Curated Public Docs Surface

**Files:**
- Inspect: `Docs/mkdocs.yml`
- Inspect: `Docs/Published/`
- Verify: `Helper_Scripts/docs/check_public_private_boundary.py`

**Step 1: List the currently curated published files**

Run:

```bash
find Docs/Published -type f | sort
```

Expected: a concrete inventory of what the public docs site can safely publish today.

**Step 2: Run the boundary checker**

Run:

```bash
source .venv/bin/activate
python Helper_Scripts/docs/check_public_private_boundary.py
```

Expected: PASS.

**Step 3: Run the strict MkDocs build to capture the current failure set**

Run:

```bash
source .venv/bin/activate
mkdocs build --strict -f Docs/mkdocs.yml
```

Expected: FAIL with missing nav targets, broken doc links, and the known embeddings anchor warning.

**Step 4: Commit nothing**

This task is baseline only.

### Task 2: Trim `Docs/mkdocs.yml` To The Real Curated Surface

**Files:**
- Modify: `Docs/mkdocs.yml`

**Step 1: Remove nav entries whose targets do not exist**

Edit `Docs/mkdocs.yml` so every retained entry points to a real file under `Docs/Published`.

Use these rules:

- keep `Home`, `Overview`, `Getting Started`, `Deployment`, and `Environment Variables` if the target files exist
- keep only API/Code/Monitoring/User Guide pages that actually exist in `Docs/Published`
- remove missing section indexes and dead leaf pages aggressively

**Step 2: Run the boundary checker**

Run:

```bash
source .venv/bin/activate
python Helper_Scripts/docs/check_public_private_boundary.py
```

Expected: PASS.

**Step 3: Run the strict MkDocs build**

Run:

```bash
source .venv/bin/activate
mkdocs build --strict -f Docs/mkdocs.yml
```

Expected: still FAIL, but with a much smaller set of warnings concentrated in retained pages such as `Docs/Published/Getting_Started/README.md`, `Docs/Published/Overview/Feature_Status.md`, and the embeddings anchor.

**Step 4: Commit the nav cleanup**

```bash
git add Docs/mkdocs.yml
git commit -m "docs: curate public mkdocs nav to published content"
```

### Task 3: Fix Broken Links In Retained Curated Pages

**Files:**
- Modify: `Docs/Published/Getting_Started/README.md`
- Modify: `Docs/Published/Overview/Feature_Status.md`

**Step 1: Fix Getting Started links**

In `Docs/Published/Getting_Started/README.md`:

- replace links to missing profile docs with links that exist in the curated public site, if suitable
- otherwise rewrite the text so it no longer points to missing local pages

**Step 2: Fix retained Feature Status links**

In `Docs/Published/Overview/Feature_Status.md`:

- replace relative links to missing curated docs with stable GitHub repo links where the source material is intentionally outside `Docs/Published`
- keep links to existing public curated pages only when the target file exists

**Step 3: Re-run the strict build**

Run:

```bash
source .venv/bin/activate
mkdocs build --strict -f Docs/mkdocs.yml
```

Expected: FAIL only if the known embeddings anchor warning remains or if a missed broken link still exists.

**Step 4: Commit the link cleanup**

```bash
git add Docs/Published/Getting_Started/README.md Docs/Published/Overview/Feature_Status.md
git commit -m "docs: repair curated public docs links"
```

### Task 4: Fix The Remaining Anchor Warning And Verify The Public Site

**Files:**
- Modify: `Docs/Published/Code_Documentation/Embeddings-Documentation.md`

**Step 1: Fix the bad TOC anchor**

Update the `Monitoring & Operations` entry in `Docs/Published/Code_Documentation/Embeddings-Documentation.md` so it matches the actual generated heading anchor.

**Step 2: Run the full public docs verification**

Run:

```bash
source .venv/bin/activate
python Helper_Scripts/docs/check_public_private_boundary.py
mkdocs build --strict -f Docs/mkdocs.yml
```

Expected:

- boundary checker PASS
- MkDocs strict build PASS

**Step 3: Run Bandit on the touched Python scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r Helper_Scripts/docs/check_public_private_boundary.py -f json -o /tmp/bandit_public_docs_curation.json
```

Expected: no new findings in the touched Python scope.

**Step 4: Commit the final docs-site fix**

```bash
git add Docs/Published/Code_Documentation/Embeddings-Documentation.md
git commit -m "docs: make curated public docs site pass strict build"
```
