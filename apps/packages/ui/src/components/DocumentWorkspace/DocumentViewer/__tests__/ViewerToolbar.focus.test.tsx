import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { ViewerToolbar } from "../ViewerToolbar"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key,
  }),
}))

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Progress: () => <div data-testid="progress" />,
  Select: ({
    value,
    onChange,
    options = [],
    className,
  }: {
    value: string | number
    onChange?: (value: string | number) => void
    options?: Array<{ value: string | number; label: React.ReactNode }>
    className?: string
  }) => (
    <select
      className={className}
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
      aria-label="select"
    >
      {options.map((option) => (
        <option key={String(option.value)} value={option.value}>
          {typeof option.label === "string" ? option.label : String(option.value)}
        </option>
      ))}
    </select>
  ),
  Input: ({
    className,
    value,
    onChange,
    onBlur,
    ...rest
  }: {
    className?: string
    value?: number | string
    onChange?: React.ChangeEventHandler<HTMLInputElement>
    onBlur?: React.FocusEventHandler<HTMLInputElement>
  }) => (
    <input
      className={className}
      value={value}
      onChange={onChange}
      onBlur={onBlur}
      {...rest}
    />
  ),
}))

vi.mock("../TTSPanel", () => ({
  TTSPanel: () => <div data-testid="tts-panel" />,
}))

vi.mock("../EpubViewer/EpubSettingsPanel", () => ({
  EpubSettingsPanel: () => <div data-testid="epub-settings" />,
}))

describe("ViewerToolbar focus-visible contract", () => {
  it("applies focus-visible classes to non-shell toolbar controls", () => {
    render(
      <ViewerToolbar
        currentPage={2}
        totalPages={10}
        zoomLevel={100}
        viewMode="single"
        documentType="pdf"
        onPageChange={vi.fn()}
        onZoomChange={vi.fn()}
        onViewModeChange={vi.fn()}
        onPreviousPage={vi.fn()}
        onNextPage={vi.fn()}
      />
    )

    const controls = [
      screen.getByRole("button", { name: "Zoom out" }),
      screen.getByRole("button", { name: "Zoom in" }),
      screen.getByRole("button", { name: "Fit width" }),
      screen.getByRole("button", { name: "Previous" }),
      screen.getByRole("button", { name: "Next" }),
    ]

    for (const control of controls) {
      expect(control.className).toContain("focus-visible:ring-2")
      expect(control.className).toContain("focus-visible:ring-focus")
      expect(control.className).toContain("focus-visible:ring-offset-2")
      expect(control.className).toContain("focus-visible:ring-offset-bg")
    }
  })
})
