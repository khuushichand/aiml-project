import React from "react"
import { Select } from "antd"
import { useTranslation } from "react-i18next"

import { useDebounce } from "@/hooks/useDebounce"
import { useGlobalFlashcardTagSuggestionsQuery } from "../hooks"

type FlashcardTagPickerProps = {
  value: string[]
  onChange: (value: string[]) => void
  active?: boolean
  disabled?: boolean
  placeholder?: string
  className?: string
  dataTestId?: string
}

const DEFAULT_WRAPPER_TEST_ID = "flashcard-tag-picker"
const SEARCH_DEBOUNCE_MS = 250

const normalizeTags = (tags: string[]) => {
  const seen = new Set<string>()
  const normalized: string[] = []

  for (const rawTag of tags) {
    const tag = rawTag.trim()
    if (!tag) continue

    const dedupeKey = tag.toLowerCase()
    if (seen.has(dedupeKey)) continue

    seen.add(dedupeKey)
    normalized.push(tag)
  }

  return normalized
}

export const FlashcardTagPicker: React.FC<FlashcardTagPickerProps> = ({
  value,
  onChange,
  active = true,
  disabled = false,
  placeholder,
  className,
  dataTestId
}) => {
  const { t } = useTranslation(["option"])
  const [dropdownOpen, setDropdownOpen] = React.useState(false)
  const [searchText, setSearchText] = React.useState("")
  const wrapperRef = React.useRef<HTMLDivElement>(null)
  const wrapperTestId = dataTestId ?? DEFAULT_WRAPPER_TEST_ID
  const searchInputTestId = `${wrapperTestId}-search-input`

  const debouncedSearchText = useDebounce(searchText, SEARCH_DEBOUNCE_MS)
  const normalizedValue = React.useMemo(() => normalizeTags(value ?? []), [value])
  const queryEnabled = active && dropdownOpen

  const tagSuggestionsQuery = useGlobalFlashcardTagSuggestionsQuery(debouncedSearchText, {
    enabled: queryEnabled,
    limit: 50
  })

  const options = React.useMemo(
    () =>
      (tagSuggestionsQuery.data?.items ?? []).map((item) => ({
        label: item.tag,
        value: item.tag
      })),
    [tagSuggestionsQuery.data]
  )

  React.useEffect(() => {
    const searchInput = wrapperRef.current?.querySelector<HTMLInputElement>("input.ant-select-input")
    if (searchInput && searchInput.getAttribute("data-testid") !== searchInputTestId) {
      searchInput.setAttribute("data-testid", searchInputTestId)
    }
  }, [searchInputTestId])

  const handleChange = React.useCallback(
    (nextValue: unknown) => {
      const nextTags = Array.isArray(nextValue) ? nextValue.map((tag) => String(tag)) : []
      onChange(normalizeTags(nextTags))
    },
    [onChange]
  )

  return (
    <div ref={wrapperRef} data-testid={wrapperTestId} className={className}>
      <Select
        mode="tags"
        value={normalizedValue}
        onChange={handleChange}
        open={dropdownOpen}
        onOpenChange={setDropdownOpen}
        showSearch
        searchValue={searchText}
        onSearch={setSearchText}
        filterOption={false}
        allowClear
        disabled={disabled}
        placeholder={
          placeholder ??
          t("option:flashcards.tagsPlaceholder", {
            defaultValue: "Add tags..."
          })
        }
        options={options}
        loading={Boolean(tagSuggestionsQuery.isLoading || tagSuggestionsQuery.isFetching)}
        notFoundContent={tagSuggestionsQuery.isError ? null : undefined}
      />
    </div>
  )
}

export default FlashcardTagPicker
