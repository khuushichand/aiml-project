import React from "react"
import { DictionaryEntryToolsPanel } from "./DictionaryEntryToolsPanel"
import { DictionaryEntryEditForm } from "./DictionaryEntryEditForm"
import { DictionaryEntryCreateForm } from "./DictionaryEntryCreateForm"
import { DictionaryEntryListSection } from "./DictionaryEntryListSection"
import { DictionaryEntryEditPanel } from "./DictionaryEntryEditPanel"
import { useDictionaryEntryManagerState } from "./useDictionaryEntryManagerState"
import {
  formatProbabilityFrequencyHint,
  normalizeProbabilityValue,
} from "./dictionaryEntryUtils"

export const DictionaryEntryManager: React.FC<{ dictionaryId: number; form: any }> = ({
  dictionaryId,
  form
}) => {
  const {
    t,
    isMobileViewport,
    editEntryForm,
    toolsPanelKeys,
    setToolsPanelKeys,
    entrySearch,
    setEntrySearch,
    entryGroupFilter,
    setEntryGroupFilter,
    entriesStatus,
    entriesError,
    refetchEntries,
    entries,
    entryGroupOptions,
    filteredEntries,
    hasAnyEntries,
    normalizedEntryGroupFilter,
    filteredEntryIds,
    highlightedValidationEntryId,
    jumpToValidationEntry,
    validationStrict,
    setValidationStrict,
    validationReport,
    validationError,
    runValidation,
    validating,
    previewTokenBudget,
    setPreviewTokenBudget,
    previewMaxIterations,
    setPreviewMaxIterations,
    previewResult,
    previewError,
    handlePreview,
    previewing,
    previewEntriesUsed,
    previewProcessedText,
    previewDiffSegments,
    previewHasDiffChanges,
    previewText,
    setPreviewText,
    previewCaseName,
    handlePreviewCaseNameChange,
    previewCaseError,
    savedPreviewCases,
    savePreviewCase,
    loadPreviewCase,
    deletePreviewCase,
    selectedEntryRowKeys,
    setSelectedEntryRowKeys,
    selectedEntryIds,
    canReorderEntries,
    canEscalateSelectAllFilteredEntries,
    handleSelectAllFilteredEntries,
    bulkEntryAction,
    handleBulkEntryAction,
    bulkGroupName,
    setBulkGroupName,
    entryTableColumns,
    editingEntry,
    closeEditEntryPanel,
    handleEditEntrySubmit,
    updatingEntry,
    adding,
    advancedMode,
    toggleAdvancedMode,
    handleAddEntrySubmit,
    handleAddEntryPatternChange,
    handleAddEntryReplacementChange,
    handleAddEntryTypeChange,
    regexError,
    regexServerError,
  } = useDictionaryEntryManagerState({ dictionaryId, form })

  const editEntryFormContent = (
    <DictionaryEntryEditForm
      form={editEntryForm}
      updatingEntry={updatingEntry}
      onSubmit={handleEditEntrySubmit}
      entryGroupOptions={entryGroupOptions}
      normalizeProbabilityValue={normalizeProbabilityValue}
      formatProbabilityFrequencyHint={formatProbabilityFrequencyHint}
    />
  )

  return (
    <div className="space-y-4">
      <DictionaryEntryToolsPanel
        entriesCount={entries.length}
        toolsPanelKeys={toolsPanelKeys}
        onToolsPanelKeysChange={setToolsPanelKeys}
        validationStrict={validationStrict}
        onValidationStrictChange={setValidationStrict}
        onRunValidation={() => runValidation()}
        validating={validating}
        validationError={validationError}
        validationReport={validationReport}
        onJumpToValidationEntry={jumpToValidationEntry}
        onRunPreview={handlePreview}
        previewing={previewing}
        previewText={previewText}
        onPreviewTextChange={setPreviewText}
        previewCaseName={previewCaseName}
        onPreviewCaseNameChange={handlePreviewCaseNameChange}
        onSavePreviewCase={savePreviewCase}
        previewCaseError={previewCaseError}
        savedPreviewCases={savedPreviewCases}
        onLoadPreviewCase={loadPreviewCase}
        onDeletePreviewCase={deletePreviewCase}
        previewTokenBudget={previewTokenBudget}
        onPreviewTokenBudgetChange={setPreviewTokenBudget}
        previewMaxIterations={previewMaxIterations}
        onPreviewMaxIterationsChange={setPreviewMaxIterations}
        previewError={previewError}
        previewResult={previewResult}
        previewHasDiffChanges={previewHasDiffChanges}
        previewDiffSegments={previewDiffSegments}
        previewProcessedText={previewProcessedText}
        previewEntriesUsed={previewEntriesUsed}
      />

      <h3 className="text-sm font-medium text-text mt-4 mb-2">
        {t("option:dictionaries.entriesHeading", "Dictionary Entries")}
      </h3>
      <DictionaryEntryListSection
        entrySearch={entrySearch}
        onEntrySearchChange={setEntrySearch}
        entryGroupFilter={entryGroupFilter}
        onEntryGroupFilterChange={setEntryGroupFilter}
        entryGroupOptions={entryGroupOptions}
        entriesStatus={entriesStatus}
        hasAnyEntries={hasAnyEntries}
        canReorderEntries={canReorderEntries}
        selectedEntryIds={selectedEntryIds}
        canEscalateSelectAllFilteredEntries={canEscalateSelectAllFilteredEntries}
        filteredEntryIds={filteredEntryIds}
        onSelectAllFilteredEntries={handleSelectAllFilteredEntries}
        onClearSelection={() => setSelectedEntryRowKeys([])}
        bulkEntryAction={bulkEntryAction}
        onActivate={() => void handleBulkEntryAction("activate")}
        onDeactivate={() => void handleBulkEntryAction("deactivate")}
        onSetGroup={() => void handleBulkEntryAction("group")}
        onDelete={() => void handleBulkEntryAction("delete")}
        bulkGroupName={bulkGroupName}
        onBulkGroupNameChange={setBulkGroupName}
        entriesError={entriesError}
        onRetryEntries={() => void refetchEntries()}
        onAddFirstEntry={() => form.scrollToField("pattern")}
        filteredEntries={filteredEntries}
        highlightedValidationEntryId={highlightedValidationEntryId}
        selectedEntryRowKeys={selectedEntryRowKeys}
        onSelectionChange={setSelectedEntryRowKeys}
        normalizedEntryGroupFilter={normalizedEntryGroupFilter}
        entryTableColumns={entryTableColumns}
      />

      <DictionaryEntryEditPanel
        open={!!editingEntry}
        isMobileViewport={isMobileViewport}
        onClose={closeEditEntryPanel}>
        {editEntryFormContent}
      </DictionaryEntryEditPanel>
      <DictionaryEntryCreateForm
        form={form}
        adding={adding}
        advancedMode={advancedMode}
        onToggleAdvancedMode={toggleAdvancedMode}
        onSubmit={handleAddEntrySubmit}
        onPatternChange={handleAddEntryPatternChange}
        onReplacementChange={handleAddEntryReplacementChange}
        onTypeChange={handleAddEntryTypeChange}
        regexError={regexError}
        regexServerError={regexServerError}
        entryGroupOptions={entryGroupOptions}
        normalizeProbabilityValue={normalizeProbabilityValue}
        formatProbabilityFrequencyHint={formatProbabilityFrequencyHint}
      />
    </div>
  )
}
