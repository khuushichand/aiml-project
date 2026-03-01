# Chat Playground Share/Automation Guardrails (2026-02-22)

## Stage Scope

Expose high-value share and automation controls with explicit role scoping and safe defaults.

## Implemented Surface

- Share modal now includes explicit read-only role scope:
  - `Access role: Read-only viewer`
  - Clear statement that recipients cannot send/edit/delete.
- TTL + revoke lifecycle remains available in the modal.
- Automation hook is visible from share flow:
  - `Open automation workflows` button routes to `/workflow-editor` with chat context query params.

## Role Contract

- Current backend permission contract remains `view` only (read-only).
- UI displays this scope directly and keeps authoring controls hidden in shared views.

## Verification

```bash
bunx vitest run \
  src/components/Layouts/__tests__/chat-share-links.test.ts \
  src/components/Layouts/__tests__/Header.share-links.integration.test.tsx \
  --reporter=dot
```

Evidence highlights:

- Active/expired/revoked link logic validated.
- TTL creation and revocation flows validated.
- Read-only role scope copy and workflow automation shortcut navigation validated.
