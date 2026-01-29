# UX/HCI Expert Review: Media Playground Chat Interface

**Reviewer Perspective**: Principal UX/HCI Designer with 15+ years of experience designing clinical software for hospital environments, with expertise in high-cognitive-load interfaces, accessibility (WCAG 2.1 AA), error-prevention, and progressive disclosure.

**Date**: 2026-01-29

---

## Part 1: Executive Summary

The Media Playground is an ambitious, feature-rich AI chat interface that attempts to serve both casual and power users through a "Pro Mode" toggle. The interface successfully implements core chat functionality with solid technical foundations, but suffers from **feature discoverability challenges** and **cognitive overload for new users**. The single biggest opportunity for improvement is **progressive onboarding with contextual feature introduction**. Currently, the interface presents too many options simultaneously, hiding critical features (voice chat, knowledge search, MCP tools) behind a generic "+Tools" popover while cluttering the visible UI with secondary controls. Voice features are particularly buried, requiring users to discover them through trial and error rather than guided discovery. With targeted improvements to the empty state, feature grouping, and voice UX, this interface could serve its mixed audience effectively.

---

## Part 2: Heuristic Evaluation

### 1. Visibility of System Status: **Partial Pass**
- **Strengths**: Token progress bar shows context usage with color-coded warnings (green/yellow/red); draft saved indicator provides persistence feedback; voice chat states defined (connecting, listening, thinking, speaking, error)
- **Weaknesses**: Voice chat state indicators are only visible within the More Tools popover, not in the main UI; no visual indication of server connection status directly in the chat area; streaming response doesn't show estimated completion

### 2. Match Between System and Real World: **Pass**
- Uses familiar chat metaphors and terminology
- Model names and provider labels are clear
- Icons match user expectations (mic for voice, paperclip for attachments)
- Slash commands follow established patterns from other tools

### 3. User Control and Freedom: **Partial Pass**
- **Strengths**: Draft persistence allows recovery; clear chat option available; stop streaming button present; conversation branching supports exploration
- **Weaknesses**: No undo for sent messages; clearing context is destructive with no confirmation dialog; temporary chat toggle could accidentally discard work

### 4. Consistency and Standards: **Pass**
- Consistent use of Ant Design components throughout
- Button styles, iconography, and spacing are uniform
- Pro Mode and casual mode maintain visual consistency
- Keyboard shortcuts follow platform conventions (Cmd/Ctrl+Enter)

### 5. Error Prevention: **Partial Pass**
- **Strengths**: Inline validation for missing models; unsupported file type feedback on drag-and-drop; disabled states prevent invalid actions
- **Weaknesses**: No confirmation before clearing context/chat; voice chat errors only shown via notifications (could miss them); large text paste handling could confuse users

### 6. Recognition Rather Than Recall: **Fail**
- **Critical Issue**: Slash commands require memorization - no persistent reference visible
- Model favorites require prior configuration to be useful
- Voice chat trigger phrases require user to remember custom configuration
- Pro Mode features not labeled - user must remember what toggles do
- MCP tools shown as cryptic chips without explanation

### 7. Flexibility and Efficiency of Use: **Pass**
- Keyboard shortcuts available (Shift+Esc to focus, Cmd/Ctrl+Enter to send)
- Favorites system for frequently used models
- Drag-and-drop file upload alternative to button
- Slash commands for power users
- Pro Mode toggle hides complexity for casual users

### 8. Aesthetic and Minimalist Design: **Partial Pass**
- **Strengths**: Clean visual hierarchy; good use of whitespace; backdrop blur provides subtle depth
- **Weaknesses**: Pro Mode shows too many controls simultaneously; the "+Tools" popover is densely packed; token usage label in casual mode is cryptic

### 9. Help Users Recognize, Diagnose, and Recover from Errors: **Partial Pass**
- Inline error messages with shake animation are effective
- Voice chat errors shown in notifications but don't persist
- No contextual help for why "Send" might be disabled
- File upload failures logged to console but not user-visible

