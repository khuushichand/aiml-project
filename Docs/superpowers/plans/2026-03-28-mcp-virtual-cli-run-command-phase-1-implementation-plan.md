# MCP Virtual CLI `run(command)` Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the phase-1 MCP Unified foundation for a governed `run(command)` tool, including workspace-bounded filesystem primitives, a virtual command runtime, and a first-class `run` MCP tool backed by existing MCP capabilities.

**Architecture:** Keep MCP Unified as the only policy authority. Add a small command-runtime package that parses and executes a finite virtual CLI, expose filesystem primitives through a new MCP module, and expose `run(command)` through a new MCP module that compiles commands into governed MCP tool calls. Extend the protocol with reusable tool-call preparation and per-call write classification so `run` participates correctly in approval, validation, path scope, and idempotency without weakening existing safeguards.

**Tech Stack:** Python 3, FastAPI MCP Unified stack, Pydantic, existing MCP protocol/module registry, pytest

---

## Scope

- This plan intentionally covers phase 1 MCP runtime foundation only.
- Prompt/tool-menu bias for chat, ACP, personas, and workflow agents should be handled in a follow-up plan after this runtime slice is stable and instrumented.
- Optional adapters from the design (`workflow`, `agent`, `memory`, top-level `search`) are out of scope for this plan.

## File Structure

- `tldw_Server_API/app/core/MCP_unified/modules/base.py`
  Purpose: add a per-call write classification hook that defaults to existing tool-definition heuristics.
- `tldw_Server_API/app/core/MCP_unified/protocol.py`
  Purpose: extract reusable governed tool-call preparation/execution helpers, route write detection through the new hook, and keep idempotency/approval behavior centralized.
- `tldw_Server_API/app/core/MCP_unified/modules/implementations/filesystem_module.py`
  Purpose: expose `fs.list`, `fs.read_text`, and `fs.write_text` with workspace-bounded, text-first semantics.
- `tldw_Server_API/app/core/MCP_unified/command_runtime/__init__.py`
  Purpose: package marker for the virtual CLI runtime.
- `tldw_Server_API/app/core/MCP_unified/command_runtime/models.py`
  Purpose: define command AST nodes, execution result models, spill-file references, and presentation payload types.
- `tldw_Server_API/app/core/MCP_unified/command_runtime/parser.py`
  Purpose: tokenize quoted command strings and build chain/pipeline AST nodes.
- `tldw_Server_API/app/core/MCP_unified/command_runtime/registry.py`
  Purpose: hold command descriptors, help text, backend-tool requirements, and policy-aware visibility filtering.
- `tldw_Server_API/app/core/MCP_unified/command_runtime/executor.py`
  Purpose: execute chains/pipelines with raw text semantics, spill intermediate data when thresholds are exceeded, and coordinate chain preflight.
- `tldw_Server_API/app/core/MCP_unified/command_runtime/presentation.py`
  Purpose: apply binary guard, preview/overflow formatting, stderr attachment, and footer metadata after execution completes.
- `tldw_Server_API/app/core/MCP_unified/command_runtime/adapters.py`
  Purpose: implement command handlers for `ls`, `cat`, `write`, `grep`, `head`, `tail`, `json`, `knowledge`, `media`, `mcp`, and `sandbox`.
- `tldw_Server_API/app/core/MCP_unified/modules/implementations/run_command_module.py`
  Purpose: expose the `run` MCP tool, bridge the command runtime to governed MCP tool calls, and derive chain/step idempotency keys.
- `tldw_Server_API/Config_Files/mcp_modules.yaml`
  Purpose: register the new `filesystem`, `knowledge`, and `run_command` modules in the default MCP module inventory while keeping optional adapters out of phase 1.
- `tldw_Server_API/app/core/MCP_unified/README.md`
  Purpose: document the new module IDs, tool names, config expectations, and targeted validation commands.
- `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_nested_tool_preparation.py`
  Purpose: lock reusable protocol preflight/execution helpers and per-call write classification behavior.
- `tldw_Server_API/app/core/MCP_unified/tests/test_filesystem_module.py`
  Purpose: prove workspace-bounded list/read/write behavior and binary/text handling.
- `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_parser.py`
  Purpose: lock quoting, pipelines, and chain-operator parsing.
- `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_registry.py`
  Purpose: verify command discovery/help filtering by effective backend-tool visibility.
