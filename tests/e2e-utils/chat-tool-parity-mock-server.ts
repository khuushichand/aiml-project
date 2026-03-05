import http from "node:http"
import type { AddressInfo } from "node:net"

type LoopParityServerStats = {
  chatCompletions: number
  models: number
  mcpTools: number
}

const readBody = (req: http.IncomingMessage) =>
  new Promise<string>((resolve) => {
    let body = ""
    req.on("data", (chunk) => {
      body += chunk
    })
    req.on("end", () => resolve(body))
  })

export const startLoopParityMockServer = async (modelId = "mock-model") => {
  const stats: LoopParityServerStats = {
    chatCompletions: 0,
    models: 0,
    mcpTools: 0
  }
  const server = http.createServer(async (req, res) => {
    const method = (req.method || "GET").toUpperCase()
    const url = req.url || "/"
    const requestOrigin =
      typeof req.headers.origin === "string" && req.headers.origin.length > 0
        ? req.headers.origin
        : "*"

    const sendJson = (code: number, payload: unknown) => {
      res.writeHead(code, {
        "content-type": "application/json",
        "access-control-allow-origin": requestOrigin,
        "access-control-allow-credentials": "true",
        vary: "origin"
      })
      res.end(JSON.stringify(payload))
    }

    if (method === "OPTIONS") {
      const requestedHeaders =
        typeof req.headers["access-control-request-headers"] === "string"
          ? req.headers["access-control-request-headers"]
          : "content-type, x-api-key, authorization, cache-control, accept"
      const requestedMethod =
        typeof req.headers["access-control-request-method"] === "string"
          ? req.headers["access-control-request-method"]
          : "POST"
      res.writeHead(204, {
        "access-control-allow-origin": requestOrigin,
        "access-control-allow-credentials": "true",
        "access-control-allow-methods": `GET,POST,OPTIONS,${requestedMethod}`,
        "access-control-allow-headers": requestedHeaders,
        vary: "origin"
      })
      return res.end()
    }

    if (url === "/api/v1/health" && method === "GET") {
      return sendJson(200, { status: "ok" })
    }

    if (url === "/openapi.json" && method === "GET") {
      return sendJson(200, {
        openapi: "3.0.0",
        info: { version: "mock" },
        paths: {
          "/api/v1/health": {},
          "/api/v1/chat/completions": {},
          "/api/v1/llm/models": {},
          "/api/v1/llm/models/metadata": {},
          "/api/v1/characters": {},
          "/api/v1/characters/search": {},
          "/api/v1/mcp/health": {},
          "/api/v1/mcp/tools": {},
          "/api/v1/mcp/tools/execute": {}
        }
      })
    }

    if (url.startsWith("/api/v1/llm/models/metadata") && method === "GET") {
      return sendJson(200, [
        {
          id: modelId,
          name: "Mock Model",
          provider: "mock",
          context_length: 8192,
          capabilities: ["chat", "tools"]
        }
      ])
    }

    if (url === "/api/v1/llm/models" && method === "GET") {
      stats.models += 1
      return sendJson(200, [modelId])
    }

    if (url.startsWith("/api/v1/characters") && method === "GET") {
      return sendJson(200, [])
    }

    if (url.startsWith("/api/v1/characters") && method === "POST") {
      return sendJson(200, [])
    }

    if (url === "/api/v1/mcp/health" && method === "GET") {
      return sendJson(200, { ok: true })
    }

    if (url.startsWith("/api/v1/mcp/tools") && method === "GET") {
      stats.mcpTools += 1
      return sendJson(200, [
        {
          name: "mock_tool",
          description: "Mock tool for parity tests",
          canExecute: true
        }
      ])
    }

    if (url === "/api/v1/mcp/tools/execute" && method === "POST") {
      const body = await readBody(req)
      let parsed: Record<string, unknown> = {}
      try {
        parsed = JSON.parse(body || "{}")
      } catch {
        parsed = {}
      }
      const toolName = String(parsed.tool_name || "")
      if (toolName === "mcp.tools.list") {
        return sendJson(200, {
          result: {
            tools: [
              {
                name: "mock_tool",
                description: "Mock tool for parity tests",
                canExecute: true
              }
            ]
          }
        })
      }
      if (toolName === "mcp.modules.list") {
        return sendJson(200, {
          result: {
            modules: [{ module_id: "mock.module" }]
          }
        })
      }
      if (toolName === "mcp.catalogs.list") {
        return sendJson(200, { result: { catalogs: [] } })
      }
      return sendJson(200, { result: {} })
    }

    if (url.startsWith("/api/v1/chat/completions") && method === "POST") {
      stats.chatCompletions += 1
      const body = await readBody(req)
      let stream = true
      try {
        const parsed = JSON.parse(body || "{}")
        stream = parsed?.stream !== false
      } catch {
        stream = true
      }

      if (!stream) {
        return sendJson(200, {
          choices: [{ message: { role: "assistant", content: "Mock reply" } }]
        })
      }

      res.writeHead(200, {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        connection: "keep-alive",
        "access-control-allow-origin": requestOrigin,
        "access-control-allow-credentials": "true",
        vary: "origin"
      })

      const emit = (payload: unknown) =>
        res.write(`data: ${JSON.stringify(payload)}\n\n`)

      emit({ event: "run_started", data: { run_id: "run_parity", seq: 1 } })
      setTimeout(() => {
        emit({
          event: "approval_required",
          data: {
            run_id: "run_parity",
            seq: 2,
            approval_id: "approval_1",
            tool_call_id: "tool_1"
          }
        })
      }, 400)
      setTimeout(() => {
        emit({ choices: [{ delta: { content: "Mock parity response" } }] })
      }, 650)
      setTimeout(() => {
        emit({
          event: "approval_resolved",
          data: {
            run_id: "run_parity",
            seq: 3,
            approval_id: "approval_1"
          }
        })
      }, 3200)
      setTimeout(() => {
        emit({
          event: "tool_started",
          data: { run_id: "run_parity", seq: 4, tool_call_id: "tool_1" }
        })
      }, 3500)
      setTimeout(() => {
        emit({
          event: "tool_finished",
          data: { run_id: "run_parity", seq: 5, tool_call_id: "tool_1" }
        })
      }, 4200)
      setTimeout(() => {
        emit({ event: "run_complete", data: { run_id: "run_parity", seq: 6 } })
      }, 5000)
      setTimeout(() => {
        res.write("data: [DONE]\n\n")
        res.end()
      }, 5300)
      return
    }

    if (url.startsWith("/api/v1/")) {
      return sendJson(200, {})
    }

    return sendJson(404, { detail: "not found" })
  })

  await new Promise<void>((resolve) =>
    server.listen(0, "127.0.0.1", resolve)
  )
  const addr = server.address() as AddressInfo
  return {
    server,
    baseUrl: `http://127.0.0.1:${addr.port}`,
    getStats: () => ({ ...stats })
  }
}
