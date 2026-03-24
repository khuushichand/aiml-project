/**
 * Page Object for Agent Tasks (Orchestration) workflow
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForAppShell, waitForConnection } from "../helpers"

export class AgentTasksPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/agent-tasks", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await waitForAppShell(this.page, 30_000)
    // Wait for Projects card or error alert
    const projectsCard = this.page.getByText("Projects")
    const errorAlert = this.page.locator(".ant-alert-error")
    await Promise.race([
      projectsCard.first().waitFor({ state: "visible", timeout: 20_000 }),
      errorAlert.first().waitFor({ state: "visible", timeout: 20_000 }),
    ]).catch(() => {})
  }

  // -- Locators --------------------------------------------------------------

  /** Projects card heading */
  get projectsHeading(): Locator {
    return this.page.getByText("Projects").first()
  }

  /** Tasks card heading */
  get tasksHeading(): Locator {
    return this.page.getByText("Tasks").first()
  }

  /** "New" button to create a project */
  get newProjectButton(): Locator {
    return this.page.getByRole("button", { name: /^New$/i })
  }

  /** "Create Project" button (in empty state) */
  get createProjectButton(): Locator {
    return this.page.getByRole("button", { name: /create project/i })
  }

  /** "New Task" button */
  get newTaskButton(): Locator {
    return this.page.getByRole("button", { name: /new task/i })
  }

  /** "Create Task" button (in empty state) */
  get createTaskButton(): Locator {
    return this.page.getByRole("button", { name: /create task/i })
  }

  /** Refresh projects button (first RefreshCw icon button) */
  get refreshProjectsButton(): Locator {
    return this.page.locator(".ant-card").first().getByRole("button").first()
  }

  /** Error alert */
  get errorAlert(): Locator {
    return this.page.locator(".ant-alert-error")
  }

  /** Empty state for projects */
  get projectsEmpty(): Locator {
    return this.page.getByText("No projects yet")
  }

  /** Empty state for tasks (select a project) */
  get tasksSelectProjectEmpty(): Locator {
    return this.page.getByText("Select a project to view tasks")
  }

  /** Empty state for tasks (no tasks) */
  get tasksEmpty(): Locator {
    return this.page.getByText("No tasks yet")
  }

  /** Create Project modal */
  get createProjectModal(): Locator {
    return this.page.locator(".ant-modal").filter({ hasText: "Create Project" })
  }

  /** Create Task modal */
  get createTaskModal(): Locator {
    return this.page.locator(".ant-modal").filter({ hasText: "Create Task" })
  }

  /** Project Name input in modal */
  get projectNameInput(): Locator {
    return this.createProjectModal.locator("#name")
  }

  /** Task Title input in modal */
  get taskTitleInput(): Locator {
    return this.createTaskModal.locator("#title")
  }

  /** Run button on task cards */
  get runButtons(): Locator {
    return this.page.getByRole("button", { name: /^Run$/i })
  }

  /** Approve button on task cards */
  get approveButtons(): Locator {
    return this.page.getByRole("button", { name: /approve/i })
  }

  /** Reject button on task cards */
  get rejectButtons(): Locator {
    return this.page.getByRole("button", { name: /reject/i })
  }

  /** Delete project buttons */
  get deleteProjectButtons(): Locator {
    return this.page.locator("[title='Delete project'] button, button[title='Delete project']")
  }

  // -- Helpers ---------------------------------------------------------------

  /** Check if the empty state (no projects) is visible */
  async isProjectsEmpty(): Promise<boolean> {
    return this.projectsEmpty.isVisible().catch(() => false)
  }

  /** Check if the tasks panel shows "select a project" */
  async isTasksSelectProject(): Promise<boolean> {
    return this.tasksSelectProjectEmpty.isVisible().catch(() => false)
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "New project button",
        locator: this.newProjectButton,
        expectation: {
          type: "modal",
          modalSelector: ".ant-modal",
        },
      },
    ]
  }
}
