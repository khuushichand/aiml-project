import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { TimelineToolbar } from "../TimelineToolbar"

const timelineState = vi.hoisted(() => ({
  graph: { nodes: [], edges: [] },
  searchQuery: "timeline-query",
  searchResults: [],
  searchMode: "fragments",
  settings: {
    layoutDirection: "TB",
    showLegend: false,
    zoomLevel: 1,
    minZoom: 0.5,
    maxZoom: 2,
  },
  isLoading: false,
  error: null,
  setSearchQuery: vi.fn(),
  setSearchMode: vi.fn(),
  clearSearch: vi.fn(),
  refreshGraph: vi.fn(),
  toggleLayoutDirection: vi.fn(),
  expandAllSwipes: vi.fn(),
  collapseAllSwipes: vi.fn(),
  updateSettings: vi.fn(),
  closeTimeline: vi.fn(),
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key,
  }),
}))

vi.mock("@/i18n/translateMessage", () => ({
  translateMessage: (
    _t: unknown,
    _key: string,
    fallback: string,
    vars?: Record<string, string>
  ) => fallback.replace(/\{\{(\w+)\}\}/g, (_match, name) => vars?.[name] ?? ""),
}))

vi.mock("antd", () => {
  const Button = ({ children, icon, className, ...props }: any) => (
    <button className={className} {...props}>
      {icon}
      {children}
    </button>
  )
  Button.Group = ({ children }: { children: React.ReactNode }) => <div>{children}</div>

  const Space = ({ children }: { children: React.ReactNode }) => <div>{children}</div>
  Space.Compact = ({ children }: { children: React.ReactNode }) => <div>{children}</div>

  return {
    Input: ({ prefix, suffix, className, allowClear: _allowClear, ...props }: any) => (
      <div>
        {prefix}
        <input className={className} {...props} />
        {suffix}
      </div>
    ),
    Button,
    Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    Space,
    Select: ({
      value,
      onChange,
      options = [],
      style,
      ...props
    }: {
      value: string
      onChange?: (value: string) => void
      options?: Array<{ value: string; label: React.ReactNode }>
      style?: React.CSSProperties
    }) => (
      <select
        value={value}
        onChange={(event) => onChange?.(event.target.value)}
        style={style}
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {typeof option.label === "string" ? option.label : option.value}
          </option>
        ))}
      </select>
    ),
    Badge: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    Typography: {
      Text: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
    },
  }
})

vi.mock("@/store/timeline", () => ({
  useTimelineStore: (selector: (state: typeof timelineState) => unknown) =>
    selector(timelineState),
}))

vi.mock("zustand/react/shallow", () => ({
  useShallow: (selector: unknown) => selector,
}))

describe("TimelineToolbar focus-visible contract", () => {
  it("applies focus-visible classes to toolbar action controls", () => {
    render(<TimelineToolbar />)

    const controls = [
      screen.getByRole("button", { name: "Close timeline" }),
      screen.getByRole("button", { name: "Clear search" }),
      screen.getByRole("button", { name: "Refresh graph" }),
      screen.getByRole("button", { name: "Switch to horizontal layout" }),
      screen.getByRole("button", { name: "Expand all alternatives" }),
      screen.getByRole("button", { name: "Collapse all alternatives" }),
      screen.getByRole("button", { name: "Show legend" }),
      screen.getByRole("button", { name: "Zoom in" }),
      screen.getByRole("button", { name: "Zoom out" }),
    ]

    for (const control of controls) {
      expect(control.className).toContain("focus-visible:ring-2")
      expect(control.className).toContain("focus-visible:ring-focus")
      expect(control.className).toContain("focus-visible:ring-offset-2")
      expect(control.className).toContain("focus-visible:ring-offset-bg")
    }
  })
})
