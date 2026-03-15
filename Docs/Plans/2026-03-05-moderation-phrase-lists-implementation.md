# Moderation Phrase Lists Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add low-friction per-user Banlist/Notify phrase UX to the moderation page, with persisted per-user rules that are enforced by moderation runtime.

**Architecture:** Add typed `rules` to per-user moderation overrides, with strict validation at write-time and tolerant sanitization at load-time. Extend moderation runtime to merge per-user rules into effective policy with per-rule phase gating (`input`/`output`/`both`) and existing regex safety protections. Add a non-Advanced User-scope quick composer in WebUI that edits override draft rules and saves via existing override flow.

**Tech Stack:** FastAPI, Pydantic, Python moderation service, React + TypeScript + Ant Design, Pytest, Vitest

---

### Task 1: Add Backend Override Rule Schema

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/moderation_schemas.py`
- Modify: `tldw_Server_API/tests/unit/test_moderation_user_override_validation.py`

**Step 1: Write the failing test**

```python
from pydantic import ValidationError


def test_user_override_rules_schema_accepts_block_and_warn_with_phase():
    model = ModerationUserOverride(
        enabled=True,
        rules=[
            {
                "id": "r1",
                "pattern": "bad phrase",
                "is_regex": False,
                "action": "block",
                "phase": "both",
            },
            {
                "id": "r2",
                "pattern": "warn\\s+me",
                "is_regex": True,
                "action": "warn",
                "phase": "input",
            },
        ],
    )
    assert len(model.rules or []) == 2


def test_user_override_rules_schema_rejects_invalid_phase():
    with pytest.raises(ValidationError):
        ModerationUserOverride(
            rules=[{"id": "r1", "pattern": "x", "is_regex": False, "action": "block", "phase": "sideways"}]
        )
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_user_override_validation.py -k rules_schema -v`
Expected: FAIL because `rules` model/validation is missing.

**Step 3: Write minimal implementation**

```python
class ModerationOverrideRule(BaseModel):
    id: str = Field(..., min_length=1)
    pattern: str = Field(..., min_length=1)
    is_regex: bool = False
    action: Literal["block", "warn"]
    phase: Literal["input", "output", "both"] = "both"


class ModerationUserOverride(BaseModel):
    ...
    rules: Optional[list[ModerationOverrideRule]] = None
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_user_override_validation.py -k rules_schema -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/moderation_schemas.py tldw_Server_API/tests/unit/test_moderation_user_override_validation.py
git commit -m "feat(moderation): add per-user override rules schema"
```

### Task 2: Add Strict Write Validation and Tolerant Load Sanitization

**Files:**
- Modify: `tldw_Server_API/app/core/Moderation/moderation_service.py`
- Modify: `tldw_Server_API/tests/unit/test_moderation_user_override_validation.py`

**Step 1: Write the failing test**

```python
def test_set_user_override_rejects_invalid_rule_action(tmp_path):
    svc = ModerationService()
    svc._user_overrides_path = str(tmp_path / "overrides.json")

    res = svc.set_user_override(
        "user1",
        {
            "rules": [
                {"id": "bad", "pattern": "x", "is_regex": False, "action": "redact", "phase": "both"}
            ]
        },
    )

    assert res["ok"] is False
    assert "invalid rule action" in (res.get("error") or "")