- `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_execution.py`
  Purpose: prove raw execution semantics, intermediate spill behavior, and non-atomic stop-on-failure behavior.
- `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_presentation.py`
  Purpose: prove binary guard, preview/overflow, stderr attachment, and footer formatting.
- `tldw_Server_API/app/core/MCP_unified/tests/test_run_command_module.py`
  Purpose: verify `run` help, core command adapters, chain preflight, and step-idempotency behavior.
- `tldw_Server_API/app/core/MCP_unified/tests/test_idempotency_and_category.py`
  Purpose: extend existing idempotency coverage so `run` participates correctly when a chain is write-capable.
- `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py`
  Purpose: verify `run` only advertises commands backed by tools that the current context can actually see/use.
- `tldw_Server_API/tests/MCP/test_mcp_tools_execute_authz.py`
  Purpose: prove HTTP MCP execution/authz paths work with the new `run` tool.
- `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`
  Purpose: prove `run` chain preflight respects path-scope approval/deny outcomes before any earlier write executes.

## Task 1: Extract Reusable Tool Preparation And Dynamic Write Classification

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/base.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_nested_tool_preparation.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_preexec_validation.py`

- [ ] **Step 1: Write the failing protocol tests for nested preparation and per-call write classification**

Create `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_nested_tool_preparation.py` with two focused tests:

```python
class DynamicRunModule(BaseModule):
    async def get_tools(self) -> list[dict[str, Any]]:
        return [create_tool_definition(
            name="run",
            description="dynamic run tool",
            parameters={"properties": {"command": {"type": "string"}}, "required": ["command"]},
            metadata={"category": "utility"},
        )]

    def is_write_tool_call(self, tool_name: str, arguments: dict[str, Any], tool_def: dict[str, Any] | None = None) -> bool:
        return str(arguments.get("command") or "").startswith("write ")
```

```python
async def test_prepare_tool_call_marks_write_from_arguments(monkeypatch):
    cfg = get_config()
    monkeypatch.setattr(cfg, "disable_write_tools", True, raising=False)
    with pytest.raises(PermissionError, match="Write tools are disabled"):
        await protocol.prepare_tool_call(
            tool_name="run",
            tool_args={"command": "write notes.txt hello"},
            context=context,
        )
```

```python
async def test_prepare_tool_call_allows_read_only_variant(monkeypatch):
    prepared = await protocol.prepare_tool_call(
        tool_name="run",
        tool_args={"command": "ls"},
        context=context,
    )
    assert prepared.is_write is False
```

Also extend `test_protocol_preexec_validation.py` so a write-capable dynamic tool still triggers validator enforcement after classification.

- [ ] **Step 2: Run the targeted protocol tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_nested_tool_preparation.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_preexec_validation.py \
  -v
```

Expected: FAIL because `BaseModule` only supports static `is_write_tool_def(...)` and `protocol.py` does not yet expose reusable preparation helpers.

- [ ] **Step 3: Implement the minimal reusable preparation flow in the protocol**

In `tldw_Server_API/app/core/MCP_unified/modules/base.py`, add a default per-call hook:

```python
def is_write_tool_call(
    self,
    tool_name: str,
    arguments: dict[str, Any],
    tool_def: dict[str, Any] | None = None,
) -> bool:
    if tool_def is not None:
        return self.is_write_tool_def(tool_def)
    return bool(re.search(r"(ingest|update|delete|create|import)", str(tool_name).lower()))
```

In `tldw_Server_API/app/core/MCP_unified/protocol.py`, add a reusable preparation dataclass and helper:

```python
@dataclass
class PreparedToolCall:
    module: BaseModule
    module_id: str
    tool_name: str
    tool_args: dict[str, Any]
    tool_def: dict[str, Any] | None
    is_write: bool
    idempotency_key: str | None
    idempotency_cache_key: str | None
```

```python
async def prepare_tool_call(..., idempotency_key: str | None = None)-> PreparedToolCall:
    # resolve module/tool def
    # sanitize args
    # compute is_write via module.is_write_tool_call(...)
    # enforce schema, write validators, path scope, approval, governance preflight
```

Then refactor `_handle_tools_call(...)` to call `prepare_tool_call(...)` and a small `execute_prepared_tool_call(...)` helper instead of duplicating the whole path inline.

