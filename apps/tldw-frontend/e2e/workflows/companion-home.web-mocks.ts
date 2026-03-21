import {
  COMPANION_HOME_PARITY_DOCS_INFO,
  COMPANION_HOME_PARITY_NOTES,
  COMPANION_HOME_PARITY_PROFILE,
  COMPANION_HOME_PARITY_READING_LIST,
  COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT
} from "../../../test-utils/companion-home.fixtures"

type CompanionHomeWebMockResponse = {
  status: number
  contentType: "application/json"
  body: string
}

type CompanionHomeWebMockResult = {
  kind: "matched" | "unhandled"
  response: CompanionHomeWebMockResponse
}

const jsonResponse = (
  payload: unknown,
  status = 200
): CompanionHomeWebMockResponse => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(payload)
})

export function resolveCompanionHomeWebMock(
  method: string,
  pathname: string
): CompanionHomeWebMockResult {
  if (method === "GET" && pathname === "/api/v1/config/docs-info") {
    return {
      kind: "matched",
      response: jsonResponse(COMPANION_HOME_PARITY_DOCS_INFO)
    }
  }

  if (method === "GET" && pathname === "/api/v1/personalization/profile") {
    return {
      kind: "matched",
      response: jsonResponse(COMPANION_HOME_PARITY_PROFILE)
    }
  }

  if (method === "GET" && pathname.startsWith("/api/v1/companion/activity")) {
    return {
      kind: "matched",
      response: jsonResponse({
        items: COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT.activity,
        total: COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT.activityTotal,
        limit: 25,
        offset: 0
      })
    }
  }

  if (method === "GET" && pathname.startsWith("/api/v1/companion/knowledge")) {
    return {
      kind: "matched",
      response: jsonResponse({
        items: COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT.knowledge,
        total: COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT.knowledgeTotal
      })
    }
  }

  if (method === "GET" && pathname === "/api/v1/companion/goals") {
    return {
      kind: "matched",
      response: jsonResponse({
        items: COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT.goals,
        total: COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT.goals.length
      })
    }
  }

  if (method === "GET" && pathname.startsWith("/api/v1/notifications")) {
    return {
      kind: "matched",
      response: jsonResponse({
        items: COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT.inbox,
        total: COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT.inbox.length
      })
    }
  }

  if (method === "GET" && pathname.startsWith("/api/v1/reading/items")) {
    return {
      kind: "matched",
      response: jsonResponse(COMPANION_HOME_PARITY_READING_LIST)
    }
  }

  if (method === "GET" && pathname.startsWith("/api/v1/notes/")) {
    return {
      kind: "matched",
      response: jsonResponse(COMPANION_HOME_PARITY_NOTES)
    }
  }

  return {
    kind: "unhandled",
    response: jsonResponse(
      {
        error: "Unhandled Companion Home parity request",
        method,
        pathname
      },
      501
    )
  }
}
