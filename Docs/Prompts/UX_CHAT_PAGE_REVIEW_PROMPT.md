# UX/HCI Expert Review: Chat Page (Playground)

## What You're Reviewing

The **Chat Page** is the primary conversational interface in a media analysis and knowledge management application. It supports multi-provider LLM chat, character roleplay, multi-model comparison, RAG-grounded Q&A, voice I/O, message branching, artifacts, and a rich composer with @mentions, system prompt templates, and parameter presets.

### Current Layout (Desktop 1024px+)
```
┌──────────────────────────────────────────────────────────────────┐
│ ChatHeader: logo, chat title (editable), sidebar toggle,         │
│ shortcuts, command palette, new chat, settings, theme toggle     │
├──────────┬───────────────────────────────────┬───────────────────┤
│ Chat     │        Message Timeline           │   Artifacts /     │
│ Sidebar  │  (PlaygroundChat)                 │   Knowledge       │
│          │                                   │   Panel           │
│ History  │  [system] [user] [assistant]...   │  (collapsible)    │
│ list,    │  ← variant swipe →                │                   │
│ search,  │  compare clusters                 │  Code viewer,     │
│ folders  │  branch indicators                │  RAG results,     │
│          │                                   │  Mermaid,         │
│          ├───────────────────────────────────┤  data tables      │
│          │ Composer (PlaygroundForm)          │                   │
│          │ [textarea] [attachments]           │                   │
│          │ [toolbar: send, voice, files,      │                   │
│          │  model select, presets, settings]  │                   │
└──────────┴───────────────────────────────────┴───────────────────┘
```
- **Sidebar** (left): Chat history list, search, character selection
- **Message Timeline** (center): Scrollable conversation with streaming, variants, compare clusters, branch indicators
- **Composer** (bottom of center): Multi-line textarea, attachments, toolbar with model selector, voice toggle, file upload, parameter presets, system prompt templates, cost estimation, token progress bar
- **Artifacts / Knowledge Panel** (right, collapsible): Code viewer with syntax highlighting, Mermaid diagrams, data tables, RAG search results, pinned sources

### Responsive Behavior
- Tablet: Sidebar collapses to hamburger overlay; artifacts panel slides out as drawer
- Mobile: Single-column layout; sidebar as full-screen overlay; sticky composer at bottom; artifacts in bottom sheet

---

## Feature Inventory (Currently Implemented)

### Streaming & Real-Time
- Chunked token streaming with visual indicator and stop button
- Live token counting during input composition
- Action info display ("Searching internet...", "Processing...")
- Server-Sent Events (SSE) for all completions

### Message Management
- Inline editing of any message (user or assistant)
- Message deletion, pinning, and ranking
- **Message variants**: swipe left/right through alternative responses per turn
- Regenerate last assistant message with same or different model
- Continue generation (extend incomplete responses)
- Copy message content (plain text and markdown)

### Compare Mode
- Toggle multi-model comparison (side-by-side responses from 2+ models)
- Per-model mini composer inputs for targeted follow-ups
- Canonical response selection (pick the "winner" per turn)
- Split chat visualization with model-labeled clusters
- Model selection/deselection UI (CompareToggle)

### Character Chat
- Character card selection with avatar preview (SillyTavern V2 compatible)
- Character greeting detection and display (ChatGreetingPicker)
- Per-chat prompt preset and generation setting overrides
- Character mood detection from responses with avatar styling
- Multi-character support (directed responses to specific participants)
- World book / lorebook context injection

### Voice I/O
- Voice mode selector: auto / push-to-talk / continuous
- Speech recognition via browser API and WebSocket streaming
- Text-to-speech with multiple providers (OpenAI, Kokoro, ElevenLabs)
- Voice chat indicator showing active recording state
- TTS clip management drawer for replaying past audio

### RAG / Knowledge Integration
- RagSearchBar with preset/expert mode toggle
- Search strategy configuration (hybrid, vector, FTS, BM25 level control)
- Multi-source search: Media DB, Notes, Characters, Chats
- Pinned RAG results kept in context across turns
- Source citing with footnote references in responses
- Source quality feedback (thumbs up/down per result)
- Batch query support with grouped results
- KnowledgeQA: Perplexity-style standalone Q&A interface

