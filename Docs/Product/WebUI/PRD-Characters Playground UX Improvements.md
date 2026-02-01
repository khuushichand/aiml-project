PRD: Characters Playground UX Improvements

 Document Info

 - Version: 1.0
 - Date: 2026-01-29
 - Status: Draft
 - Owner: UX/Engineering

 ---
 1. Executive Summary

 This PRD defines improvements to the Characters playground page based on a comprehensive UX/HCI review. The improvements span 17 discrete features organized into 5 epics, targeting task efficiency, error
 recovery, cognitive load reduction, and accessibility—with special consideration for high-cognitive-load environments like healthcare.

 Overall Heuristic Score: 3.8/5 → Target: 4.5/5

 ---
 2. Goals & Success Metrics

 Primary Goals

 1. Reduce average clicks per common workflow by 40%
 2. Eliminate data loss from interruptions
 3. Achieve WCAG 2.1 AA compliance
 4. Improve first-time user success rate

 Key Metrics
 ┌───────────────────────────────┬─────────┬────────────┐
 │            Metric             │ Current │   Target   │
 ├───────────────────────────────┼─────────┼────────────┤
 │ Clicks to create character    │ 8-12    │ 5-7        │
 ├───────────────────────────────┼─────────┼────────────┤
 │ Form abandonment rate         │ Unknown │ <15%       │
 ├───────────────────────────────┼─────────┼────────────┤
 │ Time to find & edit character │ ~15s    │ <8s        │
 ├───────────────────────────────┼─────────┼────────────┤
 │ Accessibility audit issues    │ TBD     │ 0 critical │
 └───────────────────────────────┴─────────┴────────────┘
 ---
 3. Epics & User Stories

 Epic 1: Form Experience Improvements

 Goal: Reduce cognitive load and prevent data loss in character creation/editing

 1.1 [CRITICAL] Reorder Form Fields (C1)

 Priority: P0 | Complexity: Low | Estimate: 2 hours

 Current State:
 Form order: Name → Description → Avatar → Tags → Greeting → System Prompt (required)

 Proposed State:
 Form order: Name → System Prompt (required) → Greeting → Description → Tags → Avatar

 User Story:
 As a user creating a character, I want required fields near the top so I don't scroll past optional fields to complete the form.

 Acceptance Criteria:
 - System prompt field appears immediately after name
 - Required indicator (*) is visible without scrolling
 - Tab order matches visual order
 - Edit form uses same field order as create form

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx (lines 1900-2320, 2366-2700)

 ---
 1.2 [HIGH] Implement Form Autosave Draft (H4)

 Priority: P1 | Complexity: Medium | Estimate: 8 hours

 Current State:
 Unsaved changes prompt on close, but no recovery if browser crashes or user navigates away.

 Proposed State:
 Auto-save draft to localStorage every 30 seconds; offer recovery on next session.

 User Story:
 As a user who gets interrupted frequently, I want my in-progress character form to be saved automatically so I don't lose my work.

 Acceptance Criteria:
 - Draft saves to localStorage every 30 seconds when form is dirty
 - On page load, check for orphaned drafts
 - Show "Resume editing [name]?" banner if draft exists
 - Clear draft on successful submit
 - Draft includes timestamp for staleness check (expire after 7 days)

 Technical Design:
 interface CharacterDraft {
   formData: Record<string, any>
   formType: 'create' | 'edit'
   editId?: string
   savedAt: number
 }
 const DRAFT_KEY = 'character-form-draft'
 const DRAFT_EXPIRY_MS = 7 * 24 * 60 * 60 * 1000

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx
 - New: apps/packages/ui/src/hooks/useFormDraft.ts

 ---
 1.3 [MEDIUM] Add Character Templates (M4)

 Priority: P2 | Complexity: Medium | Estimate: 6 hours

 Current State:
 Users must create from scratch or duplicate existing characters.

 Proposed State:
 Offer 5 built-in templates: Writing Assistant, Teacher, Research Helper, Code Reviewer, Creative Partner.

 User Story:
 As a new user, I want to start from a template so I can quickly create a useful character without understanding all the fields.

 Acceptance Criteria:
 - "Start from template" option in create modal
 - 5 pre-defined templates with name, description, system_prompt
 - Template selection shows preview before applying
 - Templates are customizable after selection

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx
 - New: apps/packages/ui/src/data/character-templates.ts

 ---
 1.4 [LOW] Show Preview by Default (Quick Win)

 Priority: P3 | Complexity: Low | Estimate: 15 minutes

 Change: Set showCreatePreview initial state to true in Manager.tsx:202

 ---
 Epic 2: Error Prevention & Recovery

 Goal: Prevent data loss and improve error messaging

 2.1 [CRITICAL] Add Undo for Character Deletion (C2)

 Priority: P0 | Complexity: Medium | Estimate: 8 hours

 Current State:
 Confirmation dialog → Permanent delete

 Proposed State:
 Soft delete with "Undo" toast for 10 seconds

 User Story:
 As a user who accidentally deleted a character, I want to undo the deletion within a short window so I don't lose my work.

 Acceptance Criteria:
 - Delete action shows toast with "Undo" button
 - Toast visible for 10 seconds
 - Undo restores character to list immediately
 - After 10 seconds, deletion is finalized
 - If user navigates away, deletion is finalized

 Technical Design:
 - Use optimistic UI: remove from list immediately
 - Store deleted character in component state
 - Show toast with "Undo" button for 10 seconds
 - If undo clicked: call POST /characters/{id}/restore endpoint
 - If timeout expires: no action needed (already soft-deleted)

 Files to Modify:

 Backend (new restore endpoint):
 - tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py - add restore_character_card()
 - tldw_Server_API/app/core/Character_Chat/modules/character_db.py - add facade
 - tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py - add POST /{id}/restore

 Frontend:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx
 - apps/packages/ui/src/services/tldw/TldwApiClient.ts - add restoreCharacter() method

 ---
 2.2 [HIGH] Improve AI Generation Error Messages (H2)

 Priority: P1 | Complexity: Low | Estimate: 3 hours

 Current State:
 Generic "Generation failed. Try again." for all errors.

 Proposed State:
 Specific error messages with actionable guidance:
 - Timeout: "Generation took too long. Try a simpler concept or check your connection."
 - Auth: "Model access denied. Check your API key in settings."
 - Rate limit: "Too many requests. Please wait 30 seconds."
 - Model unavailable: "Selected model is unavailable. Try a different model."

 User Story:
 As a user whose generation failed, I want to know why it failed and what I can do about it.

 Acceptance Criteria:
 - Map all error codes from CharacterGenerationService.ts:107-140 to user messages
 - Include suggested action in each error message
 - Add "Try again" button that clears error and refocuses input

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/GenerateCharacterPanel.tsx
 - apps/packages/ui/src/services/character-generation/CharacterGenerationService.ts

 ---
 2.3 [HIGH] Visual Loading Progress for AI Generation (H5)

 Priority: P1 | Complexity: Medium | Estimate: 6 hours

 Current State:
 Simple spinner with "Generating..." text.

 Proposed State:
 Step indicator: "Analyzing concept..." → "Generating fields..." → "Finalizing..."

 User Story:
 As a user waiting for generation, I want to see progress so I know the system is working.

 Acceptance Criteria:
 - Show 3-step progress indicator during generation
 - Each step has descriptive text
 - Progress updates based on actual backend status (if available) or time-based fallback
 - Cancel button remains visible at all steps

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/GenerateCharacterPanel.tsx
 - apps/packages/ui/src/services/character-generation/CharacterGenerationService.ts

 ---
 Epic 3: Task Efficiency

 Goal: Reduce clicks and time for common workflows

 3.1 [HIGH] Add Keyboard Shortcuts (H1)

 Priority: P1 | Complexity: Low | Estimate: 4 hours

 Shortcuts:
 ┌────────┬────────────────────────────────────┐
 │  Key   │               Action               │
 ├────────┼────────────────────────────────────┤
 │ N      │ New character (when no modal open) │
 ├────────┼────────────────────────────────────┤
 │ E      │ Edit selected/hovered character    │
 ├────────┼────────────────────────────────────┤
 │ /      │ Focus search input                 │
 ├────────┼────────────────────────────────────┤
 │ Escape │ Close modal / Clear selection      │
 ├────────┼────────────────────────────────────┤
 │ G T    │ Switch to table view               │
 ├────────┼────────────────────────────────────┤
 │ G G    │ Switch to gallery view             │
 └────────┴────────────────────────────────────┘
 User Story:
 As a power user, I want keyboard shortcuts so I can manage characters without using the mouse.

 Acceptance Criteria:
 - All shortcuts work when no modal is open
 - Shortcuts disabled when typing in input fields
 - Shortcuts visible in tooltip or help panel
 - Escape always closes current modal

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx
 - New: apps/packages/ui/src/hooks/useCharacterShortcuts.ts

 ---
 3.2 [HIGH] Add Conversation Count Badge (H3)

 Priority: P1 | Complexity: Medium | Estimate: 6 hours

 Current State:
 Must open separate modal to see if conversations exist.

 Proposed State:
 Badge on gallery card and table row showing conversation count.

 User Story:
 As a user, I want to see which characters have conversations so I can quickly resume.

 Acceptance Criteria:
 - Badge shows count (e.g., "3") if conversations > 0
 - Badge visible in both table and gallery views
 - Clicking badge opens conversations modal
 - Count updates after resuming/creating conversations

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/CharacterGalleryCard.tsx
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx (table columns)
 - May require API endpoint to get conversation counts efficiently

 ---
 3.3 [MEDIUM] Inline Editing for Table View (M1)

 Priority: P2 | Complexity: Medium | Estimate: 8 hours

 Current State:
 Must open full modal for any edit.

 Proposed State:
 Double-click name or description to edit inline.

 User Story:
 As a user making quick corrections, I want to edit name/description inline without opening a modal.

 Acceptance Criteria:
 - Double-click name cell enters edit mode
 - Enter saves, Escape cancels
 - Validation shows inline error
 - Focus returns to cell after save

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx (table columns)

 ---
 3.4 [MEDIUM] Bulk Operations (M5)

 Priority: P2 | Complexity: High | Estimate: 16 hours

 Operations:
 - Bulk delete (with confirmation)
 - Bulk add tag
 - Bulk export as JSON

 User Story:
 As a user with many characters, I want to perform actions on multiple characters at once.

 Acceptance Criteria:
 - Checkbox column in table view
 - "Select all" header checkbox
 - Bulk action toolbar appears when items selected
 - Actions: Delete, Add Tag, Export
 - Clear selection after action completes

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx

 ---
 3.5 [LOW] Add Character Export (L1)

 Priority: P3 | Complexity: Low | Estimate: 4 hours

 Export formats: JSON, PNG (with embedded metadata)

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/CharacterPreviewPopup.tsx
 - New: apps/packages/ui/src/utils/character-export.ts

 ---
 3.6 [LOW] Persist Sort Preference (L2)

 Priority: P3 | Complexity: Low | Estimate: 1 hour

 Save table sort column and direction to localStorage.

 ---
 Epic 4: Search & Discovery

 Goal: Help users find characters faster

 4.1 [MEDIUM] Improve Tag Input UX (M3)

 Priority: P2 | Complexity: Low-Medium | Estimate: 4 hours

 Proposed Changes:
 - Show popular tags as suggestion chips
 - Display tag usage counts
 - Autocomplete from existing tags

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx (tag Select components)

 ---
 4.2 [LOW] Clear All Filters Button in Toolbar (Quick Win)

 Priority: P3 | Complexity: Low | Estimate: 30 minutes

 Current State:
 "Clear filters" button only shows in empty state.

 Proposed State:
 Always show "Clear" button next to filter controls when filters are active.

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx (lines 964-1036)

 ---
 Epic 5: Accessibility & Polish

 Goal: Achieve WCAG 2.1 AA compliance and polish interactions

 5.1 [HIGH] Screen Reader Announcements for AI Generation

 Priority: P1 | Complexity: Low | Estimate: 2 hours

 Current State:
 No live region updates during generation.

 Proposed State:
 - Add aria-busy="true" during generation
 - Announce: "Generating character..." → "Character generated. Review before applying."

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/GenerateCharacterPanel.tsx

 ---
 5.2 [MEDIUM] Duplicate Confirmation Toast (M2)

 Priority: P2 | Complexity: Low | Estimate: 1 hour

 Current State:
 Duplicate immediately opens form.

 Proposed State:
 Show toast: "Duplicated [name]. Editing copy."

 Files to Modify:
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx

 ---
 5.3 [LOW] Dark Mode Contrast Audit (L3)

 Priority: P3 | Complexity: Low | Estimate: 3 hours

 Audit all .text-text-subtle usages for WCAG AA compliance in dark mode.

 ---
 4. Implementation Phases

 Phase 1: Quick Wins (Week 1)
 ┌──────────────────────────────────┬──────────┬───────┐
 │               Item               │ Estimate │ Owner │
 ├──────────────────────────────────┼──────────┼───────┤
 │ Reorder form fields (C1)         │ 2h       │       │
 ├──────────────────────────────────┼──────────┼───────┤
 │ Show preview by default          │ 15m      │       │
 ├──────────────────────────────────┼──────────┼───────┤
 │ Keyboard shortcut for search (/) │ 30m      │       │
 ├──────────────────────────────────┼──────────┼───────┤
 │ Clear all filters button         │ 30m      │       │
 ├──────────────────────────────────┼──────────┼───────┤
 │ Total                            │ ~3.5h    │       │
 └──────────────────────────────────┴──────────┴───────┘
 Phase 2: Critical & High Priority (Weeks 2-3)
 ┌───────────────────────────────┬──────────┬───────┐
 │             Item              │ Estimate │ Owner │
 ├───────────────────────────────┼──────────┼───────┤
 │ Undo for deletion (C2)        │ 8h       │       │
 ├───────────────────────────────┼──────────┼───────┤
 │ Form autosave (H4)            │ 8h       │       │
 ├───────────────────────────────┼──────────┼───────┤
 │ Keyboard shortcuts (H1)       │ 4h       │       │
 ├───────────────────────────────┼──────────┼───────┤
 │ AI error messages (H2)        │ 3h       │       │
 ├───────────────────────────────┼──────────┼───────┤
 │ Generation progress (H5)      │ 6h       │       │
 ├───────────────────────────────┼──────────┼───────┤
 │ Conversation count badge (H3) │ 6h       │       │
 ├───────────────────────────────┼──────────┼───────┤
 │ Screen reader announcements   │ 2h       │       │
 ├───────────────────────────────┼──────────┼───────┤
 │ Total                         │ ~37h     │       │
 └───────────────────────────────┴──────────┴───────┘
 Phase 3: Medium Priority (Weeks 4-5)
 ┌─────────────────────────────┬──────────┬───────┐
 │            Item             │ Estimate │ Owner │
 ├─────────────────────────────┼──────────┼───────┤
 │ Character templates (M4)    │ 6h       │       │
 ├─────────────────────────────┼──────────┼───────┤
 │ Inline editing (M1)         │ 8h       │       │
 ├─────────────────────────────┼──────────┼───────┤
 │ Tag input improvements (M3) │ 4h       │       │
 ├─────────────────────────────┼──────────┼───────┤
 │ Duplicate toast (M2)        │ 1h       │       │
 ├─────────────────────────────┼──────────┼───────┤
 │ Bulk operations (M5)        │ 16h      │       │
 ├─────────────────────────────┼──────────┼───────┤
 │ Total                       │ ~35h     │       │
 └─────────────────────────────┴──────────┴───────┘
 Phase 4: Low Priority (Week 6+)
 ┌───────────────────────┬──────────┬───────┐
 │         Item          │ Estimate │ Owner │
 ├───────────────────────┼──────────┼───────┤
 │ Character export (L1) │ 4h       │       │
 ├───────────────────────┼──────────┼───────┤
 │ Sort persistence (L2) │ 1h       │       │
 ├───────────────────────┼──────────┼───────┤
 │ Dark mode audit (L3)  │ 3h       │       │
 ├───────────────────────┼──────────┼───────┤
 │ Total                 │ ~8h      │       │
 └───────────────────────┴──────────┴───────┘
 ---
 5. Technical Considerations

 Files Impacted

 Frontend (Primary):
 - apps/packages/ui/src/components/Option/Characters/Manager.tsx (most changes)
 - apps/packages/ui/src/components/Option/Characters/GenerateCharacterPanel.tsx
 - apps/packages/ui/src/components/Option/Characters/CharacterGalleryCard.tsx
 - apps/packages/ui/src/components/Option/Characters/CharacterPreviewPopup.tsx
 - apps/packages/ui/src/services/tldw/TldwApiClient.ts (add restoreCharacter)

 Frontend (New Files):
 - apps/packages/ui/src/hooks/useFormDraft.ts
 - apps/packages/ui/src/hooks/useCharacterShortcuts.ts
 - apps/packages/ui/src/data/character-templates.ts
 - apps/packages/ui/src/utils/character-export.ts

 Backend (for C2 - Undo Delete):
 - tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py
 - tldw_Server_API/app/core/Character_Chat/modules/character_db.py
 - tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py
 - tldw_Server_API/app/api/v1/schemas/character_schemas.py

 Backend Dependencies

 - C2 (Undo delete): Requires new POST /characters/{id}/restore endpoint (soft-delete exists, restore does not)
 - H3 (Conversation count): May need batch endpoint or can use existing /api/v1/chats?character_id=X

 Testing Requirements

 - Unit tests for new hooks
 - E2E tests for keyboard shortcuts
 - Accessibility audit with axe-core
 - Update existing characters-ux.spec.ts and characters-a11y-snapshot.spec.ts

 ---
 6. Verification Plan

 Manual Testing Checklist

 - Create character with new field order
 - Trigger autosave by waiting 30 seconds
 - Close browser, reopen, verify draft recovery
 - Delete character, click undo within 10 seconds
 - Test all keyboard shortcuts
 - Verify screen reader announces generation progress
 - Test on mobile viewport

 Automated Tests

 - Run bun run test:e2e for existing tests
 - Run accessibility snapshot test
 - Run Lighthouse accessibility audit

 ---
 7. Resolved Questions

 1. Backend soft-delete: ✅ Soft-delete IS implemented (sets deleted = 1). However, restore endpoint does NOT exist - needs to be added:
   - Database: restore_character_card() in ChaChaNotes_DB.py
   - API: POST /{character_id}/restore in characters_endpoint.py
   - See backend files below for implementation pattern
 2. Conversation counts: TBD - may need new endpoint or can batch-fetch from existing /api/v1/chats with character_id filter
 3. Template content: ✅ Generate with AI during implementation
 4. Analytics: ✅ No tracking - skip for privacy reasons

 8. Backend Work Required

 For C2 (Undo Deletion) - New Restore Endpoint

 Files to modify:

 1. tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py
   - Add restore_character_card(character_id, expected_version) method
   - Pattern: Set deleted = 0, update last_modified, increment version
 2. tldw_Server_API/app/core/Character_Chat/modules/character_db.py
   - Add restore_character_from_db() facade function
 3. tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py
   - Add POST /{character_id}/restore endpoint
   - Return RestoreResponse with success message
 4. tldw_Server_API/app/api/v1/schemas/character_schemas.py
   - Add RestoreResponse model (or reuse DeletionResponse)

 ---
 8. Appendix: Full Improvement List
 ┌──────┬─────────────────────────────┬──────────┬────────────┬───────┐
 │  ID  │            Name             │ Priority │ Complexity │ Phase │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ C1   │ Reorder form fields         │ P0       │ Low        │ 1     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ C2   │ Undo for deletion           │ P0       │ Medium     │ 2     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ H1   │ Keyboard shortcuts          │ P1       │ Low        │ 2     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ H2   │ AI error messages           │ P1       │ Low        │ 2     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ H3   │ Conversation count badge    │ P1       │ Medium     │ 2     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ H4   │ Form autosave               │ P1       │ Medium     │ 2     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ H5   │ Generation progress         │ P1       │ Medium     │ 2     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ M1   │ Inline editing              │ P2       │ Medium     │ 3     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ M2   │ Duplicate toast             │ P2       │ Low        │ 3     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ M3   │ Tag input UX                │ P2       │ Low-Medium │ 3     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ M4   │ Character templates         │ P2       │ Medium     │ 3     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ M5   │ Bulk operations             │ P2       │ High       │ 3     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ L1   │ Character export            │ P3       │ Low        │ 4     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ L2   │ Sort persistence            │ P3       │ Low        │ 4     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ L3   │ Dark mode audit             │ P3       │ Low        │ 4     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ QW1  │ Preview by default          │ P3       │ Low        │ 1     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ QW2  │ Search shortcut             │ P3       │ Low        │ 1     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ QW3  │ Clear filters button        │ P3       │ Low        │ 1     │
 ├──────┼─────────────────────────────┼──────────┼────────────┼───────┤
 │ A11Y │ Screen reader announcements │ P1       │ Low        │ 2     │
 └──────┴─────────────────────────────┴──────────┴────────────┴───────┘