# Chat Playground Quick Usage QA Guide (2026-02-22)

## Audience

QA, onboarding reviewers, and support triage for chat-page discoverability and completion flows.

## 5-Minute Walkthrough

1. Open `/chat` with an empty conversation.
2. Confirm region orientation copy and starter cards are visible.
3. Click `Compare models`, verify compare mode activation notice appears.
4. Click `Character chat`, verify actor settings opens and character context chip appears after selection.
5. Click `Knowledge-grounded Q&A`, verify Search & Context opens and RAG mode is active.
6. Toggle voice chat, verify voice status indicator and mode telemetry event path.
7. Validate `Temporary Chat` badge and no-save semantics after creating a temporary session.

## Expected Signals

- Active model/provider chip is visible before send.
- Context strip lists active modifiers (compare, character, pinned sources, JSON, routing).
- Share modal shows read-only role scope and automation shortcut.
- Variant count uses explicit `x of y` format.
- Branch context shows fork point and depth when in branch view.

## Targeted Verification Commands

```bash
bunx vitest run \
  src/components/Option/Playground/__tests__/PlaygroundEmpty.test.tsx \
  src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx \
  src/components/Option/Playground/__tests__/ConversationBranching.integration.test.tsx \
  src/components/Layouts/__tests__/Header.share-links.integration.test.tsx \
  --reporter=dot
```

Run result (2026-02-22): passed in consolidated stage-closure sweep.
