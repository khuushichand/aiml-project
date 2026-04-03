# MCP Virtual CLI Phase 2a Chat + ACP Rollout Design

Date: 2026-03-30
Status: Approved in conversation; written for user review
Owner: Codex brainstorming session

## Summary

Phase 2a rolls the existing MCP virtual CLI `run(command)` surface into `chat` and ACP as the preferred agent workbench without changing the phase 1 runtime or command family set.

This is a rollout-and-behavior slice, not a runtime-expansion slice.

The main change is agent-facing presentation:

- `run(command)` is taught first in prompts and examples
- `run(command)` is ordered first in agent-facing tool lists
- typed tools remain executable and visible, but are described as fallback tools
- rollout is gated for selected `chat` and ACP cohorts
- telemetry is required before widening the gate

The design preserves current MCP governance, ACP runtime policy, approval semantics, and typed-tool execution. It changes what agents are taught to prefer, not what the platform allows.

## Problem

Phase 1 created the governed `run(command)` runtime and kept typed tools visible as fallback. That is necessary, but not sufficient, to change model behavior.

Today, the main agent surfaces still present tool catalogs in a mostly peer-level way:

- chat already supports server-side tool auto-execution, allow-catalog filtering, and tool-turn limits in [chat_service.py](tldw_Server_API/app/core/Chat/chat_service.py) and [tool_auto_exec.py](tldw_Server_API/app/core/Chat/tool_auto_exec.py)
- ACP already formats MCP tools for LLM use in [mcp_llm_caller.py](tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_llm_caller.py) and runs LLM-driven tool loops in [mcp_runners.py](tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_runners.py)
- ACP permission and runtime policy remain enforced in [runner_client.py](tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py)

If `run(command)` is available but taught as just another tool among peers, tool-selection burden does not drop much in practice. Phase 2a exists to turn the phase 1 runtime into a measurable interface shift on the highest-value agent surfaces first.

## User-Approved Decisions

Validated during brainstorming:

1. Phase 2 should start with `chat + ACP`, not all agent surfaces at once.
2. Phase 2a should keep the phase 1 command surface unchanged.
3. Rollout should be gated first rather than default-on for all agents.
4. Typed tools should be demoted in prompt wording, examples, and ordering, but remain executable and visible as fallback.
5. Widening the rollout requires telemetry, not intuition.
6. The preferred phase 2a approach is prompt plus tool-surface shaping, not prompt-only bias and not typed-tool virtualization.
7. The initial chat rollout cohort should be limited to provider and runtime combinations with stable tool-calling behavior; provider variance is not part of the first experiment.
8. Chat and ACP should use parallel run-first prompt fragments tuned per surface rather than one shared prompt string.

## Goals

- Make `run(command)` the taught first-choice execution surface for gated `chat` and ACP agents.
- Reduce peer-level competition between `run(command)` and typed tools in agent-facing context.
- Keep escape hatches available when `run(command)` is insufficient or when direct structured mutation is clearly better.
- Measure whether run-first presentation reduces tool-selection churn without harming completion.
- Reuse the phase 1 runtime and current governance systems instead of adding new execution paths.

## Non-Goals

- Adding new command families in this phase.
- Hiding typed tools completely.
- Changing MCP or ACP approval semantics.
- Expanding rollout to personas or workflows in this design.
- Reworking the phase 1 runtime, parser, execution layer, or presentation layer.
- Treating prompt edits alone as sufficient evidence of success.

## Current Repo Fit

Phase 2a fits current seams with relatively small surface-level changes.

### Chat already has the right configuration hooks

Chat already exposes:

- `CHAT_AUTO_EXECUTE_TOOLS`
- `CHAT_TOOL_ALLOW_CATALOG`
- `CHAT_MAX_TOOL_CALLS`
- `CHAT_TOOL_TIMEOUT_MS`
- `CHAT_TOOL_IDEMPOTENCY`

in [chat_service.py](tldw_Server_API/app/core/Chat/chat_service.py), while normalized execution outcomes already flow through [tool_auto_exec.py](tldw_Server_API/app/core/Chat/tool_auto_exec.py).

That means chat does not need a new execution engine for phase 2a. It needs gated prompt shaping, tool-order shaping, and telemetry tags.

The important boundary is that these chat hooks are execution-time controls and telemetry seams, not the primary model-facing tool-shaping seam.

For chat, run-first ordering and description shaping must happen before the provider call, where `llm_tools` and `llm_tool_choice` are assembled and passed into [chat_orchestrator.py](tldw_Server_API/app/core/Chat/chat_orchestrator.py). Post-selection paths such as [tool_auto_exec.py](tldw_Server_API/app/core/Chat/tool_auto_exec.py) should classify and record outcomes, but they cannot change what the model saw when choosing tools.