- [ ] **Step 4: Re-run the targeted protocol tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_nested_tool_preparation.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_preexec_validation.py \
  -v
```

Expected: PASS, with read-only `run` variants staying allowed while write-capable variants inherit existing write-tool policy and validator behavior.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/modules/base.py \
  tldw_Server_API/app/core/MCP_unified/protocol.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_nested_tool_preparation.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_preexec_validation.py
git commit -m "feat: add reusable MCP tool preparation flow"
```

## Task 2: Add Workspace-Bounded Filesystem MCP Primitives

**Files:**
- Create: `tldw_Server_API/app/core/MCP_unified/modules/implementations/filesystem_module.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_filesystem_module.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

- [ ] **Step 1: Write the failing filesystem module tests**

Create `tldw_Server_API/app/core/MCP_unified/tests/test_filesystem_module.py` with coverage for list/read/write and path escape rejection:

```python
async def test_fs_read_text_returns_utf8_content(tmp_path):
    (tmp_path / "notes.txt").write_text("hello\n", encoding="utf-8")
    ctx = RequestContext("req-fs-read", user_id="1", metadata={"workspace_root": str(tmp_path), "cwd": "."})
    result = await module.execute_tool("fs.read_text", {"path": "notes.txt"}, context=ctx)
    assert result["content"] == "hello\n"
```

```python
async def test_fs_read_text_rejects_binary(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ValueError, match="binary"):
        await module.execute_tool("fs.read_text", {"path": "image.png"}, context=ctx)
```

```python
async def test_fs_write_text_rejects_escape(tmp_path):
    with pytest.raises(PermissionError, match="outside"):
        await module.execute_tool("fs.write_text", {"path": "../secret.txt", "content": "x"}, context=ctx)
```

- [ ] **Step 2: Run the new filesystem tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_filesystem_module.py \
  -v
```

Expected: FAIL because `FilesystemModule` does not exist yet.

- [ ] **Step 3: Implement the minimal filesystem module**

Create `tldw_Server_API/app/core/MCP_unified/modules/implementations/filesystem_module.py` with three tools:

```python
create_tool_definition(
    name="fs.list",
    description="List directory entries under the active workspace path scope.",
    parameters={"properties": {"path": {"type": "string"}}, "required": []},
    metadata={"category": "utility", "uses_filesystem": True, "path_boundable": True, "path_argument_hints": ["path"]},
)
```

```python
create_tool_definition(
    name="fs.write_text",
    description="Write a UTF-8 text file under the active workspace path scope.",
    parameters={
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "append": {"type": "boolean"},
        },
        "required": ["path", "content"],
    },
    metadata={"category": "management", "uses_filesystem": True, "path_boundable": True, "path_argument_hints": ["path"]},
)
```

Use the existing MCP Hub workspace root resolver service instead of inventing a new path root source:

```python
resolver = McpHubWorkspaceRootResolver()
scope = await resolver.resolve_for_context(
    session_id=context.session_id,
    user_id=context.user_id,
    workspace_id=context.metadata.get("workspace_id"),
    workspace_trust_source=context.metadata.get("workspace_trust_source"),
    owner_scope_type=context.metadata.get("owner_scope_type"),
    owner_scope_id=context.metadata.get("owner_scope_id"),
)
workspace_root = scope.get("workspace_root")
if not workspace_root:
    raise PermissionError("workspace_root_unavailable")
base_dir = Path(workspace_root).resolve()
cwd = str(context.metadata.get("cwd") or ".").strip()
target = (base_dir / cwd / requested_path).resolve()
if target != base_dir and base_dir not in target.parents:
    raise PermissionError("Path escapes the active workspace scope")
```

Keep `fs.read_text` text-only and reject binary payloads early.

- [ ] **Step 4: Add the failing path-scope integration test, then make it pass**

Extend `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py` with an `fs.write_text` case that uses the real `path_argument_hints` metadata and proves an out-of-scope path is denied or escalated before execution:

```python
request = {"name": "fs.write_text", "arguments": {"path": "../secret.txt", "content": "x"}}
with pytest.raises(ApprovalRequiredError):
    await protocol._handle_tools_call(request, context)
```

Then ensure `FilesystemModule` metadata and argument names let the existing path-scope service detect the target path correctly.

