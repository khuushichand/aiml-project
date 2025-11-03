# Logging

Note: This README is scaffolded from the core template. Replace placeholders with accurate details.

## 1. Descriptive of Current Feature Set

- Purpose: Centralized logging utilities and policies.
- Capabilities: Structured logs, levels, sinks/handlers.
- Inputs/Outputs: Log events in; sinks and files out.
- Related Endpoints: Link API routes (if any) and files.
- Related Schemas: N/A unless models are logged.

## 2. Technical Details of Features

- Architecture & Data Flow: Loggers, formatters, handlers.
- Key Classes/Functions: Entry points and helpers.
- Dependencies: `loguru` and internal modules.
- Data Models & DB: Persisted logs (if any).
- Configuration: Env vars for levels/format/sinks.
- Concurrency & Performance: Asynchronous sinks; overhead.
- Error Handling: Log drops or backpressure.
- Security: Avoid logging secrets; PII handling.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure: Subpackages and responsibilities.
- Extension Points: New sinks/formatters or policies.
- Coding Patterns: Logger usage conventions.
- Tests: Where tests live; fixtures and golden files.
- Local Dev Tips: Local log config and inspection.
- Pitfalls & Gotchas: Sensitive data and volume.
- Roadmap/TODOs: Planned instrumentation and sinks.