### ACP already centralizes tool formatting

ACP converts MCP tools into LLM-facing tool definitions in [mcp_llm_caller.py](tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_llm_caller.py). The LLM-driven loop then consumes those formatted tools in [mcp_runners.py](tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_runners.py).

That is the right seam for:

- ordering `run` first
- shortening or demoting typed-tool descriptions
- attaching rollout-specific prompt guidance
- recording first-tool and fallback behavior

The current helper in [mcp_llm_caller.py](tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_llm_caller.py) is intentionally context-free. Phase 2a should therefore add a session-aware ACP tool-presentation layer above that helper, or extend the formatting boundary explicitly, rather than quietly embedding rollout policy into a pure conversion utility.

### Governance already lives below the surface layer

ACP permission, runtime policy snapshots, and interactive approvals already remain authoritative in [runner_client.py](tldw_Server_API/app/core/Agent_Client_Protocol/runner_client.py). Phase 2a should not duplicate or reinterpret those rules.

The surface policy is:

- bias the agent toward `run`
- allow direct typed fallback
- preserve all current execution and approval behavior underneath

## Approaches Considered

### Approach 1: Prompt-only bias

Change prompt text and examples so agents are told to prefer `run(command)`, but keep tool descriptions and ordering mostly unchanged.

Pros:

- lowest implementation cost
- smallest rollout risk

Cons:

- weak leverage because typed tools still appear as peers
- likely too small a shift to materially change first-tool choice

### Approach 2: Prompt plus tool-surface shaping

Bias prompts toward `run(command)`, reorder tools so `run` appears first, demote typed-tool descriptions, keep typed tools executable and visible, and instrument the result.

Pros:

- strongest match to the approved goal
- uses the phase 1 runtime unchanged
- preserves typed fallback while still creating a real run-first surface

Cons:

- requires consistency across chat and ACP
- needs careful telemetry so rollout decisions are evidence-based

### Approach 3: Surface virtualization

Expose only `run(command)` to gated agents and keep typed tools internal-only.

Pros:

- cleanest single-tool experience

Cons:

- too aggressive for phase 2a
- riskier if `run` still has help or adapter gaps
- harder to compare fallback behavior because escape hatches disappear from agent context

## Recommendation

Use Approach 2: prompt plus tool-surface shaping.

This is the smallest slice that can plausibly change agent behavior in a measurable way while preserving typed-tool fallback and all current governance semantics.

## Proposed Design

### 1. Scope And Boundary

Phase 2a is a rollout-and-behavior slice for `chat + ACP`.

It changes:

- prompt guidance
- examples
- tool ordering
- tool description framing
- rollout gates
- telemetry

It does not change:

- the phase 1 command runtime
- the command family set
- MCP authority or ACP authority
- approval behavior
- typed-tool executability

The central rule is:

`run(command)` becomes the preferred agent-facing workbench, while typed tools remain available as fallback.

### 2. Chat Surface Design

Chat should shape model behavior through three coordinated changes.

#### Prompt bias

Gated chat sessions should explicitly teach:

- prefer `run(command)` for exploration, file work, filtering, and multi-step tasks
- use typed tools when `run` lacks a suitable command or when exact structured mutation is clearly better

Prompt examples should lead with `run`, not typed tools. Representative examples:

- `run("ls")`
- `run("cat notes.txt | grep TODO")`
- `run("knowledge search \"topic\" | json")`
- `run("mcp tools")`

Chat should use a chat-specific run-first prompt fragment rather than sharing one identical string with ACP. The intent stays the same, but wording can be tuned for chat request structure and chat-specific examples.

#### Tool context shaping

In the model-facing tool menu:

- `run` should appear first
- `run` should receive the most explanatory description
- typed tools should remain listed, but with terser descriptions framed as direct fallback or specialized tools

This shaping must be driven by the effective tool list for the current session. If `run` is not available because of allow-catalog filtering, runtime policy, or surface configuration, chat should not inject run-first guidance that assumes it is callable.

Chat should resolve one session-scoped effective tool set and use it as the source of truth for both:

- the ordered `llm_tools` definitions shown to the model
- the execution-time eligibility surface used by chat-side tool auto-execution and allow-catalog enforcement

The model should not be shown tools that chat will later reject purely because of local surface filtering. Surface-level rollout shaping and execution-time eligibility must stay aligned.

The intended teaching order is:

1. try `run`
2. fall back to typed tools when needed

