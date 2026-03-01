type AdvancedFiltersProps = {
  filterText: string
  onFilterTextChange: (value: string) => void
  totalCount: number
  selectedCount: number
}

export function AdvancedFilters({
  filterText,
  onFilterTextChange,
  totalCount,
  selectedCount
}: AdvancedFiltersProps) {
  return (
    <section className="space-y-2">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Filters</h3>
        <span className="text-xs text-text-subtle">
          {selectedCount}/{totalCount} selected
        </span>
      </header>
      <input
        type="search"
        value={filterText}
        onChange={(event) => onFilterTextChange(event.target.value)}
        placeholder="Filter files"
        className="w-full rounded border px-3 py-1.5 text-sm"
      />
    </section>
  )
}
