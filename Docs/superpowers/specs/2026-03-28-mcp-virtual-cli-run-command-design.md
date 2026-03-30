# MCP Virtual CLI `run(command)` Design

Date: 2026-03-28
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Add a first-class MCP tool, `run(command)`, that gives agents one Unix-like execution surface while preserving `tldw_server`'s existing governance model.

The design does not introduce a host shell or a second policy engine. Instead, it adds a virtual command runtime inside MCP Unified:

- agents primarily see one tool, `run(command)`
- the runtime parses CLI-like command strings with composition operators such as `|`, `&&`, `||`, and `;`
- each command resolves into existing MCP tools, modules, or sandbox capabilities
- MCP Hub policy, ACP runtime policy, persona scope, workspace/path enforcement, and approval semantics remain authoritative
- typed MCP tools stay visible as fallback escape hatches during rollout

This aims to improve agent completion rate, reduce tool-selection burden, and provide one portable execution surface across chat, ACP, personas, workflows, and future agent runtimes.

## Problem

The current platform has strong governance and tool execution primitives, but agent interaction is still tool-catalog shaped rather than command-surface shaped.

Today:

- MCP Unified exposes typed tools and modules through JSON-RPC and HTTP in [tldw_Server_API/app/core/MCP_unified/README.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/MCP_unified/README.md).
- server-side callers use the thin MCP wrapper in [tldw_Server_API/app/core/Tools/tool_executor.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Tools/tool_executor.py).
- chat-side auto-execution already normalizes assistant tool calls in [tldw_Server_API/app/core/Chat/tool_auto_exec.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Chat/tool_auto_exec.py).
- ACP sessions already enforce approval and runtime policy snapshots in [tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py).
- sandbox execution already exists as a governed MCP tool in [tldw_Server_API/app/core/MCP_unified/modules/implementations/sandbox_module.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/MCP_unified/modules/implementations/sandbox_module.py).

This gives the platform a solid control plane, but the agent-facing interface still has the classic failure mode of typed tool catalogs:

- the model must choose between many tool names and schemas
- composition usually takes multiple model turns
- help and error behavior varies by tool family
- portability across chat, ACP, personas, and future surfaces depends on keeping many tools and prompts aligned

The desired change is not to replace MCP governance. The desired change is to give agents a more natural, text-native execution surface on top of that governance.

## User-Approved Decisions

Validated during brainstorming:

1. Target the MCP layer first so the capability is available to all agent surfaces.
2. Make `run(command)` the preferred default surface rather than a thin optional alias.
3. Optimize for broad mixed use from day one, even if v1 starts with a narrow command set.
4. Default to a curated virtual CLI only, not raw shell access.
5. Primary success criteria are:
   - higher agent completion rate
   - lower integration complexity through one stable execution surface
   - stronger cross-runtime portability
6. Keep typed tools visible as fallback escape hatches in v1.
7. Preserve existing approval and policy semantics exactly. Change the interface, not the governing authority.

## Goals

- Give agents one primary execution tool, `run(command)`, instead of a large heterogeneous menu.
- Make command composition first-class through CLI operators rather than repeated model turns.
- Reuse current MCP Unified, MCP Hub, ACP, persona, and workspace governance rather than duplicating it.
- Create one portable execution surface that can behave consistently across chat, ACP, personas, workflows, and future runtimes.
- Improve agent recovery through progressive help, actionable errors, and consistent result formatting.

## Non-Goals

- Exposing an unrestricted host shell.
- Replacing MCP Unified with a shell runtime.
- Replacing MCP Hub policy, ACP policy snapshots, persona scope, or path/workspace enforcement.
- Simplifying or redesigning approval semantics in this effort.
- Hiding or deleting all typed tools in v1.
- Recreating every existing MCP tool as a command before rollout can begin.

## Current Repo Fit

This design layers onto existing repo structures rather than introducing a parallel execution stack.

### MCP Unified remains the authority

MCP Unified is already the platform's governed execution plane with RBAC, rate limiting, module registration, tool execution, and monitoring in [tldw_Server_API/app/core/MCP_unified/README.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/MCP_unified/README.md).

### Tool execution already has a stable wrapper

Server-side call sites can already route through [tldw_Server_API/app/core/Tools/tool_executor.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Tools/tool_executor.py), which means the new command runtime can stay protocol-focused and reuse current permission checks.

### ACP runtime policy already exists

ACP runtime permission outcomes already flow through policy snapshots and approval handling in [tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py) and permission tier heuristics in [tldw_Server_API/app/core/Agent_Client_Protocol/permission_tiers.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Agent_Client_Protocol/permission_tiers.py).

### Governance packs already define the right boundary

