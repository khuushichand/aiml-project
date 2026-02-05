# ACP Agent Orchestration and Third-Party Agent Support PRD

Author: tldw_server team
Status: Draft (v0.1)
Target Version: v0.2.x

## 1) Summary
Introduce first-party (pi-agent) and third-party ACP agents into tldw_server with a unified orchestration layer, inspired by RalphBoard's task pipeline (todo -> inprogress -> review -> complete/triage) and explicit completion signaling. The system will support a global agent registry, agent discovery via ACP, and a workflow runner that enforces completion tokens, reviewer gates, and triage escalation after repeated failures.

The first-party pi-agent runs as a separate ACP Node process and uses tldw_server LLMs via OpenAI-compatible baseURL. Third-party agents are configured globally and exposed as selectable ACP agents.

## 2) Problem / Motivation
- We need a consistent way to run a first-party agent and multiple third-party agents without changing the tldw_server API surface per agent.
- Current agent execution does not enforce explicit completion signals or QA gating, which increases false positives and inconsistent task outcomes.
- Users need a simple way to define tasks, dependencies, and review gates, and then dispatch them to configured agents.

RalphBoard demonstrates a proven approach with:
- Explicit completion markers ("Ralph Wiggum" loop)
- Reviewer gate with triage escalation
- Queue-based agent dispatch and dependency gating

## 3) Goals
- Provide a global agent registry that lists available ACP agents with metadata (name, description, command, args, env, requires_api_key).
- Expose ACP agent discovery to tldw_server clients (agent list and default).
- Implement an orchestration flow that supports:
  - Task dependencies
  - Explicit completion signal
  - Reviewer gate and triage escalation after max failures
- Use pi-agent as the first-party implementation via ACP, running as a separate Node process.
- Make pi-agent use tldw_server LLMs via OpenAI-compatible baseURL.
- Provide server APIs to create tasks, launch runs, and query status.

## 4) Non-Goals
- Building a full Kanban UI in v0.2.x (basic UI elements are acceptable, full board can follow later).
- Replacing existing MCP or Jobs system.
- Rewriting the ACP protocol.
- Building a full marketplace or installation flow for third-party agents (registry is config-based only).

## 5) Personas
- Admin/Power User: configures agent registry and manages execution policies.
- Analyst/Researcher: creates tasks and runs them through agents with QA.
- Developer: integrates external ACP agents into the registry.

## 6) User Stories
1. As an admin, I can configure third-party agents in a global registry and see them in the UI/API.
2. As a user, I can create a project with tasks and dependencies and run it with an agent.
3. As a user, I can require a reviewer agent to approve work before completion.
4. As a user, I can view task history, including failures and retry attempts.
5. As a developer, I can run the pi-agent against tldw_server using OpenAI-compatible LLM endpoints.

## 7) Requirements

### 7.1 Functional Requirements
- Agent Registry
  - Global config file with agent entries:
    - `type`, `name`, `description`, `command`, `args`, `env`, `requires_api_key`
  - ACP runner exposes `agent/list` returning available agents and default.

- ACP Integration
  - tldw_server uses ACP runner to:
    - `agent/list`
    - `session/new`
    - `session/prompt`
    - `session/cancel`
  - Agents can invoke tools via ACP tool calls (fs, search, git, terminal).

- Task Orchestration
  - Create project and tasks with dependencies.
  - Enforce a workflow pipeline:
    - todo -> inprogress -> review -> complete
    - review failures increment review_count; after N failures, move to triage.
  - Support explicit completion token (or structured completion event) before moving to review/complete.

- Reviewer Gate
  - Reviewer agent validates success criteria and outputs explicit "COMPLETE" or "REJECTED".
  - Rejections trigger retry or triage after `max_review_attempts`.

- First-party pi-agent
  - Runs as separate ACP process.
  - Uses tldw_server LLMs via OpenAI-compatible baseURL.

### 7.2 Non-Functional Requirements
- Reliability: each run is idempotent and recoverable on restart.
- Observability: logs and run history stored for audit.
- Security: agent registry and tool permissions are admin-controlled.
- Latency: first token within 2 seconds for local LLMs; degrade gracefully.

