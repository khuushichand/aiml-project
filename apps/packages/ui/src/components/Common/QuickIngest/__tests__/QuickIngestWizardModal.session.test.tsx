import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  startQuickIngestSession: vi.fn(),
  submitQuickIngestBatch: vi.fn(),
  cancelQuickIngestSession: vi.fn(),
  runtimeListeners: [] as Array<(message: any) => void>,
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
            [k: string]: unknown
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      return defaultValueOrOptions?.defaultValue || key
    },
  }),
}))

vi.mock("antd", () => ({
  Modal: Object.assign(
    ({ children, open, onCancel, className, title }: any) =>
      open ? (
        <div role="dialog" className={className}>
          <div className="ant-modal-content">
            <h2>{title}</h2>
            <button onClick={onCancel}>Close</button>
            {children}
          </div>
        </div>
      ) : null,
    {
      confirm: vi.fn(),
      destroyAll: vi.fn(),
    }
  ),
  Button: ({ children, onClick, disabled, ...props }: any) => (
    <button onClick={onClick} disabled={disabled} {...props}>
      {children}
    </button>
  ),
  Switch: ({ checked, onChange, ...props }: any) => (
    <input
      type="checkbox"
      checked={checked}
      onChange={(event) => onChange?.(event.target.checked)}
      {...props}
    />
  ),
  Select: ({ value, onChange, options, ...props }: any) => (
    <select value={value} onChange={(event) => onChange?.(event.target.value)} {...props}>
      {(options || []).map((option: any) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
  Radio: Object.assign(
    ({ children, value, checked, onChange, ...props }: any) => (
      <label>
        <input
          type="radio"
          value={value}
          checked={checked}
          onChange={onChange}
          {...props}
        />
        {children}
      </label>
    ),
    {
      Group: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    }
  ),
  Collapse: ({ items }: any) => (
    <div>{items?.map((item: any) => <div key={item.key}>{item.children}</div>)}</div>
  ),
}))

vi.mock("lucide-react", () => {
  const icon = (name: string) => (props: any) => (
    <span data-icon={name} aria-hidden={props?.["aria-hidden"]} />
  )
  return {
    ArrowLeft: icon("ArrowLeft"),
    ArrowRight: icon("ArrowRight"),
    ChevronDown: icon("ChevronDown"),
    Minimize2: icon("Minimize2"),
    XCircle: icon("XCircle"),
    Info: icon("Info"),
  }
})

vi.mock("wxt/browser", () => ({
  browser: {
    runtime: {
      onMessage: {
        addListener: (listener: (message: any) => void) => {
          mocks.runtimeListeners.push(listener)
        },
        removeListener: (listener: (message: any) => void) => {
          const index = mocks.runtimeListeners.indexOf(listener)
          if (index >= 0) {
            mocks.runtimeListeners.splice(index, 1)
          }
        },
      },
    },
  },
}))

vi.mock("@/services/tldw/quick-ingest-batch", () => ({
  startQuickIngestSession: (...args: unknown[]) => mocks.startQuickIngestSession(...args),
  submitQuickIngestBatch: (...args: unknown[]) => mocks.submitQuickIngestBatch(...args),
  cancelQuickIngestSession: (...args: unknown[]) => mocks.cancelQuickIngestSession(...args),
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    initialize: vi.fn().mockResolvedValue(undefined),
  },
}))

vi.mock("@/components/Common/QuickIngest/IngestWizardStepper", () => ({
  IngestWizardStepper: () => <div data-testid="wizard-stepper" />,
}))

vi.mock("@/components/Common/QuickIngest/AddContentStep", async () => {
  const actual = await vi.importActual<
    typeof import("@/components/Common/QuickIngest/IngestWizardContext")
  >("@/components/Common/QuickIngest/IngestWizardContext")
  return {
    AddContentStep: ({ onQuickProcess }: { onQuickProcess?: () => void }) => {
      const { setQueueItems } = actual.useIngestWizard()
      return (
        <button
          onClick={() => {
            setQueueItems([
              {
                id: "queued-url-1",
                url: "https://example.com/article",
                detectedType: "web",
                icon: "Globe",
                fileSize: 0,
                validation: { valid: true },
              },
            ])
            onQuickProcess?.()
          }}
        >
          Queue And Process
        </button>
      )
    },
  }
})

vi.mock("@/components/Common/QuickIngest/ReviewStep", () => ({
  ReviewStep: () => <div data-testid="wizard-review" />,
}))

vi.mock("@/components/Common/QuickIngest/ProcessingStep", async () => {
  const actual = await vi.importActual<
    typeof import("@/components/Common/QuickIngest/IngestWizardContext")
  >("@/components/Common/QuickIngest/IngestWizardContext")
  return {
    ProcessingStep: () => {
      const { state } = actual.useIngestWizard()
      return (
        <div data-testid="wizard-processing">
          {state.processingState.status}:{state.processingState.perItemProgress.length}
        </div>
      )
    },
  }
})

vi.mock("@/components/Common/QuickIngest/WizardResultsStep", async () => {
  const actual = await vi.importActual<
    typeof import("@/components/Common/QuickIngest/IngestWizardContext")
  >("@/components/Common/QuickIngest/IngestWizardContext")
  return {
    WizardResultsStep: () => {
      const { state } = actual.useIngestWizard()
      return (
        <div data-testid="wizard-results">
          {state.processingState.status}:{state.results.length}
        </div>
      )
    },
  }
})

vi.mock("@/components/Common/QuickIngest/FloatingProgressWidget", () => ({
  FloatingProgressWidget: () => null,
}))

import { QuickIngestWizardModal } from "@/components/Common/QuickIngestWizardModal"

const emitRuntimeMessage = (message: any) => {
  for (const listener of [...mocks.runtimeListeners]) {
    listener(message)
  }
}

describe("QuickIngestWizardModal session runtime", () => {
  beforeEach(() => {
    mocks.runtimeListeners.splice(0, mocks.runtimeListeners.length)
    mocks.startQuickIngestSession.mockReset()
    mocks.submitQuickIngestBatch.mockReset()
    mocks.cancelQuickIngestSession.mockReset()
    mocks.cancelQuickIngestSession.mockResolvedValue({ ok: true })
  })

  it("submits the queued wizard batch through the authenticated quick-ingest transport", async () => {
    const user = userEvent.setup()
    mocks.startQuickIngestSession.mockResolvedValue({
      ok: true,
      sessionId: "qi-direct-test",
    })
    mocks.submitQuickIngestBatch.mockResolvedValue({
      ok: true,
      results: [
        {
          id: "queued-url-1",
          status: "ok",
          url: "https://example.com/article",
          type: "html",
        },
      ],
    })

    render(<QuickIngestWizardModal open onClose={vi.fn()} />)

    expect(screen.getByRole("dialog")).toHaveClass(
      "quick-ingest-modal",
      "quick-ingest-wizard-modal"
    )

    await user.click(screen.getByRole("button", { name: "Queue And Process" }))

    await waitFor(() => {
      expect(mocks.startQuickIngestSession).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(mocks.submitQuickIngestBatch).toHaveBeenCalledTimes(1)
    })

    expect(mocks.submitQuickIngestBatch).toHaveBeenCalledWith(
      expect.objectContaining({
        __quickIngestSessionId: "qi-direct-test",
        entries: [
          expect.objectContaining({
            id: "queued-url-1",
            url: "https://example.com/article",
            type: "html",
          }),
        ],
      })
    )

    await waitFor(() => {
      expect(screen.getByTestId("wizard-results")).toHaveTextContent("complete:1")
    })
  })

  it("uses runtime completion events for extension-backed sessions instead of calling the broken SSE path", async () => {
    const user = userEvent.setup()
    mocks.startQuickIngestSession.mockResolvedValue({
      ok: true,
      sessionId: "qi-runtime-test",
    })

    render(<QuickIngestWizardModal open onClose={vi.fn()} />)

    expect(screen.getByRole("dialog")).toHaveClass(
      "quick-ingest-modal",
      "quick-ingest-wizard-modal"
    )

    await user.click(screen.getByRole("button", { name: "Queue And Process" }))

    await waitFor(() => {
      expect(mocks.startQuickIngestSession).toHaveBeenCalledTimes(1)
    })

    expect(mocks.submitQuickIngestBatch).not.toHaveBeenCalled()

    emitRuntimeMessage({
      type: "tldw:quick-ingest/completed",
      payload: {
        sessionId: "qi-runtime-test",
        results: [
          {
            id: "queued-url-1",
            status: "ok",
            url: "https://example.com/article",
            type: "html",
          },
        ],
      },
    })

    await waitFor(() => {
      expect(screen.getByTestId("wizard-results")).toHaveTextContent("complete:1")
    })
  })
})