The approved governance-pack design explicitly says portable packs are not the live runtime authority and that adapters should map semantic capability intent onto concrete runtime behavior in [Docs/Plans/2026-03-13-opa-governance-packs-design.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/2026-03-13-opa-governance-packs-design.md). The virtual CLI should follow that same rule: it is an interface and adapter layer, not an authority layer.

### Sandbox already points toward argv-based execution

The sandbox MCP module already uses structured command arrays and explicit policy-aware execution rather than shell interpolation in [tldw_Server_API/app/core/MCP_unified/modules/implementations/sandbox_module.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/MCP_unified/modules/implementations/sandbox_module.py). That makes it a good explicit bridge command for the virtual CLI without requiring shell-first behavior.

## Approaches Considered

### Approach 1: Wrapper tool

Add a single `run(command)` MCP tool that mostly aliases existing typed MCP tools through a simple router.

Pros:

- smallest delivery risk
- minimal changes to agent prompts and tool exposure
- easy to thread through existing MCP and ACP surfaces

Cons:

- captures only the naming uniformity benefit
- does not create a genuine CLI substrate with compositional semantics
- likely underdelivers on the main thesis that models naturally work better inside one command namespace

### Approach 2: Virtual CLI runtime in MCP

Add a first-class command runtime inside MCP Unified with:

- command registry
- chain parser
- execution layer
- presentation layer
- command adapters that route into MCP tools, modules, and sandbox capabilities

Pros:

- strongest fit for the stated goals
- gives agents one true execution surface
- enables CLI-native composition and progressive command discovery
- portable across agent surfaces without changing governance

Cons:

- more architectural work up front
- requires careful guardrails so the command layer does not become a second policy engine

### Approach 3: Command-first surface compiled to structured plans

Accept command strings but compile them into structured execution plans before any tool calls.

Pros:

- easier to audit and validate than looser command parsing
- governance is straightforward to inspect

Cons:

- less Unix-like
- weaker match to the "LLMs already speak CLI" thesis
- risks becoming an artificial DSL rather than a natural command surface

## Recommendation

Use Approach 2: build a first-class virtual CLI runtime inside MCP Unified, with one hard rule:

`run(command)` is a façade over existing MCP governance, not an alternative authority.

## Proposed Design

### 1. Architecture Boundary

`run(command)` becomes a new agent-facing execution surface inside MCP Unified.

Stack:

1. Agent-facing tool menu
   - agents primarily see `run(command)` as their execution tool
   - typed tools remain visible as fallback escape hatches in v1

2. Virtual command runtime
   - parses command strings
   - resolves commands against a governed registry
   - executes command chains
   - formats results for model consumption

3. MCP adapter layer
   - each command maps to existing MCP tools, modules, or sandbox capabilities
   - command resolution is adapter-driven, not hardcoded into prompts

4. Governance layer
   - existing MCP Hub, ACP, persona, and workspace/path rules remain authoritative
   - approval and denial outcomes remain unchanged

The command layer owns interface and orchestration only.

### 2. Command Model

`run(command)` accepts one string and behaves like a controlled Unix-style command line over a finite command registry.

#### Supported composition operators

The parser supports:

- `|`
- `&&`
- `||`
- `;`
- quoted strings
- escaped spaces

Minimal grammar:

```txt
chain     := pipeline (("&&" | "||" | ";") pipeline)*
pipeline  := command ("|" command)*
command   := WORD+
```

#### Execution semantics

- `|` passes prior `stdout` into next command `stdin`
- `&&` executes next pipeline only if prior exit code is zero
- `||` executes next pipeline only if prior exit code is non-zero
- `;` executes next pipeline regardless of prior result

#### v1 pipe contract

The command runtime is text-stream-first.

Rules for v1:

- pipe payloads are UTF-8 text only
- commands with structured results must serialize to JSON or NDJSON text when they participate in pipes
- artifact-producing commands are terminal by default unless they expose an explicit text-rendering subcommand
- `json` is the canonical bridge command for inspecting or transforming structured text output

This prevents command adapters from inventing incompatible in-memory payload formats while still letting domain commands participate in Unix-style composition.

#### Command registry

Each command should carry explicit metadata:

- command name
- summary
- usage/help text
- argument grammar
- backend mapping rules
- read/write classification
- whether it can pipe
- which arguments imply path or workspace scope
- expected output type: text, structured, artifact

### 3. Two-Layer Runtime

The runtime should preserve the same execution/presentation split that motivated this design.

#### Execution layer

Responsibilities:

- parse the chain
- execute raw command semantics
- pass `stdout`, `stderr`, and exit codes between commands
- keep pipe data unmodified

Must not do:

- truncation
- metadata footers
- binary warnings inside pipe streams
- prompt-friendly formatting that would corrupt downstream command input

#### Presentation layer

Runs only after the chain completes. Responsibilities:

- binary guard
- output truncation and overflow handling
- stderr attachment
- normalized metadata footer
- artifact references for large outputs

