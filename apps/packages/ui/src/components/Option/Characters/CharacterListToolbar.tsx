import React from "react"
import {
  Button,
  Input,
  Select,
  Checkbox,
  Segmented,
  Dropdown,
  Tooltip
} from "antd"
import type { InputRef } from "antd"
import {
  ChevronDown,
  ChevronUp,
  LayoutGrid,
  List,
  Keyboard,
  Upload as UploadIcon
} from "lucide-react"
import { ActiveFilterChips } from "./ActiveFilterChips"
import {
  isCharacterFolderToken,
  normalizeCharacterFolderId,
  type CharacterListScope,
  type TableDensity,
  type CharacterFolderOption
} from "./utils"
import type { GalleryCardDensity } from "./CharacterGalleryCard"
import type { TFunction } from "i18next"

export type CharacterListToolbarProps = {
  t: TFunction
  // search
  searchInputRef: React.RefObject<InputRef | null>
  searchTerm: string
  setSearchTerm: (v: string) => void
  // view
  viewMode: "table" | "gallery"
  setViewMode: (v: "table" | "gallery") => void
  // scope
  characterListScope: CharacterListScope
  setCharacterListScope: (v: CharacterListScope) => void
  // filters
  advancedFiltersOpen: boolean
  setAdvancedFiltersOpen: React.Dispatch<React.SetStateAction<boolean>>
  activeAdvancedFilterCount: number
  hasFilters: boolean
  clearFilters: () => void
  // filter values
  filterTags: string[]
  setFilterTags: React.Dispatch<React.SetStateAction<string[]>>
  folderFilterId: string | undefined
  setFolderFilterId: (v: string | undefined) => void
  creatorFilter: string | undefined
  setCreatorFilter: (v: string | undefined) => void
  createdFromDate: string
  setCreatedFromDate: (v: string) => void
  createdToDate: string
  setCreatedToDate: (v: string) => void
  updatedFromDate: string
  setUpdatedFromDate: (v: string) => void
  updatedToDate: string
  setUpdatedToDate: (v: string) => void
  matchAllTags: boolean
  setMatchAllTags: (v: boolean) => void
  hasConversationsOnly: boolean
  setHasConversationsOnly: (v: boolean) => void
  favoritesOnly: boolean
  setFavoritesOnly: (v: boolean) => void
  // filter options
  tagFilterOptions: Array<{ value: string; label: string }>
  creatorFilterOptions: Array<{ value: string; label: string }>
  characterFolderOptions: CharacterFolderOption[]
  characterFolderOptionsLoading: boolean
  selectedFolderFilterLabel: string | undefined
  // density
  galleryDensity: GalleryCardDensity
  setGalleryDensity: (v: GalleryCardDensity) => void
  tableDensity: TableDensity
  setTableDensity: (v: TableDensity) => void
  // shortcuts
  shortcutHelpItems: Array<{ id: string; keys: string[]; label: string }>
  shortcutSummaryText: string
  // import
  isImportBusy: boolean
  triggerImportPicker: () => void
  // new button
  newButtonRef: React.RefObject<HTMLButtonElement | null>
  openCreateModal: () => void
  // tag manager
  openTagManager: () => void
}