- [ ] **Step 5: Re-run the filesystem tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_filesystem_module.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  -v
```

Expected: PASS, with `fs.read_text` rejecting binary files and `fs.write_text` remaining path-boundable.

- [ ] **Step 6: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/modules/implementations/filesystem_module.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_filesystem_module.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py
git commit -m "feat: add workspace-bounded MCP filesystem tools"
```

## Task 3: Build Command Models, Parser, And Policy-Aware Registry

**Files:**
- Create: `tldw_Server_API/app/core/MCP_unified/command_runtime/__init__.py`
- Create: `tldw_Server_API/app/core/MCP_unified/command_runtime/models.py`
- Create: `tldw_Server_API/app/core/MCP_unified/command_runtime/parser.py`
- Create: `tldw_Server_API/app/core/MCP_unified/command_runtime/registry.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_parser.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_registry.py`

- [ ] **Step 1: Write the failing parser and registry tests**

Create `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_parser.py`:

```python
def test_parser_handles_quotes_pipes_and_and_operator():
    chain = parse_command('cat "notes one.txt" | grep ERROR && write out.txt "done"')
    assert chain.segments[0].commands[0].argv == ["cat", "notes one.txt"]
    assert chain.segments[0].commands[1].argv == ["grep", "ERROR"]
    assert chain.links == ["&&"]
```

Create `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_registry.py`:

```python
def test_registry_hides_commands_without_visible_backing_tools():
    registry = build_default_registry()
    visible = registry.visible_commands(allowed_tools={"fs.list", "mcp.tools.list"})
    assert "ls" in visible
    assert "mcp" in visible
    assert "knowledge" not in visible
    assert "sandbox" not in visible
```

- [ ] **Step 2: Run the parser and registry tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_parser.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_registry.py \
  -v
```

Expected: FAIL because the `command_runtime` package does not exist yet.

- [ ] **Step 3: Implement the command AST and parser**

In `tldw_Server_API/app/core/MCP_unified/command_runtime/models.py`, define focused dataclasses:

```python
@dataclass(frozen=True)
class CommandInvocation:
    argv: list[str]

@dataclass(frozen=True)
class Pipeline:
    commands: list[CommandInvocation]

@dataclass(frozen=True)
class CommandChain:
    segments: list[Pipeline]
    links: list[str]
```

In `parser.py`, implement a tokenizer that preserves quoted strings and operators:

```python
TOKEN_RE = re.compile(r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'|\|\||&&|[|;]|[^\s|;]+')
```

Build `parse_command(...)` so it returns `CommandChain` and rejects malformed sequences like `| grep` or dangling `&&`.

- [ ] **Step 4: Implement the policy-aware registry**

In `registry.py`, define descriptors that separate pure transforms from MCP-backed commands:

```python
@dataclass(frozen=True)
class CommandDescriptor:
    name: str
    summary: str
    backend_tools: tuple[str, ...]
    pure_transform: bool = False
```

```python
def visible_commands(self, allowed_tools: set[str]) -> dict[str, CommandDescriptor]:
    result = {}
    for name, descriptor in self._commands.items():
        if descriptor.pure_transform or any(tool in allowed_tools for tool in descriptor.backend_tools):
            result[name] = descriptor
    return result
```

Register only phase-1 core commands:

- `ls`, `cat`, `write` -> `fs.*`
- `grep`, `head`, `tail`, `json` -> pure transforms
- `knowledge` -> `knowledge.search`, `knowledge.get`
- `media` -> `media.search`, `media.get`
- `mcp` -> `mcp.modules.list`, `mcp.tools.list`
- `sandbox` -> `sandbox.run`

- [ ] **Step 5: Re-run the parser and registry tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_parser.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_registry.py \
  -v
```

Expected: PASS, with quoted paths preserved and command visibility filtered by backing-tool availability.

- [ ] **Step 6: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/command_runtime/__init__.py \
  tldw_Server_API/app/core/MCP_unified/command_runtime/models.py \
  tldw_Server_API/app/core/MCP_unified/command_runtime/parser.py \
  tldw_Server_API/app/core/MCP_unified/command_runtime/registry.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_parser.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_registry.py
