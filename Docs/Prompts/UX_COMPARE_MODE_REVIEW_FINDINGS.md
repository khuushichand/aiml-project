# UX Review: Chat Compare Mode — Detailed Findings

> **Updated 2026-02-22:** Review accuracy corrections (UX-006 diff rendering, UX-005 contract panel already implemented) and fix status for UX-002, UX-004, UX-011, UX-013, UX-015, UX-016, UX-018, UX-019.

> **Review Date:** 2026-02-22
> **Scope:** Compare Mode feature within the Chat Page (Playground)
> **Methodology:** Dual-perspective review (A: Senior HCI/UX Designer, B: End User) applied against actual implementation code
> **Source Files Reviewed:** `CompareToggle.tsx`, `compare-slice.ts`, `useCompareMode.ts`, `compare-preflight.ts`, `compare-interoperability.ts`, `compare-response-diff.ts`, `compare-normalized-preview.ts`, `compare-metrics.ts`, `compare-constants.ts`, `PlaygroundForm.tsx`, `PlaygroundChat.tsx`, `Playground.tsx`, `ComposerToolbar.tsx`, `useChatActions.ts`, locale files (`playground.json`)

---

## 1. Executive Summary

Compare Mode is an ambitious, well-architected feature that enables users to fan out a single prompt to 2–3 LLM providers and compare responses side-by-side. The implementation demonstrates strong engineering foundations — persistent state via IndexedDB, pre-flight capability validation, interoperability notices, and a rich telemetry layer — but the **user-facing experience exposes several critical UX gaps**. The feature is gated behind a feature flag (`FEATURE_FLAGS.COMPARE_MODE`) and disabled by default, which creates a discovery problem: users who would benefit most never find it. Once discovered, the three-phase mental model (enable feature → select models → send prompt → choose winner → continue) has **insufficient scaffolding** at each transition, particularly around the "what happens next" question after selecting a canonical response. The diff computation logic (`compare-response-diff.ts`) exists but has **no visual rendering path** in the current UI — highlights are computed but never displayed. The overall maturity is "engineering-complete, UX-incomplete."

---

## 2. Findings by Dimension

### Dimension 1: Mental Model Clarity

| ID | Severity | Finding | Impact | Recommendation | Comparable |
|----|----------|---------|--------|----------------|------------|
| UX-001 | **Major** | **Two-layer activation creates confusion.** Users must (1) enable the feature flag in settings, then (2) activate compare mode per-session via CompareToggle. The `compareFeatureEnabled` flag in `useCompareMode.ts:43` gates visibility, and `compareMode` (line 44) gates behavior. A user who enables the feature flag but forgets to click Compare sees no change, with no prompt explaining the next step. | All users on first use. | Collapse to a single activation: clicking "Compare" in the composer auto-enables the feature flag. Remove the two-step gate or add a first-use tooltip: "Compare mode is ready — click the Compare button to start." | Poe: single toggle; TypingMind: one-click comparison. |
| UX-002 | **Major** | **"Main response" / "Canonical" terminology inconsistency.** The codebase uses three terms interchangeably: "canonical" (`compareCanonicalByCluster` in `compare-slice.ts:53`), "main response" (`composer.comparePrimaryOn` = "Main response"), and "chosen" (`compareChosenLabel` = "Chosen"). Users encounter different labels depending on where they look — the button says "Use as main response", the badge says "Chosen", the state key says "canonical." | All users; erodes trust in the UI's precision. | Standardize on **one user-facing term** — recommend "Primary" or "Chosen answer" — and use it consistently in all buttons, badges, tooltips, and notifications. Reserve "canonical" for internal code only. | ChatGPT: "selected response"; Poe: "best answer". |
| UX-003 | **Major** | **Post-selection continuation contract is poorly communicated.** After choosing a winner, `compareContinueContract` reads: "Next turns continue with {{model}} only. Re-enable Compare to send to multiple models again." This is a major behavioral shift (fan-out collapses to single model) communicated via a single text string. There is no visual indicator on subsequent messages that the conversation has "narrowed" to one model. | Power users doing multi-turn compare evaluations. | Add a persistent banner/chip below the composer when continuation mode is active: "Continuing with [Model Name] — [Switch back to Compare]". Add a model badge on each subsequent assistant message. | OpenRouter: shows active model badge per message. |
| UX-004 | **Minor** | **"Winner" terminology in continuation state.** `compareContinuationModeByCluster` uses "winner" as a mode value (visible in guard test). This competitive/gamified language may feel inappropriate for analytical use cases (e.g., comparing medical or legal responses). | Users in professional/sensitive contexts. | Use "selected" instead of "winner" in internal state and any surfaced labels. | N/A — most tools avoid ranked language. |
| UX-005 | **Minor** | **No pre-send contract panel.** Before the user sends their first compare prompt, there is no dedicated UI element summarizing what will happen: "Your message will be sent to [Model A], [Model B], [Model C] simultaneously." The send button label `compareSendToModels` ("Send to {{count}} models") helps but doesn't name the models. | First-time compare users. | Add a compact "contract" strip above the composer when compare mode is active, listing model icons + names. E.g., `[GPT-4] [Claude] [Gemini] — your message goes to all three.` | Poe: shows model avatars in the compose area before sending. |

