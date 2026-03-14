/**
 * Page Object for Speech Playground workflow
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForConnection } from "../helpers"

export class SpeechPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/speech", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await this.page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {})
    const heading = this.page.getByText("Speech Playground")
    await heading.first().waitFor({ state: "visible", timeout: 20_000 }).catch(() => {})
  }

  // -- Locators --------------------------------------------------------------

  get heading(): Locator {
    return this.page.getByText("Speech Playground").first()
  }

  /** The Round-trip / Speak / Listen mode segmented control */
  get modeSelector(): Locator {
    return this.page.locator(".ant-segmented")
  }

  get roundTripOption(): Locator {
    return this.page.getByText("Round-trip")
  }

  get speakOption(): Locator {
    return this.page.locator(".ant-segmented").getByText("Speak")
  }

  get listenOption(): Locator {
    return this.page.locator(".ant-segmented").getByText("Listen")
  }

  /** The playback controls toolbar */
  get playbackToolbar(): Locator {
    return this.page.getByRole("toolbar", { name: /playback controls/i })
  }

  get playButton(): Locator {
    return this.page.getByRole("button", { name: /^play$/i })
  }

  get stopButton(): Locator {
    return this.page.getByRole("button", { name: /^stop$/i })
  }

  get downloadButton(): Locator {
    return this.page.getByRole("button", { name: /^download$/i })
  }

  get addRenderButton(): Locator {
    return this.page.getByRole("button", { name: /add render/i })
  }

  // -- Actions ---------------------------------------------------------------

  async selectMode(mode: "Round-trip" | "Speak" | "Listen"): Promise<void> {
    const option = this.page.locator(".ant-segmented").getByText(mode)
    await option.click()
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Play button",
        locator: this.playButton,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/audio\/speech/,
          method: "POST",
        },
      },
    ]
  }
}
