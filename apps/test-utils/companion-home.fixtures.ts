export const COMPANION_HOME_PARITY_TIMESTAMP = "2026-03-20T12:00:00.000Z"

export const COMPANION_HOME_PARITY_OPENAPI_SPEC = {
  info: {
    version: "parity-fixture"
  },
  paths: {
    "/api/v1/chat/completions": {},
    "/api/v1/notes/": {},
    "/api/v1/notifications": {},
    "/api/v1/personalization/profile": {},
    "/api/v1/personalization/opt-in": {},
    "/api/v1/persona/catalog": {},
    "/api/v1/persona/session": {},
    "/api/v1/persona/stream": {},
    "/api/v1/reading/items": {}
  }
}

export const COMPANION_HOME_PARITY_DOCS_INFO = {
  capabilities: {
    personalization: true,
    persona: true
  },
  supported_features: {
    personalization: true,
    persona: true
  }
}

export const COMPANION_HOME_PARITY_PROFILE = {
  enabled: true,
  updated_at: COMPANION_HOME_PARITY_TIMESTAMP
}

export const COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT = {
  activity: [
    {
      id: "activity-1",
      event_type: "reading.saved",
      source_type: "reading_item",
      source_id: "reading-1",
      surface: "companion.workspace",
      tags: ["research"],
      provenance: {},
      metadata: {
        title: "Queue article",
        summary: "Captured while reviewing the reading queue."
      },
      created_at: "2026-03-18T10:00:00.000Z"
    }
  ],
  activityTotal: 1,
  knowledge: [],
  knowledgeTotal: 0,
  goals: [
    {
      id: "goal-1",
      title: "Finish queue review",
      description: "Review the saved queue.",
      goal_type: "reading_backlog",
      config: {},
      progress: {},
      status: "active",
      created_at: "2026-03-01T09:00:00.000Z",
      updated_at: "2026-03-01T09:00:00.000Z"
    }
  ],
  activeGoalCount: 1,
  reflections: [],
  inbox: [
    {
      id: 101,
      kind: "browser_selection",
      title: "Inbox capture",
      message: "Captured while reviewing the reading queue.",
      severity: "info",
      link_type: "browser_selection",
      link_id: "capture-1",
      created_at: "2026-03-19T09:30:00.000Z",
      read_at: null,
      dismissed_at: null
    }
  ],
  reflectionNotifications: []
}

export const COMPANION_HOME_PARITY_READING_LIST = {
  items: [
    {
      id: "reading-1",
      title: "Queue article",
      url: "https://example.com/queue",
      summary: "Saved for later reading.",
      status: "saved",
      favorite: false,
      tags: ["research"],
      created_at: "2026-03-05T08:00:00.000Z",
      updated_at: "2026-03-05T08:00:00.000Z"
    }
  ],
  total: 1,
  page: 1,
  size: 25
}

export const COMPANION_HOME_PARITY_NOTES = {
  items: [
    {
      id: "note-1",
      title: "Draft outline",
      content: "Turn the queue review into a checklist.",
      status: "draft",
      updated_at: "2026-03-04T12:00:00.000Z"
    }
  ],
  total: 1
}

export const COMPANION_HOME_PARITY_CARD_ROWS = [
  {
    id: "inbox-preview",
    title: "Inbox Preview"
  },
  {
    id: "needs-attention",
    title: "Needs Attention"
  },
  {
    id: "resume-work",
    title: "Resume Work"
  },
  {
    id: "goals-focus",
    title: "Goals / Focus"
  },
  {
    id: "recent-activity",
    title: "Recent Activity"
  },
  {
    id: "reading-queue",
    title: "Reading Queue"
  }
] as const
