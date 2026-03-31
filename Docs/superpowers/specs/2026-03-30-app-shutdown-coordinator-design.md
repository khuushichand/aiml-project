# App Shutdown Coordinator Design

## Summary

This design improves application shutdown performance by replacing the current large, serial FastAPI lifespan teardown with an explicit shutdown coordinator that supports:

- immediate transition to a `draining` state
- immediate readiness failure plus explicit admission gating for new work
- parallel shutdown by ordered phases instead of one long serial await chain
- different shutdown policies for local development and production-style runs
- structured shutdown observability so tuning is based on data rather than log archaeology

The target budgets confirmed with the user are:

- development: under `5s`
- production-style/self-hosted runtime: under `15s`, with a preference to let in-flight work finish even if shutdown occasionally exceeds that target

This spec is intentionally scoped to shutdown orchestration, admission control, and observability. It does not attempt a full startup architecture rewrite in the first slice.

## Goals

- Reduce shutdown wall-clock time for local restarts and container stop events.
- Fail readiness immediately when shutdown begins.
- Reject new heavy or mutating work as soon as the app enters shutdown.
- Preserve as much in-flight work as practical in production-style environments.
- Make shutdown ordering explicit and testable.
- Provide per-component shutdown timing and outcome data.
- Preserve existing lifecycle reentrancy expectations in tests.

## Non-Goals

- Redesigning every startup path in the same tranche.
- Rewriting every service to self-register on day one.
- Guaranteeing resumable shutdown for job types that do not currently support checkpointing or safe requeue.
- Changing request routing or deployment topology.
- Optimizing unrelated startup latency beyond the minimum needed to handle deferred-startup shutdown interactions correctly.

## Current State

The app currently performs shutdown inside the main FastAPI lifespan handler in `tldw_Server_API/app/main.py`.

Important current behaviors:

- shutdown already flips readiness false via `mark_lifecycle_shutdown(...)`
- background job acquisition is already gated via `JobManager.set_acquire_gate(True)`
- many workers are stopped sequentially with repeated `await asyncio.wait_for(task, timeout=5.0)`
- shared resources are cleaned up later through a long hand-written list of stop and shutdown calls
- deferred startup can still be active when shutdown begins

This has two practical consequences:

1. Shutdown time scales with the number of components because many waits are serialized.
2. Ordering and ownership are implicit in `main.py`, so regressions are easy to introduce and hard to reason about.

The current teardown also shows duplicate-style responsibilities that a coordinator should eliminate, for example:

- usage aggregator shutdown appears in more than one section
- AuthNZ scheduler shutdown is handled more than once
- shutdown summary information is not emitted as a first-class structured artifact

## Requirements Confirmed With User

- Support a two-tier operating model:
  - aggressive fast exit for local development
  - safer bounded drain for production-like Docker and mixed self-hosted installs
- Primary budget targets:
  - development under `5s`
  - production under `15s`
- In development, in-flight work may be cancelled aggressively.
- In production-like environments, the system should prefer waiting longer for active jobs to finish, even if shutdown sometimes exceeds the target.
- The user is comfortable with a larger cleanup effort rather than only incremental tuning.
- The app should immediately stop advertising readiness and reject new work when shutdown begins.
- The design should work for Docker/single-host installs and mixed self-hosted environments without assuming Kubernetes-specific primitives.

## Problems To Solve

### 1. Serial teardown dominates shutdown time

The current lifespan teardown contains many per-component waits with `5s` budgets. Even when most services stop quickly, a few slow components can produce a long serial tail.

### 2. Readiness flip alone is not enough

Marking the app not ready is necessary, but it does not guarantee that no new requests or new internal work will start during the shutdown window. The design needs an admission gate in addition to readiness signaling.

### 3. Shutdown policy is implicit

Today the code does not have an explicit notion of:

- development fast shutdown
- production drain shutdown
- best-effort cleanup that should never hold exit hostage

### 4. Service ownership is too centralized

`main.py` currently knows too much about individual workers, stop events, and resource cleanup details. That makes shutdown fragile and expensive to evolve.

### 5. Test and reentrancy constraints are real

Existing tests expect lifecycle startup and shutdown to be reentrant on the same app object. Any coordinator must preserve that contract and behave safely when lifespan is disabled in selected tests.

## Approaches Considered

### Approach 1: Tune the existing teardown only

Reduce selected timeouts and parallelize a few calls inside the existing shutdown section.

Pros:

- minimal structural change
- low short-term implementation risk

Cons:

- leaves shutdown ownership implicit
- hard to enforce long-term consistency
- likely to regress as more workers are added