## 8) UX / UI (Initial)
- Agent list view with metadata (name, description, requires_api_key).
- Task list with status (todo/inprogress/review/complete/triage).
- Per-task run history with last result and failure count.

## 9) Architecture & Data Model

### 9.1 Orchestration Model
- Use Jobs for user-facing orchestration visibility.
- Add an Agent Orchestration layer that:
  - Creates tasks and dependencies.
  - Dispatches ACP sessions to selected agents.
  - Tracks status transitions and review outcomes.

### 9.2 Proposed Tables (minimal)
- `agent_projects` (id, name, description, created_at)
- `agent_tasks` (id, project_id, title, description, success_criteria, dependency_id, status, review_count)
- `agent_runs` (id, task_id, agent_type, status, started_at, finished_at, error, output_ref)

Alternatively, map `agent_tasks` and `agent_runs` to Jobs with metadata in a JSON payload.

## 10) API / Integration

### 10.1 Public Endpoints (new)
- `POST /api/v1/agent_projects` (create project)
- `POST /api/v1/agent_tasks` (create task)
- `POST /api/v1/agent_tasks/{id}/run` (dispatch via ACP)
- `GET /api/v1/agent_tasks/{id}` (task status + history)
- `GET /api/v1/agent_agents` (list agents from ACP runner)

### 10.2 ACP Runner Methods
- `agent/list`
- `session/new`
- `session/prompt`
- `session/cancel`

## 11) Permissions & Security
- Registry changes restricted to admin.
- Per-agent tool permissions configurable (auto-approve list).
- ACP processes inherit environment variables; secrets never logged.

## 12) Metrics / Monitoring
- Task completion rate
- Avg. iterations per task
- Review rejection rate
- Triage rate
- Average time to completion

## 13) Rollout Plan

### Phase 1 (MVP)
- Agent registry + `agent/list` integration
- Create tasks, dispatch runs, status tracking
- Reviewer gate and triage logic

### Phase 2
- UI enhancements (task list + basic status)
- Task expansion via LLM
- richer run history

### Phase 3
- Kanban-style workflow UI
- Advanced scheduling (batch runs, auto-dispatch)

## 14) Risks & Mitigations
- Risk: False positives if completion token is not enforced.
  - Mitigation: Require explicit completion signal and reviewer gate.
- Risk: Third-party agents behave inconsistently.
  - Mitigation: Validate capabilities and provide per-agent tool policies.
- Risk: Task dependency deadlocks.
  - Mitigation: Detect cycles and surface errors at task creation.

## 15) Open Questions
- Should tasks be stored as Jobs (single source) or as a dedicated agent schema?
- What is the minimum UI surface to deliver in v0.2.x?
- Should reviewer be a distinct agent type or allow "self-review" as an option?

## 16) Design Doc

**Purpose**  
Define the concrete architecture, data model, and flows for ACP-based agent orchestration with a first-party pi-agent and globally configured third-party agents. This design follows the RalphBoard-inspired loop (explicit completion + reviewer gate + triage escalation).

**Decisions (Confirmed)**  
1. The pi-agent runs as a separate Node ACP process.  
2. Third-party agents are globally configured via a registry.  
3. The pi-agent uses tldw_server LLMs via the OpenAI-compatible baseURL.

**Architecture Overview**  
Components:
1. `tldw_server2` API and orchestration service (FastAPI).  
2. ACP runner client (`runner_client.py`) for agent discovery and session control.  
3. ACP runner process (Go) that spawns agent processes using the global registry.  
4. pi-agent ACP CLI (Node) that handles session lifecycle and tool calls.  
5. Storage for tasks, runs, and history (SQLite or Jobs metadata).

Data Flow (Happy Path):
1. User creates project and tasks.  
2. Orchestrator selects agent type and calls ACP `session/new`.  
3. Orchestrator sends `session/prompt` with task details.  
4. Agent runs loop and emits explicit completion signal.  
5. Orchestrator dispatches reviewer agent if configured.  
6. Task transitions to `complete` or `triage` based on reviewer result.

**System Responsibilities**  
`tldw_server2`:
1. Persist projects, tasks, and run history.  
2. Enforce task state transitions and dependency gating.  
3. Invoke ACP sessions and handle tool permission prompts.  
4. Provide API endpoints and UI data.