git commit -m "feat: add MCP virtual CLI parser and registry"
```

## Task 4: Implement Raw Execution And Presentation Layers

**Files:**
- Create: `tldw_Server_API/app/core/MCP_unified/command_runtime/executor.py`
- Create: `tldw_Server_API/app/core/MCP_unified/command_runtime/presentation.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_execution.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_presentation.py`

- [ ] **Step 1: Write the failing execution tests**

Create `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_execution.py` to lock raw Unix-like semantics:

```python
async def test_executor_preserves_pipe_data_without_footer_pollution():
    result = await executor.execute(parse_command("cat notes.txt | grep ERROR | head 1"), context=ctx)
    assert result.stdout == "ERROR first line\n"
    assert result.exit_code == 0
```

```python
async def test_executor_spills_large_intermediate_output(tmp_path):
    result = await executor.execute(parse_command("cat huge.log | grep ERROR"), context=ctx)
    assert result.stdout_spool is not None
    assert result.stdout_spool.path.exists()
```

Also add `&&`, `||`, and `;` behavior checks so failures stop or continue exactly as expected.

- [ ] **Step 2: Run the new execution tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_execution.py \
  -v
```

Expected: FAIL because there is no executor yet.

- [ ] **Step 3: Implement the raw execution layer with a spill contract**

In `executor.py`, keep pipe data metadata-free and spill large intermediate stdout to disk instead of holding unbounded strings in memory:

```python
if len(buffer_bytes) > self._spill_threshold_bytes:
    spill_path = self._spill_dir / f"cmd-{request_id}-{step_index}.txt"
    spill_path.write_bytes(buffer_bytes)
    stdout_ref = SpillReference(path=spill_path, byte_count=len(buffer_bytes))
```

Execute operators with strict semantics:

- `|` passes prior stdout into the next command's stdin
- `&&` skips the next pipeline when the previous exit code is non-zero
- `||` skips the next pipeline when the previous exit code is zero
- `;` always continues

Do not append footers, stderr labels, or truncation markers inside the execution layer.

- [ ] **Step 4: Write the failing presentation tests**

Create `tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_presentation.py`:

```python
def test_presentation_truncates_and_points_to_spill_file(tmp_path):
    raw = RawExecutionResult(stdout="line\n" * 500, exit_code=0, duration_ms=12, stdout_spool=SpillReference(path=tmp_path / "cmd-1.txt", byte_count=2500))
    rendered = present_for_model(raw, line_limit=3, byte_limit=80)
    assert "--- output truncated" in rendered.text
    assert str(tmp_path / "cmd-1.txt") in rendered.text
```

```python
def test_presentation_rejects_binary_output():
    raw = RawExecutionResult(stdout_bytes=b"\x89PNG\r\n\x1a\n", exit_code=0, duration_ms=4)
    rendered = present_for_model(raw)
    assert "binary" in rendered.text.lower()
```

- [ ] **Step 5: Implement the presentation layer**

In `presentation.py`, apply post-execution formatting only after the whole chain completes:

```python
def present_for_model(raw: RawExecutionResult, line_limit: int = 200, byte_limit: int = 50_000) -> PresentedResult:
    # binary guard
    # preview/truncate with spill reference
    # attach stderr on failure
    # append [exit:N | Xms]
```

Make overflow guidance use the same CLI surface:

```text
--- output truncated (5000 lines, 198.5KB) ---
Full output: /tmp/mcp-run-command/cmd-3.txt
Explore: cat /tmp/mcp-run-command/cmd-3.txt | grep <pattern>
         cat /tmp/mcp-run-command/cmd-3.txt | tail 100
```

- [ ] **Step 6: Re-run the execution and presentation tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_execution.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_presentation.py \
  -v
```

Expected: PASS, with intermediate spill files available and model-facing formatting applied only after execution finishes.

- [ ] **Step 7: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/command_runtime/executor.py \
  tldw_Server_API/app/core/MCP_unified/command_runtime/presentation.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_execution.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_presentation.py
git commit -m "feat: add MCP virtual CLI execution layers"
```

## Task 5: Expose The `run` MCP Tool And Core Phase-1 Command Adapters

**Files:**
- Create: `tldw_Server_API/app/core/MCP_unified/command_runtime/adapters.py`
- Create: `tldw_Server_API/app/core/MCP_unified/modules/implementations/run_command_module.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_run_command_module.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/tests/test_idempotency_and_category.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py`

- [ ] **Step 1: Write the failing `run` module tests**