### 10. Help and Documentation: **Fail**
- No onboarding tour or feature introduction
- No tooltips explaining slash commands
- No documentation links within the interface
- Empty state examples are too generic to teach feature usage
- Voice chat settings have no explanatory text for advanced options (barge-in, trigger phrases)

---

## Part 3: Priority Issues (Top 10)

### 1. First-Time User Overwhelm
- **Severity**: Critical
- **Location**: PlaygroundEmpty.tsx, PlaygroundForm.tsx
- **Problem**: New users see a minimal empty state that doesn't explain the interface's capabilities. When they focus the input, they encounter a complex form with unfamiliar options (Pro Mode, tokens, models) without guidance.
- **Recommendation**: Implement a progressive onboarding flow with 3-4 steps: (1) Basic chat introduction, (2) Model selection explanation, (3) Knowledge/file upload discovery, (4) Voice features invitation. Show feature tips on first use.
- **Effort**: High

### 2. Voice Chat Buried in Popover
- **Severity**: Critical
- **Location**: moreToolsContent (lines 3238-3491), PlaygroundForm.tsx
- **Problem**: Voice chat, a major feature, is hidden inside a "+Tools" popover alongside 10+ other controls. Users must click the popover, scroll down, and parse a dense settings section to discover/enable voice.
- **Recommendation**: Surface a dedicated voice chat toggle button in the main input area. Show voice states (idle/listening/speaking) as a prominent indicator. Move detailed voice settings to a modal or settings page.
- **Effort**: Medium

### 3. Slash Commands Not Discoverable
- **Severity**: Major
- **Location**: SlashCommandMenu.tsx, PlaygroundForm.tsx
- **Problem**: Slash commands (`/search`, `/web`, `/vision`, `/generate-image`, `/model`) only appear when user types "/" - no indication they exist. New users won't discover these powerful shortcuts.
- **Recommendation**: Add a "/" button next to the input that shows available commands on click. Include a "Type / for commands" hint in the empty placeholder text.
- **Effort**: Low

### 4. More Tools Popover is Overloaded
- **Severity**: Major
- **Location**: moreToolsContent (lines 3238-3491)
- **Problem**: The popover contains: Search toggle, Web search toggle, Voice chat settings (6+ controls), Image provider, Tool choice, MCP tools, Multi-model compare link, Image upload, Document upload, Clear context. This is too much for one popover.
- **Recommendation**: Split into logical groups: (1) Search & Knowledge panel (inline), (2) Voice features (dedicated button + modal), (3) Attachments (grouped buttons), (4) Advanced/MCP settings (separate panel or settings page).
- **Effort**: Medium

### 5. No Voice State Visibility in Main UI
- **Severity**: Major
- **Location**: PlaygroundForm.tsx
- **Problem**: When voice chat is active, the only indicator is within the popover. Users can't tell at a glance if voice is listening, speaking, or errored. The `VoiceChatState` type defines clear states (`idle`, `connecting`, `listening`, `thinking`, `speaking`, `error`) but they're not surfaced.
- **Recommendation**: Add a persistent voice status indicator near the input when voice is enabled. Use distinct visual states (pulsing mic for listening, speaker icon for speaking, spinner for thinking).
- **Effort**: Medium

### 6. Context Tokens Display is Cryptic
- **Severity**: Major
- **Location**: TokenProgressBar.tsx, line 1129-1137 in PlaygroundForm.tsx
- **Problem**: In casual mode, token display shows "123 · 456/789 ctx" which is meaningless to most users. Even the tooltip requires technical understanding.
- **Recommendation**: Simplify to "Memory: 45% full" or "Room for ~500 more words". Hide technical token counts unless Pro Mode is enabled.
- **Effort**: Low

