# Persona Voice Assistant Builder Design

Date: 2026-03-12
Status: Approved for planning
Owner: Codex brainstorming pass

## Summary

Design a shared WebUI/extension surface that helps users build their own voice assistant quickly and safely.

The assistant container in V1 is **not** a new profile type. It is an existing **Persona** from the Persona module. The new work should extend the current Persona Garden and voice-command systems instead of creating a parallel assistant model.

User-facing copy can say **Assistant** where it improves clarity, but the underlying data model should remain persona-first.

## Goals

- Make it fast to create useful voice-triggered commands from templates.
- Support both fixed shortcut phrases and parameterized phrases.
- Make testing and debugging first-class so users can see what was heard, matched, extracted, and executed.
- Make external API and webhook usage possible without making the system feel unsafe.
- Reuse the shared WebUI/extension codebase and existing Persona/Voice Assistant infrastructure.

## Non-Goals

- Do not merge deeply with the full Persona live planning/chat experience in V1.
- Do not introduce free-form NLU-heavy command extraction as the primary path.
- Do not store raw secrets directly on command records.
- Do not create a second assistant-profile abstraction separate from Persona.

## Existing Context

Relevant current surfaces and contracts:

- Persona route and tabs already exist in the shared UI.
- Persona backend already supports profile CRUD, sessions, policies, state docs, and voice/example management.
- Voice assistant backend already supports voice-command CRUD, usage stats, sessions, and execution types:
  - `mcp_tool`
  - `workflow`
  - `custom`
  - `llm_chat`

This means V1 should add a command-building layer **inside the Persona experience**, not beside it.

## Key Design Decisions

### 1. Persona Is The Top-Level Container

Each assistant is a Persona.

Implications:

- Commands belong to a persona.
- Safety defaults belong to a persona.
- Voice/examples remain persona attributes.
- Future voice/persona convergence becomes additive instead of migratory.

### 2. Deterministic Commands Run Before Persona Planning

Execution precedence for voice/text command handling:

1. Attempt deterministic persona-bound command matching.
2. If a command matches, run the direct command flow.
3. If no command matches, fall back to normal persona chat/planning behavior.

This keeps common actions fast and predictable while preserving the broader Persona agent behavior.

### 3. Command Creation Is The V1 Primary Workflow

The main value is not deep persona authoring first. It is quickly creating useful commands.

The page should therefore open on a command workbench for the selected persona, with templates and testing exposed immediately.

### 4. External Integrations Use Reusable Connections

Commands must reference reusable connection records rather than embedding credentials inline.

Benefits:

- safer secret handling
- cleaner command editor
- easier reuse across multiple commands
- clearer auditing and validation

## Recommended IA

Extend the existing Persona Garden route with additional tabs and adjusted priority.

Recommended tab order:

1. `Commands`
2. `Test Lab`
3. `Live`
4. `Profile`
5. `Connections`
6. `Voice`
7. `Policies`
8. `Scopes`

Notes:

- `Commands` becomes the default tab when a persona is selected.
- `Live` remains for the real-time persona experience.
- `Policies` and `Scopes` remain available but should not dominate first-run setup.
- User-facing tab labels may use `Assistant` language in supporting copy while preserving `Persona` in IDs and routing.

## Commands Workbench

The Commands tab should optimize for three actions:

1. create a command from a template
2. edit a command without reading raw JSON
3. see whether a command is safe, working, and recently tested

### Command List

Each row/card should show:

- enabled state
- command name
- primary phrase
- target type
- safety badge
- last test result
- last used timestamp

Recommended filters:

- enabled
- needs confirmation
- external API
- broken
- never tested
- most used

### Command Creation Modes

Support two authoring modes in V1:

- `Shortcut Command`
  - fixed phrases mapped to one fixed action
- `Parameterized Command`
  - slot-based phrases such as `search notes for {topic}`

V1 should favor explicit placeholders over loose natural-language extraction.

### Command Editor Sections

1. `What people can say`
   - name
   - primary phrase
   - alternate phrases
   - slot placeholders
   - phrase preview
2. `What happens`
   - target type: tool, workflow, prompt action, webhook/API
   - target picker
3. `Input mapping`
   - slot to parameter mapping
   - constants and defaults
4. `Safety`
   - inherited persona defaults
   - per-command overrides when allowed
5. `Response`
   - spoken success line
   - spoken failure line
   - show-result-in-UI toggle

## Templates

The new-command flow should start from templates, not a blank screen.

Starter groups:

- Productivity
  - open notes
  - create note
  - search notes for `{topic}`
  - summarize current page
- Research
  - web search for `{query}`
  - arXiv lookup for `{topic}`
  - save current source
- Workflow
  - run workflow `{name}` or selected workflow templates
- External
  - send webhook
  - call API endpoint
- Custom
  - blank shortcut
  - blank parameterized command

## Test Lab

Testing and debugging must be a first-class tab, not a side panel.

Each dry run or live run should expose a visible pipeline:

