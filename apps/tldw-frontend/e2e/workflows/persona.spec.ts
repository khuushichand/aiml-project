/**
 * Persona Workflow E2E Tests
 *
 * Validates persona route stream UX with mocked persona API and websocket events.
 */
import { test, expect } from "../utils/fixtures"

test.describe("Persona Workflow", () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.addInitScript(() => {
      type MockSocket = {
        url: string
        readyState: number
        binaryType: string
        sent: string[]
        onopen: ((event: Event) => void) | null
        onmessage: ((event: MessageEvent) => void) | null
        onerror: ((event: Event) => void) | null
        onclose: ((event: CloseEvent) => void) | null
      }
      type PersonaWsMockControl = {
        getSentPayloads: () => unknown[]
        emitJson: (payload: unknown) => void
      }
      type PersonaMockWindow = Window & {
        __personaWsMock?: PersonaWsMockControl
      }

      const state: { sockets: MockSocket[] } = { sockets: [] }
      const personaWindow = window as PersonaMockWindow

      personaWindow.__personaWsMock = {
        getSentPayloads: () => {
          const socket = state.sockets[state.sockets.length - 1]
          if (!socket) return []
          return socket.sent.map((raw) => {
            try {
              return JSON.parse(raw)
            } catch {
              return raw
            }
          })
        },
        emitJson: (payload: unknown) => {
          const socket = state.sockets[state.sockets.length - 1]
          if (!socket || !socket.onmessage) return
          socket.onmessage({
            data: JSON.stringify(payload)
          } as MessageEvent)
        }
      }

      const MockWebSocket = class {
        url: string
        readyState = 0
        binaryType = "blob"
        onopen: ((event: Event) => void) | null = null
        onmessage: ((event: MessageEvent) => void) | null = null
        onerror: ((event: Event) => void) | null = null
        onclose: ((event: CloseEvent) => void) | null = null
        sent: string[] = []

        constructor(url: string) {
          this.url = url
          state.sockets.push(this as unknown as MockSocket)
          setTimeout(() => {
            this.readyState = 1
            this.onopen?.(new Event("open"))
          }, 0)
        }

        send(payload: string) {
          this.sent.push(String(payload))
        }

        close() {
          this.readyState = 3
          this.onclose?.({} as CloseEvent)
        }
      }
      window.WebSocket = MockWebSocket as unknown as typeof WebSocket
    })

    await authedPage.route("**/api/v1/persona/catalog*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "research_assistant",
            name: "Research Assistant"
          }
        ])
      })
    })

    await authedPage.route("**/api/v1/persona/session*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "sess-e2e-001"
        })
      })
    })

    await authedPage.route("**/api/v1/chats/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          total: 0
        })
      })
    })
  })

  test("supports persona connect, send, confirm plan, and cancel plan", async ({
    authedPage,
    diagnostics
  }) => {
    await authedPage.goto("/persona", { waitUntil: "domcontentloaded" })

    await authedPage
      .getByRole("button", { name: /^Connect$/ })
      .evaluate((el: HTMLElement) => el.click())
    await expect(
      authedPage.getByRole("button", { name: /^Disconnect$/ })
    ).toBeVisible()

    await authedPage.getByPlaceholder("Ask Persona...").fill("hello from playwright")
    await authedPage.getByRole("button", { name: /^Send$/ }).click()

    await expect
      .poll(
        async () =>
          await authedPage.evaluate(() => {
            return (
              (
                window as Window & {
                  __personaWsMock?: { getSentPayloads?: () => unknown[] }
                }
              ).__personaWsMock?.getSentPayloads?.() ?? []
            )
          })
      )
      .toContainEqual(
        expect.objectContaining({
          type: "user_message",
          session_id: "sess-e2e-001",
          text: "hello from playwright"
        })
      )

    await authedPage.evaluate(() => {
      ;(
        window as Window & {
          __personaWsMock?: { emitJson?: (payload: unknown) => void }
        }
      ).__personaWsMock?.emitJson?.({
        event: "tool_plan",
        plan_id: "plan-e2e-1",
        steps: [
          { idx: 0, tool: "ingest_url", description: "ingest source" },
          { idx: 1, tool: "rag_search", description: "search notes" }
        ]
      })
    })

    await expect(authedPage.getByText("Pending tool plan")).toBeVisible()

    const checkboxes = authedPage.getByRole("checkbox")
    await checkboxes.nth(0).click()
    await authedPage.getByRole("button", { name: /^Confirm plan$/ }).click()

    await expect
      .poll(
        async () =>
          await authedPage.evaluate(() => {
            return (
              (
                window as Window & {
                  __personaWsMock?: { getSentPayloads?: () => unknown[] }
                }
              ).__personaWsMock?.getSentPayloads?.() ?? []
            )
          })
      )
      .toContainEqual(
        expect.objectContaining({
          type: "confirm_plan",
          session_id: "sess-e2e-001",
          plan_id: "plan-e2e-1",
          approved_steps: [1]
        })
      )

    await authedPage.evaluate(() => {
      ;(
        window as Window & {
          __personaWsMock?: { emitJson?: (payload: unknown) => void }
        }
      ).__personaWsMock?.emitJson?.({
        event: "tool_plan",
        plan_id: "plan-e2e-2",
        steps: [{ idx: 0, tool: "summarize", description: "summarize result" }]
      })
    })

    await expect(authedPage.getByText("Pending tool plan")).toBeVisible()
    await authedPage.getByRole("button", { name: /^Cancel$/ }).click()

    await expect
      .poll(
        async () =>
          await authedPage.evaluate(() => {
            return (
              (
                window as Window & {
                  __personaWsMock?: { getSentPayloads?: () => unknown[] }
                }
              ).__personaWsMock?.getSentPayloads?.() ?? []
            )
          })
      )
      .toContainEqual(
        expect.objectContaining({
          type: "cancel",
          session_id: "sess-e2e-001",
          reason: "user_cancelled"
        })
      )

    expect(diagnostics.pageErrors).toHaveLength(0)
  })
})