### 7. Dictation vs Voice Chat Confusion
- **Severity**: Major
- **Location**: PlaygroundForm.tsx (lines 4700-4760 for dictation, 3301-3316 for voice chat)
- **Problem**: Two separate voice features exist - Dictation (speech-to-text that fills the input) and Voice Chat (full conversational mode with TTS). They're controlled by different buttons in different locations with no clear explanation of the difference.
- **Recommendation**: Rename and explain: "Dictation" becomes "Voice typing" with clear "(fills text box)" label. "Voice Chat" becomes "Voice conversation" with "(hands-free)" label. Group them together with brief explanations.
- **Effort**: Low

### 8. Empty State Doesn't Teach Features
- **Severity**: Major
- **Location**: PlaygroundEmpty.tsx, FeatureEmptyState.tsx
- **Problem**: Empty state shows generic examples ("Ask a question, then drag in documents") but doesn't demonstrate actual features. No interactive elements, no feature cards, no sample prompts to click.
- **Recommendation**: Add clickable example prompts that populate the input. Show feature cards for Voice, Knowledge Search, and Compare Mode. Include a "Take a tour" link.
- **Effort**: Medium

### 9. Model Selection Requires Pre-knowledge
- **Severity**: Minor
- **Location**: modelDropdownMenuItems (lines 575-738)
- **Problem**: Model selector shows raw model IDs grouped by provider. New users don't know which model to pick. No recommendations, no descriptions of model strengths/weaknesses.
- **Recommendation**: Add "(Recommended)" tag to a default model. Include brief capability hints ("Best for code", "Most creative", "Fastest"). Show a "Help me choose" option linking to documentation.
- **Effort**: Medium

### 10. Keyboard Shortcut Discoverability
- **Severity**: Minor
- **Location**: Throughout PlaygroundForm.tsx
- **Problem**: Shortcuts (Shift+Esc, Cmd/Ctrl+Enter) are only documented in code. Users who would benefit most from them don't know they exist.
- **Recommendation**: Add keyboard shortcut hints to tooltips (e.g., Send button tooltip: "Send message (Cmd+Enter)"). Include a "Keyboard shortcuts" reference accessible via "?" key or in settings.
- **Effort**: Low

---

## Part 4: Focus Area Deep-Dives

### A. First-Time User Experience

**60-Second Walkthrough (Current State)**:

0:00 - User lands on Playground page. Sees an empty state card with a chat icon, title "Start a new chat", and three bullet-point examples. Two buttons: "Start chatting" and "Quick ingest".

0:10 - User clicks "Start chatting". Focus moves to textarea. User sees:
- An input area with placeholder "Type a message..."
- Below: A progress bar, model selector showing "API / model", and a Send dropdown button
- If Pro Mode: Additional rows of controls appear (persistence toggle, parameter presets, search button, character select, dictation, chat settings, +Tools)

0:20 - User is confused. What model should they select? What do all these controls do? They try typing a message.

0:30 - User types "Hello" and clicks Send. Gets error: "Select a model to continue" (if no default). User must now figure out the model dropdown.

0:45 - User opens model dropdown. Sees a list of unfamiliar model names grouped by provider. No guidance on which to pick. They randomly select one.

0:55 - User clicks Send again. Now they need server connection. If not connected, they see "Connect to your tldw server to start chatting" but don't know how.

**Friction Points**:
1. Empty state examples don't mention model selection requirement
2. No default model pre-selected
3. No explanation of server connection requirement
4. Pro Mode controls appear without explanation
5. Voice features completely invisible
6. Knowledge search toggle not discoverable

**Recommended Onboarding Improvements**:

1. **Pre-flight Check**: Before first message, show a setup checklist:
   - [ ] Server connected (with "Connect" link)
   - [ ] Model selected (with quick picker)
   - [ ] Ready to chat!

2. **Feature Spotlights**: On first visit, highlight one feature at a time with dismissible tooltips:
   - "Select a model to start" (pointing to model selector)
   - "Drag files here to discuss them" (pointing to input area)
   - "Use voice for hands-free chat" (pointing to voice button - once visible)

