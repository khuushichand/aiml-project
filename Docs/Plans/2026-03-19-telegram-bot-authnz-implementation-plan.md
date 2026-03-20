# Telegram Bot + AuthNZ Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a tenant-scoped Telegram bot integration that supports assistant chat, persona chat, character chat, Jobs/workflow execution, and Telegram-native approvals under MCP Hub/AuthNZ-controlled scoped execution identities.

**Architecture:** Reuse the existing integration pattern from Slack/Discord for webhook intake, admin configuration, dedupe, and Jobs handoff, but make Telegram stricter on actor linkage and scope inheritance. All Telegram-originated execution must flow through a new scoped execution identity broker so MCP Hub remains the single policy authority for tools, workflows, personas, and spawned agents. Chat/session continuity should reuse existing assistant/persona/character stores, with Telegram metadata attached rather than creating a parallel store.

**Tech Stack:** FastAPI, Pydantic, existing AuthNZ repos and encrypted provider secrets, Jobs, Workflows, MCP Hub policy resolution, existing chat/persona/character services, pytest, Bandit

---

### Task 1: Add Telegram Permission and Schema Foundations

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/telegram_schemas.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/permissions.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_schemas.py`
- Test: `tldw_Server_API/tests/AuthNZ/unit/test_telegram_permission_constants.py`

**Step 1: Write the failing tests**

```python
from tldw_Server_API.app.core.AuthNZ import permissions as perms
from tldw_Server_API.app.api.v1.schemas.telegram_schemas import TelegramBotConfigUpdate


def test_telegram_permission_constants_exist():
    assert perms.TELEGRAM_ADMIN == "telegram.admin"
    assert perms.TELEGRAM_RECEIVE == "telegram.receive"
    assert perms.TELEGRAM_REPLY == "telegram.reply"


def test_telegram_bot_config_requires_token_and_secret():
    model = TelegramBotConfigUpdate(
        bot_token="123:abc",
        webhook_secret="secret-123",
        enabled=True,
    )
    assert model.bot_token == "123:abc"
    assert model.webhook_secret == "secret-123"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_schemas.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_permission_constants.py -v`

Expected: FAIL with import errors or missing permission constants.

**Step 3: Write minimal implementation**

```python
# permissions.py
TELEGRAM_ADMIN = "telegram.admin"
TELEGRAM_RECEIVE = "telegram.receive"
TELEGRAM_REPLY = "telegram.reply"


# telegram_schemas.py
class TelegramBotConfigUpdate(BaseModel):
    bot_token: str = Field(..., min_length=5)
    webhook_secret: str = Field(..., min_length=8)
    enabled: bool = True
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_schemas.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_permission_constants.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/telegram_schemas.py tldw_Server_API/app/core/AuthNZ/permissions.py tldw_Server_API/tests/Telegram/test_telegram_schemas.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_permission_constants.py
git commit -m "feat: add Telegram permission and schema foundations"
```

### Task 2: Build Tenant Bot Config and Admin API

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/telegram.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/telegram_support.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_admin_api.py`

**Step 1: Write the failing test**

```python
def test_put_and_get_telegram_bot_config(client, auth_header, monkeypatch):
    payload = {
        "bot_token": "123:abc",
        "webhook_secret": "secret-123",
        "enabled": True,
    }
    put_res = client.put("/api/v1/telegram/admin/bot", json=payload, headers=auth_header)
    assert put_res.status_code == 200

    get_res = client.get("/api/v1/telegram/admin/bot", headers=auth_header)
    assert get_res.status_code == 200
    assert get_res.json()["bot_username"] is not None
    assert get_res.json()["enabled"] is True
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_admin_api.py::test_put_and_get_telegram_bot_config -v`

Expected: FAIL with 404 or missing route.

**Step 3: Write minimal implementation**