def test_load_user_overrides_drops_invalid_rules_but_keeps_file_data(tmp_path):
    path = tmp_path / "overrides.json"
    path.write_text(
        json.dumps(
            {
                "alice": {
                    "rules": [
                        {"id": "bad", "pattern": "(", "is_regex": True, "action": "block", "phase": "both"},
                        {"id": "ok", "pattern": "safe", "is_regex": False, "action": "warn", "phase": "both"},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    svc = ModerationService()
    svc._user_overrides_path = str(path)

    loaded = svc._load_user_overrides()
    assert loaded["alice"]["rules"] == [
        {"id": "ok", "pattern": "safe", "is_regex": False, "action": "warn", "phase": "both"}
    ]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_user_override_validation.py -k "invalid_rule_action or drops_invalid_rules" -v`
Expected: FAIL because strict rule validation and tolerant sanitization are not implemented.

**Step 3: Write minimal implementation**

```python
def _validate_override_rules_strict(self, override: dict[str, object]) -> str | None:
    # Validate rule shape/action/phase/regex safety for write API path only
    ...


def _sanitize_user_override(self, override: dict[str, object]) -> dict[str, object]:
    # Never raise; drop invalid rule entries and keep valid ones
    ...


def set_user_override(self, user_id: str, override: dict[str, object]) -> dict[str, object]:
    err = self._validate_override_actions(override)
    if err:
        return {"ok": False, "persisted": False, "error": err}
    rule_err = self._validate_override_rules_strict(override)
    if rule_err:
        return {"ok": False, "persisted": False, "error": rule_err}
    normalized = self._sanitize_user_override(self._normalize_override_actions(override))
    ...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_user_override_validation.py -k "invalid_rule_action or drops_invalid_rules" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Moderation/moderation_service.py tldw_Server_API/tests/unit/test_moderation_user_override_validation.py
git commit -m "feat(moderation): strict rule validation with tolerant override sanitization"
```

### Task 3: Add Rule Phase to Runtime Pattern Model and Enforce It

**Files:**
- Modify: `tldw_Server_API/app/core/Moderation/moderation_service.py`
- Modify: `tldw_Server_API/tests/unit/test_moderation_check_text_snippet.py`

**Step 1: Write the failing test**

```python
def test_rule_phase_input_only_does_not_trigger_output():
    svc = ModerationService()
    rule = PatternRule(
        regex=re.compile(r"danger", re.IGNORECASE),
        action="block",
        phase="input",
    )
    policy = ModerationPolicy(enabled=True, input_enabled=True, output_enabled=True, block_patterns=[rule])

    in_action, _, _, _ = svc.evaluate_action("danger", policy, "input")
    out_action, _, _, _ = svc.evaluate_action("danger", policy, "output")

    assert in_action == "block"
    assert out_action == "pass"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_check_text_snippet.py -k phase_input_only -v`
Expected: FAIL because `PatternRule` has no `phase` and evaluator does not gate by rule phase.

**Step 3: Write minimal implementation**

```python
@dataclass
class PatternRule:
    regex: re.Pattern
    action: str | None = None
    replacement: str | None = None
    categories: set[str] | None = None
    phase: str = "both"  # input | output | both


# in check_text and _evaluate_action_internal loops
if isinstance(rule, PatternRule):
    rphase = (rule.phase or "both").lower()
    if rphase not in {"both", phase}:
        continue
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_check_text_snippet.py -k phase_input_only -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Moderation/moderation_service.py tldw_Server_API/tests/unit/test_moderation_check_text_snippet.py
git commit -m "feat(moderation): enforce per-rule phase gating"
```

### Task 4: Compile Per-User Rules with Existing Regex Safety

**Files:**
- Modify: `tldw_Server_API/app/core/Moderation/moderation_service.py`
- Modify: `tldw_Server_API/tests/unit/test_moderation_blocklist_parse.py`

**Step 1: Write the failing test**

```python
def test_user_regex_rule_rejected_when_dangerous():
    svc = ModerationService()
    override = {
        "rules": [
            {"id": "r1", "pattern": "(a+)+$", "is_regex": True, "action": "block", "phase": "both"}
        ]
    }
    err = svc._validate_override_rules_strict(override)
    assert "dangerous regex" in (err or "")
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_blocklist_parse.py -k dangerous_user_regex -v`
Expected: FAIL because strict per-user regex safety validation is missing.

**Step 3: Write minimal implementation**

```python
def _compile_user_rule(self, raw: dict[str, object]) -> PatternRule | None:
    pattern = str(raw.get("pattern", "")).strip()
    if not pattern:
        return None
    if bool(raw.get("is_regex")):
        if self._is_regex_dangerous(pattern):
            return None
        try:
            regex = re.compile(pattern, flags=re.IGNORECASE)
        except re.error:
            return None
    else:
        regex = re.compile(re.escape(pattern), flags=re.IGNORECASE)
    return PatternRule(regex=regex, action=str(raw.get("action", "warn")), phase=str(raw.get("phase", "both")))
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_blocklist_parse.py -k dangerous_user_regex -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Moderation/moderation_service.py tldw_Server_API/tests/unit/test_moderation_blocklist_parse.py
git commit -m "feat(moderation): apply regex safety checks to per-user rules"
```

### Task 5: Merge Per-User Rules into Effective Policy

**Files:**
- Modify: `tldw_Server_API/app/core/Moderation/moderation_service.py`
- Modify: `tldw_Server_API/tests/unit/test_moderation_test_endpoint_sample.py`

**Step 1: Write the failing test**

```python
def test_effective_policy_merges_user_rules_and_returns_warn_action():
    svc = ModerationService()
    svc._global_policy = ModerationPolicy(enabled=True, input_enabled=True, output_enabled=True, block_patterns=[])
    svc._user_overrides = {
        "alice": {
            "rules": [
                {"id": "r1", "pattern": "heads up", "is_regex": False, "action": "warn", "phase": "both"}
            ]
        }
    }

    policy = svc.get_effective_policy("alice")
    action, _, sample, _ = svc.evaluate_action("please heads up now", policy, "output")
    assert action == "warn"
    assert sample
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_test_endpoint_sample.py -k merges_user_rules -v`
Expected: FAIL because `get_effective_policy` does not append per-user rules.

**Step 3: Write minimal implementation**

```python
def get_effective_policy(self, user_id: str | None) -> ModerationPolicy:
    ...
    policy = ModerationPolicy(..., block_patterns=list(p.block_patterns or []), ...)
    user_rules = u.get("rules") if isinstance(u, dict) else None
    if isinstance(user_rules, list):
        for raw in user_rules:
            if not isinstance(raw, dict):
                continue
            compiled = self._compile_user_rule(raw)
            if compiled is not None:
                policy.block_patterns.append(compiled)
    return policy
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_test_endpoint_sample.py -k merges_user_rules -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Moderation/moderation_service.py tldw_Server_API/tests/unit/test_moderation_test_endpoint_sample.py
git commit -m "feat(moderation): merge per-user rules into effective policy"
```

### Task 6: Add API Contract Coverage for Rules Roundtrip

**Files:**
- Modify: `tldw_Server_API/tests/unit/test_moderation_user_override_contract.py`

**Step 1: Write the failing test**

```python
def test_get_user_override_returns_rules_payload(monkeypatch):
    monkeypatch.setattr(
        moderation_mod,
        "get_moderation_service",
        lambda: _Svc(
            {
                "alice": {
                    "enabled": True,
                    "rules": [
                        {"id": "r1", "pattern": "bad", "is_regex": False, "action": "block", "phase": "both"}
                    ],
                }
            }
        ),
    )
    app = _build_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/moderation/users/alice")

    assert resp.status_code == 200
    assert resp.json()["override"]["rules"][0]["action"] == "block"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_user_override_contract.py -k rules_payload -v`
Expected: FAIL until updated expected payload assertions are added.

**Step 3: Write minimal implementation**

```python
assert resp.json() == {
    "exists": True,
    "override": {
        "enabled": True,
        "rules": [
            {"id": "r1", "pattern": "bad", "is_regex": False, "action": "block", "phase": "both"}
        ],
    },
}
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_user_override_contract.py -k rules_payload -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/unit/test_moderation_user_override_contract.py
git commit -m "test(moderation): verify override rules API payload"
```

### Task 7: Add UI Rule Types and Ensure Payload/Dirty-State Include Rules

**Files:**
- Modify: `apps/packages/ui/src/services/moderation.ts`
- Modify: `apps/packages/ui/src/components/Option/ModerationPlayground/index.tsx`
- Modify: `apps/packages/ui/src/services/__tests__/moderation.service.contract.test.ts`

**Step 1: Write the failing test**

```ts
it("keeps rules in override payload type", async () => {
  bgRequestMock.mockResolvedValue({
    exists: true,
    override: {
      rules: [{ id: "r1", pattern: "bad", is_regex: false, action: "block", phase: "both" }]
    }
  })

  const response = await getUserOverride("alice")
  expect(response.override.rules?.[0].phase).toBe("both")
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/moderation.service.contract.test.ts`
Expected: FAIL due missing `rules` typing.

**Step 3: Write minimal implementation**

```ts
export interface ModerationOverrideRule {
  id: string
  pattern: string
  is_regex: boolean
  action: "block" | "warn"
  phase: "input" | "output" | "both"
}

export interface ModerationUserOverride {
  ...
  rules?: ModerationOverrideRule[]
}
```

Update moderation playground helpers so rules survive draft lifecycle:

```tsx
const buildOverridePayload = (draft: ModerationUserOverride): ModerationUserOverride => {
  const payload: ModerationUserOverride = {}
  ...
  if (draft.rules !== undefined) payload.rules = draft.rules
  return payload
}

const normalizeOverrideForCompare = (draft: ModerationUserOverride) => {
  const payload = buildOverridePayload(draft)
  if (payload.rules) {
    payload.rules = [...payload.rules].sort((a, b) => a.id.localeCompare(b.id))
  }
  ...
  return payload
}
```

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/moderation.service.contract.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/moderation.ts apps/packages/ui/src/components/Option/ModerationPlayground/index.tsx apps/packages/ui/src/services/__tests__/moderation.service.contract.test.ts
git commit -m "feat(webui): wire moderation override rules through payload and types"
```

### Task 8: Add Non-Advanced User Phrase Composer and Concrete Interaction Tests

**Files:**
- Modify: `apps/packages/ui/src/components/Option/ModerationPlayground/index.tsx`
- Add: `apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders quick phrase composer in user scope without advanced mode", async () => {
  render(<ModerationPlayground />)
  fireEvent.click(screen.getByRole("radio", { name: "User (Individual)" }))

  expect(screen.getByText("User Phrase Lists")).toBeInTheDocument()
  expect(screen.getByPlaceholderText("Add a word or phrase")).toBeInTheDocument()
})

it("adds ban and notify items to separate lists", async () => {
  render(<ModerationPlayground />)
  // load user id, add one ban phrase and one notify phrase
  // assert both list sections contain expected phrase rows
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx`
Expected: FAIL because composer/list UI and handlers do not exist.

**Step 3: Write minimal implementation**

```tsx
const [quickPhrase, setQuickPhrase] = React.useState("")
const [quickListType, setQuickListType] = React.useState<"ban" | "notify">("ban")
const [quickRegex, setQuickRegex] = React.useState(false)

const createRuleId = () =>
  (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function")
    ? crypto.randomUUID()
    : `rule-${Date.now()}-${Math.random().toString(16).slice(2)}`

const toQuickRule = (): ModerationOverrideRule => ({
  id: createRuleId(),
  pattern: quickPhrase.trim(),
  is_regex: quickRegex,
  action: quickListType === "ban" ? "block" : "warn",
  phase: "both"
})
```

Render card in default mode with User-scope gating and explicit helper copy.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/index.tsx apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx
git commit -m "feat(webui): add per-user moderation phrase composer"
```

### Task 9: Add Duplicate/Regex Validation and Save-Payload Assertion Test

**Files:**
- Modify: `apps/packages/ui/src/components/Option/ModerationPlayground/index.tsx`
- Modify: `apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx`

**Step 1: Write the failing test**

```tsx
it("prevents duplicate quick rules", async () => {
  // add same phrase twice with same list type and regex toggle
  // assert one row exists and warning shown
})

it("blocks invalid regex quick rule", async () => {
  // toggle regex, input invalid pattern "("
  // assert no row added and validation warning shown
})

it("includes rules in setUserOverride payload on save", async () => {
  // mock setUserOverride
  // add phrase and click Save override
  // assert payload.rules is present with action+phase fields
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx`
Expected: FAIL because validation and save payload assertions are not yet implemented.

**Step 3: Write minimal implementation**

```tsx
const isDuplicateRule = (candidate: ModerationOverrideRule, rules: ModerationOverrideRule[]) =>
  rules.some((rule) =>
    rule.pattern.toLowerCase() === candidate.pattern.toLowerCase() &&
    rule.is_regex === candidate.is_regex &&
    rule.action === candidate.action &&
    rule.phase === candidate.phase
  )

if (quickRegex) {
  try {
    new RegExp(pattern)
  } catch {
    messageApi.warning("Invalid regex pattern")
    return
  }
}

if (isDuplicateRule(nextRule, overrideDraft.rules ?? [])) {
  messageApi.warning("Phrase already exists in this list")
  return
}
```

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/ModerationPlayground/index.tsx apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx
git commit -m "feat(webui): validate quick phrase list entries and payload"
```

### Task 10: Verification and Security Gate

**Files:**
- Verify touched files only

**Step 1: Run backend moderation tests for touched behavior**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/unit/test_moderation_user_override_validation.py tldw_Server_API/tests/unit/test_moderation_user_override_contract.py tldw_Server_API/tests/unit/test_moderation_check_text_snippet.py tldw_Server_API/tests/unit/test_moderation_blocklist_parse.py tldw_Server_API/tests/unit/test_moderation_test_endpoint_sample.py -v`
Expected: PASS

**Step 2: Run frontend moderation tests**

Run: `bunx vitest run apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.quick-lists.test.tsx apps/packages/ui/src/services/__tests__/moderation.service.contract.test.ts`
Expected: PASS

**Step 3: Run Bandit on touched backend files**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Moderation/moderation_service.py tldw_Server_API/app/api/v1/schemas/moderation_schemas.py -f json -o /tmp/bandit_moderation_phrase_lists.json`
Expected: JSON generated; no new High findings in touched code.

**Step 4: Validate scope drift**

Run: `git status --short && git diff --stat`
Expected: Only intended moderation backend/UI files changed.

**Step 5: Final commit (if verification fixes needed)**

```bash
git add <final-fix-files>
git commit -m "chore(moderation): finalize per-user phrase list support"
```

## Notes for Implementer

- Keep plan files in `Docs/Plans` for this repo (existing convention).
- Do not regress Advanced blocklist studio or raw editor behavior.
- Do not allow invalid user rule writes to clobber existing persisted overrides.
- Ensure rule phase is enforced in both `check_text` and `evaluate_action` paths.
