# Default Production Onboarding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the repo's default onboarding and `make quickstart` path provision a Docker single-user deployment, while moving local/dev setup into development documentation and keeping Docker multi-user + Postgres as the visible public/team deployment path.

**Architecture:** Treat onboarding as a contract across `README.md`, Getting Started docs, the website quickstart page, and the `Makefile`. Add small regression tests for docs metadata, entrypoint wording/order, and `Makefile` target wiring so the default path cannot silently drift back to local development.

**Tech Stack:** Markdown docs, Makefile, YAML manifest metadata, pytest docs tests, pytest utility tests.

---

### Task 1: Add failing onboarding contract tests

**Files:**
- Modify: `tldw_Server_API/tests/Docs/test_onboarding_entrypoints.py`
- Create: `tldw_Server_API/tests/Docs/test_onboarding_default_profile.py`
- Create: `tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py`

**Step 1: Write the failing docs test for the new default profile**

```python
from pathlib import Path

import yaml


def test_onboarding_manifest_marks_docker_single_user_as_default() -> None:
    manifest = yaml.safe_load(Path("Docs/Getting_Started/onboarding_manifest.yaml").read_text())
    assert manifest["default_profile"] == "docker_single_user"
```

**Step 2: Write the failing README/default entrypoint assertions**

```python
from pathlib import Path


def test_readme_points_first_quickstart_to_docker_single_user() -> None:
    text = Path("README.md").read_text()
    assert "make quickstart" in text
    assert "Docker single-user" in text
    assert text.index("make quickstart") < text.index("Local single-user")
    assert "apps/DEVELOPMENT.md" in text
```

**Step 3: Write the failing Makefile default-target assertion**

```python
from pathlib import Path
import re


def _target_block(makefile_text: str, target: str) -> str:
    pattern = rf"^{re.escape(target)}:.*?(?=^[A-Za-z0-9_.-]+:|\\Z)"
    match = re.search(pattern, makefile_text, flags=re.MULTILINE | re.DOTALL)
    assert match is not None
    return match.group(0)


def test_quickstart_target_delegates_to_docker_single_user() -> None:
    text = Path("Makefile").read_text(encoding="utf-8")
    quickstart = _target_block(text, "quickstart")
    assert "quickstart-docker" in quickstart
```

**Step 4: Run tests to verify they fail**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Docs/test_onboarding_entrypoints.py tldw_Server_API/tests/Docs/test_onboarding_default_profile.py tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py
```

Expected:
- failure because `default_profile` does not exist yet,
- failure because `README.md` still leads with local/dev setup,
- failure because `Makefile` `quickstart` still starts local uvicorn.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Docs/test_onboarding_entrypoints.py tldw_Server_API/tests/Docs/test_onboarding_default_profile.py tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py
git commit -m "test: lock default onboarding to docker quickstart"
```

### Task 2: Encode the default profile in onboarding metadata and index docs

**Files:**
- Modify: `Docs/Getting_Started/onboarding_manifest.yaml`
- Modify: `Docs/Getting_Started/README.md`
- Modify: `Docs/Published/Getting_Started/README.md`

**Step 1: Add manifest metadata for the default profile**

```yaml
default_profile: docker_single_user
profiles:
  local_single_user:
    title: "Local single-user"
```

**Step 2: Rewrite the Getting Started index introduction**

Required content:
- explicitly state `Docker single-user` is the default recommended profile,
- explicitly state `Docker multi-user + Postgres` is for teams/public deployments,
- explicitly state `Local single-user` is for development/debugging.

**Step 3: Mirror the same index content into the published docs copy**

Keep `Docs/Published/Getting_Started/README.md` aligned with the source page.

**Step 4: Run the targeted docs tests**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Docs/test_onboarding_manifest.py tldw_Server_API/tests/Docs/test_onboarding_default_profile.py tldw_Server_API/tests/Docs/test_published_onboarding_parity.py
```

Expected:
- all tests pass.

**Step 5: Commit**

```bash
git add Docs/Getting_Started/onboarding_manifest.yaml Docs/Getting_Started/README.md Docs/Published/Getting_Started/README.md
git commit -m "docs: make docker single-user the default onboarding profile"
```

### Task 3: Make the README and website production-first

**Files:**
- Modify: `README.md`
- Modify: `Docs/Website/index.html`

**Step 1: Rewrite the top-level quickstart block in `README.md`**

Required structure:
- first command path: `make quickstart`,
- explain that `make quickstart` provisions Docker single-user,
- include `make quickstart-docker-webui` as the optional WebUI add-on,
- add a clear callout for `Docker multi-user + Postgres`,
- move local Python and local WebUI setup under a `Development` or `For developers` section linking to `apps/DEVELOPMENT.md`.

**Step 2: Reorder website quickstart cards**

Required ordering:
1. Recommended: Docker single-user
2. Docker API + WebUI
3. Public/team deployment callout
4. Manual/local development section

**Step 3: Remove developer-only language from the main onboarding lead**

Examples to remove or demote:
- `make quickstart-install` as the first path,
- `bun run dev`,
- `npm run dev -- -p 8080` as a peer setup option.

**Step 4: Run the README entrypoint tests**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Docs/test_onboarding_entrypoints.py tldw_Server_API/tests/Docs/test_onboarding_default_profile.py
```