### Dimension 2: Comparison Integrity & Bias Reduction

| ID | Severity | Finding | Impact | Recommendation | Comparable |
|----|----------|---------|--------|----------------|------------|
| UX-006 | **Critical** | **Response diff highlights are computed but never rendered.** `compare-response-diff.ts` computes `addedHighlights`, `removedHighlights`, and `overlapRatio`, but no component in `PlaygroundChat.tsx` or any other file consumes this output to render visual diff markers. The diff logic is test-covered but UI-invisible. Users must manually read and compare responses without any visual aid. | All compare users — the core value proposition (easy comparison) is undermined. | Wire `computeResponseDiffPreview()` into the compare cluster renderer. Display added segments in green highlight, removed in red. Show `overlapRatio` as a similarity badge (e.g., "72% similar"). Minimum viable: show overlap % between each pair. | OpenRouter: highlights divergent sections; Cursor: shows inline diffs with green/red highlighting. |
| UX-007 | **Major** | **No randomization of response card order.** Compare responses are rendered in a fixed order determined by the model selection array (`compareSelectedModels` in `compare-slice.ts:27`). The first model always appears first, creating a position bias (primacy effect). Research shows the first option in a list receives 15-20% more selections. | All compare users — evaluation integrity compromised. | Randomize card order on each compare cluster render. Optionally allow users to toggle between "randomized" and "ordered" views. Store the randomization seed per cluster so it's stable within a session but different across clusters. | Academic A/B testing tools randomize by default. |
| UX-008 | **Major** | **No cost anchoring or token count per response.** The locale includes `compareTokens` ("Tokens: {{count}}") and `compareLatency` ("Latency"), but these appear to be available only as metadata labels — there's no evidence in `PlaygroundChat.tsx` that actual token counts or latency measurements are rendered per card. Users comparing a 50-token response from GPT-4 vs. a 500-token response from Claude have no signal about the cost/efficiency tradeoff. | Cost-conscious users; enterprise users with budgets. | Display per-response: (1) output token count, (2) latency in ms, (3) estimated cost. Render as subtle metadata under each response card. | OpenRouter: shows cost per message; TypingMind: shows token count. |
| UX-009 | **Minor** | **Normalized preview truncation loses comparison value.** `compare-normalized-preview.ts` truncates previews to 120–280 chars. For responses that differ only in their conclusions (which tend to come later), the preview may show only the similar introductions. The budget is based on the shortest response length, which may be a terse refusal. | Users scanning response previews in compact view. | Allow "tail preview" mode that shows the last N chars instead of the first N. Or use the diff highlights to select the most distinctive excerpt for each preview. | N/A — novel recommendation. |
| UX-010 | **Minor** | **No blind evaluation mode.** Model identities are always visible during comparison. Users who want unbiased evaluation cannot hide which model produced which response. | Researchers, evaluators conducting systematic model assessments. | Add a "Blind mode" toggle (per-cluster) that hides model labels, replacing them with "Response A / B / C". Reveal identities after selection. | Academic evaluation practices; some A/B testing platforms. |

