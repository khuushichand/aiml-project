# Chat Slash Skills Commands Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add backend-native `/skills` and `/skill <name> [args]` slash commands that are discoverable in chat and execute against the existing Skills module with RBAC/rate-limit/injection parity.

**Architecture:** Extend the existing `command_router` registry with two new commands, then reuse `SkillsService` + existing skill execution helpers to list and run invocable skills. Keep discovery in `GET /api/v1/chat/commands`, preserve existing injection modes (`system|preface|replace`), and verify behavior with unit + integration coverage.

**Tech Stack:** FastAPI, command router (`tldw_Server_API.app.core.Chat.command_router`), Skills module (`SkillsService`, `SkillExecutor`, `context_integration`), pytest, Bandit.

**Skill References:** @test-driven-development @systematic-debugging @verification-before-completion

---

### Task 1: Register `/skills` and `/skill` in Command Metadata

**Files:**
- Modify: `tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py`
- Modify: `tldw_Server_API/app/core/Chat/command_router.py`
- Modify: `tldw_Server_API/Config_Files/privilege_catalog.yaml`

**Step 1: Write the failing test**

```python
@pytest.mark.unit
def test_list_commands_includes_skill_commands_metadata(monkeypatch):
    by_name = {entry["name"]: entry for entry in command_router.list_commands()}

    assert "skills" in by_name
    assert by_name["skills"]["usage"] == "/skills [filter]"
    assert by_name["skills"]["args"] == ["filter"]

    assert "skill" in by_name
    assert by_name["skill"]["usage"] == "/skill <name> [args]"
    assert by_name["skill"]["args"] == ["name", "args"]
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py::test_list_commands_includes_skill_commands_metadata -v
```

Expected: FAIL (commands not present yet).

**Step 3: Write minimal implementation**

```python
register_command(
    "skills",
    "List invocable skills for this user.",
    _skills_handler,
    required_permission="chat.commands.skills",
    usage="/skills [filter]",
    args=["filter"],
    requires_api_key=True,
    rbac_required=True,
)
register_command(
    "skill",
    "Execute an invocable skill by name.",
    _skill_handler,
    required_permission="chat.commands.skill",
    usage="/skill <name> [args]",
    args=["name", "args"],
    requires_api_key=True,
    rbac_required=True,
)
```

Also add privilege catalog entries for:

- `chat.commands.skills`
- `chat.commands.skill`

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py::test_list_commands_includes_skill_commands_metadata -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py tldw_Server_API/app/core/Chat/command_router.py tldw_Server_API/Config_Files/privilege_catalog.yaml
git commit -m "feat(chat-commands): register skills slash command metadata"
```

### Task 2: Implement `/skills` Listing Handler (Invocable Skills Only)

**Files:**
- Modify: `tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py`
- Modify: `tldw_Server_API/app/core/Chat/command_router.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_skills_command_lists_only_invocable_skills(monkeypatch):
    async def fake_list(ctx, filter_text=None):
        return [
            {"name": "summarize", "description": "Summarize docs", "argument_hint": "[topic]"},
            {"name": "code-review", "description": "Review code", "argument_hint": None},
        ]

    monkeypatch.setattr(command_router, "_list_invocable_skills", fake_list)
    ctx = command_router.CommandContext(user_id="u1", auth_user_id=1)

    res = await command_router.async_dispatch_command(ctx, "skills", None)
    assert res.ok
    assert "summarize" in res.content
    assert "code-review" in res.content

@pytest.mark.asyncio
async def test_skills_command_applies_filter(monkeypatch):
    async def fake_list(ctx, filter_text=None):
        assert filter_text == "sum"
        return [{"name": "summarize", "description": "Summarize docs", "argument_hint": None}]

    monkeypatch.setattr(command_router, "_list_invocable_skills", fake_list)
    ctx = command_router.CommandContext(user_id="u1", auth_user_id=1)

    res = await command_router.async_dispatch_command(ctx, "skills", "sum")
    assert res.ok
    assert "summarize" in res.content

@pytest.mark.unit
def test_filter_skills_for_query_matches_name_description_and_hint():
    skills = [
        {"name": "summarize", "description": "Summarize docs", "argument_hint": "[topic]"},
        {"name": "code-review", "description": "Review code", "argument_hint": None},
        {"name": "research", "description": "Deep analysis", "argument_hint": "[question]"},
    ]

    by_name = command_router._filter_skills_for_query(skills, "sum")
    assert [s["name"] for s in by_name] == ["summarize"]

    by_desc = command_router._filter_skills_for_query(skills, "analysis")
    assert [s["name"] for s in by_desc] == ["research"]

    by_hint = command_router._filter_skills_for_query(skills, "topic")
    assert [s["name"] for s in by_hint] == ["summarize"]