Expected:
- tests pass with Docker single-user as the first-class path.

**Step 5: Commit**

```bash
git add README.md Docs/Website/index.html
git commit -m "docs: make top-level onboarding production-first"
```

### Task 4: Switch `make quickstart` to Docker and quarantine local dev targets

**Files:**
- Modify: `Makefile`
- Modify: `Docs/Getting_Started/Profile_Local_Single_User.md`
- Modify: `Docs/Published/Getting_Started/Profile_Local_Single_User.md`
- Modify: `tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py`
- Create: `tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py`

**Step 1: Extract the current local targets into explicit dev-only names**

Target sketch:

```make
quickstart-local-dev-prereqs:
	@...

quickstart-local-dev:
	@echo "[quickstart-local-dev] Starting server on http://127.0.0.1:8000"
	$(PYTHON) -m uvicorn ...

quickstart-local-dev-install:
	@...
	@$(MAKE) quickstart-local-dev PYTHON=$(VENV_PYTHON)
```

**Step 2: Make `quickstart` delegate to Docker single-user**

Target sketch:

```make
quickstart:
	@$(MAKE) quickstart-docker
```

**Step 3: Convert `quickstart-install` into a compatibility/deprecation bridge**

Example behavior:

```make
quickstart-install:
	@echo "[quickstart-install] Local development setup moved. Use make quickstart-local-dev-install."
	@$(MAKE) quickstart-local-dev-install
```

This preserves existing muscle memory without keeping local dev as the default recommendation.

**Step 4: Update the local single-user profile text**

Required wording:
- local single-user is for development, local debugging, or contributors,
- private/self-hosted users should start with Docker single-user instead.

**Step 5: Run the Makefile tests**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py
```

Expected:
- Docker target hardening still passes,
- new default quickstart target test passes.

**Step 6: Commit**

```bash
git add Makefile Docs/Getting_Started/Profile_Local_Single_User.md Docs/Published/Getting_Started/Profile_Local_Single_User.md tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py
git commit -m "build: default quickstart to docker single-user"
```

### Task 5: Move local WebUI and API dev flows into developer docs

**Files:**
- Modify: `apps/DEVELOPMENT.md`

**Step 1: Add a dedicated local development setup section**

Required topics:
- local API startup,
- local WebUI startup,
- `bun run dev`,
- Turbopack cache/corruption caveat,
- `bun run dev:webpack` fallback,
- distinction between developer setup and recommended user deployment.

**Step 2: Link back to the production/self-hosting docs**

Required links:
- `README.md`
- `Docs/Getting_Started/README.md`
- `Docs/Getting_Started/Profile_Docker_Single_User.md`
- `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md`

**Step 3: Run a quick doc smoke check**

Run:
```bash
rg -n "quickstart-local-dev|dev:webpack|Docker single-user|Docker multi-user \\+ Postgres" apps/DEVELOPMENT.md README.md Docs/Getting_Started/README.md
```

Expected:
- all new link targets and labels are present.

**Step 4: Commit**

```bash
git add apps/DEVELOPMENT.md
git commit -m "docs: isolate local web and api setup in development guide"
```

### Task 6: Full verification and security check

**Files:**
- Verify touched files only

**Step 1: Run the combined regression suite**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Docs/test_onboarding_entrypoints.py tldw_Server_API/tests/Docs/test_onboarding_manifest.py tldw_Server_API/tests/Docs/test_onboarding_default_profile.py tldw_Server_API/tests/Docs/test_published_onboarding_parity.py tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py
```

Expected:
- all tests pass.

**Step 2: Run command-level verification for the renamed/default targets**

Run:
```bash
make -n quickstart
make -n quickstart-docker
make -n quickstart-install
make -n quickstart-local-dev
make -n quickstart-local-dev-install
```

Expected:
- `quickstart` prints delegation to Docker,
- local dev targets remain available under explicit names,
- compatibility messaging is visible for `quickstart-install`.

**Step 3: Run Bandit on the touched Python tests**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/tests/Docs/test_onboarding_entrypoints.py tldw_Server_API/tests/Docs/test_onboarding_default_profile.py tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py -f json -o /tmp/bandit_default_prod_onboarding.json
```

Expected:
- no new Bandit findings in touched Python files.

**Step 4: Final commit**

```bash
git add README.md Makefile Docs/Getting_Started/onboarding_manifest.yaml Docs/Getting_Started/README.md Docs/Getting_Started/Profile_Local_Single_User.md Docs/Published/Getting_Started/README.md Docs/Published/Getting_Started/Profile_Local_Single_User.md Docs/Website/index.html apps/DEVELOPMENT.md tldw_Server_API/tests/Docs/test_onboarding_entrypoints.py tldw_Server_API/tests/Docs/test_onboarding_default_profile.py tldw_Server_API/tests/Utils/test_docker_quickstart_hardening.py tldw_Server_API/tests/Utils/test_makefile_quickstart_default.py
git commit -m "docs: default onboarding to production docker setup"
```