This separation is required so CLI composition remains correct.

### 4. Governance, Routing, And Approval Semantics

The command runtime must be policy-transparent.

Execution flow:

1. Parse `run(command)` into a chain.
2. Resolve each command token into one or more backend execution steps.
3. Route each step through ordinary MCP permission and policy evaluation.
4. Preserve deny and approval outcomes exactly as they exist today.
5. Convert those outcomes into CLI-native result messages without altering the underlying authority.

#### Chain preflight and partial execution rules

Mutating chains need stricter behavior than read-only chains.

Rules for v1:

- if a chain contains any write-capable or approval-gated step, the runtime resolves and preflights the full chain before executing the first mutating step
- if any step is denied or requires approval that has not been granted, the chain does not begin execution
- once execution begins, the chain is still operationally non-atomic; runtime failures can still occur after earlier steps have succeeded
- when a mutating chain fails after execution has started, the result must clearly indicate partial execution so the agent does not assume rollback happened automatically

This keeps approval behavior predictable without pretending the runtime can provide full transactional rollback across arbitrary MCP-backed operations.

Rules:

- no second allowlist model
- no separate command policy DSL
- no command-local approval tiers
- no bypass of persona scope
- no bypass of workspace or path enforcement
- no bypass of ACP runtime policy snapshots

Examples:

- `cat file.md | grep TODO` may resolve to one MCP-backed file read plus one in-memory text filter step
- `sandbox run ...` resolves to the existing `sandbox.run` tool path
- `agent list` resolves to current ACP/admin listing capabilities
- `workflow status ...` resolves to current workflow APIs or MCP-backed adapters

The router translates commands into existing governed operations. It does not decide what is allowed.

### 5. Command Discovery, Help, And Error Design

This is the primary agent-usability layer.

#### Startup command index

At session start, agents receive a compact injected command index with one-line summaries only, grouped by domain.

The visible command list must be derived from the caller's effective policy and scope, not from the global registry.

Rules:

- do not advertise commands that cannot resolve to any currently allowed backend capability
- prefer annotating visible commands with posture such as read-only, approval-required, or limited
- ensure persona scope, ACP runtime policy, catalog scoping, and workspace/path restrictions can narrow what the agent sees

The command surface should reduce decision burden, not teach the agent commands it is guaranteed to have rejected.

Suggested grouping:

- files
- search
- knowledge
- media
- workflow
- agent
- sandbox
- system

#### Progressive help

- `run("command")` with no args returns usage
- `run("command subcommand")` with missing args returns subcommand-specific usage
- help stays local and on-demand instead of bloating session prompts

#### Error messages as routing hints

Every error should include:

- what went wrong
- what the agent should try next

Examples:

- unknown command -> suggest closest valid commands
- binary output -> suggest `see`, `artifact show`, or `cat -b`
- policy denial -> say blocked by policy rather than generic failure
- wrong modality -> route toward the correct command family

#### Consistent result footer

Every presented result ends with normalized execution metadata such as:

```txt
[exit:0 | 18ms]
```

#### Overflow mode

Large outputs produce:

- preview snippet
- overflow notice with size/line count
- artifact or temp reference
- exploration suggestions using normal commands

This teaches the model how to continue using the same command surface instead of requiring a second navigation system.

### 6. Initial Command Families

The long-term target is broad mixed use. v1 should still start with a narrow but cross-domain command set.

The current MCP module inventory does not yet expose generic filesystem primitives such as workspace-bounded list/read/write operations. That means v1 cannot be treated as a routing-only project.

Phase 1 foundation work should explicitly add a small MCP-native filesystem/text capability surface for workspace-bounded file access. Suggested primitives:

- `fs.list`
- `fs.read_text`
- `fs.write_text`

Command mapping expectations:

- `ls`, `cat`, and `write` adapt to the new filesystem primitives
- `grep`, `head`, `tail`, and `json` are pure runtime text transforms and do not require new backend modules
- `mcp`, `knowledge`, `media`, and `sandbox` already have clear backing surfaces in the current MCP inventory
- `workflow` is viable only when the chosen rollout slice explicitly targets the existing `kanban.workflow.*` surfaces
- `agent`, `memory`, and any top-level `search` alias are optional adapters only if a concrete MCP-backed implementation is chosen for the rollout slice

This keeps the design honest about implementation scope while preserving the intended v1 command set.

Phase 1 should explicitly split command families into core required commands and optional adapters.

#### Core required phase 1 commands

These are the commands that should be treated as required for the first implementation plan because they are either backed by existing MCP capabilities or by the new filesystem primitives already called out above.

##### Files and text

- `ls`
- `cat`
- `grep`
- `head`
- `tail`
- `write`

##### Structured inspection

- `json`

##### Platform retrieval

- `knowledge`
- `media`

