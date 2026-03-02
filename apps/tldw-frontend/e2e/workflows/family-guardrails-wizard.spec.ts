import { assertNoCriticalErrors, expect, test } from "../utils/fixtures"
import { seedAuth } from "../utils/helpers"
import type { Page } from "@playwright/test"

test.describe("Family Guardrails Wizard Workflow", () => {
  const mockFamilyWizardApi = async (
    page: Page,
    options?: {
      latestDraft?: {
        id: string
        owner_user_id: string
        name: string
        mode: "family" | "institutional"
        status: string
        created_at: string
        updated_at: string
      } | null
      snapshot?: {
        household: {
          id: string
          owner_user_id: string
          name: string
          mode: "family" | "institutional"
          status: string
          created_at: string
          updated_at: string
        }
        members: Array<Record<string, unknown>>
        relationships: Array<Record<string, unknown>>
        plans: Array<Record<string, unknown>>
      } | null
      activationSummary?: {
        household_draft_id: string
        status: string
        active_count: number
        pending_count: number
        failed_count: number
        items: Array<{
          dependent_user_id: string
          relationship_status: string
          plan_status: string
          message: string | null
        }>
      }
    }
  ) => {
    let memberIndex = 0
    let relationshipIndex = 0
    let planIndex = 0
    const activationSummary =
      options?.activationSummary ??
      {
        household_draft_id: "draft-e2e-1",
        status: "invites_pending",
        active_count: 1,
        pending_count: 1,
        failed_count: 0,
        items: [
          {
            dependent_user_id: "alex-kid",
            relationship_status: "pending",
            plan_status: "queued",
            message: "Queued until acceptance"
          },
          {
            dependent_user_id: "sam-kid",
            relationship_status: "active",
            plan_status: "active",
            message: null
          }
        ]
      }
    const latestDraft = options?.latestDraft ?? null
    const snapshot = options?.snapshot ?? null

    await page.route("**/api/v1/guardian/wizard/**", async (route, request) => {
      const url = request.url()
      const method = request.method()
      const now = "2026-01-01T00:00:00Z"

      if (method === "GET" && /\/api\/v1\/guardian\/wizard\/drafts\/latest$/.test(url)) {
        if (!latestDraft) {
          await route.fulfill({
            status: 404,
            contentType: "application/json",
            body: JSON.stringify({ detail: "No household draft found" })
          })
          return
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(latestDraft)
        })
        return
      }

      if (method === "GET" && /\/api\/v1\/guardian\/wizard\/drafts\/[^/]+\/snapshot$/.test(url)) {
        if (!snapshot) {
          await route.fulfill({
            status: 404,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Household snapshot not found" })
          })
          return
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(snapshot)
        })
        return
      }

      if (method === "POST" && /\/api\/v1\/guardian\/wizard\/drafts$/.test(url)) {
        const body = request.postDataJSON() as { name?: string; mode?: "family" | "institutional" }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "draft-e2e-1",
            owner_user_id: "guardian-e2e",
            name: body?.name ?? "My Household",
            mode: body?.mode ?? "family",
            status: "draft",
            created_at: now,
            updated_at: now
          })
        })
        return
      }

      if (method === "PATCH" && /\/api\/v1\/guardian\/wizard\/drafts\/[^/]+$/.test(url)) {
        const body = request.postDataJSON() as { name?: string; mode?: "family" | "institutional" }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "draft-e2e-1",
            owner_user_id: "guardian-e2e",
            name: body?.name ?? "My Household",
            mode: body?.mode ?? "family",
            status: "draft",
            created_at: now,
            updated_at: now
          })
        })
        return
      }

      if (method === "POST" && /\/api\/v1\/guardian\/wizard\/drafts\/[^/]+\/members$/.test(url)) {
        const body = request.postDataJSON() as {
          role?: "guardian" | "dependent" | "caregiver"
          display_name?: string
          user_id?: string
          email?: string
          invite_required?: boolean
        }
        memberIndex += 1
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: `member-e2e-${memberIndex}`,
            household_draft_id: "draft-e2e-1",
            role: body?.role ?? "guardian",
            display_name: body?.display_name ?? `Member ${memberIndex}`,
            user_id: body?.user_id ?? `member-${memberIndex}`,
            email: body?.email ?? null,
            invite_required: body?.invite_required ?? false,
            metadata: {},
            created_at: now,
            updated_at: now
          })
        })
        return
      }

      if (method === "POST" && /\/api\/v1\/guardian\/wizard\/drafts\/[^/]+\/relationships$/.test(url)) {
        const body = request.postDataJSON() as {
          guardian_member_draft_id?: string
          dependent_member_draft_id?: string
          relationship_type?: string
          dependent_visible?: boolean
        }
        relationshipIndex += 1
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: `relationship-e2e-${relationshipIndex}`,
            household_draft_id: "draft-e2e-1",
            guardian_member_draft_id: body?.guardian_member_draft_id ?? "member-e2e-1",
            dependent_member_draft_id: body?.dependent_member_draft_id ?? "member-e2e-2",
            relationship_type: body?.relationship_type ?? "parent",
            dependent_visible: body?.dependent_visible ?? true,
            status: "pending",
            metadata: {},
            created_at: now,
            updated_at: now
          })
        })
        return
      }

      if (method === "POST" && /\/api\/v1\/guardian\/wizard\/drafts\/[^/]+\/plans$/.test(url)) {
        const body = request.postDataJSON() as {
          dependent_user_id?: string
          relationship_draft_id?: string
          template_id?: string
          overrides?: Record<string, unknown>
        }
        planIndex += 1
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: `plan-e2e-${planIndex}`,
            household_draft_id: "draft-e2e-1",
            dependent_user_id: body?.dependent_user_id ?? `dependent-${planIndex}`,
            relationship_draft_id: body?.relationship_draft_id ?? "relationship-e2e-1",
            template_id: body?.template_id ?? "default-child-safe",
            overrides: body?.overrides ?? {},
            status: "queued",
            materialized_policy_id: null,
            failure_reason: null,
            created_at: now,
            updated_at: now
          })
        })
        return
      }

      if (method === "POST" && /\/api\/v1\/guardian\/wizard\/drafts\/[^/]+\/invites\/resend$/.test(url)) {
        const body = request.postDataJSON() as {
          dependent_user_ids?: string[]
        }
        const dependentUserIds = body?.dependent_user_ids ?? []
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            household_draft_id: "draft-e2e-1",
            resent_count: dependentUserIds.length,
            skipped_count: 0,
            resent_user_ids: dependentUserIds,
            skipped_user_ids: []
          })
        })
        return
      }

      if (method === "GET" && /\/api\/v1\/guardian\/wizard\/drafts\/[^/]+\/activation-summary$/.test(url)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(activationSummary)
        })
        return
      }

      await route.continue()
    })
  }

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("family wizard route is present and reachable", async ({
    authedPage,
    diagnostics
  }) => {
    await authedPage.goto("/settings/family-guardrails")
    await expect(authedPage).toHaveURL(/\/settings\/family-guardrails/)
    await expect(
      authedPage.getByRole("heading", { name: /Family Guardrails Wizard/i })
    ).toBeVisible()
    await expect(authedPage.getByText("Household Basics")).toBeVisible()
    await expect(authedPage.getByText("Step 1 of 8")).toBeVisible()
    await expect(authedPage.getByText("Tracker")).toBeVisible()
    await expect(authedPage.getByText("Next: Guardians")).toBeVisible()
    await expect(
      authedPage.getByRole("button", { name: /Save & Continue/i })
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("can progress from household basics to guardian setup step", async ({
    authedPage,
    diagnostics
  }) => {
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(authedPage.getByText("Add every guardian who can manage alerts and safety settings.")).toBeVisible()
    await expect(authedPage.getByRole("button", { name: /Add Guardian/i })).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("two-guardian preset seeds two guardian entries on guardian step", async ({
    authedPage,
    diagnostics
  }) => {
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.getByRole("radio", { name: "Two Guardians (shared household)" }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(authedPage.getByText("Add every guardian who can manage alerts and safety settings.")).toBeVisible()
    await expect(authedPage.getByPlaceholder("Guardian 1 display name")).toBeVisible()
    await expect(authedPage.getByPlaceholder("Guardian 2 display name")).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("bulk guardian entry supports larger households", async ({
    authedPage,
    diagnostics
  }) => {
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText("Add every guardian who can manage alerts and safety settings.")
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Bulk entry/i }).click()
    await authedPage
      .getByPlaceholder("One per line: Display Name | user_id | email(optional)")
      .fill("Ana|ana-kid\nBen|ben-kid\nCleo|cleo-kid|cleo@example.com")
    await authedPage.getByRole("button", { name: /Apply bulk entries/i }).click()
    await expect(authedPage.getByText("3 entries ready")).toBeVisible()
    await authedPage.getByRole("button", { name: /Card entry/i }).click()
    await expect(authedPage.getByPlaceholder("Guardian 3 display name")).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("dependent table mode supports keyboard shortcuts for bulk selection and removal", async ({
    authedPage,
    diagnostics
  }) => {
    await mockFamilyWizardApi(authedPage)

    await authedPage.goto("/settings/family-guardrails")
    await authedPage.evaluate(() => {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "e2e-family-guardrails-key"
        })
      )
    })

    await authedPage.getByRole("spinbutton", { name: /Dependents to set up/i }).fill("5")
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText("Add every guardian who can manage alerts and safety settings.")
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()

    await authedPage.getByRole("button", { name: /Table entry/i }).click()
    await expect(
      authedPage.getByText("Shortcuts: Ctrl/Cmd+A select all, Delete removes selected.")
    ).toBeVisible()
    await expect(authedPage.getByText("Selected: 0")).toBeVisible()

    await authedPage.keyboard.press("ControlOrMeta+A")
    await expect(authedPage.getByText("Selected: 5")).toBeVisible()

    await authedPage.keyboard.press("Delete")
    await expect(authedPage.getByText("Removed 5 selected dependents.")).toBeVisible()
    await expect(authedPage.getByText("Selected: 0")).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("single-guardian flow skips relationship mapping and advances to templates", async ({
    authedPage,
    diagnostics
  }) => {
    await mockFamilyWizardApi(authedPage)
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.evaluate(() => {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "e2e-family-guardrails-key"
        })
      )
    })

    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText("Add every guardian who can manage alerts and safety settings.")
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()
    await authedPage.getByPlaceholder("Child 1 display name").fill("Alex")
    await authedPage.getByPlaceholder("Child 2 display name").fill("Sam")
    await authedPage
      .getByRole("button", { name: /Auto-fill missing user IDs/i })
      .click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText("Apply a template first, then customize if needed.")
    ).toBeVisible()
    await expect(
      authedPage.getByText(
        "Relationship mapping was auto-applied to Primary Guardian for all dependents."
      )
    ).toBeVisible()
    await expect(
      authedPage.getByText(
        "Map each dependent to a guardian. For shared households, dependents can be mapped to different guardians."
      )
    ).not.toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("single-guardian flow returns to dependents when navigating back from templates", async ({
    authedPage,
    diagnostics
  }) => {
    await mockFamilyWizardApi(authedPage)
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.evaluate(() => {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "e2e-family-guardrails-key"
        })
      )
    })

    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText("Add every guardian who can manage alerts and safety settings.")
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()
    await authedPage.getByPlaceholder("Child 1 display name").fill("Alex")
    await authedPage.getByPlaceholder("Child 2 display name").fill("Sam")
    await authedPage.getByRole("button", { name: /Auto-fill missing user IDs/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText("Apply a template first, then customize if needed.")
    ).toBeVisible()

    await authedPage.getByRole("button", { name: /^Back$/i }).click()

    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()
    await expect(
      authedPage.getByText(
        "Map each dependent to a guardian. For shared households, dependents can be mapped to different guardians."
      )
    ).not.toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("two-guardian flow keeps relationship mapping step", async ({
    authedPage,
    diagnostics
  }) => {
    await mockFamilyWizardApi(authedPage)
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.evaluate(() => {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "e2e-family-guardrails-key"
        })
      )
    })

    await authedPage.getByRole("radio", { name: "Two Guardians (shared household)" }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText("Add every guardian who can manage alerts and safety settings.")
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()
    await authedPage.getByPlaceholder("Child 1 display name").fill("Alex")
    await authedPage.getByPlaceholder("Child 2 display name").fill("Sam")
    await authedPage
      .getByRole("button", { name: /Auto-fill missing user IDs/i })
      .click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText(
        "Map each dependent to a guardian. For shared households, dependents can be mapped to different guardians."
      )
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("two-guardian flow returns to relationship mapping when navigating back from templates", async ({
    authedPage,
    diagnostics
  }) => {
    await mockFamilyWizardApi(authedPage)
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.evaluate(() => {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "e2e-family-guardrails-key"
        })
      )
    })

    await authedPage.getByRole("radio", { name: "Two Guardians (shared household)" }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText("Add every guardian who can manage alerts and safety settings.")
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()
    await authedPage.getByPlaceholder("Child 1 display name").fill("Alex")
    await authedPage.getByPlaceholder("Child 2 display name").fill("Sam")
    await authedPage.getByRole("button", { name: /Auto-fill missing user IDs/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText(
        "Map each dependent to a guardian. For shared households, dependents can be mapped to different guardians."
      )
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText("Apply a template first, then customize if needed.")
    ).toBeVisible()
    await expect(
      authedPage.getByText(
        "Relationship mapping was auto-applied to Primary Guardian for all dependents."
      )
    ).not.toBeVisible()

    await authedPage.getByRole("button", { name: /^Back$/i }).click()

    await expect(
      authedPage.getByText(
        "Map each dependent to a guardian. For shared households, dependents can be mapped to different guardians."
      )
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("tracker step explains pending invite acceptance status", async ({
    authedPage,
    diagnostics
  }) => {
    await mockFamilyWizardApi(authedPage)
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.evaluate(() => {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "e2e-family-guardrails-key"
        })
      )
    })

    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText("Add every guardian who can manage alerts and safety settings.")
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()
    await authedPage.getByPlaceholder("Child 1 display name").fill("Alex")
    await authedPage.getByPlaceholder("Child 2 display name").fill("Sam")
    await authedPage.getByRole("button", { name: /Auto-fill missing user IDs/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText("Apply a template first, then customize if needed.")
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText("Choose how guardians receive moderation context when alerts trigger.")
    ).toBeVisible()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText("1 dependent is waiting on invite acceptance.")
    ).toBeVisible()
    await expect(
      authedPage.getByText("Guardrails for pending dependents stay queued until acceptance.")
    ).toBeVisible()
    await expect(
      authedPage.getByRole("button", { name: "Resend Pending Invites" })
    ).toBeEnabled()
    await expect(
      authedPage.getByRole("button", { name: "Copy pending invite reminder" })
    ).toBeEnabled()
    await expect(
      authedPage.getByRole("button", { name: "Resend invite for alex-kid" })
    ).toBeVisible()

    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText("Setup is saved, and 1 dependent is still waiting on acceptance.")
    ).toBeVisible()
    await expect(
      authedPage.getByText("Pending dependents activate guardrails automatically after invite acceptance.")
    ).toBeVisible()
    await expect(
      authedPage.getByRole("button", { name: "Finish Setup (Invites Pending)" })
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("tracker step shows status-aware fallback messages when API messages are empty", async ({
    authedPage,
    diagnostics
  }) => {
    await mockFamilyWizardApi(authedPage, {
      activationSummary: {
        household_draft_id: "draft-e2e-1",
        status: "needs_attention",
        active_count: 0,
        pending_count: 1,
        failed_count: 1,
        items: [
          {
            dependent_user_id: "alex-kid",
            relationship_status: "pending",
            plan_status: "queued",
            message: null
          },
          {
            dependent_user_id: "sam-kid",
            relationship_status: "active",
            plan_status: "failed",
            message: null
          }
        ]
      }
    })
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.evaluate(() => {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "e2e-family-guardrails-key"
        })
      )
    })

    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()
    await authedPage.getByPlaceholder("Child 1 display name").fill("Alex")
    await authedPage.getByPlaceholder("Child 2 display name").fill("Sam")
    await authedPage.getByRole("button", { name: /Auto-fill missing user IDs/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText("Activation failed. Review configuration and retry.")
    ).toBeVisible()
    await expect(
      authedPage.getByRole("cell", { name: "Queued until acceptance" }).first()
    ).toBeVisible()
    await expect(
      authedPage.getByRole("button", { name: "Review template for sam-kid" })
    ).toBeVisible()
    await authedPage.getByRole("button", { name: "Review template for sam-kid" }).click()
    await expect(
      authedPage.getByText("Reviewing template for sam-kid.")
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("tracker step shows fix-mapping blocker action for declined relationship rows", async ({
    authedPage,
    diagnostics
  }) => {
    await mockFamilyWizardApi(authedPage, {
      activationSummary: {
        household_draft_id: "draft-e2e-1",
        status: "needs_attention",
        active_count: 0,
        pending_count: 0,
        failed_count: 1,
        items: [
          {
            dependent_user_id: "alex-kid",
            relationship_status: "declined",
            plan_status: "queued",
            message: null
          }
        ]
      }
    })
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.evaluate(() => {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "e2e-family-guardrails-key"
        })
      )
    })

    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()
    await authedPage.getByPlaceholder("Child 1 display name").fill("Alex")
    await authedPage.getByPlaceholder("Child 2 display name").fill("Sam")
    await authedPage.getByRole("button", { name: /Auto-fill missing user IDs/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()

    await expect(
      authedPage.getByText("Relationship no longer active. Remap this dependent and resend invite.")
    ).toBeVisible()
    await expect(
      authedPage.getByRole("button", { name: "Fix mapping for alex-kid" })
    ).toBeVisible()
    await authedPage.getByRole("button", { name: "Fix mapping for alex-kid" }).click()
    await expect(
      authedPage.getByText("Fixing mapping for alex-kid.")
    ).toBeVisible()
    await expect(
      authedPage.getByPlaceholder("Child account user ID").first()
    ).toHaveValue("alex-kid")

    await assertNoCriticalErrors(diagnostics)
  })

  test("resume flow restores latest draft snapshot for returning guardians", async ({
    authedPage,
    diagnostics
  }) => {
    await mockFamilyWizardApi(authedPage, {
      latestDraft: {
        id: "draft-e2e-resume-1",
        owner_user_id: "guardian-e2e",
        name: "Resume Home",
        mode: "family",
        status: "draft",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z"
      },
      snapshot: {
        household: {
          id: "draft-e2e-resume-1",
          owner_user_id: "guardian-e2e",
          name: "Resume Home",
          mode: "family",
          status: "draft",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z"
        },
        members: [
          {
            id: "member-guardian-1",
            household_draft_id: "draft-e2e-resume-1",
            role: "guardian",
            display_name: "Primary Guardian",
            user_id: "guardian-primary",
            email: null,
            invite_required: false,
            metadata: {},
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z"
          },
          {
            id: "member-dependent-1",
            household_draft_id: "draft-e2e-resume-1",
            role: "dependent",
            display_name: "Alex",
            user_id: "alex-kid",
            email: null,
            invite_required: true,
            metadata: {},
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z"
          }
        ],
        relationships: [
          {
            id: "relationship-draft-1",
            household_draft_id: "draft-e2e-resume-1",
            guardian_member_draft_id: "member-guardian-1",
            dependent_member_draft_id: "member-dependent-1",
            relationship_type: "parent",
            dependent_visible: true,
            status: "pending",
            relationship_id: "relationship-1",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z"
          }
        ],
        plans: []
      }
    })

    await authedPage.goto("/settings/family-guardrails")
    await authedPage.evaluate(() => {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "e2e-family-guardrails-key"
        })
      )
    })

    await expect(
      authedPage.getByText("Apply a template first, then customize if needed.")
    ).toBeVisible()

    await authedPage.getByRole("button", { name: /^Back$/i }).click()
    await expect(
      authedPage.getByText(
        "Create or link dependent accounts here. User IDs are required for invitation and acceptance."
      )
    ).toBeVisible()
    await expect(
      authedPage.getByPlaceholder("Child account user ID").first()
    ).toHaveValue("alex-kid")

    await assertNoCriticalErrors(diagnostics)
  })
})
