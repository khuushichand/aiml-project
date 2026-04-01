import React from "react"

import type { VisualStyleRecord } from "@/services/tldw/TldwApiClient"

type VisualStylePickerProps = {
  label: string
  value: string
  styles: VisualStyleRecord[]
  onChange: (value: string) => void
  disabled?: boolean
  loading?: boolean
  description?: string
}

type ParsedStyleValue = {
  visualStyleId: string | null
  visualStyleScope: string | null
}

const BUILTIN_CATEGORY_ORDER = [
  "legacy",
  "educational",
  "technical",
  "narrative",
  "playful",
  "nostalgic"
] as const

const BUILTIN_CATEGORY_LABELS: Record<(typeof BUILTIN_CATEGORY_ORDER)[number], string> = {
  legacy: "Existing built-ins",
  educational: "Educational and Explainer",
  technical: "Technical and Engineering",
  narrative: "Narrative and Strategic",
  playful: "Playful and Tactile",
  nostalgic: "Nostalgic and Artistic"
}

const encodeVisualStyleValue = (styleId: string | null, styleScope: string | null): string =>
  styleId && styleScope ? `${styleScope}::${styleId}` : ""

const parseVisualStyleValue = (value: string): ParsedStyleValue => {
  if (!value) {
    return { visualStyleId: null, visualStyleScope: null }
  }
  const separatorIndex = value.indexOf("::")
  if (separatorIndex === -1) {
    return { visualStyleId: null, visualStyleScope: null }
  }
  const visualStyleScope = value.slice(0, separatorIndex).trim()
  const visualStyleId = value.slice(separatorIndex + 2).trim()
  if (!visualStyleScope || !visualStyleId) {
    return { visualStyleId: null, visualStyleScope: null }
  }
  return { visualStyleId, visualStyleScope }
}

const normalizeSearchText = (value: unknown): string => {
  if (typeof value === "string") {
    return value.trim().toLowerCase()
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value).toLowerCase()
  }
  return ""
}

const normalizeCategoryKey = (value: string | null | undefined): string | null => {
  if (typeof value !== "string") {
    return null
  }
  const normalized = value.trim().toLowerCase()
  return normalized.length > 0 ? normalized : null
}

const getBuiltInCategoryLabel = (category: string | null | undefined): string => {
  const normalized = normalizeCategoryKey(category)
  if (!normalized) {
    return "Built-in styles"
  }
  return (
    BUILTIN_CATEGORY_LABELS[normalized as keyof typeof BUILTIN_CATEGORY_LABELS] ||
    (typeof category === "string" ? category.trim() : "Built-in styles")
  )
}

const getBuiltInCategoryOrder = (category: string | null | undefined): number => {
  const normalized = normalizeCategoryKey(category)
  if (!normalized) {
    return BUILTIN_CATEGORY_ORDER.length
  }
  const index = BUILTIN_CATEGORY_ORDER.indexOf(
    normalized as (typeof BUILTIN_CATEGORY_ORDER)[number]
  )
  return index === -1 ? BUILTIN_CATEGORY_ORDER.length : index
}

const buildSearchText = (style: VisualStyleRecord): string => {
  const pieces = [
    style.id,
    style.name,
    style.scope,
    style.description || "",
    style.category || "",
    style.scope === "builtin" ? getBuiltInCategoryLabel(style.category) : "",
    style.guide_number ?? "",
    ...(style.tags || []),
    ...(style.best_for || [])
  ]
  return pieces.map(normalizeSearchText).filter(Boolean).join(" ")
}

const describeBestFor = (style: VisualStyleRecord): string | null => {
  if (!style.best_for?.length) {
    return null
  }
  return style.best_for.join(", ")
}

const renderChips = (style: VisualStyleRecord): React.ReactNode => {
  const chips: Array<{ key: string; label: string }> = []
  if (style.scope === "builtin") {
    chips.push({ key: "scope", label: "Built-in" })
  } else {
    chips.push({ key: "scope", label: "Custom" })
  }
  if (style.scope === "builtin" && style.category) {
    chips.push({ key: "category", label: getBuiltInCategoryLabel(style.category) })
  }
  if (style.scope === "builtin" && typeof style.guide_number === "number") {
    chips.push({ key: "guide_number", label: `Guide ${style.guide_number}` })
  }
  for (const tag of (style.tags || []).slice(0, 3)) {
    chips.push({ key: `tag:${tag}`, label: tag })
  }
  return chips.map((chip) => (
    <span
      key={chip.key}
      className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600"
    >
      {chip.label}
    </span>
  ))
}