```

**Step 2: Run tests to verify failure**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py -k "skills_command_lists_only_invocable_skills or skills_command_applies_filter or filter_skills_for_query_matches_name_description_and_hint" -v
```

Expected: FAIL (`_list_invocable_skills` / `_filter_skills_for_query` / handler not implemented).

**Step 3: Write minimal implementation**

```python
def _filter_skills_for_query(skills: list[dict[str, Any]], query: str | None) -> list[dict[str, Any]]:
    if not query:
        return skills
    q = query.strip().lower()
    if not q:
        return skills
    return [
        s for s in skills
        if q in str(s.get("name", "")).lower()
        or q in str(s.get("description", "")).lower()
        or q in str(s.get("argument_hint", "")).lower()
    ]

async def _list_invocable_skills(ctx: CommandContext, filter_text: str | None = None) -> list[dict[str, Any]]:
    # resolve user runtime (user id, db, base path), then call SkillsService.get_context_payload_async()
    # return entries filtered by name/description/argument_hint when filter_text is provided

async def _skills_handler(ctx: CommandContext, args: str | None) -> CommandResult:
    filter_text = (args or "").strip() or None
    skills = _filter_skills_for_query(
        await _list_invocable_skills(ctx, filter_text=None),
        filter_text,
    )
    if not skills:
        return CommandResult(ok=True, command="skills", content="No invocable skills are available.", metadata={"count": 0})

    lines = [f"Available skills ({len(skills)}):"]
    for skill in skills:
        hint = f" {skill.get('argument_hint')}" if skill.get("argument_hint") else ""
        lines.append(f"- {skill['name']}{hint}: {skill.get('description') or 'No description'}")
    return CommandResult(ok=True, command="skills", content="\n".join(lines), metadata={"count": len(skills)})
```

**Step 4: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py -k "skills_command_lists_only_invocable_skills or skills_command_applies_filter or filter_skills_for_query_matches_name_description_and_hint" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py tldw_Server_API/app/core/Chat/command_router.py
git commit -m "feat(chat-commands): add /skills invocable listing handler"
```

### Task 3: Implement `/skill <name> [args]` Execution Handler

**Files:**
- Modify: `tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py`
- Modify: `tldw_Server_API/app/core/Chat/command_router.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_skill_command_requires_name(monkeypatch):
    ctx = command_router.CommandContext(user_id="u1", auth_user_id=1)
    res = await command_router.async_dispatch_command(ctx, "skill", None)
    assert not res.ok
    assert "Usage" in res.content

@pytest.mark.asyncio
async def test_skill_command_executes_inline(monkeypatch):
    async def fake_exec(ctx, skill_name, skill_args):
        assert skill_name == "summarize"
        assert skill_args == "release notes"
        return {"success": True, "execution_mode": "inline", "rendered_prompt": "Summarized", "fork_output": None}

    monkeypatch.setattr(command_router, "_execute_skill", fake_exec)
    ctx = command_router.CommandContext(user_id="u1", auth_user_id=1)
    res = await command_router.async_dispatch_command(ctx, "skill", "summarize release notes")
    assert res.ok
    assert "Summarized" in res.content

@pytest.mark.asyncio
async def test_skill_command_executes_fork(monkeypatch):
    async def fake_exec(ctx, skill_name, skill_args):
        return {"success": True, "execution_mode": "fork", "rendered_prompt": "ignored", "fork_output": "Fork result"}

    monkeypatch.setattr(command_router, "_execute_skill", fake_exec)
    ctx = command_router.CommandContext(user_id="u1", auth_user_id=1)
    res = await command_router.async_dispatch_command(ctx, "skill", "research-plan q1")
    assert res.ok
    assert "Fork result" in res.content

@pytest.mark.asyncio
async def test_skill_command_rejects_non_invocable_skill(monkeypatch):
    async def fake_exec(ctx, skill_name, skill_args):
        return {"success": False, "error": "skill_not_invocable"}

    monkeypatch.setattr(command_router, "_execute_skill", fake_exec)
    ctx = command_router.CommandContext(user_id="u1", auth_user_id=1)
    res = await command_router.async_dispatch_command(ctx, "skill", "hidden-skill x")
    assert not res.ok
    assert "not invocable" in res.content.lower()

@pytest.mark.asyncio
async def test_skill_command_reports_not_found(monkeypatch):
    async def fake_exec(ctx, skill_name, skill_args):
        return {"success": False, "error": "skill_not_found"}

    monkeypatch.setattr(command_router, "_execute_skill", fake_exec)
    ctx = command_router.CommandContext(user_id="u1", auth_user_id=1)
    res = await command_router.async_dispatch_command(ctx, "skill", "missing-skill x")
    assert not res.ok
    assert "not found" in res.content.lower()
```

**Step 2: Run tests to verify failure**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py -k "skill_command_requires_name or skill_command_executes_inline or skill_command_executes_fork or skill_command_rejects_non_invocable_skill or skill_command_reports_not_found" -v
```