```python
router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


@router.put("/admin/bot")
async def telegram_admin_put_bot(...):
    # encrypt bot token through the existing user/provider secret storage helper
    return {"ok": True, "enabled": True}


@router.get("/admin/bot")
async def telegram_admin_get_bot(...):
    return {
        "ok": True,
        "enabled": True,
        "bot_username": "example_bot",
    }
```

Also mount the router in `tldw_Server_API/app/main.py`.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_admin_api.py::test_put_and_get_telegram_bot_config -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/telegram.py tldw_Server_API/app/api/v1/endpoints/telegram_support.py tldw_Server_API/app/main.py tldw_Server_API/tests/Telegram/test_telegram_admin_api.py
git commit -m "feat: add Telegram admin bot configuration API"
```

### Task 3: Add Webhook Intake, Secret Validation, and Dedupe

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram_support.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_webhook.py`

**Step 1: Write the failing test**

```python
def test_telegram_webhook_rejects_invalid_secret(client):
    res = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"update_id": 1, "message": {"message_id": 10}},
    )
    assert res.status_code == 401


def test_telegram_webhook_dedupes_replayed_update(client, telegram_secret):
    payload = {"update_id": 5, "message": {"message_id": 10, "chat": {"id": 22}}}
    headers = {"X-Telegram-Bot-Api-Secret-Token": telegram_secret}
    first = client.post("/api/v1/telegram/webhook", headers=headers, json=payload)
    second = client.post("/api/v1/telegram/webhook", headers=headers, json=payload)
    assert first.status_code == 200
    assert second.json()["status"] == "duplicate"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_webhook.py -v`

Expected: FAIL with missing secret validation or dedupe handling.

**Step 3: Write minimal implementation**

```python
def _verify_telegram_secret(expected: str, provided: str | None) -> bool:
    return bool(expected and provided and secrets.compare_digest(expected, provided))


@router.post("/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    if not _verify_telegram_secret(expected_secret, request.headers.get("X-Telegram-Bot-Api-Secret-Token")):
        return JSONResponse(status_code=401, content={"ok": False, "error": "invalid_secret"})
    if _UPDATE_RECEIPTS.seen_or_store(str(payload["update_id"]), ttl=3600):
        return {"ok": True, "status": "duplicate"}
    return {"ok": True, "status": "accepted"}
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_webhook.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/telegram.py tldw_Server_API/app/api/v1/endpoints/telegram_support.py tldw_Server_API/tests/Telegram/test_telegram_webhook.py
git commit -m "feat: add Telegram webhook validation and dedupe"
```

### Task 4: Implement Actor Linking and Chat Policy Enforcement

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram_support.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_linking_and_policy.py`

**Step 1: Write the failing test**

```python
def test_start_link_creates_pairing_code(client, auth_header):
    res = client.post("/api/v1/telegram/admin/link/start", headers=auth_header)
    assert res.status_code == 200
    assert len(res.json()["pairing_code"]) >= 6


def test_unknown_user_is_denied_for_privileged_action(client, telegram_secret):
    payload = {
        "update_id": 7,
        "message": {
            "message_id": 4,
            "chat": {"id": 1, "type": "private"},
            "from": {"id": 99, "username": "unknown"},
            "text": "/persona set analyst",
        },
    }
    res = client.post("/api/v1/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": telegram_secret}, json=payload)
    assert res.status_code == 403
    assert res.json()["error"] == "account_link_required"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_linking_and_policy.py -v`

Expected: FAIL with missing link endpoints or no deny path.

**Step 3: Write minimal implementation**

```python
@router.post("/admin/link/start")
async def telegram_start_link(...):
    code = generate_pairing_code()
    await repo.create_pairing_code(...)
    return {"ok": True, "pairing_code": code}


