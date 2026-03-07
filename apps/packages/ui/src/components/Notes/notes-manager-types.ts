export type { NoteListItem } from './types'

export type {
  KeywordSyncWarning,
  SaveNoteOptions,
  SaveIndicatorState,
  NotesEditorMode,
  NotesInputMode,
  NotesSortOption,
  KeywordPickerSortMode,
  KeywordFrequencyTone,
  KeywordManagementItem,
  KeywordRenameDraft,
  KeywordMergeDraft,
  MarkdownToolbarAction,
  OfflineDraftSyncState,
  OfflineDraftEntry,
  OfflineDraftSyncResult,
  RemoteVersionInfo,
  NotesAssistAction,
  EditProvenanceState,
  MonitoringAlertSeverity,
  MonitoringNoticeState,
  ExportFormat,
  ExportProgressState,
  NotesListViewMode,
  MoodboardSummary,
  NotebookFilterOption,
  ImportFormat,
  ImportDuplicateStrategy,
  PendingImportFile,
  NotesImportResponsePayload,
  NotesTitleSettingsResponse,
  NoteTemplateDefinition,
  NotesTocEntry,
} from './notes-manager-utils'

export type NoteWithKeywords = {
  metadata?: { keywords?: any[] }
  keywords?: any[]
}
