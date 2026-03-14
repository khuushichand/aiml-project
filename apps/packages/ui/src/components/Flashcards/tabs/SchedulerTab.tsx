import React from "react"
import { Alert, Button, Card, Checkbox, Empty, Input, List, Space, Typography } from "antd"
import { useTranslation } from "react-i18next"

import {
  useDecksQuery,
  useDueCountsQuery,
  useUpdateDeckMutation
} from "../hooks/useFlashcardQueries"
import type { Deck } from "@/services/flashcards"
import type {
  SchedulerSettingsDraft,
  SchedulerValidationErrors
} from "../utils/scheduler-settings"
import {
  SCHEDULER_PRESETS,
  DEFAULT_SCHEDULER_SETTINGS,
  applySchedulerPreset,
  copySchedulerSettings,
  createSchedulerDraft,
  formatSchedulerSummary,
  validateSchedulerDraft
} from "../utils/scheduler-settings"

const { Text, Title } = Typography

type EditorStatus = "idle" | "dirty" | "saving" | "saved" | "conflict"

export interface SchedulerTabProps {
  isActive?: boolean
  onDirtyChange?: (dirty: boolean) => void
  discardSignal?: number
}

const matchesDeckQuery = (deck: Deck, query: string): boolean => {
  const normalizedQuery = query.trim().toLowerCase()
  if (!normalizedQuery) return true
  const haystack = `${deck.name} ${deck.description ?? ""}`.trim().toLowerCase()
  return haystack.includes(normalizedQuery)
}

const isVersionConflict = (error: unknown): boolean =>
  typeof error === "object" &&
  error !== null &&
  "response" in error &&
  typeof (error as { response?: { status?: unknown } }).response?.status === "number" &&
  (error as { response?: { status?: number } }).response?.status === 409

const cloneDraft = (draft: SchedulerSettingsDraft): SchedulerSettingsDraft => ({
  ...draft
})

const discardFieldError = (
  errors: SchedulerValidationErrors,
  field: keyof SchedulerValidationErrors
): SchedulerValidationErrors => {
  if (!errors[field]) return errors
  const next = { ...errors }
  delete next[field]
  return next
}

