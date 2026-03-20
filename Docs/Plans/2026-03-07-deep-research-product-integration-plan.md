# Deep Research Product Integration Plan

**Date:** 2026-03-07

## Goal

Expose deep research as a shared product capability across chat and workflows while preserving the existing `research_session`, artifact, and bundle model.

## Why This Comes After The First Two Workstreams

The backend engine and dedicated console already exist, but:

- checkpoint editing is still needed to make research collaborative
- trust hardening is still needed to make outputs safe to amplify into more surfaces

Once those are in place, deep research should stop being a standalone page and become a reusable product primitive.

## Architecture Direction

Do not build separate “research engines” for chat and workflows.

Instead:

- keep the current research APIs and service layer as the only execution backend
- add shared launch and attachment contracts for other surfaces
- let chat and workflows reference the same run IDs, checkpoint state, artifacts, and final bundles

## Scope

This workstream covers:

- launching deep research from chat
- launching deep research from workflows
- linking back to the same run console and bundle views
- reusing research artifacts and final bundles across surfaces

This workstream does not cover:

- a completely separate chat-native research engine
- replacing the dedicated `/research` page
- multi-run orchestration UIs beyond existing workflow concepts

## Stage 1: Shared Launch Contract

### Outcome

Other product surfaces can start a research session without inventing new backend contracts.

### Deliverables

- a stable launch payload shape shared by chat, workflows, and the dedicated console
- clear rules for source policy, autonomy mode, limits, and provider overrides
- shared “open existing run” and “open final bundle” navigation affordances

### Success Criteria

- all launch paths create the same kind of session
- the dedicated run console remains the canonical place to inspect a run in detail

## Stage 2: Chat Integration

### Outcome

Chat can invoke deep research as a mode rather than only answering inline.

### Deliverables

- a deep-research launch action from chat
- chat-visible progress and handoff messages tied to a research run ID
- final bundle or concise-answer insertion back into the chat thread when the run completes

### Success Criteria

- a user can start a deep research session from chat and follow it without losing session context
- the resulting answer or report links back to the underlying bundle and artifacts

## Stage 3: Workflow Integration

### Outcome

Workflows can call deep research as a reusable long-running step.

### Deliverables

- a workflow adapter or step type that launches a research session
- step outputs that reference run ID, bundle, and selected artifacts
- workflow-safe waiting, retry, and resume semantics

### Success Criteria

- a workflow can orchestrate deep research without duplicating research logic
- downstream workflow steps can consume the same bundle object produced by the dedicated console flow

## Stage 4: Shared Consumption Patterns

### Outcome

Different surfaces consume research outputs consistently.

### Deliverables

- common rendering rules for concise answer, report sections, claims, citations, and unresolved questions
- shared links from chat and workflows into the run console
- consistent permissions and ownership enforcement across surfaces

### Success Criteria

- a run started anywhere can be inspected anywhere the user has access
- bundle rendering semantics do not drift between chat, workflows, and the console

## Stage 5: Operational Hardening

### Outcome

Deep research behaves predictably as a cross-product capability.

### Deliverables

- rate-limit and quota review for multi-surface launches
- clearer analytics or audit events for launch origin and consumption path
- regression coverage for cross-surface launch and consumption flows

### Success Criteria

- chat and workflow integrations do not break research-session durability or ownership guarantees
- operational controls remain understandable as adoption broadens

## Risks

### Surface Divergence

If chat and workflows each add bespoke research rendering or launch logic, the product will fragment.

Mitigation:

- keep launch and consumption contracts shared and thin

### Premature Inline Expectations

If chat tries to make long-running research feel like an ordinary synchronous answer, users will get confused.

Mitigation:

- make research-mode launches explicit and tie them to durable run status

### Workflow Coupling

If workflows depend on unstable bundle fields, iteration on the research backend will become harder.

Mitigation:

- stabilize bundle contracts before broad workflow adoption

## Exit Condition

This workstream is complete when chat and workflows can both launch and consume deep research sessions through the same backend contracts, while the dedicated run console remains the canonical detailed inspection surface.