def _resolve_actor_link(...):
    link = repo.get_actor_link(telegram_user_id)
    if not link and action in {"persona", "character", "workflow", "tool"}:
        raise HTTPException(status_code=403, detail="account_link_required")
    return link
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_linking_and_policy.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/telegram.py tldw_Server_API/app/api/v1/endpoints/telegram_support.py tldw_Server_API/tests/Telegram/test_telegram_linking_and_policy.py
git commit -m "feat: add Telegram actor linking and policy enforcement"
```

### Task 5: Add Command Parsing and Telegram Chat Modes

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram_support.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_commands.py`

**Step 1: Write the failing test**

```python
def test_parse_mode_and_ask_commands():
    parsed = parse_telegram_command("/mode persona")
    assert parsed["action"] == "mode"
    assert parsed["input"] == "persona"

    parsed = parse_telegram_command("/ask summarize the last report")
    assert parsed["action"] == "ask"
    assert parsed["input"] == "summarize the last report"


def test_group_chat_requires_explicit_command_for_freeform():
    decision = evaluate_group_message_policy(chat_type="group", text="hello bot", is_reply_to_bot=False)
    assert decision == "ignore"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_commands.py -v`

Expected: FAIL with missing parser or group policy helper.

**Step 3: Write minimal implementation**

```python
def parse_telegram_command(text: str) -> dict[str, str]:
    command, _, remainder = text.partition(" ")
    return {
        "action": command.lstrip("/").strip().lower(),
        "input": remainder.strip(),
    }


def evaluate_group_message_policy(*, chat_type: str, text: str, is_reply_to_bot: bool) -> str:
    if chat_type in {"group", "supergroup"} and not text.startswith("/") and not is_reply_to_bot:
        return "ignore"
    return "process"
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_commands.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/telegram_support.py tldw_Server_API/app/api/v1/endpoints/telegram.py tldw_Server_API/tests/Telegram/test_telegram_commands.py
git commit -m "feat: add Telegram command parsing and chat mode guards"
```

### Task 6: Map Telegram to Assistant, Persona, and Character Sessions

**Files:**
- Create: `tldw_Server_API/app/core/Telegram/session_mapper.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Modify: `tldw_Server_API/app/core/Persona/session_manager.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_session_mapper.py`

**Step 1: Write the failing test**

```python
def test_dm_session_key_is_tenant_plus_user():
    key = build_telegram_session_key(
        tenant_id="tenant-a",
        chat_id=100,
        chat_type="private",
        telegram_user_id=200,
        topic_id=None,
    )
    assert key == "tenant-a:dm:200"


def test_group_session_key_isolated_per_user_and_topic():
    key = build_telegram_session_key(
        tenant_id="tenant-a",
        chat_id=100,
        chat_type="supergroup",
        telegram_user_id=200,
        topic_id=300,
    )
    assert key == "tenant-a:group:100:topic:300:user:200"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_session_mapper.py -v`

Expected: FAIL with missing mapper module.

**Step 3: Write minimal implementation**

```python
def build_telegram_session_key(*, tenant_id: str, chat_id: int, chat_type: str, telegram_user_id: int, topic_id: int | None) -> str:
    if chat_type == "private":
        return f"{tenant_id}:dm:{telegram_user_id}"
    topic_part = topic_id if topic_id is not None else "root"
    return f"{tenant_id}:group:{chat_id}:topic:{topic_part}:user:{telegram_user_id}"
```

Then thread this key into the Telegram handler so assistant/persona/character flows reuse canonical session records instead of a Telegram-only store.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_session_mapper.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Telegram/session_mapper.py tldw_Server_API/app/api/v1/endpoints/telegram.py tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/app/core/Persona/session_manager.py tldw_Server_API/tests/Telegram/test_telegram_session_mapper.py
git commit -m "feat: map Telegram contexts onto canonical chat sessions"
```

### Task 7: Add Jobs Handoff and Telegram Reply Delivery

**Files:**
- Create: `tldw_Server_API/app/services/telegram_delivery_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_jobs_and_delivery.py`

**Step 1: Write the failing test**

