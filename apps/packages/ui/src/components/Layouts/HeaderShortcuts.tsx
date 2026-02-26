import React, { useEffect, useRef, useState, useCallback, useMemo } from "react"
import { createPortal } from "react-dom"
import { useTranslation } from "react-i18next"
import { NavLink, useLocation, useNavigate } from "react-router-dom"
import { useShortcut } from "@/hooks/useKeyboardShortcuts"
import { isMac } from "@/hooks/useKeyboardShortcuts"
import { useSetting } from "@/hooks/useSetting"
import {
  HEADER_SHORTCUTS_EXPANDED_SETTING,
  HEADER_SHORTCUT_SELECTION_SETTING
} from "@/services/settings/ui-settings"
import { Search } from "lucide-react"
import { cn } from "@/libs/utils"
import {
  HEADER_SHORTCUT_GROUPS,
  type HeaderShortcutGroup,
  type HeaderShortcutItem
} from "./header-shortcut-items"

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const ALL_CATEGORY = "__all__"
const META_LABEL = isMac ? "\u2318" : "Ctrl+"

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type ResolvedItem = {
  item: HeaderShortcutItem
  label: string
  groupId: string
  groupTitle: string
}

interface HeaderShortcutsProps {
  /** Whether to initially show shortcuts expanded */
  defaultExpanded?: boolean
  /** Additional CSS classes */
  className?: string
  /** Whether to render the toggle button (unused in modal mode, kept for API compat) */
  showToggle?: boolean
  /** Controlled expanded state — drives modal open/close */
  expanded?: boolean
  /** Controlled state updater */
  onExpandedChange?: (next: boolean) => void
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function HeaderShortcuts({
  defaultExpanded = false,
  expanded,
  onExpandedChange,
}: HeaderShortcutsProps) {
  const { t } = useTranslation(["option", "common", "settings"])
  const navigate = useNavigate()
  const location = useLocation()

  /* ---------- settings ---------- */
  const [shortcutsPreference, setShortcutsPreference] = useSetting(
    HEADER_SHORTCUTS_EXPANDED_SETTING
  )
  const [shortcutSelection] = useSetting(HEADER_SHORTCUT_SELECTION_SETTING)

  /* ---------- open state ---------- */
  const isControlled = typeof expanded === "boolean"
  const [openInternal, setOpenInternal] = useState(() =>
    Boolean(shortcutsPreference ?? defaultExpanded)
  )
  const open = isControlled ? expanded : openInternal

  const setOpen = useCallback(
    (next: boolean) => {
      if (isControlled) {
        onExpandedChange?.(next)
        return
      }
      setOpenInternal(next)
      void setShortcutsPreference(next).catch(() => {})
    },
    [isControlled, onExpandedChange, setShortcutsPreference]
  )

  // Sync with storage preference when uncontrolled
  useEffect(() => {
    if (isControlled) return
    setOpenInternal(Boolean(shortcutsPreference))
  }, [isControlled, shortcutsPreference])

  /* ---------- search + category ---------- */
  const [query, setQuery] = useState("")
  const [activeCategory, setActiveCategory] = useState(ALL_CATEGORY)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const previousPathRef = useRef(location.pathname)
  const triggerRef = useRef<HTMLElement | null>(null)

  /* ---------- resolved items (respecting user selection) ---------- */
  const shortcutSelectionSet = useMemo(
    () => new Set(shortcutSelection),
    [shortcutSelection]
  )

  const resolvedGroups = useMemo(() => {
    return HEADER_SHORTCUT_GROUPS.map((group) => ({
      ...group,
      title: t(group.titleKey, group.titleDefault),
      items: group.items
        .filter((item) => shortcutSelectionSet.has(item.id))
        .map(
          (item): ResolvedItem => ({
            item,
            label: t(item.labelKey, item.labelDefault),
            groupId: group.id,
            groupTitle: t(group.titleKey, group.titleDefault)
          })
        )
    })).filter((g) => g.items.length > 0)
  }, [shortcutSelectionSet, t])

  const allItems = useMemo(
    () => resolvedGroups.flatMap((g) => g.items),
    [resolvedGroups]
  )

  /* ---------- fuzzy filter ---------- */
  const filteredItems = useMemo(() => {
    let items = allItems
    if (query) {
      const q = query.toLowerCase()
      items = items.filter((ri) => ri.label.toLowerCase().includes(q))
    }
    if (activeCategory !== ALL_CATEGORY) {
      items = items.filter((ri) => ri.groupId === activeCategory)
    }
    return items
  }, [allItems, query, activeCategory])

  /* ---------- match counts per category ---------- */
  const matchCounts = useMemo(() => {
    const queryFiltered = query
      ? allItems.filter((ri) => ri.label.toLowerCase().includes(query.toLowerCase()))
      : allItems
    const counts: Record<string, number> = { [ALL_CATEGORY]: queryFiltered.length }
    for (const g of resolvedGroups) {
      counts[g.id] = queryFiltered.filter((ri) => ri.groupId === g.id).length
    }
    return counts
  }, [allItems, query, resolvedGroups])

  /* ---------- grouped items for right panel ---------- */
  const groupedFiltered = useMemo(() => {
    const groups: { id: string; title: string; items: ResolvedItem[] }[] = []
    for (const g of resolvedGroups) {
      const items = filteredItems.filter((ri) => ri.groupId === g.id)
      if (items.length > 0) {
        groups.push({ id: g.id, title: g.title, items })
      }
    }
    return groups
  }, [filteredItems, resolvedGroups])

  /* ---------- flat index for keyboard nav ---------- */
  const flatItems = useMemo(
    () => groupedFiltered.flatMap((g) => g.items),
    [groupedFiltered]
  )

  // Clamp selection index when items change
  useEffect(() => {
    setSelectedIndex((prev) => {
      if (flatItems.length === 0) return 0
      return Math.min(prev, flatItems.length - 1)
    })
  }, [flatItems])

  // Reset selection on query or category change
  useEffect(() => {
    setSelectedIndex(0)
  }, [query, activeCategory])

  /* ---------- toggle shortcut (Shift+?) ---------- */
  const handleToggle = useCallback(() => {
    setOpen(!open)
  }, [open, setOpen])

  useShortcut({
    key: "?",
    modifiers: ["shift"],
    action: handleToggle,
    description: "Toggle keyboard shortcuts",
    allowInInput: false,
  })

  /* ---------- close on route change ---------- */
  useEffect(() => {
    if (previousPathRef.current !== location.pathname) {
      previousPathRef.current = location.pathname
      if (open) {
        setOpen(false)
      }
    }
  }, [location.pathname, open, setOpen])

  /* ---------- focus on open, restore on close ---------- */
  useEffect(() => {
    if (open) {
      triggerRef.current = document.activeElement as HTMLElement | null
      setQuery("")
      setActiveCategory(ALL_CATEGORY)
      setSelectedIndex(0)
      requestAnimationFrame(() => inputRef.current?.focus())
    } else {
      triggerRef.current?.focus()
      triggerRef.current = null
    }
  }, [open])

  /* ---------- scroll selected into view ---------- */
  useEffect(() => {
    if (!listRef.current) return
    const selected = listRef.current.querySelector('[data-selected="true"]')
    if (typeof selected?.scrollIntoView === "function") {
      selected.scrollIntoView({ block: "nearest" })
    }
  }, [selectedIndex])

  /* ---------- navigation ---------- */
  const navigateTo = useCallback(
    (to: string) => {
      navigate(to)
      setOpen(false)
    },
    [navigate, setOpen]
  )

  /* ---------- keyboard (meta+1-9 shortcuts) ---------- */
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      const digit = parseInt(e.key, 10)
      if (digit >= 1 && digit <= 9 && (e.metaKey || e.ctrlKey)) {
        const target = allItems.find((ri) => ri.item.shortcutIndex === digit)
        if (target) {
          e.preventDefault()
          navigateTo(target.item.to)
        }
      }
    }
    window.addEventListener("keydown", handler, true)
    return () => window.removeEventListener("keydown", handler, true)
  }, [open, allItems, navigateTo])

  /* ---------- keyboard navigation within modal ---------- */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Tab trapping
      if (e.key === "Tab") {
        const modal = e.currentTarget
        const focusable = Array.from(
          modal.querySelectorAll<HTMLElement>(
            'input, a[href], button, [tabindex]:not([tabindex="-1"])'
          )
        ).filter((el) => !el.hasAttribute("disabled"))
        if (focusable.length === 0) return
        const current = focusable.indexOf(document.activeElement as HTMLElement)
        let next = current
        if (e.shiftKey) {
          next = current <= 0 ? focusable.length - 1 : current - 1
        } else {
          next = current >= focusable.length - 1 ? 0 : current + 1
        }
        e.preventDefault()
        focusable[next]?.focus()
        return
      }

      switch (e.key) {
        case "Escape":
          e.preventDefault()
          setOpen(false)
          break
        case "ArrowDown":
          e.preventDefault()
          setSelectedIndex((i) =>
            flatItems.length === 0 ? 0 : Math.min(i + 1, flatItems.length - 1)
          )
          break
        case "ArrowUp":
          e.preventDefault()
          setSelectedIndex((i) =>
            flatItems.length === 0 ? 0 : Math.max(i - 1, 0)
          )
          break
        case "Enter":
          e.preventDefault()
          if (flatItems[selectedIndex]) {
            navigateTo(flatItems[selectedIndex].item.to)
          }
          break
      }
    },
    [flatItems, selectedIndex, setOpen, navigateTo]
  )

  /* ---------- render ---------- */
  if (!open) return null
  if (typeof document === "undefined") return null

  const showGroupHeaders = activeCategory === ALL_CATEGORY

  const modalContent = (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
        onClick={() => setOpen(false)}
      />

      {/* Modal */}
      <div
        className="fixed left-1/2 top-[15vh] z-50 flex w-[calc(100%-2rem)] max-w-[640px] -translate-x-1/2 flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-modal"
        style={{ maxHeight: "70vh" }}
        role="dialog"
        aria-modal="true"
        aria-label={t("option:header.showShortcuts", "Shortcuts")}
        onKeyDown={handleKeyDown}
      >
        {/* Search bar */}
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          <Search className="size-5 shrink-0 text-text-subtle" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t(
              "option:header.launcherSearchPlaceholder",
              "Search pages..."
            )}
            className="flex-1 bg-transparent text-base text-text placeholder:text-text-subtle focus:outline-none"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
          />
          <kbd className="hidden items-center rounded border border-border bg-surface2 px-1.5 py-0.5 text-xs text-text-subtle sm:flex">
            Esc
          </kbd>
        </div>

        {/* Two-panel body */}
        <div className="flex min-h-0 flex-1">
          {/* Left sidebar */}
          <nav
            className="flex w-44 shrink-0 flex-col gap-0.5 overflow-y-auto border-r border-border p-2"
            aria-label={t("option:header.launcherCategories", "Categories")}
          >
            {/* "All" category */}
            <button
              type="button"
              onClick={() => setActiveCategory(ALL_CATEGORY)}
              className={cn(
                "flex items-center justify-between rounded-md px-3 py-1.5 text-left text-sm transition",
                activeCategory === ALL_CATEGORY
                  ? "bg-primary/10 font-medium text-primary"
                  : "text-text-muted hover:bg-surface2 hover:text-text"
              )}
            >
              <span>{t("option:header.launcherAll", "All")}</span>
              {query && (
                <span className="ml-1 text-xs text-text-subtle">
                  {matchCounts[ALL_CATEGORY] ?? 0}
                </span>
              )}
            </button>

            {resolvedGroups.map((group) => {
              const count = matchCounts[group.id] ?? 0
              const isActive = activeCategory === group.id
              const isDimmed = query !== "" && count === 0
              return (
                <button
                  key={group.id}
                  type="button"
                  onClick={() => setActiveCategory(group.id)}
                  className={cn(
                    "flex items-center justify-between rounded-md px-3 py-1.5 text-left text-sm transition",
                    isActive
                      ? "bg-primary/10 font-medium text-primary"
                      : isDimmed
                        ? "text-text-subtle opacity-50 hover:bg-surface2"
                        : "text-text-muted hover:bg-surface2 hover:text-text"
                  )}
                >
                  <span className="truncate">{group.title}</span>
                  {query && (
                    <span className="ml-1 shrink-0 text-xs text-text-subtle">
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>

          {/* Right panel */}
          <div
            ref={listRef}
            className="flex-1 overflow-y-auto p-2"
            role="listbox"
            aria-label={t("option:header.launcherItems", "Pages")}
          >
            {flatItems.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-text-subtle">
                {t(
                  "option:header.launcherNoResults",
                  "No pages match your search"
                )}
              </div>
            ) : (
              groupedFiltered.map((group) => (
                <div key={group.id} className="mb-2">
                  {showGroupHeaders && (
                    <div className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-text-subtle">
                      {group.title}
                    </div>
                  )}
                  {group.items.map((ri) => {
                    const globalIdx = flatItems.indexOf(ri)
                    const isSelected = globalIdx === selectedIndex
                    const Icon = ri.item.icon
                    const isCurrentRoute =
                      location.pathname === ri.item.to ||
                      (ri.item.to === "/" && location.pathname === "/chat")

                    return (
                      <NavLink
                        key={ri.item.id}
                        to={ri.item.to}
                        onClick={(e) => {
                          e.preventDefault()
                          navigateTo(ri.item.to)
                        }}
                        onMouseEnter={() => setSelectedIndex(globalIdx)}
                        data-selected={isSelected}
                        role="option"
                        aria-selected={isSelected}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                          isCurrentRoute && "border-l-2 border-primary bg-primary/5",
                          isSelected
                            ? "bg-surface2 text-text"
                            : "text-text hover:bg-surface2"
                        )}
                      >
                        <span
                          className={cn(
                            "shrink-0",
                            isSelected || isCurrentRoute
                              ? "text-primary"
                              : "text-text-subtle"
                          )}
                        >
                          <Icon className="size-4" aria-hidden="true" />
                        </span>
                        <span className="min-w-0 flex-1 truncate">
                          {ri.label}
                        </span>
                        {ri.item.shortcutIndex != null && (
                          <kbd className="ml-auto shrink-0 rounded border border-border bg-surface2 px-1.5 py-0.5 text-xs text-text-subtle">
                            {META_LABEL}{ri.item.shortcutIndex}
                          </kbd>
                        )}
                      </NavLink>
                    )
                  })}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border px-4 py-2 text-xs text-text-subtle">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-border bg-surface2 px-1">
                &uarr;
              </kbd>
              <kbd className="rounded border border-border bg-surface2 px-1">
                &darr;
              </kbd>
              <span className="ml-1">
                {t("option:header.launcherNavigate", "navigate")}
              </span>
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-border bg-surface2 px-1">
                &crarr;
              </kbd>
              <span className="ml-1">
                {t("option:header.launcherSelect", "select")}
              </span>
            </span>
          </div>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-border bg-surface2 px-1">
              &lsaquo;?
            </kbd>
            <span className="ml-1">
              {t("option:header.launcherToggle", "toggle")}
            </span>
          </span>
        </div>
      </div>
    </>
  )

  return createPortal(modalContent, document.body)
}

export default HeaderShortcuts