Expected: FAIL.

**Step 3: Write minimal implementation**

```python
async def _execute_skill(ctx: CommandContext, skill_name: str, skill_args: str) -> dict[str, Any]:
    # call existing skills execution integration helper; enforce invocable checks

async def _skill_handler(ctx: CommandContext, args: str | None) -> CommandResult:
    payload = (args or "").strip()
    if not payload:
        return CommandResult(ok=False, command="skill", content="Usage: /skill <name> [args]", metadata={"error": "missing_name"})

    skill_name, _, skill_args = payload.partition(" ")
    result = await _execute_skill(ctx, skill_name.strip().lower(), skill_args.strip())

    if not result.get("success"):
        err = str(result.get("error") or "execution_failed")
        message = {
            "missing_name": "Usage: /skill <name> [args]",
            "skill_not_found": f"Skill '{skill_name.strip().lower()}' not found.",
            "skill_not_invocable": f"Skill '{skill_name.strip().lower()}' is not invocable.",
        }.get(err, "Skill execution failed.")
        return CommandResult(ok=False, command="skill", content=message, metadata={"error": err})

    mode = str(result.get("execution_mode") or "inline")
    output = str(result.get("fork_output") or "") if mode == "fork" else str(result.get("rendered_prompt") or "")
    return CommandResult(ok=True, command="skill", content=output or "Skill executed.", metadata={"execution_mode": mode, "skill_name": skill_name.strip().lower()})
```

**Step 4: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py -k "skill_command_requires_name or skill_command_executes_inline or skill_command_executes_fork or skill_command_rejects_non_invocable_skill or skill_command_reports_not_found" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py tldw_Server_API/app/core/Chat/command_router.py
git commit -m "feat(chat-commands): add /skill execution handler"
```

### Task 4: Wire Runtime Resolution and Command Discovery Integration Tests

**Files:**
- Modify: `tldw_Server_API/app/core/Chat/command_router.py`
- Modify: `tldw_Server_API/tests/Chat_NEW/integration/test_chat_commands_endpoint.py`
- Modify: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_command_injection.py`

**Step 1: Write failing integration assertions**

```python
@pytest.mark.integration
def test_list_chat_commands_basic(test_client, auth_headers, monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "true")
    r = test_client.get("/api/v1/chat/commands", headers=auth_headers)
    assert r.status_code == 200
    names = {c.get("name") for c in r.json()["commands"]}
    assert "skills" in names
    assert "skill" in names

@pytest.mark.integration
def test_list_chat_commands_rbac_filtering(test_client, auth_headers, monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "true")
    monkeypatch.setenv("CHAT_COMMANDS_REQUIRE_PERMISSIONS", "true")
    from tldw_Server_API.app.api.v1.endpoints import chat as chat_mod
    monkeypatch.setattr(chat_mod, "user_has_permission", lambda user_id, perm: False, raising=True)

    r = test_client.get("/api/v1/chat/commands", headers=auth_headers)
    names = {c.get("name") for c in r.json()["commands"]}
    assert "skills" not in names
    assert "skill" not in names

@pytest.mark.integration
def test_list_chat_commands_rbac_allow_path(test_client, auth_headers, monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "true")
    monkeypatch.setenv("CHAT_COMMANDS_REQUIRE_PERMISSIONS", "true")
    from tldw_Server_API.app.api.v1.endpoints import chat as chat_mod
    monkeypatch.setattr(chat_mod, "user_has_permission", lambda user_id, perm: True, raising=True)

    r = test_client.get("/api/v1/chat/commands", headers=auth_headers)
    names = {c.get("name") for c in r.json()["commands"]}
    assert "skills" in names
    assert "skill" in names

@pytest.mark.asyncio
async def test_orchestrator_skill_command_without_request_meta(monkeypatch):
    # Verifies resolver fallback works when command context has no request-scoped DB/base-path.
    from tldw_Server_API.app.core.Chat import command_router as command_router_module
    from tldw_Server_API.app.core.Chat import chat_orchestrator

    async def fake_exec(ctx, skill_name, skill_args):
        return {"success": True, "execution_mode": "inline", "rendered_prompt": "From resolver", "fork_output": None}

    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setattr(command_router_module, "_execute_skill", fake_exec)
    # Build minimal orchestrator chat invocation using '/skill summarize'
    # Assert injected command text is present and no runtime resolution exception occurs.
```

**Step 2: Run tests to verify failure**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/integration/test_chat_commands_endpoint.py -v
```

Expected: FAIL before runtime/metadata is complete.

**Step 3: Implement minimal runtime resolver improvements**

```python
async def _resolve_skills_runtime(ctx: CommandContext) -> tuple[int, Path, CharactersRAGDB]:
    # resolve auth_user_id, derive base path via DatabasePaths, open CharactersRAGDB