1. `Heard`
   - transcript or typed input
2. `Matched`
   - matched command or no-match result
   - confidence
   - best phrase
   - ambiguity details if relevant
3. `Extracted`
   - slot values
4. `Planned Action`
   - target plus redacted argument preview
5. `Safety Gate`
   - whether confirmation is required
   - why it is required
6. `Execution Result`
   - dry run: what would happen
   - live run: status, latency, summarized output

Critical requirement:

- The UI must clearly distinguish:
  - phrase mismatch
  - disabled command
  - ambiguous match
  - bad parameter mapping
  - connection/auth failure
  - fallback to persona planner

Without this, users will not trust the system.

## Connections

Connections are reusable external integration definitions scoped to a persona.

Suggested V1 fields:

- `id`
- `persona_id`
- `name`
- `base_url`
- `auth_type`
- `secret_ref`
- `headers_template`
- `timeout_ms`
- `allowed_hosts` or validated host metadata

Connection UX:

- create/edit connection
- test connection
- preview redacted request config
- show last validation result

Commands should reference `connection_id` and a request template, not raw credentials.

## Safety Model

Safe-by-default is required.

### Persona-Level Defaults

Persona policies define the baseline:

- read-only actions may auto-run
- mutating actions require confirmation
- external API/webhook actions require confirmation by default

### Command-Level Rules

Commands may:

- inherit persona defaults
- tighten safety further
- only bypass certain confirmations when explicitly allowed by persona policy and advanced mode

### Safety Classification

Every command should surface one classification badge:

- `Read only`
- `Changes data`
- `Calls external API`

### Secret Handling

- never show full secrets after save
- store references, not raw credentials in command definitions
- redact sensitive request previews

## Data Model Changes

### Persona

Reuse existing Persona profile as the top-level assistant object.

### Voice Command

Extend current command model to support persona ownership and richer command behavior.

Suggested additions:

- `persona_id`
- `match_mode`
- `parameter_schema`
- `response_config`
- `safety_classification`
- `connection_id`
- `last_test_status` optional cached UI/helper field

### Connection

Add a new reusable connection model scoped to persona.

### Test Run

Persist later if needed. V1 can start with recent local history or lightweight server-side logging.

## Backend Contract Changes

Required V1 change:

- voice commands must become persona-scoped, not only user-scoped

Recommended additions:

- list/create/update/delete commands by persona
- list/create/update/delete connections by persona
- dry-run command test endpoint
- command-match debug response contract

The current voice assistant CRUD can remain the base implementation, but it should be extended rather than bypassed.

## UX Risks And Improvements

### Risk: Duplicate assistant model

Problem:

- a new assistant-profile object would duplicate Persona and create migration debt

Resolution:

- use Persona as the only top-level assistant container

### Risk: Two competing execution paths

Problem:

- users will not know whether a request hits direct command matching or the Persona planner

Resolution:

- deterministic command first, planner fallback second
- show fallback explicitly in Test Lab

### Risk: Parameterized phrases feel flaky

Problem:

- free-form extraction will break under STT noise

Resolution:

- V1 uses slot-based phrase patterns and visible extraction previews

### Risk: Two permission systems

Problem:

- command safety and persona policy could drift apart

Resolution:

- persona policy is baseline
- command rules only inherit or tighten by default

### Risk: External integrations become unsafe

Problem:

- per-command URLs and secrets are hard to validate and audit

Resolution:

- reusable connections
- redacted previews
- default confirmation for external calls

### Improvement: Assistant-first copy

Use approachable product language in the UI:

- "Build your assistant"
- "Assistant commands"
- "Test your assistant"

Keep persona-first naming in routes, APIs, and storage.

## Testing Strategy

### Unit

- phrase matching
- slot extraction
- safety classification
- connection validation helpers
- planner fallback selection

### UI

- template creation flow
- command editor behavior
- test-lab pipeline rendering
- safety badges and confirmation messaging
- persona-tab navigation and deep-link behavior

### Integration

- persona-scoped command CRUD
- connection CRUD
- dry-run testing
- execution with tool/workflow/webhook bindings
- fallback from command layer to persona planner

### Accessibility

The route will be form-heavy and test-heavy, so include:

- keyboard navigation checks
- live-region announcements for test results
- labels for icon-only actions
- focus management for tab and panel transitions

## Rollout Notes

Recommended V1 release order:

1. persona-scoped command model
2. Commands tab with templates
3. Test Lab with dry-run pipeline
4. Connections tab
5. live execution and fallback integration

This sequence reduces risk and surfaces value early.

## Final Recommendation

Build this as a **Persona-first Assistant Builder**:

- persona is the real assistant container
- commands are persona-bound
- command creation is the main workflow
- deterministic command matching runs before persona planning
- external actions go through reusable connections
- safe-by-default behavior is enforced through persona policy plus command safety

This produces a V1 that feels like "build your own Siri" without fighting the existing Persona architecture.