### Dimension 3: Error Prevention & Recovery

| ID | Severity | Finding | Impact | Recommendation | Comparable |
|----|----------|---------|--------|----------------|------------|
| UX-011 | **Critical** | **No visible handling when one model fails in a compare fan-out.** The code tracks `compareError` as a prop on `PlaygroundMessage` but there is no dedicated error card or partial-success UI. If Model B fails (rate limit, timeout, auth error) while A and C succeed, the user may see 2 cards with no explanation of why the third is missing. | All compare users — a single provider failure silently degrades the experience. | Render a dedicated error card for failed models with: (1) model name, (2) error type (rate limit / timeout / auth), (3) "Retry" button, (4) "Remove from comparison" option. Show the card in-place where the response would have appeared. | ChatGPT: shows clear error state per message; TypingMind: shows retry button on failure. |
| UX-012 | **Major** | **No undo for accidental compare send.** Once a compare fan-out is triggered, there is no way to cancel individual model requests or undo the entire compare turn. The stop button (if wired) would need to cancel multiple concurrent streams. | Users who accidentally send to the wrong model set. | Add a "Cancel all" button that stops all in-flight streams. For already-completed responses, allow "Discard this compare turn" which removes the cluster and restores the conversation to pre-send state. | Claude.ai: stop button cancels generation; ChatGPT: stop applies to current generation. |
| UX-013 | **Major** | **Feature auto-disables without notification.** `useCompareMode.ts:70-73`: if `effectiveCompareEnabled` becomes false while `compareMode` is true, compare mode silently deactivates and clears selected models. The user gets no toast/notification explaining why compare mode turned off. | Users whose feature flag is toggled externally (e.g., admin settings, A/B test cohort change). | Show a toast: "Compare mode was disabled. Your model selections have been saved and will restore when compare mode is re-enabled." Persist selections separately from the enabled state so they survive flag toggles. | N/A — most tools don't toggle features under the user mid-session. |
| UX-014 | **Minor** | **No validation when selected models become unavailable.** If a previously selected compare model goes offline or is removed from the provider list, it remains in `compareSelectedModels` as a stale string ID. The `getModelLabel` fallback (CompareToggle.tsx:53-54) will show the raw model ID string, which is a poor UX signal. | Users with dynamic provider configurations. | On hydration and before send, validate selected models against the current `availableModels` list. Remove stale entries and notify: "Model X is no longer available and was removed from your comparison." | TypingMind: grays out unavailable models. |
| UX-015 | **Minor** | **Max model limit has no warning before hitting it.** `CompareToggle.tsx:62` checks `canAddMore` silently — the Add dropdown simply doesn't appear when the limit is reached. There's a locale string `compareMaxModelsTitle` ("Compare limit reached") but no code path that displays it as a toast or modal. | Users trying to add a 4th model. | Show a brief inline message or tooltip when the limit is reached: "Maximum of {{limit}} models reached. Remove one to add another." | Poe: shows "limit reached" inline message. |

### Dimension 4: Cognitive Load & Information Density