### Artifacts Panel
- Syntax-highlighted code viewer (Prism) with language auto-detection
- Mermaid diagram rendering
- Interactive data table visualization
- Copy / download artifact buttons
- Pin artifacts for persistent display

### System Prompts & Steering
- System prompt template library (SystemPromptTemplates)
- Custom system prompt input (free-form text)
- Message steering modes: continue-as-user, impersonate-user, force-narrate
- Steering prompt overrides (custom text for each mode)
- Clear/reset steering state

### Conversation Branching
- Fork conversation from any message (ConversationBranching modal)
- Include or exclude the subsequent response when forking
- Branch history tracking and navigation
- Parent/child conversation tree structure

### Composer Features
- Multi-line auto-growing textarea (ComposerTextarea)
- File and image drag-and-drop attachments (AttachmentsSummary)
- @mention system for referencing tabs, files, or context (MentionsDropdown)
- Parameter presets: Creative / Balanced / Precise (one-click)
- JSON mode toggle for structured output
- Token progress bar (visual budget indicator)
- Cost estimation display (CostEstimation)
- Draft auto-persistence across navigation
- Slash command support

### Provider & Model Management
- Model selector with provider icons and display names
- Model availability checking against server capabilities
- 16+ provider support with metadata caching (15-min TTL)
- Bring-Your-Own-Key credential overrides per request

### Session & State
- Session persistence and restoration on re-open
- Temporary chat mode (ephemeral, no history save)
- Chat title editing for saved conversations
- Chat history search and filtering in sidebar

### Feedback & Analytics
- FeedbackModal for user ratings on responses
- Source quality feedback collection
- Implicit feedback tracking for personalization
- Message ranking (rate individual responses)

---

## Review Dimensions

Please evaluate the page across these dimensions, providing specific findings for each:

### 1. Information Architecture & Discoverability
- Is the relationship between the sidebar (history), timeline (conversation), composer (input), and right panel (artifacts/knowledge) immediately clear?
- Can a first-time user discover compare mode, character chat, RAG search, and voice input without a tutorial?
- Are advanced features (steering, branching, presets, JSON mode, @mentions) findable through progressive disclosure or buried behind non-obvious icons?
- How does the model selector communicate which provider is active, what it costs, and what it supports (tools, vision, streaming)?
- Is the distinction between "new chat", "temporary chat", and "character chat" clear?
- How does the user know a character is active and affecting responses?

### 2. Information Density & Missing Signals
- What information does the user *need* to see that isn't shown? Consider:
  - Token usage per message (input + output) and cumulative session cost
  - Model currently in use and its capabilities (context window, vision, tool use)
  - RAG retrieval transparency: why was this source selected? relevance score? which chunk?
  - Character context size: how much of the context window is consumed by character card + world book + exemplars?
  - Streaming progress: estimated tokens remaining, generation speed (tokens/sec)
  - Provider status: is the selected provider healthy / rate-limited / degraded?
  - Message variant count indicator (e.g., "response 2 of 4")
  - Branch indicator showing fork point and depth
  - Conversation state label (in-progress, resolved, backlog)
- What information is shown that adds noise rather than signal?
- Are error states (provider failure, rate limit, context overflow) clear and actionable?

### 3. User Flows & Task Completion
Evaluate these critical flows for friction, dead ends, and missing affordances:
- **First message**: Empty state → type prompt → send → receive streamed response
- **Multi-turn conversation**: 5+ exchanges with follow-ups, clarifications, and corrections
- **Character roleplay**: Select character → see greeting → respond in character → adjust persona settings mid-chat
- **Compare mode**: Enable compare → select 3 models → send prompt → evaluate responses → pick winner → continue with selected model
- **RAG-grounded chat**: Open knowledge panel → search sources → pin relevant results → ask question referencing sources → verify citations
- **Voice conversation**: Enable voice mode → speak → see transcription → hear TTS response → switch to typing mid-conversation
- **Message branching**: Mid-conversation → fork from message 3 → explore alternative → return to original branch
- **Error recovery**: Provider fails mid-stream → what can the user do? Switch provider? Retry? See what was generated?
- **Export and share**: Export conversation → share via link → recipient views read-only