export const CharacterListToolbar: React.FC<CharacterListToolbarProps> = ({
  t,
  searchInputRef,
  searchTerm,
  setSearchTerm,
  viewMode,
  setViewMode,
  characterListScope,
  setCharacterListScope,
  advancedFiltersOpen,
  setAdvancedFiltersOpen,
  activeAdvancedFilterCount,
  hasFilters,
  clearFilters,
  filterTags,
  setFilterTags,
  folderFilterId,
  setFolderFilterId,
  creatorFilter,
  setCreatorFilter,
  createdFromDate,
  setCreatedFromDate,
  createdToDate,
  setCreatedToDate,
  updatedFromDate,
  setUpdatedFromDate,
  updatedToDate,
  setUpdatedToDate,
  matchAllTags,
  setMatchAllTags,
  hasConversationsOnly,
  setHasConversationsOnly,
  favoritesOnly,
  setFavoritesOnly,
  tagFilterOptions,
  creatorFilterOptions,
  characterFolderOptions,
  characterFolderOptionsLoading,
  selectedFolderFilterLabel,
  galleryDensity,
  setGalleryDensity,
  tableDensity,
  setTableDensity,
  shortcutHelpItems,
  shortcutSummaryText,
  isImportBusy,
  triggerImportPicker,
  newButtonRef,
  openCreateModal,
  openTagManager
}) => (
  <>
    <div id="characters-shortcuts-summary" className="sr-only">
      {`${t("settings:manageCharacters.shortcuts.title", {
        defaultValue: "Keyboard shortcuts"
      })}: ${shortcutSummaryText}`}
    </div>
    <div className="flex flex-col gap-3">
      {/* Primary toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        {/* New character button + Import button */}
        <Tooltip title="N" placement="bottom">
          <Button
            type="primary"
            ref={newButtonRef}
            onClick={openCreateModal}
            data-testid="characters-new-button"
          >
            {t("settings:manageCharacters.addBtn", {
              defaultValue: "New character"
            })}
          </Button>
        </Tooltip>
        <Tooltip title={t("settings:manageCharacters.import.button", { defaultValue: "Import" })}>
          <Button
            size="small"
            icon={<UploadIcon className="h-4 w-4" />}
            loading={isImportBusy}
            onClick={triggerImportPicker}
            aria-label={t("settings:manageCharacters.import.button", {
              defaultValue: "Import character"
            })}
          />
        </Tooltip>

        {/* Search */}
        <Tooltip
          title={t("settings:manageCharacters.search.shortcut", {
            defaultValue: "Press / to search"
          })}>
          <Input
            ref={searchInputRef}
            allowClear
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            data-testid="characters-search-input"
            placeholder={t(
              "settings:manageCharacters.search.placeholder",
              {
                defaultValue: "Search characters"
              }
            )}
            aria-label={t("settings:manageCharacters.search.label", {
              defaultValue: "Search characters"
            })}
            className="w-full sm:w-72"
            suffix={
              <span className="hidden text-xs text-text-subtle sm:inline">/</span>
            }
          />
        </Tooltip>

        {/* View mode toggle */}
        <Segmented
          value={viewMode}
          data-testid="characters-view-mode-segmented"
          onChange={(v) => setViewMode(v as "table" | "gallery")}
          disabled={characterListScope === "deleted"}
          options={[
            {
              value: "table",
              icon: <List className="h-4 w-4" />,
              title: t("settings:manageCharacters.viewMode.table", {
                defaultValue: "Table view"
              })
            },
            {
              value: "gallery",
              icon: <LayoutGrid className="h-4 w-4" />,
              title: t("settings:manageCharacters.viewMode.gallery", {
                defaultValue: "Gallery view"
              })
            }
          ]}
          aria-label={t("settings:manageCharacters.viewMode.label", {
            defaultValue: "View mode"
          })}
        />

        <div className="flex-1" />

        {/* Secondary controls: scope, filters, display options */}
        <Segmented
          value={characterListScope}
          data-testid="characters-scope-segmented"
          onChange={(value) =>
            setCharacterListScope(value as CharacterListScope)
          }
          options={[
            {
              value: "active",
              label: t("settings:manageCharacters.scope.active", {
                defaultValue: "Active"
              }),
              title: t("settings:manageCharacters.scope.activeTitle", {
                defaultValue: "Active characters"
              })
            },
            {
              value: "deleted",
              label: t("settings:manageCharacters.scope.deleted", {
                defaultValue: "Trash"
              }),
              title: t("settings:manageCharacters.scope.deletedTitle", {
                defaultValue: "Recently deleted characters"
              })
            }
          ]}
          aria-label={t("settings:manageCharacters.scope.label", {
            defaultValue: "Character list view"
          })}
        />

        <Button
          size="small"
          type={advancedFiltersOpen ? "primary" : "default"}
          icon={
            advancedFiltersOpen ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )
          }
          aria-expanded={advancedFiltersOpen}
          aria-controls="characters-advanced-filters-panel"
          onClick={() => setAdvancedFiltersOpen((prev) => !prev)}>
          {t("settings:manageCharacters.filter.showAdvanced", {
            defaultValue: "Filters"
          })}
          {activeAdvancedFilterCount > 0
            ? ` (${activeAdvancedFilterCount})`
            : ""}
        </Button>

        {/* Display options dropdown: density + shortcuts */}
        <Dropdown
          menu={{
            items: [
              ...(viewMode === "gallery"
                ? [
                    {
                      key: "density-label",
                      label: t("settings:manageCharacters.galleryDensity.label", {
                        defaultValue: "Gallery card density"
                      }),
                      type: "group" as const,
                      children: [
                        {
                          key: "rich",
                          label: t("settings:manageCharacters.galleryDensity.rich", {
                            defaultValue: "Rich"
                          }),
                          onClick: () => setGalleryDensity("rich" as GalleryCardDensity)
                        },
                        {
                          key: "compact",
                          label: t("settings:manageCharacters.galleryDensity.compact", {
                            defaultValue: "Compact"
                          }),
                          onClick: () => setGalleryDensity("compact" as GalleryCardDensity)
                        }
                      ]
                    }
                  ]
                : [
                    {
                      key: "density-label",
                      label: t("settings:manageCharacters.tableDensity.label", {
                        defaultValue: "Table density"
                      }),
                      type: "group" as const,
                      children: [
                        {
                          key: "comfortable",
                          label: t("settings:manageCharacters.tableDensity.comfortable", {
                            defaultValue: "Comfortable"
                          }),
                          onClick: () => setTableDensity("comfortable" as TableDensity)
                        },
                        {
                          key: "compact-table",
                          label: t("settings:manageCharacters.tableDensity.compact", {
                            defaultValue: "Compact"
                          }),
                          onClick: () => setTableDensity("compact" as TableDensity)
                        },
                        {
                          key: "dense",
                          label: t("settings:manageCharacters.tableDensity.dense", {
                            defaultValue: "Dense"
                          }),
                          onClick: () => setTableDensity("dense" as TableDensity)
                        }
                      ]
                    }
                  ]),
              { type: "divider" as const },
              {
                key: "shortcuts",
                label: t("settings:manageCharacters.shortcuts.title", {
                  defaultValue: "Keyboard shortcuts"
                }),
                icon: <Keyboard className="h-4 w-4" />,
                children: shortcutHelpItems.map((item) => ({
                  key: item.id,
                  label: (
                    <span>
                      {item.keys.map((key, index) => (
                        <React.Fragment key={`${item.id}-${key}-${index}`}>
                          {index > 0 && " "}
                          <kbd className="rounded bg-surface2 px-1 text-xs">{key}</kbd>
                        </React.Fragment>
                      ))}{" "}
                      {item.label}
                    </span>
                  ),
                  disabled: true
                }))
              }
            ]
          }}
          trigger={["click"]}
        >
          <Button
            size="small"
            aria-label={t("settings:manageCharacters.displayOptions", {
              defaultValue: "Display options"
            })}
          >
            {t("settings:manageCharacters.displayOptions", {
              defaultValue: "Display"
            })}
            <ChevronDown className="ml-1 h-3 w-3" />
          </Button>
        </Dropdown>
      </div>

      {/* Active filter chips -- always visible when filters are set */}
      {!advancedFiltersOpen && (
        <ActiveFilterChips
          filterTags={filterTags}
          folderFilterId={folderFilterId}
          folderLabel={selectedFolderFilterLabel}
          creatorFilter={creatorFilter}
          createdFromDate={createdFromDate}
          createdToDate={createdToDate}
          updatedFromDate={updatedFromDate}
          updatedToDate={updatedToDate}
          hasConversationsOnly={hasConversationsOnly}
          favoritesOnly={favoritesOnly}
          onRemoveTag={(tag) => setFilterTags((prev) => prev.filter((t) => t !== tag))}
          onClearFolder={() => setFolderFilterId(undefined)}
          onClearCreator={() => setCreatorFilter(undefined)}
          onClearCreatedDate={() => { setCreatedFromDate(""); setCreatedToDate("") }}
          onClearUpdatedDate={() => { setUpdatedFromDate(""); setUpdatedToDate("") }}
          onClearConversations={() => setHasConversationsOnly(false)}
          onClearFavorites={() => setFavoritesOnly(false)}
          onClearAll={clearFilters}
        />
      )}

      {advancedFiltersOpen && (
        <div
          id="characters-advanced-filters-panel"
          className="space-y-3 rounded-lg border border-border bg-surface/60 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-text-muted">
              {t("settings:manageCharacters.filter.panelDescription", {
                defaultValue:
                  "Refine the character list by metadata, dates, and conversation activity."
              })}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {hasFilters && (
                <Button size="small" onClick={clearFilters}>
                  {t("settings:manageCharacters.filter.clear", {
                    defaultValue: "Clear filters"
                  })}
                </Button>
              )}
              <Button size="small" onClick={openTagManager}>
                {t("settings:manageCharacters.tags.manageButton", {
                  defaultValue: "Manage tags"
                })}
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Select
              mode="multiple"
              allowClear
              className="w-full sm:w-[15rem]"
              placeholder={t("settings:manageCharacters.filter.tagsPlaceholder", {
                defaultValue: "Filter by tags"
              })}
              aria-label={t("settings:manageCharacters.filter.tagsAriaLabel", {
                defaultValue: "Filter characters by tags"
              })}
              value={filterTags}
              options={tagFilterOptions}
              onChange={(value) =>
                setFilterTags(
                  (value as string[]).filter(
                    (v) => v && v.trim().length > 0 && !isCharacterFolderToken(v)
                  )
                )
              }
            />
            <Select
              allowClear
              className="w-full sm:w-[13rem]"
              placeholder={t("settings:manageCharacters.filter.folderPlaceholder", {
                defaultValue: "Filter by folder"
              })}
              aria-label={t("settings:manageCharacters.filter.folderAriaLabel", {
                defaultValue: "Filter characters by folder"
              })}
              value={folderFilterId}
              options={characterFolderOptions.map((folder) => ({
                value: String(folder.id),
                label: folder.name
              }))}
              loading={characterFolderOptionsLoading}
              onChange={(value) => {
                const normalized = normalizeCharacterFolderId(value)
                setFolderFilterId(normalized)
              }}
            />
            <Select
              allowClear
              className="w-full sm:w-[13rem]"
              placeholder={t("settings:manageCharacters.filter.creatorPlaceholder", {
                defaultValue: "Filter by creator"
              })}
              aria-label={t("settings:manageCharacters.filter.creatorAriaLabel", {
                defaultValue: "Filter characters by creator"
              })}
              value={creatorFilter}
              options={creatorFilterOptions}
              onChange={(value) => setCreatorFilter(value || undefined)}
            />
          </div>

          <div className="grid gap-2 lg:grid-cols-2">
            <div className="rounded-md border border-border bg-surface2/30 p-2">
              <p className="mb-1 text-xs font-medium text-text-muted">
                {t("settings:manageCharacters.filter.createdDateRange", {
                  defaultValue: "Created date range"
                })}
              </p>
              <div className="w-full max-w-[30rem] space-y-1 lg:max-w-[26rem]">
                <div className="flex items-center justify-between text-[11px] text-text-subtle">
                  <span>{t("settings:manageCharacters.filter.from", { defaultValue: "From" })}</span>
                  <span>{t("settings:manageCharacters.filter.to", { defaultValue: "To" })}</span>
                </div>
                <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1.5">
                  <Input
                    size="small"
                    type="date"
                    className="w-full"
                    aria-label={t("settings:manageCharacters.filter.createdFromAriaLabel", {
                      defaultValue: "Filter characters created on or after"
                    })}
                    value={createdFromDate}
                    max={createdToDate || undefined}
                    onChange={(event) => setCreatedFromDate(event.target.value)}
                  />
                  <span className="text-xs text-text-subtle">
                    {t("settings:manageCharacters.filter.rangeSeparator", {
                      defaultValue: "to"
                    })}
                  </span>
                  <Input
                    size="small"
                    type="date"
                    className="w-full"
                    aria-label={t("settings:manageCharacters.filter.createdToAriaLabel", {
                      defaultValue: "Filter characters created on or before"
                    })}
                    value={createdToDate}
                    min={createdFromDate || undefined}
                    onChange={(event) => setCreatedToDate(event.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="rounded-md border border-border bg-surface2/30 p-2">
              <p className="mb-1 text-xs font-medium text-text-muted">
                {t("settings:manageCharacters.filter.updatedDateRange", {
                  defaultValue: "Updated date range"
                })}
              </p>
              <div className="w-full max-w-[30rem] space-y-1 lg:max-w-[26rem]">
                <div className="flex items-center justify-between text-[11px] text-text-subtle">
                  <span>{t("settings:manageCharacters.filter.from", { defaultValue: "From" })}</span>
                  <span>{t("settings:manageCharacters.filter.to", { defaultValue: "To" })}</span>
                </div>
                <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1.5">
                  <Input
                    size="small"
                    type="date"
                    className="w-full"
                    aria-label={t("settings:manageCharacters.filter.updatedFromAriaLabel", {
                      defaultValue: "Filter characters updated on or after"
                    })}
                    value={updatedFromDate}
                    max={updatedToDate || undefined}
                    onChange={(event) => setUpdatedFromDate(event.target.value)}
                  />
                  <span className="text-xs text-text-subtle">
                    {t("settings:manageCharacters.filter.rangeSeparator", {
                      defaultValue: "to"
                    })}
                  </span>
                  <Input
                    size="small"
                    type="date"
                    className="w-full"
                    aria-label={t("settings:manageCharacters.filter.updatedToAriaLabel", {
                      defaultValue: "Filter characters updated on or before"
                    })}
                    value={updatedToDate}
                    min={updatedFromDate || undefined}
                    onChange={(event) => setUpdatedToDate(event.target.value)}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 rounded-md border border-border bg-surface2/40 px-3 py-2">
            <Checkbox
              checked={matchAllTags}
              onChange={(e) => setMatchAllTags(e.target.checked)}>
              {t("settings:manageCharacters.filter.matchAll", {
                defaultValue: "Match all tags"
              })}
            </Checkbox>
            <Checkbox
              checked={hasConversationsOnly}
              onChange={(e) => setHasConversationsOnly(e.target.checked)}>
              {t("settings:manageCharacters.filter.hasConversations", {
                defaultValue: "Has conversations"
              })}
            </Checkbox>
            <Checkbox
              checked={favoritesOnly}
              onChange={(e) => setFavoritesOnly(e.target.checked)}>
              {t("settings:manageCharacters.filter.favoritesOnly", {
                defaultValue: "Favorites only"
              })}
            </Checkbox>
          </div>
        </div>
      )}
    </div>
  </>
)