```python
def test_ask_command_enqueues_job(client, telegram_secret, linked_user_payload):
    res = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": telegram_secret},
        json=linked_user_payload("/ask tell me about this repo"),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "queued"
    assert res.json()["request_id"]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_jobs_and_delivery.py::test_ask_command_enqueues_job -v`

Expected: FAIL with synchronous fallback or missing Jobs response.

**Step 3: Write minimal implementation**

```python
def enqueue_telegram_job(*, action: str, payload: dict[str, Any], owner_user_id: str) -> dict[str, Any]:
    job = job_manager.create_job(
        domain="telegram",
        queue="default",
        job_type=f"telegram_{action}",
        payload=payload,
        owner_user_id=owner_user_id,
        request_id=payload["request_id"],
    )
    return {"status": "queued", "job_id": job["id"], "request_id": payload["request_id"]}
```

Add a delivery service that wraps Telegram send-message calls and records delivery correlation for retries.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_jobs_and_delivery.py::test_ask_command_enqueues_job -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/telegram_delivery_service.py tldw_Server_API/app/api/v1/endpoints/telegram.py tldw_Server_API/tests/Telegram/test_telegram_jobs_and_delivery.py
git commit -m "feat: add Telegram Jobs handoff and delivery service"
```

### Task 8: Add Telegram Approval Callbacks and Exact-Scope Approval Records

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram_support.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_approvals.py`
- Test: `tldw_Server_API/tests/AuthNZ/unit/test_telegram_approval_scope.py`

**Step 1: Write the failing test**

```python
def test_only_initiating_user_can_approve_group_request(client, telegram_secret):
    approval_update = {
        "update_id": 20,
        "callback_query": {
            "id": "cbq-1",
            "from": {"id": 999},
            "data": "approve:approval-123",
            "message": {"chat": {"id": 333, "type": "supergroup"}},
        },
    }
    res = client.post("/api/v1/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": telegram_secret}, json=approval_update)
    assert res.status_code == 403
    assert res.json()["error"] == "approval_not_authorized"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_approvals.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_approval_scope.py -v`

Expected: FAIL with missing approval handling.

**Step 3: Write minimal implementation**

```python
def approval_scope_fingerprint(tool_name: str, args: dict[str, Any], workspace_ids: list[str]) -> str:
    material = json.dumps(
        {
            "tool": tool_name,
            "args": args,
            "workspace_ids": sorted(workspace_ids),
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def validate_approval_actor(*, approval: dict[str, Any], actor_user_id: str) -> None:
    if str(approval["initiating_auth_user_id"]) != str(actor_user_id):
        raise HTTPException(status_code=403, detail="approval_not_authorized")
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_approvals.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_approval_scope.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/telegram.py tldw_Server_API/app/api/v1/endpoints/telegram_support.py tldw_Server_API/tests/Telegram/test_telegram_approvals.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_approval_scope.py
git commit -m "feat: add Telegram exact-scope approval callbacks"
```

### Task 9: Build Telegram Scoped Execution Identity Broker

**Files:**
- Create: `tldw_Server_API/app/services/telegram_execution_identity_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram.py`
- Test: `tldw_Server_API/tests/AuthNZ/unit/test_telegram_execution_identity_service.py`
- Test: `tldw_Server_API/tests/AuthNZ/unit/test_telegram_downscoped_child_agents.py`

**Step 1: Write the failing test**

```python
def test_child_agent_identity_is_downscoped():
    parent = mint_telegram_identity(
        tenant_id="tenant-a",
        auth_user_id="42",
        permissions=["telegram.reply", "email.read", "email.delete"],
        capability_scopes={"tool": ["email.read", "email.delete"]},
    )
    child = mint_child_identity(parent, permissions=["telegram.reply", "email.read"])
    assert "email.read" in child.permissions
    assert "email.delete" not in child.permissions
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_telegram_execution_identity_service.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_downscoped_child_agents.py -v`

