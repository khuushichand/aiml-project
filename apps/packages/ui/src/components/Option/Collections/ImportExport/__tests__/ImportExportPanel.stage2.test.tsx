import React from "react"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ImportExportPanel } from "../ImportExportPanel"
import { useCollectionsStore } from "@/store/collections"

const state = vi.hoisted(() => ({
  importReadingList: vi.fn(),
  getReadingImportJob: vi.fn(),
  listReadingImportJobs: vi.fn(),
  getReadingList: vi.fn(),
  getReadingItem: vi.fn(),
  getHighlights: vi.fn(),
  exportReadingList: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: unknown, vars?: Record<string, unknown>) => {
      const template =
        typeof fallback === "string"
          ? fallback
          : typeof key === "string"
            ? key
            : ""
      if (!vars) return template
      return template.replace(/\{\{(\w+)\}\}/g, (_match, group: string) => {
        const value = vars[group]
        return value == null ? "" : String(value)
      })
    }
  })
}))

vi.mock("@/hooks/useTldwApiClient", () => ({
  useTldwApiClient: () => ({
    importReadingList: state.importReadingList,
    getReadingImportJob: state.getReadingImportJob,
    listReadingImportJobs: state.listReadingImportJobs,
    getReadingList: state.getReadingList,
    getReadingItem: state.getReadingItem,
    getHighlights: state.getHighlights,
    exportReadingList: state.exportReadingList
  })
}))

vi.mock("@/hooks/useSelectionKeyboard", () => ({
  useSelectionKeyboard: () => ({
    focusedIndex: -1,
    handleItemClick: vi.fn(),
    handleItemToggle: vi.fn(),
    handleKeyDown: vi.fn(),
    listRef: { current: null }
  })
}))

vi.mock("antd", () => {
  const Button = ({ children, onClick, disabled, loading, ...rest }: any) => (
    <button
      type="button"
      disabled={Boolean(disabled) || Boolean(loading)}
      onClick={() => onClick?.()}
      {...rest}
    >
      {children}
    </button>
  )

  const Checkbox = ({ children, checked, onChange }: any) => (
    <label>
      <input
        type="checkbox"
        checked={Boolean(checked)}
        onChange={(event) => onChange?.({ target: { checked: event.currentTarget.checked } })}
      />
      <span>{children}</span>
    </label>
  )

  const RadioButton = ({ children, value, __groupValue, __onGroupChange }: any) => (
    <button
      type="button"
      aria-pressed={String(__groupValue) === String(value)}
      onClick={() => __onGroupChange?.({ target: { value } })}
    >
      {children}
    </button>
  )

  const RadioGroup = ({ value, onChange, children }: any) => (
    <div>
      {React.Children.map(children, (child: any) =>
        React.cloneElement(child, {
          __groupValue: value,
          __onGroupChange: onChange
        })
      )}
    </div>
  )

  const Radio = {
    Group: RadioGroup,
    Button: RadioButton
  }

  const Upload = {
    Dragger: ({ beforeUpload, disabled, children }: any) => (
      <div>
        {children}
        <input
          data-testid="import-upload-input"
          type="file"
          disabled={Boolean(disabled)}
          onChange={(event) => {
            const file = event.currentTarget.files?.[0]
            if (file) {
              beforeUpload?.(file)
            }
          }}
        />
      </div>
    )
  }

  const Card = ({ title, children }: any) => (
    <section>
      <div>{title}</div>
      {children}
    </section>
  )

  const Input = ({ value, onChange, placeholder, ...rest }: any) => (
    <input
      value={value ?? ""}
      placeholder={placeholder}
      onChange={(event) => onChange?.(event)}
      {...rest}
    />
  )

  const List: any = ({ dataSource = [], renderItem }: any) => (
    <div>{dataSource.map((item: any, index: number) => renderItem(item, index))}</div>
  )
  List.Item = ({ children, ...rest }: any) => <div {...rest}>{children}</div>

  const Empty: any = ({ description, children }: any) => (
    <div>
      <span>{description}</span>
      {children}
    </div>
  )
  Empty.PRESENTED_IMAGE_SIMPLE = null

  const Result = ({ title, subTitle, extra }: any) => (
    <div>
      <h3>{title}</h3>
      <p>{subTitle}</p>
      {extra}
    </div>
  )

  const Steps = () => <div data-testid="steps" />
  const Alert = ({ message, description }: any) => (
    <div>
      <span>{message}</span>
      {description ? <div>{description}</div> : null}
    </div>
  )
  const Spin = () => <div>loading</div>

  return {
    Alert,
    Button,
    Card,
    Checkbox,
    Empty,
    Input,
    List,
    Radio,
    Result,
    Spin,
    Steps,
    Upload,
    message: {
      success: vi.fn(),
      warning: vi.fn(),
      error: vi.fn()
    }
  }
})