export const SchedulerTab: React.FC<SchedulerTabProps> = ({
  isActive = false,
  onDirtyChange,
  discardSignal = 0
}) => {
  const { t } = useTranslation(["option", "common"])
  const decksQuery = useDecksQuery()
  const updateDeckMutation = useUpdateDeckMutation()

  const [searchText, setSearchText] = React.useState("")
  const [selectedDeckId, setSelectedDeckId] = React.useState<number | null>(null)
  const [draft, setDraft] = React.useState<SchedulerSettingsDraft | null>(null)
  const [copyDeckId, setCopyDeckId] = React.useState("")
  const [validationErrors, setValidationErrors] = React.useState<SchedulerValidationErrors>({})
  const [editorStatus, setEditorStatus] = React.useState<EditorStatus>("idle")
  const [baseDeckId, setBaseDeckId] = React.useState<number | null>(null)
  const [baseVersion, setBaseVersion] = React.useState<number | null>(null)
  const [conflictDraft, setConflictDraft] = React.useState<SchedulerSettingsDraft | null>(null)
  const [saveError, setSaveError] = React.useState<string | null>(null)

  const allDecks = decksQuery.data ?? []
  const visibleDecks = React.useMemo(
    () => allDecks.filter((deck) => matchesDeckQuery(deck, searchText)),
    [allDecks, searchText]
  )

  React.useEffect(() => {
    if (allDecks.length === 0) {
      setSelectedDeckId(null)
      return
    }

    const stillExists = selectedDeckId != null && allDecks.some((deck) => deck.id === selectedDeckId)
    if (!stillExists) {
      setSelectedDeckId(visibleDecks[0]?.id ?? allDecks[0]?.id ?? null)
    }
  }, [allDecks, selectedDeckId, visibleDecks])

  const activeDeck = React.useMemo(
    () => allDecks.find((deck) => deck.id === selectedDeckId) ?? null,
    [allDecks, selectedDeckId]
  )
  const activeDeckCounts = useDueCountsQuery(activeDeck?.id, {
    enabled: isActive && !!activeDeck
  })

  const syncDraftFromDeck = React.useCallback(
    (deck: Deck, status: EditorStatus = "idle") => {
      setBaseDeckId(deck.id)
      setBaseVersion(deck.version)
      setDraft(createSchedulerDraft(copySchedulerSettings(deck.scheduler_settings)))
      setCopyDeckId("")
      setValidationErrors({})
      setConflictDraft(null)
      setSaveError(null)
      setEditorStatus(status)
    },
    []
  )

  const refreshDeckFromServer = React.useCallback(
    async (deckId: number, status: EditorStatus = "idle") => {
      const response = await decksQuery.refetch()
      const refreshedDecks = response.data ?? decksQuery.data ?? []
      const latestDeck = refreshedDecks.find((deck) => deck.id === deckId) ?? null
      if (latestDeck) {
        syncDraftFromDeck(latestDeck, status)
      }
      return latestDeck
    },
    [decksQuery, syncDraftFromDeck]
  )

  React.useEffect(() => {
    if (!activeDeck) {
      setBaseDeckId(null)
      setBaseVersion(null)
      setDraft(null)
      setCopyDeckId("")
      setValidationErrors({})
      setConflictDraft(null)
      setSaveError(null)
      setEditorStatus("idle")
      return
    }

    if (baseDeckId !== activeDeck.id) {
      syncDraftFromDeck(activeDeck)
      return
    }

    if (
      (editorStatus === "idle" || editorStatus === "saved") &&
      baseVersion != null &&
      activeDeck.version > baseVersion
    ) {
      syncDraftFromDeck(activeDeck, editorStatus)
    }
  }, [activeDeck, baseDeckId, baseVersion, editorStatus, syncDraftFromDeck])

  const markDirty = React.useCallback(() => {
    setEditorStatus("dirty")
    setConflictDraft(null)
    setSaveError(null)
  }, [])

  const updateDraftField = React.useCallback(
    <K extends keyof SchedulerSettingsDraft>(field: K, value: SchedulerSettingsDraft[K]) => {
      setDraft((current) => (current ? { ...current, [field]: value } : current))
      setValidationErrors((current) => discardFieldError(current, field as keyof SchedulerValidationErrors))
      markDirty()
    },
    [markDirty]
  )

  const otherDecks = React.useMemo(
    () => allDecks.filter((deck) => deck.id !== activeDeck?.id),
    [activeDeck?.id, allDecks]
  )

  const draftPreview = React.useMemo(() => {
    if (!draft) return null
    const parsed = validateSchedulerDraft(draft)
    return parsed.settings ? formatSchedulerSummary(parsed.settings) : null
  }, [draft])

  const applyPreset = React.useCallback(
    (presetId: (typeof SCHEDULER_PRESETS)[number]["id"]) => {
      setDraft(createSchedulerDraft(applySchedulerPreset(presetId)))
      setValidationErrors({})
      markDirty()
    },
    [markDirty]
  )

  const copyFromSelectedDeck = React.useCallback(() => {
    const sourceDeck = otherDecks.find((deck) => String(deck.id) === copyDeckId)
    if (!sourceDeck) return
    setDraft(createSchedulerDraft(copySchedulerSettings(sourceDeck.scheduler_settings)))
    setValidationErrors({})
    markDirty()
  }, [copyDeckId, markDirty, otherDecks])

  const resetToDefaults = React.useCallback(() => {
    setDraft(createSchedulerDraft(DEFAULT_SCHEDULER_SETTINGS))
    setValidationErrors({})
    markDirty()
  }, [markDirty])

  const reloadLatest = React.useCallback(async () => {
    if (!activeDeck) return
    setSaveError(null)

    try {
      await refreshDeckFromServer(activeDeck.id)
    } catch (_error) {
      setSaveError(
        t("option:flashcards.schedulerReloadError", {
          defaultValue: "Failed to reload scheduler settings."
        })
      )
    }
  }, [activeDeck, refreshDeckFromServer, t])

  const reapplyConflict = React.useCallback(() => {
    if (!conflictDraft) return
    setDraft(cloneDraft(conflictDraft))
    setValidationErrors({})
    setEditorStatus("dirty")
    setSaveError(null)
  }, [conflictDraft])

  const handleSave = React.useCallback(async () => {
    if (!activeDeck || !draft) return

    const parsed = validateSchedulerDraft(draft)
    setValidationErrors(parsed.errors)
    if (!parsed.settings) return

    setEditorStatus("saving")
    setSaveError(null)

    try {
      const updatedDeck = await updateDeckMutation.mutateAsync({
        deckId: activeDeck.id,
        update: {
          scheduler_settings: parsed.settings,
          expected_version: baseVersion ?? activeDeck.version
        }
      })
      syncDraftFromDeck(updatedDeck, "saved")
    } catch (error: unknown) {
      if (isVersionConflict(error)) {
        const pendingDraft = cloneDraft(draft)

        try {
          const latestDeck = await refreshDeckFromServer(activeDeck.id)
          if (!latestDeck) {
            syncDraftFromDeck(activeDeck)
          }
        } catch (_refreshError) {
          syncDraftFromDeck(activeDeck)
        }

        setConflictDraft(pendingDraft)
        setEditorStatus("conflict")
        return
      }

      setEditorStatus("dirty")
      setSaveError(
        t("option:flashcards.schedulerSaveError", {
          defaultValue: "Failed to save scheduler settings."
        })
      )
    }
  }, [activeDeck, baseVersion, draft, refreshDeckFromServer, syncDraftFromDeck, t, updateDeckMutation])

  const renderFieldError = (field: keyof SchedulerValidationErrors) => {
    const error = validationErrors[field]
    if (!error) return null
    return (
      <Text type="danger" className="text-xs">
        {error}
      </Text>
    )
  }

  const isDirty = editorStatus === "dirty" || editorStatus === "conflict"

  React.useEffect(() => {
    onDirtyChange?.(isDirty)
  }, [isDirty, onDirtyChange])

  React.useEffect(() => {
    if (discardSignal <= 0) return

    if (!activeDeck) {
      setBaseDeckId(null)
      setBaseVersion(null)
      setDraft(null)
      setCopyDeckId("")
      setValidationErrors({})
      setConflictDraft(null)
      setSaveError(null)
      setEditorStatus("idle")
      return
    }

    syncDraftFromDeck(activeDeck)
  }, [activeDeck, discardSignal, syncDraftFromDeck])

  const confirmDiscardChanges = React.useCallback(() => {
    if (!isDirty) return true
    return window.confirm(
      t("option:flashcards.schedulerDiscardChangesPrompt", {
        defaultValue: "Discard unsaved scheduler changes?"
      })
    )
  }, [isDirty, t])

  return (
    <div className="space-y-4">
      <div>
        <Title level={4} className="!mb-1">
          {t("option:flashcards.schedulerTabTitle", { defaultValue: "Scheduler" })}
        </Title>
        <Text type="secondary">
          {t("option:flashcards.schedulerTabDescription", {
            defaultValue: "Choose a deck to inspect and edit its spaced-repetition policy."
          })}
        </Text>
      </div>

      <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Card size="small" title={t("option:flashcards.schedulerDecks", { defaultValue: "Decks" })}>
          <Space orientation="vertical" size={12} className="w-full">
            <Input.Search
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder={t("option:flashcards.searchDecks", { defaultValue: "Search decks" })}
              allowClear
            />

            {visibleDecks.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={t("option:flashcards.noDecksForScheduler", {
                  defaultValue: "No decks match the current filter."
                })}
              />
            ) : (
              <List
                dataSource={visibleDecks}
                renderItem={(deck) => (
                  <List.Item className="!px-0">
                    <Button
                      type={deck.id === selectedDeckId ? "primary" : "text"}
                      className="!h-auto !w-full !justify-start"
                      onClick={() => {
                        if (deck.id === selectedDeckId) return
                        if (!confirmDiscardChanges()) return
                        setSelectedDeckId(deck.id)
                      }}
                    >
                      <div className="min-w-0 text-left">
                        <div className="font-medium">{deck.name}</div>
                        {deck.description ? (
                          <div className="text-xs text-text-muted">{deck.description}</div>
                        ) : null}
                        <div className="text-xs text-text-subtle">
                          {formatSchedulerSummary(deck.scheduler_settings)}
                        </div>
                      </div>
                    </Button>
                  </List.Item>
                )}
              />
            )}
          </Space>
        </Card>

        <Card size="small">
          {activeDeck && draft ? (
            <Space orientation="vertical" size={16} className="w-full">
              <div>
                <Title level={5} className="!mb-0">
                  {t("option:flashcards.schedulerDeckHeading", {
                    defaultValue: "{{name}} Scheduler",
                    name: activeDeck.name
                  })}
                </Title>
                <Text type="secondary">
                  {t("option:flashcards.schedulerDeckVersion", {
                    defaultValue: "Version {{version}}",
                    version: baseVersion ?? activeDeck.version
                  })}
                </Text>
              </div>

              {editorStatus === "conflict" && (
                <div
                  className="rounded border border-amber-300 bg-amber-50 p-3"
                  data-testid="flashcards-scheduler-conflict"
                >
                  <div className="font-medium">
                    {t("option:flashcards.schedulerConflictTitle", {
                      defaultValue: "Deck settings changed elsewhere."
                    })}
                  </div>
                  <div className="text-sm text-text-muted">
                    {t("option:flashcards.schedulerConflictDescription", {
                      defaultValue: "Reload the latest saved settings or reapply your draft before saving again."
                    })}
                  </div>
                  <Space className="mt-3">
                    <Button size="small" onClick={reloadLatest}>
                      {t("option:flashcards.schedulerReloadLatest", {
                        defaultValue: "Reload latest"
                      })}
                    </Button>
                    <Button size="small" type="primary" onClick={reapplyConflict}>
                      {t("option:flashcards.schedulerReapplyDraft", {
                        defaultValue: "Reapply my draft"
                      })}
                    </Button>
                  </Space>
                </div>
              )}

              {saveError && <Alert type="error" message={saveError} />}

              <Card
                size="small"
                title={t("option:flashcards.schedulerSummaryCard", {
                  defaultValue: "Current draft"
                })}
              >
                <Text type={draftPreview ? "secondary" : "danger"}>
                  {draftPreview ??
                    t("option:flashcards.schedulerDraftInvalid", {
                      defaultValue: "Draft has validation errors."
                    })}
                </Text>
              </Card>

              <Card
                size="small"
                title={t("option:flashcards.schedulerCountsCard", {
                  defaultValue: "Active deck counts"
                })}
              >
                <div className="grid gap-3 sm:grid-cols-4">
                  <div>
                    <Text type="secondary">Due review</Text>
                    <div className="text-lg font-semibold">{activeDeckCounts.data?.due ?? 0}</div>
                  </div>
                  <div>
                    <Text type="secondary">New</Text>
                    <div className="text-lg font-semibold">{activeDeckCounts.data?.new ?? 0}</div>
                  </div>
                  <div>
                    <Text type="secondary">Learning</Text>
                    <div className="text-lg font-semibold">{activeDeckCounts.data?.learning ?? 0}</div>
                  </div>
                  <div>
                    <Text type="secondary">Total due</Text>
                    <div className="text-lg font-semibold">{activeDeckCounts.data?.total ?? 0}</div>
                  </div>
                </div>
              </Card>

              <Card
                size="small"
                title={t("option:flashcards.schedulerTools", { defaultValue: "Tools" })}
              >
                <Space orientation="vertical" size={12} className="w-full">
                  <div>
                    <Text strong>
                      {t("option:flashcards.schedulerPresets", { defaultValue: "Presets" })}
                    </Text>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {SCHEDULER_PRESETS.map((preset) => (
                        <Button
                          key={preset.id}
                          onClick={() => applyPreset(preset.id)}
                          data-testid={`flashcards-scheduler-preset-${preset.id}`}
                        >
                          {preset.label}
                        </Button>
                      ))}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-end gap-2">
                    <label className="flex min-w-[220px] flex-col gap-1 text-sm text-text-muted">
                      <span>
                        {t("option:flashcards.schedulerCopyFromDeck", {
                          defaultValue: "Copy from deck"
                        })}
                      </span>
                      <select
                        value={copyDeckId}
                        onChange={(event) => setCopyDeckId(event.target.value)}
                        data-testid="flashcards-scheduler-copy-select"
                        className="rounded border border-border bg-background px-2 py-1"
                      >
                        <option value="">
                          {t("option:flashcards.schedulerCopySelectPlaceholder", {
                            defaultValue: "Choose another deck"
                          })}
                        </option>
                        {otherDecks.map((deck) => (
                          <option key={deck.id} value={String(deck.id)}>
                            {deck.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <Button onClick={copyFromSelectedDeck} disabled={!copyDeckId}>
                      {t("option:flashcards.schedulerCopyAction", {
                        defaultValue: "Copy settings"
                      })}
                    </Button>
                    <Button onClick={resetToDefaults}>
                      {t("option:flashcards.schedulerResetAction", {
                        defaultValue: "Reset to defaults"
                      })}
                    </Button>
                  </div>
                </Space>
              </Card>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-1">
                  <Text strong>
                    {t("option:flashcards.schedulerFieldNewSteps", {
                      defaultValue: "New steps (minutes)"
                    })}
                  </Text>
                  <Input
                    value={draft.new_steps_minutes}
                    onChange={(event) => updateDraftField("new_steps_minutes", event.target.value)}
                    data-testid="flashcards-scheduler-field-new-steps"
                    aria-label="New steps"
                    placeholder="1, 10"
                  />
                  {renderFieldError("new_steps_minutes")}
                </label>

                <label className="flex flex-col gap-1">
                  <Text strong>
                    {t("option:flashcards.schedulerFieldRelearnSteps", {
                      defaultValue: "Relearn steps (minutes)"
                    })}
                  </Text>
                  <Input
                    value={draft.relearn_steps_minutes}
                    onChange={(event) => updateDraftField("relearn_steps_minutes", event.target.value)}
                    data-testid="flashcards-scheduler-field-relearn-steps"
                    aria-label="Relearn steps"
                    placeholder="10"
                  />
                  {renderFieldError("relearn_steps_minutes")}
                </label>

                <label className="flex flex-col gap-1">
                  <Text strong>Graduating interval (days)</Text>
                  <Input
                    value={draft.graduating_interval_days}
                    onChange={(event) => updateDraftField("graduating_interval_days", event.target.value)}
                    data-testid="flashcards-scheduler-field-graduating-interval"
                    aria-label="Graduating interval"
                  />
                  {renderFieldError("graduating_interval_days")}
                </label>

                <label className="flex flex-col gap-1">
                  <Text strong>Easy interval (days)</Text>
                  <Input
                    value={draft.easy_interval_days}
                    onChange={(event) => updateDraftField("easy_interval_days", event.target.value)}
                    data-testid="flashcards-scheduler-field-easy-interval"
                    aria-label="Easy interval"
                  />
                  {renderFieldError("easy_interval_days")}
                </label>

                <label className="flex flex-col gap-1">
                  <Text strong>Easy bonus</Text>
                  <Input
                    value={draft.easy_bonus}
                    onChange={(event) => updateDraftField("easy_bonus", event.target.value)}
                    data-testid="flashcards-scheduler-field-easy-bonus"
                    aria-label="Easy bonus"
                  />
                  {renderFieldError("easy_bonus")}
                </label>

                <label className="flex flex-col gap-1">
                  <Text strong>Interval modifier</Text>
                  <Input
                    value={draft.interval_modifier}
                    onChange={(event) => updateDraftField("interval_modifier", event.target.value)}
                    data-testid="flashcards-scheduler-field-interval-modifier"
                    aria-label="Interval modifier"
                  />
                  {renderFieldError("interval_modifier")}
                </label>

                <label className="flex flex-col gap-1">
                  <Text strong>Max interval (days)</Text>
                  <Input
                    value={draft.max_interval_days}
                    onChange={(event) => updateDraftField("max_interval_days", event.target.value)}
                    data-testid="flashcards-scheduler-field-max-interval"
                    aria-label="Max interval"
                  />
                  {renderFieldError("max_interval_days")}
                </label>

                <label className="flex flex-col gap-1">
                  <Text strong>Leech threshold</Text>
                  <Input
                    value={draft.leech_threshold}
                    onChange={(event) => updateDraftField("leech_threshold", event.target.value)}
                    data-testid="flashcards-scheduler-field-leech-threshold"
                    aria-label="Leech threshold"
                  />
                  {renderFieldError("leech_threshold")}
                </label>
              </div>

              <Checkbox
                checked={draft.enable_fuzz}
                onChange={(event) => updateDraftField("enable_fuzz", event.target.checked)}
                data-testid="flashcards-scheduler-field-enable-fuzz"
              >
                {t("option:flashcards.schedulerEnableFuzz", {
                  defaultValue: "Enable review fuzz"
                })}
              </Checkbox>

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  type="primary"
                  onClick={() => void handleSave()}
                  loading={editorStatus === "saving" || updateDeckMutation.isPending}
                >
                  {t("option:flashcards.schedulerSaveAction", {
                    defaultValue: "Save changes"
                  })}
                </Button>
                {editorStatus === "dirty" && (
                  <Text type="warning">
                    {t("option:flashcards.schedulerDirtyState", {
                      defaultValue: "Unsaved changes"
                    })}
                  </Text>
                )}
                {editorStatus === "saved" && (
                  <Text type="success">
                    {t("option:flashcards.schedulerSavedState", {
                      defaultValue: "All changes saved"
                    })}
                  </Text>
                )}
              </div>
            </Space>
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={t("option:flashcards.selectDeckForScheduler", {
                defaultValue: "Select a deck to inspect its scheduler."
              })}
            />
          )}
        </Card>
      </div>
    </div>
  )
}

export default SchedulerTab