Expected: FAIL with missing execution identity broker.

**Step 3: Write minimal implementation**

```python
@dataclass
class TelegramExecutionIdentity:
    tenant_id: str
    auth_user_id: str
    permissions: list[str]
    source: str = "telegram"


def mint_child_identity(parent: TelegramExecutionIdentity, permissions: list[str]) -> TelegramExecutionIdentity:
    effective = [perm for perm in permissions if perm in set(parent.permissions)]
    return TelegramExecutionIdentity(
        tenant_id=parent.tenant_id,
        auth_user_id=parent.auth_user_id,
        permissions=effective,
    )
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_telegram_execution_identity_service.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_downscoped_child_agents.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/telegram_execution_identity_service.py tldw_Server_API/app/api/v1/endpoints/telegram.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_execution_identity_service.py tldw_Server_API/tests/AuthNZ/unit/test_telegram_downscoped_child_agents.py
git commit -m "feat: add Telegram scoped execution identities"
```

### Task 10: Final Integration Verification, Security Scan, and Docs Touch-Up

**Files:**
- Modify: `Docs/Plans/2026-03-19-telegram-bot-authnz-design.md`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_admin_api.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_webhook.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_linking_and_policy.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_commands.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_session_mapper.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_jobs_and_delivery.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_approvals.py`
- Test: `tldw_Server_API/tests/AuthNZ/unit/test_telegram_execution_identity_service.py`
- Test: `tldw_Server_API/tests/AuthNZ/unit/test_telegram_downscoped_child_agents.py`

**Step 1: Run the focused test suite**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Telegram/test_telegram_admin_api.py \
  tldw_Server_API/tests/Telegram/test_telegram_webhook.py \
  tldw_Server_API/tests/Telegram/test_telegram_linking_and_policy.py \
  tldw_Server_API/tests/Telegram/test_telegram_commands.py \
  tldw_Server_API/tests/Telegram/test_telegram_session_mapper.py \
  tldw_Server_API/tests/Telegram/test_telegram_jobs_and_delivery.py \
  tldw_Server_API/tests/Telegram/test_telegram_approvals.py \
  tldw_Server_API/tests/AuthNZ/unit/test_telegram_execution_identity_service.py \
  tldw_Server_API/tests/AuthNZ/unit/test_telegram_downscoped_child_agents.py \
  -v
```

Expected: PASS

**Step 2: Run Bandit on the touched scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/telegram.py \
  tldw_Server_API/app/api/v1/endpoints/telegram_support.py \
  tldw_Server_API/app/services/telegram_delivery_service.py \
  tldw_Server_API/app/services/telegram_execution_identity_service.py \
  tldw_Server_API/app/core/Telegram/session_mapper.py \
  -f json -o /tmp/bandit_telegram_bot.json
```

Expected: JSON report written with no new high-severity findings in touched code.

**Step 3: Update docs if implementation drifted from the approved design**

```markdown
- Adjust endpoint names, policy names, or constraints only if the code forced a defensible deviation.
- Keep the approved design doc authoritative and current.
```

**Step 4: Commit**

```bash
git add Docs/Plans/2026-03-19-telegram-bot-authnz-design.md \
  tldw_Server_API/app/api/v1/endpoints/telegram.py \
  tldw_Server_API/app/api/v1/endpoints/telegram_support.py \
  tldw_Server_API/app/services/telegram_delivery_service.py \
  tldw_Server_API/app/services/telegram_execution_identity_service.py \
  tldw_Server_API/app/core/Telegram/session_mapper.py \
  tldw_Server_API/tests/Telegram \
  tldw_Server_API/tests/AuthNZ/unit/test_telegram_execution_identity_service.py \
  tldw_Server_API/tests/AuthNZ/unit/test_telegram_downscoped_child_agents.py
git commit -m "feat: complete Telegram bot integration foundation"
```