describe("ImportExportPanel stage 2", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useCollectionsStore.getState().resetStore()

    state.getReadingList.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      size: 200
    })
    state.exportReadingList.mockResolvedValue({
      blob: new Blob(["{}"], { type: "application/x-ndjson" }),
      filename: "reading_export.jsonl"
    })
    state.getHighlights.mockResolvedValue([])
    state.getReadingItem.mockImplementation(async (id: string) => ({
      id,
      title: `Item ${id}`,
      favorite: false,
      tags: []
    }))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("polls reading import job lifecycle until completion", async () => {
    vi.useFakeTimers()

    state.importReadingList.mockResolvedValue({
      job_id: 42,
      job_uuid: "job-42",
      status: "queued"
    })
    state.getReadingImportJob
      .mockResolvedValueOnce({
        job_id: 42,
        job_uuid: "job-42",
        status: "processing",
        progress_percent: 20,
        progress_message: "Parsing import"
      })
      .mockResolvedValueOnce({
        job_id: 42,
        job_uuid: "job-42",
        status: "completed",
        progress_percent: 100,
        result: {
          source: "auto",
          imported: 3,
          updated: 1,
          skipped: 0,
          errors: []
        }
      })

    render(<ImportExportPanel />)

    fireEvent.click(screen.getByRole("button", { name: "collections:import.sources.auto.label" }))

    const uploadInput = screen.getByTestId("import-upload-input") as HTMLInputElement
    const file = new File(["{}"], "pocket.json", { type: "application/json" })
    fireEvent.change(uploadInput, { target: { files: [file] } })

    await waitFor(() => {
      expect(state.importReadingList).toHaveBeenCalledWith(
        expect.objectContaining({
          source: "auto",
          merge_tags: true
        })
      )
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000)
    })

    await waitFor(() => {
      expect(state.getReadingImportJob).toHaveBeenCalled()
      expect(screen.getByText("Import Complete")).toBeInTheDocument()
      expect(screen.getByText("Imported: 3, Updated: 1, Skipped: 0")).toBeInTheDocument()
    })
  })

  it("applies reading filters and include toggles to export requests", async () => {
    useCollectionsStore.setState({
      itemsSearch: "llm",
      filterStatus: "saved",
      filterTags: ["research"],
      filterFavorite: true,
      filterDomain: "example.com"
    })

    render(<ImportExportPanel />)

    await waitFor(() => {
      expect(state.getReadingList).toHaveBeenCalled()
    })

    fireEvent.click(screen.getByRole("button", { name: "Download Export" }))

    await waitFor(() => {
      expect(state.exportReadingList).toHaveBeenCalledWith(
        expect.objectContaining({
          format: "jsonl",
          q: "llm",
          status: ["saved"],
          tags: ["research"],
          favorite: true,
          domain: "example.com",
          include_highlights: false,
          include_notes: true
        })
      )
    })

    fireEvent.click(screen.getByLabelText("Include highlights"))
    fireEvent.click(screen.getByLabelText("Include notes"))
    fireEvent.click(screen.getByRole("button", { name: "Download Export" }))

    await waitFor(() => {
      expect(state.exportReadingList).toHaveBeenLastCalledWith(
        expect.objectContaining({
          include_highlights: true,
          include_notes: false
        })
      )
    })
  })
})