| ID | Severity | Finding | Impact | Recommendation | Comparable |
|----|----------|---------|--------|----------------|------------|
| UX-016 | **Major** | **Interoperability notices can stack to 6 items simultaneously.** `compare-interoperability.ts` generates up to 6 notices (voice, character, pinned sources, web search, prompt steering, JSON mode). When multiple features are active alongside compare, the notice area could show 6 information blocks, overwhelming the composer area. | Power users combining character chat + RAG + compare. | Collapse notices after the first 2 into an expandable "N more notices" link. Prioritize warning-tone notices (voice) over neutral ones. | Claude.ai: uses a single contextual banner. |
| UX-017 | **Major** | **Compare cluster rendering in the message timeline has no visual grouping boundary.** Locale strings reference `compareClusterLabel` ("Multi-model answers") and `compareClusterCount` ("{{count}} models"), but the cluster is rendered as adjacent cards in `PlaygroundChat.tsx`. Without a strong visual container (border, background, or grouped header), users scrolling through a long conversation may not immediately perceive which responses belong to the same compare turn. | All compare users in multi-turn conversations. | Wrap each compare cluster in a visually distinct container: light background color, left border accent, and a header bar showing "Compare turn · 3 models · [View diff]". | Poe: wraps multi-model responses in a card group with tabs. |
| UX-018 | **Minor** | **Model chip labels truncate at 60px.** `CompareToggle.tsx:205`: `max-w-[60px] truncate text-[9px]`. For models like "claude-3-opus-20240229" or "gpt-4-turbo-preview", the truncated chip is unreadable. Users can't distinguish between similar model names. | Users comparing models within the same family (e.g., GPT-4 vs. GPT-4-turbo). | Increase chip width to 80-100px, or use the model `nickname` field more aggressively. When models share a prefix, show only the distinguishing suffix (e.g., "opus" vs. "sonnet"). | OpenRouter: shows abbreviated model names with full tooltip. |
| UX-019 | **Minor** | **Per-model thread preview uses 10px uppercase labels.** `PlaygroundChat.tsx` renders thread labels as `text-[10px] font-medium uppercase text-text-subtle`. At 10px, these labels are below the WCAG minimum text size recommendation of 12px and may be illegible on standard-DPI screens. | Users with visual impairments; older users. | Increase to at least 11px (ideally 12px). Remove uppercase styling which reduces legibility at small sizes. | WCAG 2.1 AA recommends minimum 12px for UI text. |
| UX-020 | **Enhancement** | **No "quick comparison" summary.** After responses arrive, users must read each one fully. There's no auto-generated summary like "Response A is 2x longer, uses more technical language, and includes code examples. Response B is concise and conversational." | Users comparing lengthy responses. | Optionally generate a 1-2 sentence AI-powered comparison summary per cluster. Could use `computeResponseDiffPreview()` data (overlap ratio, segment counts) as a lightweight alternative. | N/A — novel recommendation; Cursor's diff summary is a partial analog. |

### Dimension 5: Interoperability Coherence

| ID | Severity | Finding | Impact | Recommendation | Comparable |
|----|----------|---------|--------|----------------|------------|
| UX-021 | **Major** | **Character chat is fully disabled during compare mode.** `PlaygroundChat.tsx:717`: `characterIdentityEnabled = !compareModeActive && selectedCharacter?.id`. This is a hard either/or — users cannot compare how different models roleplay the same character. The UI provides no explanation for why the character avatar and mood styling disappear. | Character chat power users who want model comparison. | Allow character context to be shared across compare models (the system prompt with character card already goes to all models). Keep character identity UI active. The interoperability notice for characters (`compareInteropCharacter`) already exists — use it as confirmation rather than justification for disabling. | SillyTavern: allows model switching during character sessions. |
| UX-022 | **Major** | **Voice mode warning is passive, not preventive.** `compare-interoperability.ts:34-43` generates a warning notice about voice + compare, but doesn't prevent activation. Voice TTS playback of multiple simultaneous responses could produce audio chaos — overlapping speech from different models. | Voice mode users who enable compare. | Either (1) auto-disable TTS for compare responses and show text-only with a "Play" button per card, or (2) queue TTS playback sequentially (A then B then C) with a visible player. The warning notice alone is insufficient. | No comparable — most tools don't combine voice + comparison. |
| UX-023 | **Minor** | **JSON mode constraint is noted but not enforced differently per model.** `compareInteropJson` notes "JSON mode constrains every compare response." But if one model returns valid JSON and another returns a JSON parsing error, the error handling may differ. There's no validation that all models support JSON mode equally. | Developers using compare to test JSON output across models. | Add JSON-mode support to the preflight capability check (`compare-preflight.ts`). Flag models that don't support structured output before sending. | N/A |
| UX-024 | **Minor** | **Pinned RAG sources count is informational only.** The notice `compareInteropPinned` says "{{count}} pinned sources are shared" but doesn't surface whether different models used those sources differently. Each model may weight or cite the pinned sources differently, but there's no per-response citation comparison. | RAG users evaluating source usage across models. | Show per-response citation indicators: "Model A cited 3/5 sources, Model B cited 1/5 sources." | Perplexity: shows per-response source citations. |
| UX-025 | **Enhancement** | **No compare-specific behavior for web search results.** When web search is enabled, `compareInteropWebSearch` notes tool calls are "shared" — but it's unclear whether each model performs its own search or if results are cached and shared. | Users evaluating search-augmented responses. | Clarify in the notice whether search results are shared (same results, different interpretations) or independent (each model searches separately). Add a "Search results" disclosure per response card. | Perplexity: shows search results per response. |