### Approach 2: Add a shutdown coordinator over the current lifecycle

Introduce a coordinator that owns lifecycle state, admission gating, phase ordering, budgets, and summary reporting, while initially wrapping existing stop hooks from `main.py`.

Pros:

- most of the performance payoff
- good fit for staged migration
- does not require every service to be rewritten immediately

Cons:

- still leaves some startup/shutdown wiring in legacy form during migration

### Approach 3: Full startup and shutdown ownership redesign

Require each subsystem to own its lifecycle contract immediately and move both startup and shutdown into a unified registry design.

Pros:

- strongest long-term architecture

Cons:

- too broad for the first delivery
- increases risk that shutdown optimization gets buried under general lifecycle cleanup

## Recommendation

Use Approach 2 as the first delivery, while designing it so the system can later evolve toward Approach 3.

That means:

- build a shutdown coordinator now
- keep the first scope centered on shutdown, not a full lifecycle rewrite
- initially register legacy stop hooks from `main.py` through coordinator adapters
- migrate selected high-value services to first-class lifecycle registration later

## Proposed Architecture

### Lifecycle States

The app should expose explicit lifecycle states:

- `starting`
- `ready`
- `draining`
- `stopped`

`draining` is a first-class state, not just a side effect of readiness flipping false.

Lifecycle state and admission-gate state must be scoped to the FastAPI app instance, not stored only in module-global state. The coordinator should keep its mutable runtime state on `app.state` or an equivalent per-app container so repeated lifespan runs in tests do not leak shutdown state across app reuse.

Stage 1 must include the bridge work needed to move control-plane readiness and admission checks onto coordinator-owned app-scoped state. Control-plane handlers, middleware, and guards should read shutdown state from `request.app.state` or an equivalent app-scoped source rather than continuing to rely on module-global state.

### Shutdown Coordinator

A new coordinator owns shutdown sequencing and observability. `main.py` remains the FastAPI lifespan entry point, but delegates shutdown orchestration to the coordinator.

The coordinator is responsible for:

- transitioning lifecycle state
- opening and closing admission gates
- enforcing a global shutdown deadline
- dividing remaining time into phase budgets
- stopping registered components in ordered parallel phases
- recording per-component outcomes and durations
- emitting a structured shutdown summary before telemetry is torn down

### Admission Control

When shutdown begins, the coordinator must perform both of these actions immediately:

1. mark readiness false
2. activate an admission gate that rejects new heavy or mutating work

The admission gate must cover more than background jobs. The practical rule is:

- no new job acquisition
- no new scheduler-enqueued work
- no new long-running or mutating requests
- lightweight diagnostic or liveness paths may remain available until late shutdown if needed

The coordinator should define an explicit drain admission contract:

- allowed during `draining`:
  - control-plane liveness endpoints
  - control-plane readiness endpoints that report non-ready
  - only the explicitly allowlisted control-plane health aliases needed by current deployments and tests
- rejected during `draining`:
  - mutating API requests
  - long-running requests
  - requests that enqueue, lease, or begin background work

For the first delivery, the allowlist should be intentionally narrow and route-specific rather than pattern-based. The default allowlist should be limited to the existing control-plane health routes such as `/health`, `/ready`, `/health/ready`, and the exact API-v1 health equivalents if required by current callers.

Rejected work should return a consistent `503 Service Unavailable` response with a machine-readable shutdown reason and a retry hint where appropriate.

Admission gating must not rely on request ingress checks alone. The first delivery should require a second drain-state check immediately before any handler or transport actually starts expensive or stateful work, such as:

- enqueueing or leasing a job
- starting a background task
- launching a long-running stream
- mutating durable state
- invoking an expensive provider or subprocess

This second check closes the race where a request or handshake enters just before `draining` begins but would otherwise still start new work afterward.

The drain admission contract must also cover long-lived connection entry points:

- new WebSocket handshakes that would start work must be rejected during `draining`
- new SSE or other streaming response sessions that would start work must be rejected during `draining`
- existing already-established long-lived connections should be handled later by the worker or resource phases according to their shutdown policy rather than being silently ignored

Long-lived transport families must be coordinator-visible. Each transport family that can keep work alive across shutdown, such as WebSocket hubs, SSE session managers, or MCP connection managers, must expose one of the following before it is considered managed by the coordinator:

- an explicit connection or session registry with active-count visibility, or
- a dedicated shutdown hook that can enumerate and close or drain active sessions under a deadline

Generic stream primitives that do not own global session tracking are not sufficient by themselves. The owning endpoint or transport manager must provide the coordinator-visible registry or shutdown surface.