# _list_invocable_skills and _execute_skill should use _resolve_skills_runtime
# and close DB connections in finally blocks.
```

(If runtime data is already available in `ctx.request_meta`, use it first; fallback to resolver to support orchestrator paths.)

**Step 4: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/integration/test_chat_commands_endpoint.py -v
```

Expected: PASS.

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_command_injection.py -k orchestrator_skill_command_without_request_meta -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/command_router.py tldw_Server_API/tests/Chat_NEW/integration/test_chat_commands_endpoint.py
git add tldw_Server_API/tests/Chat_NEW/unit/test_chat_command_injection.py
git commit -m "test(chat-commands): cover runtime resolver + RBAC allow/deny for skills commands"
```

### Task 5: Add Slash Injection Coverage for `/skill` in `system|preface|replace` and Update Docs

**Files:**
- Modify: `tldw_Server_API/tests/Chat_NEW/integration/test_chat_command_replace_mode.py`
- Modify: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_command_injection.py`
- Modify: `Docs/User_Guides/WebUI_Extension/Chatbook_Tools_Getting_Started.md`
- Modify: `Docs/API-related/Chatbook_Features_API_Documentation.md`

**Step 1: Write failing integration test for replace injection**

```python
@pytest.mark.integration
def test_skill_command_replace_mode_injects_skill_output(test_client, auth_headers, monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "true")
    monkeypatch.setenv("CHAT_COMMAND_INJECTION_MODE", "replace")

    from tldw_Server_API.app.core.Chat import command_router

    async def fake_exec(ctx, skill_name, skill_args):
        return {"success": True, "execution_mode": "inline", "rendered_prompt": "Skill output", "fork_output": None}

    monkeypatch.setattr(command_router, "_execute_skill", fake_exec)

    payload = {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "/skill summarize notes"}], "stream": False}
    r = test_client.post("/api/v1/chat/completions", json=payload, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assistant_content = data["choices"][0]["message"]["content"]
    assert isinstance(assistant_content, str)
    assert "[/skill]" in assistant_content
    assert "Skill output" in assistant_content

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["system", "preface"])
async def test_skill_command_injection_modes(mode, monkeypatch):
    # Build minimal orchestrator call with '/skill summarize notes'
    # For 'system': assert injected system message includes [/skill] and user text is args-only.
    # For 'preface': assert user text is prefixed with [/skill] and contains args.
```

**Step 2: Run test to verify failure**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/integration/test_chat_command_replace_mode.py -k skill_command_replace_mode -v
```

Expected: FAIL until handler path is fully wired.

**Step 3: Implement minimal changes + docs updates**

- Ensure `/skill` output flows through standard `build_injection_text("skill", ...)` path.
- Update user-facing docs to include:
  - `/skills [filter]`
  - `/skill <name> [args]`
  - discovery endpoint examples including both commands.

**Step 4: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/integration/test_chat_command_replace_mode.py -k skill_command_replace_mode -v
```

Expected: PASS.

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_command_injection.py -k "skill_command_injection_modes" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Chat_NEW/integration/test_chat_command_replace_mode.py Docs/User_Guides/WebUI_Extension/Chatbook_Tools_Getting_Started.md Docs/API-related/Chatbook_Features_API_Documentation.md
git add tldw_Server_API/tests/Chat_NEW/unit/test_chat_command_injection.py
git commit -m "feat(chat-commands): verify /skill injection behavior across modes and document commands"
```

### Task 6: Verification Gate (Tests + Security Scan)

**Files:**
- No new code expected.

**Step 1: Run focused unit/integration suites**

Run:
```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Chat_NEW/unit/test_command_router.py \
  tldw_Server_API/tests/Chat_NEW/integration/test_chat_commands_endpoint.py \
  tldw_Server_API/tests/Chat_NEW/integration/test_chat_command_replace_mode.py \
  tldw_Server_API/tests/Chat_NEW/unit/test_chat_command_injection.py -v
```

Expected: PASS.

**Step 2: Run skills regression smoke**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Skills/integration/test_skills_api.py -k "list_skills or create_skill_and_get" -v
```

Expected: PASS (no regression in Skills API behavior).

**Step 3: Run Bandit on touched scope**

Run:
```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Chat/command_router.py tldw_Server_API/app/api/v1/endpoints/chat.py -f json -o /tmp/bandit_chat_slash_skills.json
```

Expected: no new high-signal findings in changed code.

**Step 4: Inspect git diff and finalize**

Run:
```bash
git status --short
git log --oneline -n 6
```

Expected: only intended files changed; commit history follows task checkpoints.

**Step 5: Final commit (if any uncommitted follow-up remains)**

```bash
git add <remaining_files>
git commit -m "chore(chat-commands): finalize slash skills verification and docs"
```