### Dimension 6: Continuation & Long-Conversation Ergonomics

| ID | Severity | Finding | Impact | Recommendation | Comparable |
|----|----------|---------|--------|----------------|------------|
| UX-026 | **Major** | **No visual distinction between compare clusters and regular messages when scrolling back.** In a conversation with 10+ turns, some compare and some single-model, the timeline offers no quick visual scan to identify which turns were compared. The `compareClusterLabel` text exists but blends with regular message formatting. | Users reviewing conversation history with mixed compare/single turns. | Add a colored left-border (e.g., 3px primary-color stripe) to compare clusters. Add a small `GitCompare` icon in the message metadata area. Allow clicking it to expand/collapse the cluster. | SillyTavern: shows swipe indicators on variant messages. |
| UX-027 | **Major** | **Split chat provenance is one-way.** `compareSplitChats` in `compare-slice.ts:69-79` maps `clusterId → modelKey → historyId`, creating new chat histories from compare responses. But the new chat has no back-link to its origin. Users who split a compare turn into 3 separate chats cannot later trace which comparison spawned them. | Users managing multiple split conversations. | Add `compareHistoryPrefix` ("Compare: {{title}}") as the default title for split chats. Store a `parentCompareClusterId` field in the new chat's metadata. Add a "View original comparison" link in the split chat's header. | N/A — novel feature; Git's branch visualization is a loose analog. |
| UX-028 | **Minor** | **Bulk split success/failure messages are vague.** `compareBulkSplitSuccess` says "Created {{count}} chats" and `compareBulkSplitPartialFail` says "Failed to create {{count}} chats." Neither message tells the user where the new chats are or which ones failed. | Users performing bulk splits. | Include chat names or links in the success message: "Created 3 chats: [GPT-4 thread], [Claude thread], [Gemini thread]." For failures, specify which model's split failed and why. | N/A |
| UX-029 | **Minor** | **Continuation mode per-cluster has no aggregate view.** `compareContinuationModeByCluster` stores per-cluster continuation preferences, but there's no summary showing "Turn 3: continued with GPT-4; Turn 7: continued with Claude." Users lose track of which model "won" at each compare point. | Power users doing systematic model evaluation over many turns. | Add a "Compare history" summary accessible from the chat header or sidebar, showing a timeline of compare turns and selections. | N/A — novel recommendation. |
| UX-030 | **Enhancement** | **No export of comparison results.** The metrics track `export_canonical` but there's no user-facing export that captures the full comparison: all responses, diff data, and the selection rationale. Users doing model evaluation can't produce a report. | Researchers, enterprise evaluators. | Add "Export comparison" button per cluster that generates a markdown or JSON file with all model responses, metadata (tokens, latency), diff highlights, and the user's selection. | N/A — would be a differentiating feature. |

---

## 3. Cross-Cutting Concerns

### 3.1 Accessibility