### 4. Composer Complexity & Input Ergonomics
- Is the composer toolbar overwhelming or well-organized? (Model select, voice, files, images, presets, system prompt, JSON mode, cost, tokens, settings, send)
- How does the composer handle multiple simultaneous contexts: character active + RAG sources pinned + system prompt template + parameter preset?
- Is the @mention system discoverable and easy to use?
- Do parameter presets (Creative/Balanced/Precise) communicate what they change?
- Is the cost estimation useful or anxiety-inducing?
- How does file attachment preview work? Can users remove attachments easily?
- Is the JSON mode toggle clear about what it does and when to use it?

### 5. Compare Mode UX
- Is the mental model of "same prompt → multiple models → pick winner" clear?
- How does the UI handle different response lengths across models?
- Can users easily identify which response came from which model?
- Is the "canonical selection" concept intuitive?
- What happens after compare mode: does the conversation continue with all models or just the selected one?
- How does compare mode interact with character chat, RAG, and voice?

### 6. Responsive Design & Device Parity
- Does the collapsing sidebar feel natural on tablet?
- Is the sticky mobile composer usable with the virtual keyboard open?
- Are touch targets adequate for message actions (variant swipe, action bar buttons)?
- Do compare mode and branching work on mobile, or silently degrade?
- Is the artifacts panel accessible on small screens?
- Can voice mode work well on mobile (where it arguably matters most)?

### 7. Accessibility & Inclusivity
- Keyboard navigation completeness: can every feature be reached without a mouse?
- Screen reader experience: ARIA labels on message actions, live regions for streaming tokens, compare mode cluster announcements
- Focus management: where does focus go after sending a message? After switching variants? After forking?
- Color contrast and color-independence: model labels in compare mode, error states, character mood indicators
- Voice mode accessibility: can deaf users use the chat effectively? Can blind users navigate compare mode?
- Touch target sizes for message action bar buttons

### 8. Missing Functionality & Feature Gaps
Based on comparable tools (see list below), what capabilities would a user expect that are missing? Consider:
- **Message search** within a conversation (Cmd+F equivalent that searches message content)
- **Prompt library** integration (save/load prompts from the prompt studio)
- **Conversation templates** (start from a pre-configured setup: model + system prompt + RAG sources + character)
- **Response diffing** in compare mode (highlight differences between model outputs)
- **Token budget visualization** (how much context remains before truncation?)
- **Conversation summarization** (auto-summarize long threads for context window management)
- **Model recommendation** ("for this task, consider using X because...")
- **Collaborative chat** (multiple users in same conversation)
- **Scheduled messages / automation** (periodic prompts, watchdog queries)
- **Conversation analytics dashboard** (usage by model, cost over time, topic distribution)
- **Quick actions on messages** (summarize this, translate this, explain this, make this shorter)

---

## Backend Capabilities Available (Not All Surfaced in UI)

These backend features exist but may not be fully exposed in the current chat UI. Assess which would most benefit users if surfaced:

| Capability | Backend Support | UI Status |
|---|---|---|
| Provider fallback (auto-retry on different provider) | Full | Not exposed |
| Bring-Your-Own-Key per request | Full | Partial |
| Bedrock guardrails (compliance/safety) | Full | Not exposed |
| Persona exemplar selection (off/default/hybrid/embeddings) | Full | Partial |
| Persona exemplar debug metadata | Full | Not exposed |
| Mood tracking (label, confidence, topic) | Full | Partial (mood styling) |
| Lorebook/world book trigger diagnostics | Full | Not exposed |
| Message ranking (explicit 1-5 rating) | Full | Partial |
| Conversation tree visualization (depth-capped) | Full | Partial (branching UI) |
| Share links with TTL and revocation | Full | Not exposed |
| Per-message RAG context persistence & citation retrieval | Full | Partial |
| Knowledge save (chat → notes with flashcards + tags) | Full | Not exposed |
| Multi-character directed responses | Full | Not exposed |
| Author note token budgeting (UI vs prompt versions) | Full | Not exposed |
| Voice command registry with custom workflows | Full | Not exposed |
| Conversation analytics (bucketed by time/state) | Full | Not exposed |
| Chat slash commands (system/preface/replace injection) | Full | Partial |
| Queue status monitoring | Full | Not exposed |
| Conversation state management (in-progress/resolved/backlog/non-viable) | Full | Not exposed |
| Conversation keyword/tag filtering | Full | Not exposed |
| Optimistic locking on conversation updates | Full | Not exposed |