type BuiltInStyleGroup = {
  categoryKey: string | null
  label: string
  styles: VisualStyleRecord[]
}

const groupBuiltInStyles = (styles: VisualStyleRecord[]): BuiltInStyleGroup[] => {
  const groups = new Map<string, BuiltInStyleGroup>()
  for (const style of styles) {
    const categoryKey = normalizeCategoryKey(style.category)
    const groupKey = categoryKey || "__uncategorized__"
    const existingGroup = groups.get(groupKey)
    if (existingGroup) {
      existingGroup.styles.push(style)
      continue
    }
    groups.set(groupKey, {
      categoryKey,
      label: getBuiltInCategoryLabel(style.category),
      styles: [style]
    })
  }

  return [...groups.values()]
    .map((group) => ({
      ...group,
      styles: [...group.styles].sort((left, right) => {
        const leftGuide = typeof left.guide_number === "number" ? left.guide_number : Number.POSITIVE_INFINITY
        const rightGuide = typeof right.guide_number === "number" ? right.guide_number : Number.POSITIVE_INFINITY
        if (leftGuide !== rightGuide) {
          return leftGuide - rightGuide
        }
        return left.name.localeCompare(right.name)
      })
    }))
    .sort((leftGroup, rightGroup) => {
      const orderDelta =
        getBuiltInCategoryOrder(leftGroup.categoryKey) - getBuiltInCategoryOrder(rightGroup.categoryKey)
      if (orderDelta !== 0) {
        return orderDelta
      }
      return leftGroup.label.localeCompare(rightGroup.label)
    })
}

const toDomIdFragment = (value: string): string =>
  value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "style-group"