| Issue | Detail | Severity |
|-------|--------|----------|
| **Compare toggle is keyboard-accessible** | `aria-pressed={active}` on the main button (`CompareToggle.tsx:165`) correctly communicates toggle state. | OK |
| **Model removal buttons have aria-labels** | `aria-label={t("common:remove", "Remove")}` on each chip removal button (`CompareToggle.tsx:98`). | OK |
| **No live region for compare cluster arrival** | When 2–3 responses stream in simultaneously, screen readers receive no announcement that a compare cluster has completed. No `aria-live` region wraps the cluster. | Major |
| **Thread preview text too small** | 10px text (`text-[10px]`) in per-model thread preview is below WCAG minimum. | Minor |
| **Popover focus trap** | Antd Popover manages focus internally but doesn't return focus to the trigger button on close in all cases. | Minor |
| **No keyboard shortcut for compare toggle** | Power users cannot activate compare mode without mouse interaction. No documented shortcut. | Enhancement |

### 3.2 State Persistence & Data Integrity

| Issue | Detail | Severity |
|-------|--------|----------|
| **Hydration race condition possible** | `useCompareMode.ts:96-142`: The `cancelled` flag prevents stale writes, but there's a window between `compareHydratingRef.current = true` (line 102) and the async `getCompareState` resolving where a user toggle would be overwritten by the hydration result. The save is debounced at 200ms, so a fast toggle could be lost. | Minor |
| **No state versioning** | The `saveCompareState` payload has no schema version. If the state shape evolves (new fields added), old persisted states may cause undefined behavior on hydration. | Minor |
| **Temporary chats excluded** | `useCompareMode.ts:97`: `historyId === "temp"` causes early return — compare state is never persisted for temporary chats. Users in temp mode get compare functionality but lose all selections on navigation. | Minor |

### 3.3 Performance Considerations

| Issue | Detail | Severity |
|-------|--------|----------|
| **200ms debounce on every state change** | `useCompareMode.ts:156-169`: Every change to any of 8 state branches triggers a 200ms debounced IndexedDB write. With rapid model selection/deselection, this could queue multiple writes. | Minor |
| **Model metadata rebuilt on every render** | `buildCompareModelMetaById` in `compare-preflight.ts` takes the full model list and creates a new Map. If called in a render path without memoization, this O(n) operation runs on every re-render. | Minor |
| **Metrics writes are async but serial** | `compare-metrics.ts:60-104`: Each metric event reads, mutates, and writes back. Concurrent events could cause a lost-update race. | Minor — low event frequency mitigates. |

---

## 4. Priority Matrix

Findings sorted by severity and estimated user impact:

| Priority | ID | Severity | Finding Summary | Effort | Status |
|----------|----|----------|----------------|--------|--------|
| **P0** | UX-006 | Critical | Response diffs computed but never rendered | Medium | Already Implemented |
| **P0** | UX-011 | Critical | No error card for failed model in fan-out | Medium | Fixed |
| **P1** | UX-001 | Major | Two-layer activation gate | Low | Open |
| **P1** | UX-002 | Major | Inconsistent canonical/main/chosen terminology | Low | Fixed |
| **P1** | UX-003 | Major | Post-selection continuation poorly communicated | Low | Open |
| **P1** | UX-007 | Major | No response card order randomization (bias) | Low | Open |
| **P1** | UX-008 | Major | No per-response token/cost/latency display | Medium | Open |
| **P1** | UX-017 | Major | Compare cluster has no visual grouping boundary | Low | Partial |
| **P1** | UX-021 | Major | Character chat fully disabled during compare | Medium | Open |
| **P1** | UX-022 | Major | Voice mode warning passive, not preventive | Medium | Open |
| **P1** | UX-012 | Major | No undo for accidental compare send | High | Open |
| **P1** | UX-013 | Major | Feature auto-disables without notification | Low | Fixed |
| **P1** | UX-016 | Major | Up to 6 interoperability notices can stack | Low | Fixed |
| **P1** | UX-026 | Major | No visual distinction for compare clusters in history | Low | Open |
| **P1** | UX-027 | Major | Split chat provenance is one-way | Medium | Open |
| **P2** | UX-004 | Minor | "Winner" terminology in continuation state | Low | Fixed (user-facing labels only) |
| **P2** | UX-005 | Minor | No pre-send contract panel | Low | Already Implemented |
| **P2** | UX-009 | Minor | Preview truncation loses comparison value | Medium | Open |
| **P2** | UX-010 | Minor | No blind evaluation mode | Medium | Open |
| **P2** | UX-014 | Minor | No validation for stale model selections | Low | Open |
| **P2** | UX-015 | Minor | Max model limit has no visible warning | Low | Fixed |
| **P2** | UX-018 | Minor | Model chip labels truncate at 60px | Low | Fixed |
| **P2** | UX-019 | Minor | Thread preview uses 10px text | Low | Fixed |
| **P2** | UX-023 | Minor | JSON mode not in preflight capability check | Low | Open |
| **P2** | UX-024 | Minor | Pinned sources citation comparison missing | Medium | Open |
| **P2** | UX-028 | Minor | Bulk split messages are vague | Low | Open |
| **P2** | UX-029 | Minor | No aggregate continuation mode view | Medium | Open |
| **P3** | UX-020 | Enhancement | No quick comparison summary | High | Open |
| **P3** | UX-025 | Enhancement | No compare-specific web search behavior clarity | Low | Open |
| **P3** | UX-030 | Enhancement | No export of comparison results | Medium | Open |

