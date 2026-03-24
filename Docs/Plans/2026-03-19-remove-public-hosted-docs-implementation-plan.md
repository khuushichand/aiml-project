# Remove Public Hosted Docs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove hosted SaaS deployment docs from the public curated docs tree and tighten boundary enforcement so they cannot reappear in public docs surfaces.

**Architecture:** Treat the private repo as canonical for hosted deployment docs, hard-delete the public copies, remove hosted-doc exceptions from the public/private boundary checker, and add explicit tests asserting those files do not exist in `Docs/Published/Deployment`. Verify the public checker and strict MkDocs build remain green after the deletion.

**Tech Stack:** Markdown, Python, pytest, MkDocs, shell verification commands.

---

### Task 1: Add The Failing Absence Test

**Files:**
- Modify: `tldw_Server_API/tests/test_public_private_boundary.py`

**Step 1: Add a failing test for hosted doc absence**

Extend `tldw_Server_API/tests/test_public_private_boundary.py` with a test like:

```python
def test_public_curated_tree_does_not_ship_hosted_deployment_docs() -> None:
    hosted_docs = [
        Path("Docs/Published/Deployment/Hosted_SaaS_Profile.md"),
        Path("Docs/Published/Deployment/Hosted_Staging_Runbook.md"),
        Path("Docs/Published/Deployment/Hosted_Production_Runbook.md"),
    ]
    for path in hosted_docs:
        _require(not path.exists(), f"expected hosted doc to be absent from public tree: {path}")
```

**Step 2: Run the boundary test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: FAIL because the hosted docs still exist in the public repo.

### Task 2: Delete The Public Hosted Deployment Docs

**Files:**
- Delete: `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- Delete: `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- Delete: `Docs/Published/Deployment/Hosted_Production_Runbook.md`

**Step 1: Remove the public hosted deployment docs**

Delete the three hosted deployment docs from `Docs/Published/Deployment`.

Do not replace them with stubs, redirects, or placeholders.

**Step 2: Re-run the boundary test**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: still FAIL or stay red until the checker exceptions are tightened in the next task, depending on current test coverage.

**Step 3: Commit the public docs removal**

```bash
git add tldw_Server_API/tests/test_public_private_boundary.py Docs/Published/Deployment
git commit -m "docs: remove hosted deployment docs from public tree"
```

### Task 3: Tighten The Boundary Checker

**Files:**
- Modify: `Helper_Scripts/docs/check_public_private_boundary.py`

**Step 1: Remove hosted-doc skip exceptions**

Delete the `SKIP_PATHS` entries for:

- `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- `Docs/Published/Deployment/Hosted_Production_Runbook.md`

Keep the checker scoped to public publish/runtime surfaces only. Do not expand scanning into `Docs/Plans` or policy docs.

**Step 2: Run the checker**

Run:

```bash
source .venv/bin/activate
python Helper_Scripts/docs/check_public_private_boundary.py
```

Expected: PASS.

**Step 3: Re-run boundary pytest**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
```

Expected: PASS.

**Step 4: Commit the checker tightening**

```bash
git add Helper_Scripts/docs/check_public_private_boundary.py
git commit -m "test: tighten hosted docs boundary enforcement"
```

### Task 4: Verify The Public Docs Site Still Passes

**Files:**
- Verify: `Docs/mkdocs.yml`

**Step 1: Run the full public docs verification**

Run:

```bash
source .venv/bin/activate
python Helper_Scripts/docs/check_public_private_boundary.py
python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v
mkdocs build --strict -f Docs/mkdocs.yml
```

Expected:

- checker PASS
- boundary pytest PASS
- strict MkDocs PASS

**Step 2: Run Bandit on the touched Python scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r Helper_Scripts/docs/check_public_private_boundary.py tldw_Server_API/tests/test_public_private_boundary.py -f json -o /tmp/bandit_remove_public_hosted_docs.json
```

Expected: no new findings in the touched Python scope.

**Step 3: Commit the verification-only checkpoint if needed**

If verification required additional touched-scope edits, commit them. Otherwise, do not create an extra commit.