Create `tldw_Server_API/app/core/MCP_unified/tests/test_run_command_module.py` with four anchor cases:

```python
async def test_run_ls_uses_fs_list_and_returns_footer():
    result = await module.execute_tool("run", {"command": "ls"}, context=ctx)
    assert "notes.txt" in result["text"]
    assert "[exit:0 |" in result["text"]
```

```python
async def test_run_cat_without_path_returns_usage():
    result = await module.execute_tool("run", {"command": "cat"}, context=ctx)
    assert "usage" in result["text"].lower()
```

```python
async def test_run_preflights_write_chain_before_executing_first_step():
    with pytest.raises(ApprovalRequiredError):
        await module.execute_tool("run", {"command": "write notes.txt hi && sandbox python"}, context=ctx)
    assert not (workspace_root / "notes.txt").exists()
```

```python
async def test_run_derives_step_idempotency_from_parent_key():
    first = await module.execute_tool("run", {"command": "write notes.txt hi", "idempotencyKey": "demo-1"}, context=ctx)
    second = await module.execute_tool("run", {"command": "write notes.txt hi", "idempotencyKey": "demo-1"}, context=ctx)
    assert first == second
```

Also extend `test_protocol_allowed_tools.py` so `run` help only advertises commands backed by tools visible in the current context.

- [ ] **Step 2: Run the new `run` module tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_run_command_module.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py \
  -v
```

Expected: FAIL because the adapter layer and `run` MCP module do not exist yet.

- [ ] **Step 3: Implement the command adapter layer**

In `command_runtime/adapters.py`, separate pure transforms from governed MCP-backed commands:

```python
class AdapterContext(NamedTuple):
    protocol: MCPProtocol
    request_context: RequestContext
    parent_idempotency_key: str | None
```

```python
async def prepare_fs_write(argv: list[str], ctx: AdapterContext) -> PreparedToolCall:
    return await ctx.protocol.prepare_tool_call(
        tool_name="fs.write_text",
        tool_args={"path": argv[1], "content": argv[2]},
        context=ctx.request_context,
        idempotency_key=_derive_step_key(ctx.parent_idempotency_key, argv),
    )
