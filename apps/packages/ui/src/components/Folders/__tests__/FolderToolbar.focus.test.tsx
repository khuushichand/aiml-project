import React from "react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { FolderToolbar } from "../FolderToolbar"

const folderActions = vi.hoisted(() => ({
  setViewMode: vi.fn(),
  expandAllFolders: vi.fn(),
  collapseAllFolders: vi.fn(),
  refreshFromServer: vi.fn(),
  createFolder: vi.fn(),
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}))

vi.mock("antd", () => ({
  Button: ({ children, icon, className, loading: _loading, ...props }: any) => (
    <button className={className} {...props}>
      {icon}
      {children}
    </button>
  ),
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Dropdown: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Input: (props: any) => <input {...props} />,
  Modal: ({ open, children, title, footer }: any) =>
    open ? (
      <div role="dialog" aria-label={title}>
        {children}
        {footer}
      </div>
    ) : null,
}))

vi.mock("@/store/folder", () => ({
  useFolderActions: () => folderActions,
  useFolderViewMode: () => "folders",
  useFolderIsLoading: () => false,
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({ error: vi.fn() }),
}))

describe("FolderToolbar focus-visible contract", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("applies focus-visible classes to compact toolbar controls", () => {
    render(<FolderToolbar compact />)

    const controls = [
      screen.getByRole("button", { name: "common:dateView" }),
      screen.getByRole("button", { name: "common:newFolder" }),
      screen.getByRole("button", { name: "option:moreActions" }),
    ]

    for (const control of controls) {
      expect(control.className).toContain("focus-visible:ring-2")
      expect(control.className).toContain("focus-visible:ring-focus")
      expect(control.className).toContain("focus-visible:ring-offset-2")
      expect(control.className).toContain("focus-visible:ring-offset-bg")
    }
  })

  it("applies focus-visible classes to expanded toolbar controls", () => {
    render(<FolderToolbar />)

    const controls = [
      screen.getByRole("button", { name: "common:folders" }),
      screen.getByRole("button", { name: "common:date" }),
      screen.getByRole("button", { name: "common:newFolder" }),
      screen.getByRole("button", { name: "common:expandAll" }),
      screen.getByRole("button", { name: "common:collapseAll" }),
      screen.getByRole("button", { name: "common:refresh" }),
    ]

    for (const control of controls) {
      expect(control.className).toContain("focus-visible:ring-2")
      expect(control.className).toContain("focus-visible:ring-focus")
      expect(control.className).toContain("focus-visible:ring-offset-2")
      expect(control.className).toContain("focus-visible:ring-offset-bg")
    }
  })
})
