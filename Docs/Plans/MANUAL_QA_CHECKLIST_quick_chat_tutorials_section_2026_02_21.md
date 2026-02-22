# Manual QA Checklist: Quick Chat Tutorials Section

Date: 2026-02-21
Owner: UI tutorials rollout
Scope: Quick Chat Browse Guides tutorial section + P0 page tutorial coverage

## Preconditions

1. Launch WebUI/extension build with latest tutorial registry.
2. Ensure routes are reachable:
   - `/chat`
   - `/workspace-playground`
   - `/media`
   - `/knowledge`
   - `/characters`
3. Clear tutorial progress state once before run (Tutorials -> Reset Progress).

## Global Checks

1. Open Quick Chat helper -> Browse Guides mode.
2. Confirm `Tutorials for this page` section renders above workflow Q&A cards.
3. Confirm section shows title, description, step count, and `Start` action for incomplete tutorials.
4. Start a tutorial from Quick Chat:
   - Tutorial begins immediately.
   - Quick Chat closes (or does not block interaction).
5. Complete tutorial and reopen Quick Chat:
   - Button changes from `Start` to `Replay`.
   - Status icon indicates completion.
6. Confirm routes with no tutorial (example `/settings/health`) show the tutorials empty state while workflow cards still render.

## Route Coverage Checks (P0)

1. `/chat`
   - Tutorials list includes at least `Chat Basics`.
   - `Tools & Attachments` and `Voice Chat` remain locked until `Chat Basics` is completed.
2. `/workspace-playground`
   - Tutorials list includes `Research Studio Basics`.
   - Steps target header, sources pane, chat pane, studio pane, and workspace switcher.
3. `/media`
   - Tutorials list includes `Media Basics`.
   - Steps target search input, filters panel, run search, results list, content viewer, and tools toggle.
4. `/knowledge`
   - Tutorials list includes `Knowledge Basics`.
   - Steps target search input, source selector, context bar, history surface, and results shell.
5. `/characters`
   - Tutorials list includes `Characters Basics`.
   - Steps target new button, search input, scope toggle, view mode toggle, and list/gallery area.

## Regression Checks

1. Browse Guides search/filter still narrows workflow cards correctly.
2. `Ask docs mode` on a workflow card still sends its canned question.
3. `Open <page>` buttons still navigate to the mapped route.
4. Help modal `Tutorials` tab still lists page tutorials independently of Quick Chat.
5. Legacy route aliases continue to resolve tutorials:
   - `/options/playground` -> `/chat`
   - `/options/media` -> `/media`
   - `/options/knowledge` -> `/knowledge`
   - `/options/characters` -> `/characters`