3. **Smart Empty State**: Replace generic examples with:
   - Clickable example prompts that fill the input
   - Feature discovery cards: "Try Voice Chat", "Search Your Knowledge", "Compare Models"
   - A "New here? Take a quick tour" link

4. **Intelligent Defaults**:
   - Pre-select a recommended model (if available)
   - Show connection status inline with actionable "Connect" button
   - Start in casual mode with option to "Unlock Pro features"

---

### B. Voice Features UX Deep-Dive

**Current Implementation Analysis**:

The voice system has two distinct features:

1. **Dictation** (Browser/Server speech-to-text):
   - Located: In Pro Mode controls, inline with other buttons (lines 4700-4760)
   - Trigger: Click mic button
   - Output: Fills textarea with transcribed text
   - State feedback: Button border color changes when active
   - Settings: STT model/language in global settings

2. **Voice Chat** (Full conversational mode):
   - Located: Inside "+Tools" popover (lines 3301-3322)
   - Trigger: Click "Voice chat: Idle" button in popover
   - Output: Real-time conversation with TTS responses
   - States: idle, connecting, listening, thinking, speaking, error
   - Settings: Within popover - model, pause duration, trigger phrases, TTS mode, auto-resume, barge-in

**Discoverability Issues**:
- Voice chat is 3 clicks away: Click "+Tools" > Scroll > Click "Voice chat: Idle"
- No visual indication that voice chat exists until popover is opened
- When active, state only visible inside popover
- Users must keep popover open to see voice status

**Learnability Issues**:
- "Barge-in" is jargon - what does it mean?
- "Trigger phrases" not explained - what are they for?
- "TTS mode: Stream vs Full" - no explanation of difference
- "Auto resume" - resume what, when?
- Relationship between Dictation and Voice Chat unclear - can they be used together?

**Accessibility Concerns**:
- Voice chat controls have no screen reader descriptions for states
- Focus doesn't move to voice indicator when activated
- No audio feedback for state changes (ironic for a voice feature)
- Trigger phrase input has no example format guidance

**Recommendations**:

1. **Surface Voice Toggle**:
   ```
   [Input area] [Voice Chat 🎤] [Send]
   ```
   Add a prominent voice toggle button next to Send. When active, show state inline:
   ```
   [Input area] [🎤 Listening...] [Send]
   ```

2. **State Indicator**:
   Create a persistent voice status component showing:
   - Idle: "Voice ready"
   - Connecting: Animated spinner
   - Listening: Pulsing mic with "Listening..."
   - Thinking: Spinner with "Processing..."
   - Speaking: Speaker icon with audio wave animation
   - Error: Red indicator with error message

3. **Settings Refactor**:
   Move voice settings to a dedicated modal triggered by a settings icon next to the voice toggle:
   - Rename "Barge-in" to "Interrupt while speaking" with explanation
   - Rename "Trigger phrases" to "Wake words" with example
   - Explain TTS modes: "Stream: Start speaking immediately" vs "Full: Wait for complete response"
   - Explain "Auto resume": "Automatically start listening again after response"

4. **Contextual Help**:
   Add (?) icons next to voice settings that expand inline help text.

5. **Unified Voice Entry Point**:
   Create a "Voice" button that opens a voice mode selector:
   - "Voice typing" (dictation) - "Transcribes your speech into the text box"
   - "Voice conversation" - "Hands-free chat with spoken responses"
   Both options show relevant settings inline.

---

## Part 5: Quick Wins (Low Effort, High Impact)

1. **Add "/" hint to placeholder text**
   - Current: "Type a message..."
   - Proposed: "Type a message... (/ for commands)"
   - Effort: 5 minutes
   - Impact: Immediate slash command discoverability

2. **Simplify token display in casual mode**
   - Current: "123 · 456/789 ctx"
   - Proposed: "Memory: 45% full"
   - Effort: 30 minutes
   - Impact: Removes cognitive load for non-technical users