For chat specifically, this shaping must occur at the tool-definition assembly layer before `llm_tools` are handed to the provider. Execution-time code that only sees returned `tool_calls` is not sufficient.

Phase 2a should not force `tool_choice` to `run`. The experiment depends on preference shaping, not hard selection, so provider-facing tool choice should remain unset or `auto` unless some unrelated surface already requires a stricter mode.

#### Chat rollout gate

Chat should add a dedicated phase 2a run-first gate that controls:

- whether the run-first prompt segment is injected
- whether tool ordering is reshaped
- whether session telemetry is tagged as phase 2a

This gate should be independent from core execution controls such as `CHAT_AUTO_EXECUTE_TOOLS`. It is a behavior rollout switch, not a permission switch.

If a gated chat session resolves to a tool set where `run` is not actually present, the gate should fall back to control-style tool guidance and record that the run-first policy was ineligible for that session.

### 3. ACP Surface Design

ACP should mirror the same execution habit, but through session/runtime configuration rather than only chat prompt text.

#### ACP prompt and session shaping

Gated ACP sessions should prepend run-first execution guidance to the agent context:

- prefer `run(command)` for exploration and multi-step tool work
- use typed tools when `run` is insufficient or when a direct structured mutation is the clearer governed path

ACP should use an ACP-specific run-first prompt fragment. It should preserve the same run-first and fallback rules as chat while using ACP-native wording and examples.

#### ACP tool ordering

When ACP formats tools for LLM use:

- `run` should appear first
- typed tools should remain present
- typed descriptions should be shorter and positioned as specialized fallback tools

This shaping belongs at the LLM-facing tool-format layer, not at the transport or governance layers.

As with chat, ACP should only apply run-first ordering and wording when `run` is actually present in the effective tool list for that session.

Because the current MCP-to-OpenAI formatter is context-free, the preferred implementation shape is a session-aware ACP tool presenter that:

- receives the effective tool list plus rollout context
- applies run-first ordering and description shaping when eligible
- delegates final schema conversion to the lower-level formatting helper

This keeps rollout policy out of a utility that otherwise has no session context.

#### ACP rollout gate

ACP should add a parallel phase 2a run-first gate that controls:

- whether run-first prompt context is added
- whether tool ordering/descriptions are reshaped
- whether telemetry is tagged as gated or control behavior

This gate must not alter runtime policy snapshots, permission tiers, or approval handling.

If an ACP session is in the rollout cohort but `run` is absent from the effective tool list, the system should record the session as ineligible for run-first shaping rather than pretending it was part of the true experiment.

### 4. Fallback, Errors, And Behavioral Expectations

Phase 2a depends on fallback being normal and measurable.

Expected agent behavior:

1. prefer `run(command)` first for general workbench tasks
2. fall back to typed tools when:
   - the required capability is not represented in the command registry
   - `run` emits an actionable error indicating a better direct tool path
   - the task is an obvious exact structured mutation

Expected system behavior:

- a failed or denied `run` attempt should not hide typed-tool fallback from the model
- policy denials must remain attributed to the real governed step, not softened into prompt-level language
- telemetry must distinguish between:
  - run parse/help failures
  - command adapter misses
  - governance denials
  - fallback after `run`
  - direct typed-first choices

Phase 2a is successful only if `run` becomes the primary path without making agents brittle when they need to escape to typed tools.

### 5. Rollout Gate And Metrics

Rollout must be explicit and widening must be evidence-driven.

#### Gate behavior

Both `chat` and ACP should support a phase 2a run-first rollout mode that affects:

- prompt additions
- tool ordering
- tool descriptions
- telemetry tagging

The default remains off outside the rollout cohort.

Telemetry for gated and control traffic should include an explicit rollout presentation label such as `prompt_variant` or `presentation_variant` so wording or ordering changes can be attributed cleanly during the rollout window.

#### Cohort selection

The initial rollout should be deliberately narrow.

For chat, the first cohort should be limited to provider and runtime combinations with stable tool-calling behavior and predictable tool-call serialization. Provider variance is not part of the first experiment and should not be mixed into the primary rollout signal.

Where practical, chat reporting should also match or stratify by `streaming` versus non-streaming mode, since those paths differ operationally even when provider and runtime are the same.

ACP rollout cohorts should likewise prefer the most stable LLM-driven runner paths first if multiple runner or provider paths exist.

Control cohorts must be matched to gated cohorts on the same provider and runtime combinations during the initial experiment. If exact matching is not practical, results must be stratified by provider/runtime pair instead of comparing gated stable-provider traffic against broader control traffic.
For ACP, gated versus control comparisons should follow the same rule across the chosen runner and provider paths during the initial experiment.

