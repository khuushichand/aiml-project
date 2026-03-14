/**
 * Page Object for Admin functionality
 *
 * Covers the admin sub-routes:
 *   /admin/server    - Server status, users, roles, media budget
 *   /admin/llamacpp  - Llama.cpp inference server management
 *   /admin/mlx       - MLX LM model management
 *   /admin/orgs      - Organization management (placeholder)
 *   /admin/data-ops  - Data operations (placeholder)
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForConnection, waitForNetworkIdle } from "../helpers"

export type AdminSection = "server" | "llamacpp" | "mlx" | "orgs" | "data-ops"

export class AdminPage extends BasePage {
  /* ------------------------------------------------------------------ */
  /* Constructor locators (placeholder pages)                            */
  /* ------------------------------------------------------------------ */
  readonly placeholderPanel: Locator
  readonly primaryCta: Locator
  readonly openSettingsLink: Locator
  readonly goBackButton: Locator

  constructor(page: Page) {
    super(page)
    this.placeholderPanel = page.getByTestId("route-placeholder-panel")
    this.primaryCta = page.getByTestId("route-placeholder-primary")
    this.openSettingsLink = page.getByTestId("route-placeholder-open-settings")
    this.goBackButton = page.getByTestId("route-placeholder-go-back")
  }

  /* ------------------------------------------------------------------ */
  /* Section headings                                                    */
  /* ------------------------------------------------------------------ */

  /** Server Admin heading (h2) */
  get serverHeading(): Locator {
    return this.page.getByRole("heading", { name: /Server Admin/i })
  }

  /** Llama.cpp Admin heading (h2) */
  get llamacppHeading(): Locator {
    return this.page.getByRole("heading", { name: /Llama\.cpp Admin/i })
  }

  /** MLX LM Admin heading (h2) */
  get mlxHeading(): Locator {
    return this.page.getByRole("heading", { name: /MLX LM Admin/i })
  }

  /** "Coming Soon" text in placeholder pages */
  get comingSoonText(): Locator {
    return this.page.getByText("Coming Soon", { exact: true })
  }

  /* ------------------------------------------------------------------ */
  /* Server Admin locators                                               */
  /* ------------------------------------------------------------------ */

  /** Server Admin: Refresh button for system stats */
  get refreshStatsButton(): Locator {
    return this.page.getByRole("button", { name: /^Refresh$/i }).first()
  }

  /** Server Admin: Users table */
  get usersTable(): Locator {
    return this.page.locator(".ant-table").first()
  }

  /** Server Admin: Create role button */
  get createRoleButton(): Locator {
    return this.page.getByRole("button", { name: /Create role/i })
  }

  /** Server Admin: Refresh roles button */
  get refreshRolesButton(): Locator {
    return this.page.getByRole("button", { name: /Refresh roles/i })
  }

  /** Server Admin: Role name input */
  get roleNameInput(): Locator {
    return this.page.getByPlaceholder(/Role name/i)
  }

  /** Server Admin: Connection card */
  get connectionCard(): Locator {
    return this.page.locator(".ant-card", { hasText: /Connection/i }).first()
  }

  /** Server Admin: System statistics card */
  get systemStatsCard(): Locator {
    return this.page.locator(".ant-card", { hasText: /System statistics/i }).first()
  }

  /** Server Admin: Users & roles card */
  get usersAndRolesCard(): Locator {
    return this.page.locator(".ant-card", { hasText: /Users & roles/i }).first()
  }

  /** Server Admin: Media ingestion budget card */
  get mediaBudgetCard(): Locator {
    return this.page.locator(".ant-card", { hasText: /Media ingestion budget/i }).first()
  }

  /* ------------------------------------------------------------------ */
  /* Llamacpp Admin locators                                             */
  /* ------------------------------------------------------------------ */

  /** Llamacpp: Model select dropdown */
  get llamacppModelSelect(): Locator {
    return this.page.locator(".ant-select").first()
  }

  /** Llamacpp: Start Server button */
  get llamacppStartButton(): Locator {
    return this.page.getByRole("button", { name: /Start Server/i })
  }

  /** Llamacpp: Start with Defaults button */
  get llamacppStartDefaultsButton(): Locator {
    return this.page.getByRole("button", { name: /Start with Defaults/i })
  }

  /** Llamacpp: Stop button (in StatusBanner) */
  get llamacppStopButton(): Locator {
    return this.page.getByRole("button", { name: /^Stop$/i })
  }

  /** Llamacpp: Export preset button */
  get llamacppExportPresetButton(): Locator {
    return this.page.getByRole("button", { name: /Export preset/i })
  }

  /** Llamacpp: Import preset button */
  get llamacppImportPresetButton(): Locator {
    return this.page.getByRole("button", { name: /Import preset/i })
  }

  /** Llamacpp: Load Model card */
  get llamacppLoadModelCard(): Locator {
    return this.page.locator(".ant-card", { hasText: /Load Model/i }).first()
  }

  /* ------------------------------------------------------------------ */
  /* MLX Admin locators                                                  */
  /* ------------------------------------------------------------------ */

  /** MLX: Model path input (AutoComplete combobox) */
  get mlxModelPathInput(): Locator {
    return this.page.getByRole("combobox").first()
  }

  /** MLX: Load Model button */
  get mlxLoadButton(): Locator {
    return this.page.getByRole("button", { name: "Load Model", exact: true })
  }

  /** MLX: Unload Model button */
  get mlxUnloadButton(): Locator {
    return this.page.getByRole("button", { name: "Unload Model", exact: true })
  }

  /** MLX: Load Model card */
  get mlxLoadModelCard(): Locator {
    return this.page.locator(".ant-card", { hasText: /Load Model/i }).first()
  }

  /* ------------------------------------------------------------------ */
  /* Admin guard                                                         */
  /* ------------------------------------------------------------------ */

  /** Admin guard alert (shown when admin APIs are not available) */
  get adminGuardAlert(): Locator {
    return this.page.locator(".ant-alert-warning").first()
  }

  /* ------------------------------------------------------------------ */
  /* Navigation                                                          */
  /* ------------------------------------------------------------------ */

  async goto(): Promise<void> {
    await this.page.goto("/admin", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async gotoSection(section: AdminSection): Promise<void> {
    await this.page.goto(`/admin/${section}`, { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  /* ------------------------------------------------------------------ */
  /* Readiness assertions                                                */
  /* ------------------------------------------------------------------ */

  async assertPageReady(): Promise<void> {
    await this.page.waitForLoadState("domcontentloaded")
    await waitForNetworkIdle(this.page, 15_000).catch(() => {})

    const hasServerHeading = await this.serverHeading.isVisible().catch(() => false)
    const hasLlamacppHeading = await this.llamacppHeading.isVisible().catch(() => false)
    const hasMlxHeading = await this.mlxHeading.isVisible().catch(() => false)
    const hasPlaceholder = await this.placeholderPanel.isVisible().catch(() => false)
    const hasAdminGuard = await this.adminGuardAlert.isVisible().catch(() => false)

    const anyReady =
      hasServerHeading || hasLlamacppHeading || hasMlxHeading || hasPlaceholder || hasAdminGuard
    if (!anyReady) {
      throw new Error(
        "AdminPage.assertPageReady(): No admin heading, placeholder, or admin guard alert found."
      )
    }
  }

  async assertSectionReady(section: AdminSection): Promise<void> {
    await this.page.waitForLoadState("domcontentloaded")
    await waitForNetworkIdle(this.page, 15_000).catch(() => {})

    switch (section) {
      case "server": {
        const visible = await this.serverHeading.isVisible().catch(() => false)
        const guarded = await this.adminGuardAlert.isVisible().catch(() => false)
        expect(visible || guarded).toBe(true)
        break
      }
      case "llamacpp": {
        const visible = await this.llamacppHeading.isVisible().catch(() => false)
        const guarded = await this.adminGuardAlert.isVisible().catch(() => false)
        expect(visible || guarded).toBe(true)
        break
      }
      case "mlx": {
        const visible = await this.mlxHeading.isVisible().catch(() => false)
        const guarded = await this.adminGuardAlert.isVisible().catch(() => false)
        expect(visible || guarded).toBe(true)
        break
      }
      case "orgs":
      case "data-ops":
        await expect(this.placeholderPanel).toBeVisible({ timeout: 10_000 })
        break
    }
  }

  /** Check whether the placeholder panel is visible (for placeholder pages) */
  async assertPlaceholderVisible(): Promise<void> {
    await expect(this.placeholderPanel).toBeVisible({ timeout: 15_000 })
  }

  /* ------------------------------------------------------------------ */
  /* Interactive elements                                                */
  /* ------------------------------------------------------------------ */

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Primary CTA",
        locator: this.primaryCta,
        expectation: { type: "navigation", targetUrl: "/admin/server" },
      },
      {
        name: "Open Settings",
        locator: this.openSettingsLink,
        expectation: { type: "navigation", targetUrl: "/settings" },
      },
    ]
  }
}