3. **Add keyboard hint to Send tooltip**
   - Current tooltip: "Send message"
   - Proposed: "Send message (⌘+Enter)"
   - Effort: 5 minutes
   - Impact: Power user efficiency

4. **Pre-select recommended model**
   - If one model is starred as favorite, default to it
   - If no favorites, show "(Select a model)" with warning color
   - Effort: 15 minutes
   - Impact: Reduces first-use friction

5. **Add confirmation to "Clear context"**
   - Show "Clear all messages? This can't be undone" dialog
   - Effort: 15 minutes
   - Impact: Prevents accidental data loss

6. **Rename voice feature labels**
   - "Barge-in" → "Interrupt while speaking"
   - "Auto resume" → "Continue listening after response"
   - Effort: 10 minutes
   - Impact: Immediate clarity

7. **Add voice state to window title**
   - When voice is active, set title: "🎤 Listening - Media Playground"
   - Effort: 10 minutes
   - Impact: Voice state visible even when tab is in background

---

## Part 6: Recommendations Matrix

| Recommendation | Impact | Effort | Priority |
|----------------|--------|--------|----------|
| Add "/" hint to placeholder | High | Low | 1 |
| Simplify token display (casual mode) | High | Low | 2 |
| Add keyboard hints to tooltips | Medium | Low | 3 |
| Pre-select recommended model | High | Low | 4 |
| Add confirmation to "Clear context" | Medium | Low | 5 |
| Rename voice settings labels | Medium | Low | 6 |
| Surface voice toggle button in main UI | High | Medium | 7 |
| Add voice state indicator | High | Medium | 8 |
| Split "+Tools" popover into logical groups | High | Medium | 9 |
| Add clickable example prompts to empty state | High | Medium | 10 |
| Create voice mode selector modal | Medium | Medium | 11 |
| Add onboarding tour | High | High | 12 |
| Add model recommendations/descriptions | Medium | Medium | 13 |
| Implement progressive feature introduction | High | High | 14 |

---

## Part 7: Narrative Summary

The Media Playground represents an ambitious attempt to create a comprehensive AI chat interface that serves both casual users who want simple conversations and power users who need fine-grained control over models, knowledge retrieval, and voice interaction. The technical implementation is solid, with well-structured state management, proper accessibility attributes on most elements, and thoughtful features like draft persistence and conversation branching.

However, the interface currently suffers from a common problem in feature-rich applications: **feature accretion without corresponding UX investment**. Voice chat, knowledge search, MCP tools, compare mode, parameter presets, and system prompt templates have all been added, but they're stuffed into a single "+Tools" popover that requires scrolling and hunting. The Pro Mode toggle provides some relief by hiding advanced controls, but the hidden controls are often the most powerful features that could differentiate this tool from simpler competitors.

The most critical gap is the first-time user experience. A new user landing on this page faces a minimal empty state that doesn't explain capabilities, a complex input form that requires model selection without guidance, and powerful features (voice, knowledge search) that are invisible until discovered by accident. The current empty state examples ("Ask a question, then drag in documents") assume users already understand the interface paradigm.

To achieve professional UX standards, the Media Playground needs three strategic investments:

1. **Progressive disclosure with intentional discovery**: Rather than hiding features, guide users to them. Implement an onboarding flow that introduces voice, knowledge search, and advanced features at appropriate moments. Add contextual tips that appear when users might benefit from a feature they haven't used.

2. **Information architecture refactoring**: Split the monolithic "+Tools" popover into logical groupings. Surface voice as a first-class feature with its own button and state indicator. Move advanced settings to dedicated panels or a settings page where they can be properly explained.

3. **User-centered language**: Replace technical jargon (tokens, context window, barge-in, MCP tools) with user-centered language when not in Pro Mode. Let power users opt into technical detail.

With these improvements, the Media Playground could become an exemplary interface that successfully serves its mixed audience while showcasing the full power of its feature set.