Protocol-specific rejection behavior should be explicit:

- HTTP and SSE session creation: `503 Service Unavailable`
- WebSocket handshakes: explicit close or rejection semantics appropriate to the server surface, documented and tested per endpoint family

Readiness should fail immediately. Liveness should remain healthy until the process is actually in terminal teardown.

For normal HTTP requests, the drain gate should sit early in the middleware chain after only the minimal request-context setup required to evaluate the gate, and before expensive auth, dependency resolution, or workload-start logic. Endpoint-local work-start checks remain required even when an early middleware gate exists.

### Registration Model

The coordinator manages registered shutdown components. Each registration contains:

- `name`
- `kind`
  - `acceptor`
  - `producer`
  - `worker`
  - `resource`
  - `finalizer`
- `phase`
- `policy`
  - `dev_fast`
  - `prod_drain`
  - `best_effort`
- `default_timeout_ms`
- `stop()` callable
- optional `active_work_count()` hook
- optional `health_snapshot()` hook
- optional dependency metadata if ordering within a phase is required

The first migration should allow registrations to wrap existing stop hooks in `main.py`. Self-registration by services is a later step, not a prerequisite.

### Global Deadline Model

The coordinator must enforce a single shutdown deadline per run, not independent fixed timeouts for every component.

Profile defaults:

- `dev_fast`: target budget `5s`
- `prod_drain`: target budget `15s`

The coordinator should track remaining time and allocate per-phase budgets from that remainder. If a phase consumes too much time, later phases inherit less budget instead of silently extending total shutdown indefinitely.

Production behavior may allow a bounded soft overrun when in-flight work is still finishing, but that overrun must be explicit and observable.

The coordinator must also define a hard terminal cutoff:

- `dev_fast`: once the deadline is reached, cancel remaining work immediately and continue to terminal resource cleanup
- `prod_drain`: allow a bounded soft overrun only for explicitly drain-eligible work, then force-cancel remaining components at the hard cutoff and record them as timed out or cancelled in the shutdown summary

The hard cutoff exists to prevent indefinite hangs caused by workers, executors, subprocesses, or final flushes that fail to stop cooperatively.

### Ordered Parallel Phases

Shutdown should run in these phases:

1. `transition`
   - mark `draining`
   - fail readiness
   - enable admission gate
   - stop new job acquisition

2. `acceptors`
   - stop anything that accepts or starts new externally-triggered work

3. `producers`
   - stop schedulers, queue pollers, recurring enqueuers, and health-check loops

4. `workers`
   - let workers drain or cancel according to policy and capability class

5. `resources`
   - close shared clients, pools, managers, queues, and servers

6. `finalizers`
   - emit shutdown summary
   - perform last best-effort cleanup that must happen before telemetry and logging teardown

Components inside a phase should stop concurrently unless a declared dependency requires a narrower order.

### Worker Capability Classes

Not every worker can make the same shutdown guarantees. Each worker should be classified as one of:

- `resumable`
  - can checkpoint and continue later
- `retry_safe`
  - cannot resume in-place, but can safely retry or requeue
- `cancel_only`
  - cannot provide stronger guarantees than cancellation

This classification determines production behavior:

- `resumable`: prefer checkpoint and clean exit
- `retry_safe`: prefer requeue or retry-safe termination
- `cancel_only`: allow longer wait, but cancel if the budget expires

Development fast shutdown may cancel all three classes aggressively once the short budget is exhausted.

### Startup-While-Shutting-Down Handling

Shutdown must tolerate the case where deferred startup work is still running.

The coordinator should treat startup tasks as registered components with shutdown semantics, not special-case locals. If shutdown begins before startup completes:

- new startup work must not continue past the admission gate
- in-progress deferred startup tasks must be cancelled or awaited under the same deadline model

### Observability

The coordinator should produce a structured shutdown report containing:

- total shutdown wall time
- selected shutdown profile
- deadline and soft-overrun usage
- per-phase duration
- per-component:
  - start time
  - stop completion time
  - duration
  - result: `stopped`, `timed_out`, `cancelled`, `skipped`, `failed`
  - active work count at drain start if available
  - whether cleanup was downgraded due to profile

This summary must be emitted before telemetry and audit shutdown.

## Configuration

Introduce a single shutdown profile selector:

- `APP_SHUTDOWN_PROFILE=dev_fast|prod_drain|custom`

Support optional overrides for:

- global deadline
- per-phase budget multipliers
- per-component budget overrides
- soft-overrun allowance for production drain

Defaults should be runtime-agnostic and safe for Docker plus mixed self-hosted installs.

## Migration Plan