export const VisualStylePicker: React.FC<VisualStylePickerProps> = ({
  label,
  value,
  styles,
  onChange,
  disabled = false,
  loading = false,
  description
}) => {
  const [searchTerm, setSearchTerm] = React.useState("")
  const deferredSearchTerm = React.useDeferredValue(searchTerm)

  const selectedValue = React.useMemo(() => parseVisualStyleValue(value), [value])
  const selectedStyle = React.useMemo(
    () =>
      styles.find(
        (style) =>
          style.id === selectedValue.visualStyleId &&
          style.scope === selectedValue.visualStyleScope
      ) || null,
    [selectedValue.visualStyleId, selectedValue.visualStyleScope, styles]
  )

  const filteredStyles = React.useMemo(() => {
    const query = deferredSearchTerm.trim().toLowerCase()
    if (!query) {
      return styles
    }
    return styles.filter((style) => buildSearchText(style).includes(query))
  }, [deferredSearchTerm, styles])

  const builtInStyles = React.useMemo(
    () => filteredStyles.filter((style) => style.scope === "builtin"),
    [filteredStyles]
  )
  const customStyles = React.useMemo(
    () => filteredStyles.filter((style) => style.scope !== "builtin"),
    [filteredStyles]
  )

  const groupedBuiltInStyles = React.useMemo(() => groupBuiltInStyles(builtInStyles), [builtInStyles])

  const handleChange = React.useCallback(
    (nextValue: string) => {
      if (disabled || loading) {
        return
      }
      onChange(nextValue)
    },
    [disabled, loading, onChange]
  )

  return (
    <div className="space-y-3">
      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="presentation-studio-visual-style-search"
        >
          {label}
        </label>
        {description ? <p className="text-sm text-slate-600">{description}</p> : null}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3">
          <label className="sr-only" htmlFor="presentation-studio-visual-style-search">
            Search visual styles
          </label>
          <input
            id="presentation-studio-visual-style-search"
            type="search"
            role="searchbox"
            aria-label="Search visual styles"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search by name, category, tags, or best-for"
            disabled={disabled || loading}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100"
          />
        </div>

        <div className="border-b border-slate-200 px-4 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Selected preset
              </p>
              <p className="mt-1 text-sm font-medium text-slate-900">
                {selectedStyle?.name || "No visual style preset"}
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {selectedStyle?.description ||
                  "Select a built-in or custom style to update deck appearance defaults and future generated slides."}
              </p>
            </div>
            <button
              type="button"
              onClick={() => handleChange("")}
              disabled={disabled || loading}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              No visual style preset
            </button>
          </div>
        </div>

        <div className="max-h-[34rem] space-y-5 overflow-y-auto px-4 py-4">
          {loading ? (
            <p className="text-sm text-slate-600">Loading visual styles…</p>
          ) : filteredStyles.length === 0 ? (
            <p className="text-sm text-slate-600">
              No visual styles match “{deferredSearchTerm.trim()}”.
            </p>
          ) : (
            <>
              {groupedBuiltInStyles.map((group) => (
                <section
                  key={group.categoryKey || group.label}
                  role="region"
                  aria-labelledby={`visual-style-picker-${toDomIdFragment(group.label)}`}
                  className="space-y-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h3
                      id={`visual-style-picker-${toDomIdFragment(group.label)}`}
                      className="text-sm font-semibold text-slate-900"
                    >
                      {group.label}
                    </h3>
                    <span className="text-xs uppercase tracking-wide text-slate-500">
                      {group.styles.length} style{group.styles.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    {group.styles.map((style) => {
                      const isSelected =
                        selectedValue.visualStyleId === style.id &&
                        selectedValue.visualStyleScope === style.scope
                      const bestForText = describeBestFor(style)
                      return (
                        <button
                          type="button"
                          key={`${style.scope}:${style.id}`}
                          aria-pressed={isSelected}
                          disabled={disabled || loading}
                          onClick={() => handleChange(encodeVisualStyleValue(style.id, style.scope))}
                          className={`rounded-xl border p-4 text-left transition outline-none focus-visible:ring-2 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60 ${
                            isSelected
                              ? "border-sky-400 bg-sky-50 shadow-sm"
                              : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-slate-900">{style.name}</p>
                              <p className="mt-1 text-sm text-slate-600">
                                {style.description ||
                                  "No description was provided for this preset."}
                              </p>
                            </div>
                            {isSelected ? (
                              <span className="rounded-full bg-sky-600 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-white">
                                Selected
                              </span>
                            ) : null}
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">{renderChips(style)}</div>
                          {bestForText ? (
                            <p className="mt-3 text-xs text-slate-500">
                              <span className="font-semibold uppercase tracking-wide">
                                Best for
                              </span>{" "}
                              {bestForText}
                            </p>
                          ) : null}
                        </button>
                      )
                    })}
                  </div>
                </section>
              ))}

              {customStyles.length > 0 ? (
                <section
                  role="region"
                  aria-labelledby="visual-style-picker-custom"
                  className="space-y-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h3
                      id="visual-style-picker-custom"
                      className="text-sm font-semibold text-slate-900"
                    >
                      Custom styles
                    </h3>
                    <span className="text-xs uppercase tracking-wide text-slate-500">
                      {customStyles.length} style{customStyles.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    {customStyles.map((style) => {
                      const isSelected =
                        selectedValue.visualStyleId === style.id &&
                        selectedValue.visualStyleScope === style.scope
                      return (
                        <button
                          type="button"
                          key={`${style.scope}:${style.id}`}
                          aria-pressed={isSelected}
                          disabled={disabled || loading}
                          onClick={() => handleChange(encodeVisualStyleValue(style.id, style.scope))}
                          className={`rounded-xl border p-4 text-left transition outline-none focus-visible:ring-2 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60 ${
                            isSelected
                              ? "border-sky-400 bg-sky-50 shadow-sm"
                              : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-slate-900">{style.name}</p>
                              <p className="mt-1 text-sm text-slate-600">
                                {style.description ||
                                  "No description was provided for this preset."}
                              </p>
                            </div>
                            {isSelected ? (
                              <span className="rounded-full bg-sky-600 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-white">
                                Selected
                              </span>
                            ) : null}
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">{renderChips(style)}</div>
                        </button>
                      )
                    })}
                  </div>
                </section>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