```

Rules for phase 1:

- `ls`, `cat`, `write` compile to `fs.list`, `fs.read_text`, `fs.write_text`
- `knowledge`, `media`, `mcp`, `sandbox` compile to their existing MCP tools
- `grep`, `head`, `tail`, `json` operate as pure text transforms over stdin/stdout
- any unknown command returns an error with nearest valid suggestions

- [ ] **Step 4: Implement the `run` MCP module**

Create `run_command_module.py` with one MCP tool named `run`:

```python
{
    "name": "run",
    "description": "Execute a governed command in the MCP virtual CLI runtime.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "minLength": 1},
            "idempotencyKey": {"type": "string"},
        },
        "required": ["command"],
        "additionalProperties": False,
    },
    "metadata": {"category": "utility", "notes": "Wrapper tool; nested prepared MCP calls carry path/process metadata"},
}
```

Implementation rules:

- resolve `protocol` from `get_mcp_server().protocol`, falling back to `MCPProtocol()` in isolated tests
- build the visible command index from `protocol._handle_tools_list({}, context)` so help text is policy-aware
- parse the incoming command string once
- if any prepared step is write-capable or approval-gated, preflight every step before executing step 1
- do not rely on wrapper-level path scope metadata; nested prepared tool calls must carry the real `path_argument_hints`, `uses_filesystem`, and approval semantics
- classify the top-level call with `is_write_tool_call(...)` by inspecting the parsed chain and underlying prepared steps
- derive deterministic step idempotency keys from the parent key plus normalized step content:

```python
def _derive_step_key(parent_key: str | None, argv: list[str], step_index: int) -> str | None:
    if not parent_key:
        return None
    digest = hashlib.sha256(json.dumps({"argv": argv}, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"{parent_key}:step:{step_index}:{digest}"
```

- [ ] **Step 5: Re-run the `run` module tests and the existing idempotency tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_run_command_module.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_idempotency_and_category.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py \
  -v
```

Expected: PASS, with policy-filtered help, deterministic step idempotency, and whole-chain preflight for mutating chains.

- [ ] **Step 6: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/command_runtime/adapters.py \
  tldw_Server_API/app/core/MCP_unified/modules/implementations/run_command_module.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_run_command_module.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_idempotency_and_category.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py
git commit -m "feat: add governed run command MCP tool"
```

## Task 6: Register The New Modules, Document The Runtime, And Prove HTTP/Auth Behavior

**Files:**
- Modify: `tldw_Server_API/Config_Files/mcp_modules.yaml`
- Modify: `tldw_Server_API/app/core/MCP_unified/README.md`
- Modify: `tldw_Server_API/tests/MCP/test_mcp_tools_execute_authz.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

- [ ] **Step 1: Write the failing HTTP/auth integration tests**

Extend `tldw_Server_API/tests/MCP/test_mcp_tools_execute_authz.py` with an HTTP `tools/execute` case for `run`:

```python
payload = {"tool_name": "run", "arguments": {"command": "ls"}}
response = client.post("/api/v1/mcp/tools/execute", json=payload, headers=headers)
assert response.status_code == 200
assert "[exit:0 |" in response.json()["result"]["text"]
```

Add a denied-path chain case in `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`:

```python
with pytest.raises(ApprovalRequiredError):
    await protocol._handle_tools_call(
        {"name": "run", "arguments": {"command": "write ../secret.txt hi && cat ../secret.txt"}},
        context,
    )
```

Expected behavior: no earlier write executes when the chain is blocked during preflight.

- [ ] **Step 2: Run the integration tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP/test_mcp_tools_execute_authz.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  -v
```

Expected: FAIL because the new modules are not yet in the default inventory and `run` is not an executable HTTP tool.

- [ ] **Step 3: Register the new modules in the default MCP inventory**

Update `tldw_Server_API/Config_Files/mcp_modules.yaml` to add:

```yaml
- id: filesystem
  class: tldw_Server_API.app.core.MCP_unified.modules.implementations.filesystem_module:FilesystemModule
  enabled: true
  name: Filesystem
  version: "1.0.0"
  department: system
  max_concurrent: 16
  settings: {}
```

```yaml
- id: knowledge
  class: tldw_Server_API.app.core.MCP_unified.modules.implementations.knowledge_module:KnowledgeModule
  enabled: true
  name: Knowledge
  version: "1.0.0"
  department: knowledge
  max_concurrent: 10
  settings: {}
```

```yaml
- id: run_command
  class: tldw_Server_API.app.core.MCP_unified.modules.implementations.run_command_module:RunCommandModule
  enabled: true
  name: Run Command
  version: "0.1.0"
  department: system
  max_concurrent: 16
  settings:
    spill_dir: /tmp/mcp-run-command
    spill_threshold_bytes: 65536
    preview_line_limit: 200
    preview_byte_limit: 51200
```

Do not add `workflow`, `agent`, `memory`, or top-level `search` in this slice.

- [ ] **Step 4: Document the runtime and validation commands**

Update `tldw_Server_API/app/core/MCP_unified/README.md` to include:

- the new module IDs: `filesystem`, `knowledge`, `run_command`
- the new tool names: `fs.list`, `fs.read_text`, `fs.write_text`, `run`
- the phase-1 command families and which are pure transforms vs MCP-backed adapters
- the targeted validation commands from this plan

Keep the docs explicit that typed tools remain available and `run` is phase-1 foundation, not a raw host shell.

- [ ] **Step 5: Run the final targeted verification and security scan**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_nested_tool_preparation.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_filesystem_module.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_parser.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_registry.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_execution.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_command_runtime_presentation.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_run_command_module.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_idempotency_and_category.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_allowed_tools.py \
  tldw_Server_API/tests/MCP/test_mcp_tools_execute_authz.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  -v
```

Then run Bandit on the touched MCP scope:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/MCP_unified -f json -o /tmp/bandit_mcp_virtual_cli_phase1.json
```

Expected:

- all targeted pytest cases PASS
- `/tmp/bandit_mcp_virtual_cli_phase1.json` is created
- no new Bandit findings remain in the touched files

- [ ] **Step 6: Commit**

```bash
git add tldw_Server_API/Config_Files/mcp_modules.yaml \
  tldw_Server_API/app/core/MCP_unified/README.md \
  tldw_Server_API/tests/MCP/test_mcp_tools_execute_authz.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py
git commit -m "docs: register and validate MCP virtual CLI phase 1"
```