---

## 5. Open Questions

These questions could not be definitively answered from code alone:

| # | Question | Why It Matters | Where to Look |
|---|----------|----------------|---------------|
| 1 | **Are compare fan-out requests sent sequentially or in parallel?** `useChatActions.ts`'s `sendPerModelReply` is referenced but the actual network dispatch pattern isn't visible. Parallel sends would produce near-simultaneous responses; sequential sends would show staggered streaming. | Affects latency perception and UI rendering order. | `useChatActions.ts` full implementation, network layer. |
| 2 | **What happens to compare state when the user navigates away mid-stream?** The 200ms debounce saves state, but if 2 of 3 responses have arrived when the user switches chats, is the partial cluster persisted or discarded? | Could cause orphaned partial clusters in history. | Navigation guards, message persistence layer. |
| 3 | **Is `buildHistoryForModel` creating separate conversation branches or cloned message arrays?** This affects whether split chats share message objects by reference or are fully independent copies. | Data integrity: edits in a split chat could theoretically affect the parent. | `useChatActions.ts` `buildHistoryForModel` implementation. |
| 4 | **How does the compare cluster render when `MAX_COMPARE_MODELS` is changed from 3 to 2 mid-conversation?** Existing clusters with 3 responses would still exist in history, but the constraint now says max 2. | Could cause validation errors on reload or inconsistent display. | `useCompareMode` hydration logic, cluster rendering. |
| 5 | **Is there a streaming progress indicator per response card?** The standard streaming indicator (stop button, animation) may not scale to 3 simultaneous streams. | Users need per-card streaming state to know which models have finished. | `PlaygroundChat.tsx` streaming props per-message. |
| 6 | **What is the mobile rendering behavior for compare clusters?** The `isMobile` prop is passed through `ComposerToolbar`, but it's unclear if compare cards stack vertically, use a tab/swipe pattern, or are hidden entirely on mobile. | Mobile users may be excluded from the feature without warning. | `PlaygroundChat.tsx` responsive CSS, `ComposerToolbar.tsx` mobile layout. |

---

## 6. Summary of Top 5 Priority Fixes

1. **Render the diff highlights** (UX-006): The computation is already implemented and tested. Wire `computeResponseDiffPreview()` output into the cluster renderer with green/red highlights and an overlap percentage badge. This is the single highest-impact change.

2. **Add error cards for failed fan-out models** (UX-011): When a model fails during compare, render a placeholder card with the error type and a retry button. Without this, users see an inexplicable gap.

3. **Standardize "canonical" terminology** (UX-002): A find-and-replace-level change. Pick one term, update locale files, and ensure buttons/badges/tooltips all match.

4. **Add visual grouping for compare clusters** (UX-017): Wrap each cluster in a bordered container with a "Multi-model answers · N models" header. Low effort, high readability impact.

5. **Randomize response card order** (UX-007): Add a per-cluster random seed that shuffles card order on initial render. Stable within a session, different across turns. Eliminates position bias.