### Stage 0: Instrument Current Shutdown

Before changing behavior, add structured timing around the current shutdown flow so the baseline is visible.

Deliverables:

- current shutdown wall time metric
- per-component duration logging in the existing path
- baseline evidence for local and Docker-stop runs

### Stage 1: Add Coordinator, Lifecycle State, And Admission Gate

Deliverables:

- explicit `draining` state
- immediate readiness false transition
- explicit admission gate for new heavy and mutating work
- early middleware placement for the HTTP drain gate
- global deadline handling
- control-plane readiness handlers return non-success status codes on all non-ready and shutdown-in-progress paths
- control-plane handlers and admission checks read coordinator-owned app-scoped state rather than module globals
- endpoint and transport work-start checks exist at the actual enqueue or start boundary for covered shutdown-sensitive flows

### Stage 1.5: Inventory Legacy Shutdown Dependencies And Run Shadow Mode

Before parallelizing teardown, document the current implicit ordering assumptions in `main.py` and classify legacy shutdown entries as:

- safe to parallelize now
- must stay ordered within a phase
- unknown and requiring instrumentation first

Stage 1.5 must also identify aggregate shutdown helpers that hide their own internal sequencing or unbounded waits. Examples include helpers that close many resources in a loop or call blocking shutdown APIs internally. These helpers must be either:

- decomposed into coordinator-visible sub-registrations, or
- updated to enforce their own bounded internal deadlines before they are treated as a single coordinator-managed component

Deliverables:

- dependency inventory for current shutdown steps
- list of components that cannot safely run in parallel yet
- inventory of aggregate shutdown helpers that would otherwise hide serial shutdown tails
- inventory of long-lived transport families and their coordinator-visible session registries or shutdown hooks
- optional shadow-mode coordinator run that records intended ordering and timing without owning final teardown behavior

### Stage 2: Move Legacy Teardown Into Coordinator Phases

Deliverables:

- coordinator adapter registrations for existing `main.py` stop hooks
- ordered parallel phase execution
- deduplication of repeated shutdown responsibilities
- preservation of known required ordering edges discovered in Stage 1.5

### Stage 3: Migrate Critical Workers To Capability-Based Drain Semantics

Priority candidates:

- jobs workers
- media ingest workers
- audio, audiobook, and presentation workers
- request queue and provider-health background loops
- audit-adjacent services where final flush semantics matter

### Stage 4: Expand Self-Registration And Tune Policies

Deliverables:

- selected services own their own lifecycle registration
- tuned per-component budgets based on real timing data
- optional future extension toward fuller lifecycle ownership

## Risks

- hidden ordering dependencies currently encoded only by manual shutdown order in `main.py`
- underlying thread, executor, or subprocess work may outlive the asyncio task wrapper
- some workers may not currently check shutdown or cancellation frequently enough
- duplicate shutdown ownership can cause double-stop behavior during migration
- test environments that disable lifespan may bypass coordinator paths unless explicitly covered

## Validation And Tests

Add focused tests for:

- lifecycle transition order: `starting -> ready -> draining -> stopped`
- coordinator runtime state is reset per app lifespan and does not leak across repeated test app reuse
- immediate readiness failure on shutdown start
- readiness endpoints return non-success HTTP status on shutdown-in-progress and other non-ready paths
- admission gate rejects new heavy or mutating work during drain
- drain admission allowlist remains available and rejected requests return the expected shutdown response contract
- new WebSocket and SSE session establishment is rejected during `draining` for covered endpoint families
- requests or sessions admitted just before `draining` do not start new work after the work-start boundary check fires
- covered long-lived transport families expose coordinator-visible registries or deadline-bounded shutdown hooks
- HTTP drain gate runs early enough to avoid expensive middleware or dependency work before rejection
- reentrant startup/shutdown on the same app object remains safe
- shutdown while deferred startup is still active
- global deadline enforcement for `dev_fast`
- bounded parallel shutdown for `prod_drain`
- hard cutoff behavior after any permitted production soft overrun
- component timeout handling and summary reporting
- resource shutdown ordering so dependencies are not closed too early
- idempotent shutdown for components that were previously stopped twice
- selected tests that disable lifespan continue to behave correctly
- started-TestClient fallback paths still enter and exit shutdown safely

## Success Criteria

- local shutdowns usually complete within `5s`
- production-style shutdowns usually complete within `15s`
- shutdown wall time no longer scales linearly with the count of registered components
- new work is rejected immediately once the app enters `draining`
- per-component shutdown summaries make slow or misbehaving services obvious
- shutdown logic is no longer primarily encoded as one large serial block in `main.py`