---

## Comparable Products

When benchmarking, consider how these tools handle similar features:

| Product | Key Features to Benchmark |
|---|---|
| **ChatGPT** (OpenAI) | Message editing with re-generation, conversation branching (tree navigation), memory/personalization, canvas mode (side-by-side editing), GPT selector, file/image upload, voice mode (Advanced Voice), search the web, artifacts/code execution |
| **Claude.ai** (Anthropic) | Artifacts panel (code, documents, diagrams), project knowledge (persistent context), extended thinking toggle, message retry, clean minimal composer, tool use visualization |
| **Gemini** (Google) | Multi-modal input (images, files, audio), Gems (custom personas), extensions (Google services), response modification buttons ("shorter", "longer", "simpler"), conversation sharing |
| **Poe** (Quora) | Multi-bot comparison, bot creation, prompt library, cross-model switching mid-conversation, pricing transparency per message |
| **TypingMind** (Independent) | Multi-model chat, prompt library, RAG (document chat), plugins, parameter controls, conversation folders/tags, usage tracking, self-hosted option |
| **OpenRouter Chat** | Model comparison, pricing per token displayed, provider routing transparency, fallback visibility, community model rankings |
| **SillyTavern** (Open Source) | Character cards V2, world books/lorebooks, group chats (multi-character), author notes, prompt presets, message steering (impersonate/continue/narrate), swipe variants, regex scripts, UI themes |
| **Perplexity** | Source-grounded responses with inline citations, follow-up suggestions, search-first interaction model, clean source panel, shareable threads |
| **Cursor / Windsurf** | Code-aware chat with file references, inline code application, diff preview before applying, multi-file context, terminal integration |

---

## Output Format

For each finding, provide:

| Field | Description |
|-------|-------------|
| **ID** | Sequential (e.g., UX-001) |
| **Dimension** | Which review dimension (1-8) |
| **Severity** | Critical / Major / Minor / Enhancement |
| **Finding** | Clear description of the issue or gap |
| **Impact** | Who is affected and how (new users, power users, mobile users, character chat users, etc.) |
| **Recommendation** | Specific, actionable suggestion |
| **Comparable** | How other tools handle this (if applicable) |

### Severity Definitions
- **Critical**: Blocks core task completion or causes data loss (e.g., message lost on provider failure, cannot send messages, conversation corruption)
- **Major**: Significant friction in common workflows; users may abandon the feature (e.g., compare mode confusing enough to avoid, voice mode unreliable)
- **Minor**: Noticeable but workaroundable; affects polish and trust (e.g., variant count not shown, unclear model indicator)
- **Enhancement**: Not a problem today but would meaningfully improve the experience (e.g., response diffing, conversation templates)

---

## Summary Deliverables

1. **Executive Summary**: 3-5 sentence overview of the chat page's UX maturity, strengths, and most urgent gaps
2. **Top 5 Priority Fixes**: Highest-impact improvements ranked by effort-to-impact ratio
3. **Composer Audit**: Specific recommendations for the composer toolbar's information density and control organization
4. **Information Gaps Table**: Backend data available but not surfaced in UI, with priority rating (High / Medium / Low)
5. **Compare Mode Deep Dive**: Dedicated analysis of the compare mode flow from activation through model selection to continuation
6. **Competitive Gap Analysis**: Features present in 3+ comparable tools but missing here, ranked by user expectation
7. **Detailed Findings Table**: All findings in the structured format above
