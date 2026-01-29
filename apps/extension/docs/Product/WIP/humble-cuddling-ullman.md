# Data Tables Feature - Table Editing Enhancement

## Overview

**Status:** Base feature implemented. Now adding table editing capabilities.

Add full editing support to Data Tables:
1. **Cell editing** - Click to edit individual cells in preview/detail views
2. **Row management** - Add/delete rows
3. **Column management** - Add/remove/reorder columns
4. **Inline save** - Save edits back to the server

---

## Existing Infrastructure

| Asset | Location | Notes |
|-------|----------|-------|
| **@dnd-kit** | `package.json` | Already installed for Kanban - use for column reordering |
| **Ant Design Table** | Throughout | No built-in editing, but supports custom cell renders |
| **Zustand Store** | `src/store/data-tables.tsx` | Already has column hints management |
| **DataTable types** | `src/types/data-tables.ts` | Column types defined (text, number, date, url, boolean, currency) |
| **SourceFormModal pattern** | `src/components/Option/Watchlists/` | Good pattern for modal-based editing |

---

## Implementation Design

### Editing Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EditableDataTable Component                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Toolbar: [+ Add Row] [+ Add Column] [Save] [Discard]    │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Column Headers (draggable with @dnd-kit)                │    │
│  │ [⋮⋮ Name ▾] [⋮⋮ Type ▾] [⋮⋮ Value ▾] ... [×]          │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Editable Cells (click to edit, blur to save)            │    │
│  │ ┌──────┐ ┌──────┐ ┌──────┐                 ┌─────────┐  │    │
│  │ │ cell │ │ cell │ │ cell │      ...        │ [🗑️] │  │    │
│  │ └──────┘ └──────┘ └──────┘                 └─────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### State Flow

```
User Action → Local State Update → Dirty Flag Set → Save Button Enabled
     ↓
[Save] Click → API Call → Server Persist → Dirty Flag Clear → Success Toast
```

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `src/components/Option/DataTables/EditableDataTable.tsx` | Main editable table component |
| `src/components/Option/DataTables/EditableCell.tsx` | Single cell editor with type-aware inputs |
| `src/components/Option/DataTables/ColumnManager.tsx` | Column add/remove/reorder UI |
| `src/components/Option/DataTables/AddColumnModal.tsx` | Modal for adding new columns |

### Files to Modify

| File | Changes |
|------|---------|
| `src/types/data-tables.ts` | Add editing state types |
| `src/store/data-tables.tsx` | Add editing actions (updateCell, addRow, deleteRow, etc.) |
| `src/components/Option/DataTables/TablePreview.tsx` | Replace static table with EditableDataTable |
| `src/components/Option/DataTables/TableDetailModal.tsx` | Replace static table with EditableDataTable |
| `src/services/tldw/TldwApiClient.ts` | Add `saveDataTableContent()` method |

---

## Implementation Steps

### Step 1: Update Types (`src/types/data-tables.ts`)

Add these types:
```typescript
// Editing state for a table
export interface TableEditingState {
  editingCellKey: string | null  // "rowIndex-columnId" format
  isDirty: boolean               // Has unsaved changes
  pendingChanges: TableChange[]  // Track all changes
}

// Individual change record
export interface TableChange {
  type: 'cell' | 'row_add' | 'row_delete' | 'column_add' | 'column_delete' | 'column_reorder'
  rowIndex?: number
  columnId?: string
  oldValue?: any
  newValue?: any
  timestamp: number
}

// Row with stable ID for editing
export interface DataTableRow {
  _id: string  // Stable row identifier
  [key: string]: any
}
```

### Step 2: Update Store (`src/store/data-tables.tsx`)

Add editing state and actions:
```typescript
// State additions
editingTable: DataTable | null      // Working copy for editing
editingState: TableEditingState
originalTable: DataTable | null     // Snapshot for discard/diff

// New actions
startEditing: (table: DataTable) => void
updateCell: (rowIndex: number, columnId: string, value: any) => void
addRow: (afterIndex?: number) => void
deleteRow: (rowIndex: number) => void
addColumn: (column: DataTableColumn, afterColumnId?: string) => void
deleteColumn: (columnId: string) => void
reorderColumns: (fromIndex: number, toIndex: number) => void
discardChanges: () => void
saveChanges: () => Promise<void>
```