ACP runner:
1. Expose `agent/list` to advertise configured agents.  
2. Spawn agent processes for `session/new`.  
3. Forward tool calls and permission requests.  
4. Maintain session lifecycle and cancellation.

pi-agent:
1. Implement ACP JSON-RPC over stdio.  
2. Use tldw_server OpenAI-compatible baseURL for LLM calls.  
3. Emit structured `session/update` events for assistant output and tool calls.

**Data Model**  
Minimum schema (dedicated tables), or map to Jobs with metadata.  
Suggested tables:
```\n+agent_projects\n+  id (pk)\n+  name\n+  description\n+  created_at\n+\n+agent_tasks\n+  id (pk)\n+  project_id (fk)\n+  title\n+  description\n+  success_criteria\n+  dependency_id (nullable fk)\n+  status (todo|inprogress|review|complete|triage)\n+  review_count\n+  created_at\n+  updated_at\n+\n+agent_runs\n+  id (pk)\n+  task_id (fk)\n+  agent_type\n+  status (running|succeeded|failed|cancelled)\n+  started_at\n+  finished_at\n+  error\n+  output_ref (log/artifact pointer)\n```\n+
**State Machine**  
Statuses:
1. `todo` (ready)  
2. `inprogress` (agent active)  
3. `review` (awaiting reviewer)  
4. `complete` (approved)  
5. `triage` (failed after max review attempts)

Transitions:
1. `todo` -> `inprogress` on run dispatch.  
2. `inprogress` -> `review` on explicit completion signal.  
3. `review` -> `complete` on reviewer approval.  
4. `review` -> `todo` on reviewer rejection if attempts < max.  
5. `review` -> `triage` on reviewer rejection if attempts >= max.  
6. Any -> `triage` on fatal agent error if policy requires.

**Dependency Gating**  
Rule: A task with `dependency_id` cannot move from `todo` to `inprogress` until the dependency is `complete`.  
Enforcement: Validate at dispatch time and return a structured error.

**ACP Integration Details**  
Session creation:
1. `agent/list` to resolve agent availability and default.  
2. `session/new` with `agent_type`, `cwd`, `search_tools`, `git_tools`.  
3. `session/prompt` with task payload.

Tool call handling:
1. Agent emits tool call in `session/update`.  
2. ACP runner asks for permission (`session/request_permission`).  
3. Orchestrator responds (`session/permission_response`).  
4. ACP runner executes tool and returns `tool_result`.

Completion signal:
1. The agent must emit a structured completion marker.  
2. The orchestrator validates the marker before transitioning to `review` or `complete`.

**Agent Registry (Global)**  
Configuration keys for each agent:
1. `type` (unique id)  
2. `name`  
3. `description`  
4. `command`  
5. `args`  
6. `env`  
7. `requires_api_key`  
8. `default` (optional)

Example entry:
```\n+agents:\n+  default_agent: \"pi-agent\"\n+  registry:\n+    - type: \"pi-agent\"\n+      name: \"Pi Agent\"\n+      description: \"First-party ACP agent\"\n+      command: \"node\"\n+      args:\n+        - \"/path/to/pi-agent-acp/dist/cli.js\"\n+      env:\n+        TLDW_OPENAI_BASE_URL: \"http://127.0.0.1:8000/api/v1\"\n+      requires_api_key: false\n```\n+
**Security and Permissions**  
1. Registry edits restricted to admin.  
2. Tool permissions enforced by ACP runner, with server-defined policy.  
3. Sensitive env values must be stored in server config and never logged.

**Error Handling**  
1. Agent crash -> mark run failed and task to triage if configured.  
2. Timeout -> cancel session and retry or triage based on policy.  
3. Invalid completion signal -> continue loop or fail run with clear error.

**Testing Strategy**  
1. Unit tests for state machine transitions.  
2. Integration tests for ACP session lifecycle (`session/new`, `session/prompt`, `session/cancel`).  
3. Integration tests for reviewer gate and triage escalation.  
4. Contract tests for `agent/list` response shape.

**Implementation Phases**  
1. Phase 1: Agent registry + agent discovery + task model + basic dispatch.  
2. Phase 2: Reviewer gate + triage + run history + minimal UI.  
3. Phase 3: Task expansion via LLM + Kanban UI + scheduling.