#### Minimum metrics

Before widening the gate, collect at least:

- first-tool-is-`run` rate
- fallback rate from `run` to typed tools
- completion rate for gated sessions versus control sessions
- tool-turn count per completion-proxy unit
- approval and denial rates split by `run` versus direct typed calls
- top `run` error classes and help misses
- count of gated sessions where `run` was unavailable in the effective tool set

#### Metric contract

Metrics must be defined per surface, not as one blended denominator across `chat` and ACP.

Definitions:

- eligible chat unit: one gated chat response cycle where `run` is present in the effective tool list
- eligible ACP unit: one gated ACP prompt/run loop where `run` is present in the effective tool list
- chat completion proxy: an eligible chat unit that reaches a successful assistant response without terminal provider/runtime failure and without a stream-incomplete or equivalent terminal chat error
- ACP completion proxy: an eligible ACP unit that emits a `COMPLETION` event with `stop_reason=end_turn`
- ACP non-success terminal outcomes: `ERROR`, cancellation, or `COMPLETION` with `stop_reason=max_iterations`
- first-tool-is-`run` rate: among eligible units that produced at least one tool call, the percent whose first tool call was `run`
- fallback-after-`run` rate: among eligible units whose first tool call was `run` and that later produced another tool call, the percent whose later tool calls include a typed non-`run` tool
- gated-but-ineligible units: gated sessions where `run` was absent; record them separately and exclude them from the primary run-first and fallback denominators

The minimum rollout metric named `completion rate` should mean completion proxy rate under these surface-specific definitions, not subjective task success.

Completion-proxy, denial, and tool-turn comparisons should also be reported separately for chat and ACP during the initial rollout window.
For chat, gated versus control comparisons must be computed within matched provider/runtime cohorts, or reported separately by those cohorts.
For ACP, gated versus control comparisons must be computed within matched runner/provider cohorts, or reported separately by those cohorts.

If the team wants a stronger notion of true task completion later, that should be added as a separate judged or sampled evaluation layer rather than overloaded into the phase 2a operational telemetry.

#### Stop/go rules

Widen the rollout if gated cohorts show:

- neutral or better completion
- lower or neutral tool-turn count
- acceptable fallback rates
- no evidence that help or routing gaps dominate failures

Hold or narrow the rollout if:

- completion degrades materially
- first-tool selection stays fragmented
- fallback rates stay very high
- `run` help, parse, or adapter misses dominate

Typed tools should not be hidden in a later phase unless telemetry shows `run` reliably carries the primary workload.

### 6. Testing And Validation

Phase 2a needs both code-level validation and behavior-level validation.

#### Code-level coverage

Add tests around:

- chat tool-definition shaping and rollout gating before provider calls
- chat telemetry tagging for run-first versus control cohorts
- ACP tool ordering and description shaping
- ACP prompt/session shaping
- ACP telemetry tags for first-tool and fallback behavior
- provider or runtime cohort eligibility for the initial chat rollout

#### Integration coverage

Add focused integration tests showing:

- gated chat sessions present `run` first while preserving typed fallback
- gated ACP sessions present `run` first while preserving permission workflows
- control cohorts retain current behavior

#### Rollout validation

Treat telemetry review as a release gate, not a post-hoc dashboard exercise. Phase 2a should not widen from the initial cohort until the minimum metrics above have been reviewed.

## Risks And Mitigations

### Risk: prompt drift between chat and ACP

Mitigation:

- keep separate chat and ACP prompt fragments tuned per surface
- define one shared run-first behavior contract and test both fragments against it

### Risk: provider variance swamps the rollout signal

Mitigation:

- restrict the initial chat cohort to stable tool-calling provider/runtime combinations
- report rollout metrics by surface and provider/runtime cohort instead of blending them

### Risk: run-first wording changes too little behavior

Mitigation:

- shape both prompt and tool ordering
- track first-tool selection explicitly

### Risk: demotion text makes typed tools too invisible

Mitigation:

- keep typed tools listed and executable
- frame them as specialized fallback rather than hidden internals

### Risk: rollout telemetry is too weak to guide decisions

Mitigation:

- tag gated sessions explicitly
- record first-tool choice, fallback, and error class at the same surface where the behavior is shaped

## Out Of Scope Follow-On Work

If phase 2a succeeds, later phases can consider:

- extending run-first shaping to personas and workflows
- expanding command families
- tighter help and error tuning based on observed misses
- stronger surface virtualization in a later, evidence-backed phase

Phase 2a itself should stay narrow: `chat + ACP`, run-first behavior shaping, gated rollout, and telemetry-backed decision making.