### Step 3: Create EditableCell Component

Features:
- Click to enter edit mode
- Type-aware input (text/number/date/checkbox/select for boolean)
- Escape to cancel, Enter/blur to confirm
- Visual indicator for modified cells

### Step 4: Create EditableDataTable Component

Features:
- Toolbar with Add Row, Add Column, Save, Discard buttons
- Draggable column headers using @dnd-kit
- Each cell renders EditableCell
- Actions column with delete row button
- Footer row for "Add Row" action
- Dirty state indicator

### Step 5: Create ColumnManager Component

Features:
- Drag handle for reordering
- Column name editor (inline)
- Column type selector dropdown
- Delete column button with confirmation
- Width adjustment (optional)

### Step 6: Create AddColumnModal Component

Form fields:
- Column name (required)
- Column type (select from ColumnType)
- Default value (optional)
- Position (after which column)

### Step 7: Add API Method for Saving

Add to `TldwApiClient.ts`:
```typescript
async saveDataTableContent(
  tableId: string,
  payload: {
    columns: DataTableColumn[]
    rows: Record<string, any>[]
  }
): Promise<DataTable>
```

### Step 8: Update TablePreview and TableDetailModal

Replace the current static Ant Design Table with EditableDataTable component.

---

## Component Structure

```
EditableDataTable
├── Toolbar
│   ├── AddRowButton
│   ├── AddColumnButton (opens AddColumnModal)
│   ├── SaveButton (disabled if !isDirty)
│   └── DiscardButton (disabled if !isDirty)
├── DndContext (from @dnd-kit)
│   └── SortableContext (for columns)
│       └── Table
│           ├── thead
│           │   └── SortableColumnHeader[] (draggable)
│           └── tbody
│               └── Row[]
│                   ├── EditableCell[] (per column)
│                   └── ActionsCell (delete row)
└── AddColumnModal (conditional)
```

---

## Cell Editing UX

1. **View Mode**: Display formatted value (dates formatted, URLs as links, booleans as Yes/No)
2. **Click**: Enter edit mode, show appropriate input
3. **Input Types by Column Type**:
   - `text`: `<Input />`
   - `number`: `<InputNumber />`
   - `date`: `<DatePicker />`
   - `url`: `<Input type="url" />`
   - `boolean`: `<Switch />` or `<Checkbox />`
   - `currency`: `<InputNumber prefix="$" />`
4. **Save**: Blur or Enter key → update store → mark dirty
5. **Cancel**: Escape key → revert to previous value

---

## Column Reordering (using @dnd-kit)

```typescript
import { DndContext, closestCenter } from '@dnd-kit/core'
import { SortableContext, horizontalListSortingStrategy, useSortable } from '@dnd-kit/sortable'

// Wrap table headers in SortableContext
// Each column header is a sortable item
// On drag end, call reorderColumns(oldIndex, newIndex)
```

---

## API Changes

Extend existing `PUT /api/v1/data-tables/{id}` to accept full table content:

```typescript
// Request body
{
  name?: string
  description?: string
  columns?: DataTableColumn[]   // Full column definitions
  rows?: Record<string, any>[]  // Full row data
}
```

---

## Verification Plan

1. **Cell Editing**:
   - Click cell → shows input
   - Edit value → blur → cell updates
   - Escape → reverts value
   - Modified cell shows indicator

2. **Row Management**:
   - Add row → new empty row appears
   - Delete row → confirmation → row removed
   - Changes reflected in row count

3. **Column Management**:
   - Add column → modal → new column appears
   - Delete column → confirmation → column removed
   - Drag column → reorders columns

4. **Save/Discard**:
   - Make changes → Save button enabled
   - Click Save → API call → success toast
   - Click Discard → confirmation → reverts all changes

5. **Integration**:
   - Edit in TablePreview → changes persist after save
   - Edit in TableDetailModal → changes persist after save
   - Export after edit → includes edited data