##### Runtime and orchestration inspection

- `mcp`

##### Explicit execution bridge

- `sandbox`

#### Optional adapters after the core slice

These commands are desirable but should not be treated as mandatory phase 1 scope unless the chosen rollout slice explicitly depends on them and already has a concrete backing implementation.

- `workflow`
  - only if phase 1 intentionally targets the existing `kanban.workflow.*` tools as the first workflow surface
- `agent`
  - only if phase 1 defines a concrete ACP/admin-backed adapter surface rather than a generic placeholder command
- `memory`
  - only after memory is exposed through MCP as a real governed backend capability
- `search`
  - only after choosing whether it is a real command, a thin alias, or a policy-driven router over `knowledge` and `media`

All command families should still be adapters over existing MCP capabilities or explicitly added MCP primitives, not fresh backend subsystems invented by the command layer.

### 7. Agent Surface Policy

For v1:

- agents primarily see `run(command)`
- typed tools remain visible for fallback
- prompts and examples should bias toward `run(command)` first
- instrumentation should measure when agents still fall back to typed tools and why

This lets the platform validate the interface thesis before removing escape hatches.

## Rollout Plan

### Phase 1: MCP runtime foundation

- implement `run(command)` in MCP Unified
- add parser, registry, execution layer, and presentation layer
- add workspace-bounded filesystem MCP primitives required for `ls`, `cat`, and `write`
- add chain preflight for write-capable or approval-gated command chains
- add the core required command families only
- expose only to selected agent surfaces for evaluation

### Phase 2: Default agent surface

- make `run(command)` the preferred execution surface in chat, ACP, persona, and workflow agent prompts
- keep typed tools visible as fallback
- tune help, routing errors, and instrumentation based on observed failures

### Phase 3: Tool menu simplification decision

- evaluate whether some typed tools should become internal-only for certain agent surfaces
- do not remove typed tools until measurements show `run(command)` is materially improving outcomes

## Metrics

The design should be evaluated as an interface improvement, not just a feature launch.

Track:

- task completion rate
- fallback rate from `run(command)` to typed tools
- average command chain length
- average tool-call count per completed task
- retries per task
- approval-block frequency
- deny frequency by command family
- overflow frequency
- binary-guard frequency
- median time to task completion

Success means agents choose better actions and complete tasks in fewer turns, not merely that the new tool is used often.

## Testing And Validation

### Unit tests

- parser behavior for quoting and operators
- command registry resolution
- execution-layer pipe and chain semantics
- presentation-layer truncation, footer, binary guard, and stderr attachment
- command-to-MCP adapter translation

### Integration tests

- `run(command)` over HTTP MCP tool execution
- `run(command)` over ACP-backed agent sessions
- permission-preserving execution through MCP Hub and ACP runtime policy
- workspace/path-bound commands respecting existing scoping rules

### Regression tests

- command-layer denials match existing typed-tool denials
- approval-required commands still trigger current approval flows
- typed tool fallback remains available when `run(command)` cannot satisfy a task

## Risks

### Risk: command layer becomes a second policy engine

If command metadata starts carrying independent allow/deny semantics, the design will fork governance authority.

Mitigation:

- command registry stores routing metadata only
- all allow/deny outcomes continue to come from existing MCP and ACP policy systems

### Risk: virtual CLI grows into an unbounded pseudo-shell

If v1 tries to emulate too much shell behavior, delivery risk rises sharply and the platform starts maintaining a second execution environment.

Mitigation:

- keep the command set curated
- use explicit bridge commands such as `sandbox` rather than implicit shell fallback
- defer arbitrary shell behavior entirely

### Risk: portability breaks across agent surfaces

If chat, ACP, personas, and workflows each expose different command families or help text, the portability goal fails.

Mitigation:

- use one command registry
- share one help and error presentation model
- keep agent-surface differences limited to policy and prompt context, not command semantics

### Risk: mixed workloads create a weak first release

Broad mixed-use goals can tempt v1 into too much breadth.

Mitigation:

- keep v1 command families small
- choose families that exercise multiple product domains without trying to cover every edge case

## Open Questions For Planning

- Where should the command registry live inside MCP Unified so it is reusable by chat, ACP, and workflows without creating a new monolith?
- Which existing MCP tools or API handlers should back the first `search`, `knowledge`, `media`, and `workflow` commands?
- How should overflow artifacts be stored and referenced so they are available across HTTP, WS, and ACP session surfaces?
- Which agent surfaces should receive `run(command)` first for the highest signal with the lowest rollout risk?

## Decision

Adopt a first-class virtual CLI runtime inside MCP Unified with `run(command)` as the preferred agent execution surface.

Preserve all current policy and approval semantics exactly. The new command runtime is an interface and orchestration layer over existing governed MCP capabilities, not a new authority.
