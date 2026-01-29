# Implementation Plan: Characters Playground UX Improvements

## Overview
Implementing 17 discrete UX improvements organized into 5 epics based on PRD.

## Stage 1: Quick Wins (Phase 1)
**Goal**: Implement low-effort, high-impact improvements
**Status**: Complete ✓

### Tasks:
- [x] C1: Reorder form fields (2h)
- [x] QW1: Show preview by default (15m)
- [x] QW2: Keyboard shortcut for search `/` (30m)
- [x] QW3: Clear all filters button (30m)

**Success Criteria**:
- Form fields ordered: Name → System Prompt → Greeting → Description → Tags → Avatar ✓
- Preview panel visible by default ✓
- `/` key focuses search input ✓
- Clear filters button visible in toolbar when filters active ✓

---

## Stage 2: Critical & High Priority (Phase 2)
**Goal**: Implement core reliability and efficiency features
**Status**: Not Started

### Tasks:
- [ ] C2: Undo for character deletion (8h) - Backend + Frontend
- [ ] H4: Form autosave draft (8h)
- [ ] H1: Keyboard shortcuts (4h)
- [ ] H2: AI error messages (3h)
- [ ] H5: Generation progress indicator (6h)
- [ ] H3: Conversation count badge (6h)
- [ ] A11Y: Screen reader announcements (2h)

**Success Criteria**:
- Deleted characters can be restored within 10 seconds
- Form drafts persist across browser sessions
- Full keyboard navigation support
- Specific, actionable error messages
- Visual progress during AI generation

---

## Stage 3: Medium Priority (Phase 3)
**Goal**: Enhanced functionality and polish
**Status**: Not Started

### Tasks:
- [ ] M4: Character templates (6h)
- [ ] M1: Inline editing (8h)
- [ ] M3: Tag input improvements (4h)
- [ ] M2: Duplicate toast (1h)
- [ ] M5: Bulk operations (16h)

---

## Stage 4: Low Priority (Phase 4)
**Goal**: Additional features and polish
**Status**: Not Started

### Tasks:
- [ ] L1: Character export (4h)
- [ ] L2: Sort persistence (1h)
- [ ] L3: Dark mode audit (3h)

---

## Files to Create:
- `apps/packages/ui/src/hooks/useFormDraft.ts`
- `apps/packages/ui/src/hooks/useCharacterShortcuts.ts`
- `apps/packages/ui/src/data/character-templates.ts`
- `apps/packages/ui/src/utils/character-export.ts`

## Files to Modify:
### Frontend:
- `apps/packages/ui/src/components/Option/Characters/Manager.tsx`
- `apps/packages/ui/src/components/Option/Characters/GenerateCharacterPanel.tsx`
- `apps/packages/ui/src/components/Option/Characters/CharacterGalleryCard.tsx`
- `apps/packages/ui/src/components/Option/Characters/CharacterPreviewPopup.tsx`
- `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

### Backend (for C2):
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- `tldw_Server_API/app/core/Character_Chat/modules/character_db.py`
- `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
- `tldw_Server_API/app/api/v1/schemas/character_schemas.py`
