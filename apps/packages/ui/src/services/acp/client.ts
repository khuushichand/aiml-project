/**
 * ACP REST and WebSocket Client
 */

import type {
  ACPAgentListResponse,
  ACPSessionNewRequest,
  ACPSessionNewResponse,
  ACPSessionPromptRequest,
  ACPSessionPromptResponse,
  ACPWSClientMessage,
  ACPWSServerMessage,
} from "./types"

// -----------------------------------------------------------------------------
// Configuration
// -----------------------------------------------------------------------------

export interface ACPClientConfig {
  serverUrl: string
  getAuthHeaders: () => Promise<Record<string, string>>
  getAuthParams: () => Promise<{ token?: string; api_key?: string }>
}

// -----------------------------------------------------------------------------
// REST Client
// -----------------------------------------------------------------------------

export class ACPRestClient {
  constructor(private config: ACPClientConfig) {}

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.config.serverUrl}${path}`
    const headers = await this.config.getAuthHeaders()

    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...headers,
        ...options.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  /**
   * Get list of available agents and their configuration status
   */
  async getAvailableAgents(): Promise<ACPAgentListResponse> {
    return this.request<ACPAgentListResponse>("/api/v1/acp/agents")
  }

  /**
   * Create a new ACP session
   */
  async createSession(request: ACPSessionNewRequest): Promise<ACPSessionNewResponse> {
    return this.request<ACPSessionNewResponse>("/api/v1/acp/sessions/new", {
      method: "POST",
      body: JSON.stringify(request),
    })
  }

  /**
   * Send a prompt to an existing session
   */
  async sendPrompt(request: ACPSessionPromptRequest): Promise<ACPSessionPromptResponse> {
    return this.request<ACPSessionPromptResponse>("/api/v1/acp/sessions/prompt", {
      method: "POST",
      body: JSON.stringify(request),
    })
  }

  /**
   * Cancel the current operation in a session
   */
  async cancelSession(sessionId: string): Promise<void> {
    await this.request<{ status: string }>("/api/v1/acp/sessions/cancel", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    })
  }

  /**
   * Close and cleanup a session
   */
  async closeSession(sessionId: string): Promise<void> {
    await this.request<{ status: string }>("/api/v1/acp/sessions/close", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    })
  }

  /**
   * Poll for updates (fallback when WebSocket unavailable)
   */
  async getUpdates(sessionId: string, limit = 100): Promise<Array<Record<string, unknown>>> {
    const response = await this.request<{ updates: Array<Record<string, unknown>> }>(
      `/api/v1/acp/sessions/${sessionId}/updates?limit=${limit}`
    )
    return response.updates
  }
}

// -----------------------------------------------------------------------------
// WebSocket Client
// -----------------------------------------------------------------------------

export interface ACPWebSocketCallbacks {
  onOpen?: () => void
  onClose?: (code: number, reason: string) => void
  onError?: (error: Event) => void
  onMessage?: (message: ACPWSServerMessage) => void
}

export class ACPWebSocketClient {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private isClosedManually = false

  constructor(
    private config: ACPClientConfig,
    private callbacks: ACPWebSocketCallbacks = {}
  ) {}

  /**
   * Connect to the WebSocket endpoint for a session
   */
  async connect(sessionId: string): Promise<void> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.warn("WebSocket already connected")
      return
    }

    this.isClosedManually = false
    const authParams = await this.config.getAuthParams()

    // Build WebSocket URL
    const wsUrl = this.config.serverUrl.replace(/^http/i, "ws")
    const params = new URLSearchParams()
    if (authParams.token) params.set("token", authParams.token)
    if (authParams.api_key) params.set("api_key", authParams.api_key)

    const url = `${wsUrl}/api/v1/acp/sessions/${sessionId}/stream?${params.toString()}`

    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.callbacks.onOpen?.()
    }

    this.ws.onclose = (event) => {
      this.callbacks.onClose?.(event.code, event.reason)

      // Attempt reconnection if not manually closed
      if (!this.isClosedManually && event.code !== 4401) {
        this.scheduleReconnect(sessionId)
      }
    }

    this.ws.onerror = (event) => {
      this.callbacks.onError?.(event)
    }

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as ACPWSServerMessage
        this.callbacks.onMessage?.(message)
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e)
      }
    }
  }

  /**
   * Send a message to the server
   */
  send(message: ACPWSClientMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected")
    }
    this.ws.send(JSON.stringify(message))
  }

  /**
   * Send a permission response
   */
  respondToPermission(
    requestId: string,
    approved: boolean,
    batchApproveTier?: string
  ): void {
    this.send({
      type: "permission_response",
      request_id: requestId,
      approved,
      batch_approve_tier: batchApproveTier as any,
    })
  }

  /**
   * Send a cancel request
   */
  cancelOperation(sessionId: string): void {
    this.send({
      type: "cancel",
      session_id: sessionId,
    })
  }

  /**
   * Send a prompt via WebSocket
   */
  sendPrompt(
    sessionId: string,
    prompt: Array<{ role: "system" | "user" | "assistant"; content: string }>
  ): void {
    this.send({
      type: "prompt",
      session_id: sessionId,
      prompt,
    })
  }

  /**
   * Close the WebSocket connection
   */
  close(): void {
    this.isClosedManually = true
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /**
   * Check if connected
   */
  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  /**
   * Get the current WebSocket state
   */
  get state(): number | null {
    return this.ws?.readyState ?? null
  }

  private scheduleReconnect(sessionId: string): void {
    if (this.reconnectAttempts >= 10) {
      console.error("Max reconnection attempts reached")
      return
    }

    const delay = Math.min(
      1000 * Math.pow(1.5, this.reconnectAttempts),
      30000
    )

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectAttempts++
      console.log(`Attempting reconnection ${this.reconnectAttempts}/10...`)
      this.connect(sessionId).catch(console.error)
    }, delay)
  }
}

// -----------------------------------------------------------------------------
// Combined Client Factory
// -----------------------------------------------------------------------------

export function createACPClient(config: ACPClientConfig) {
  return {
    rest: new ACPRestClient(config),
    createWebSocket: (callbacks: ACPWebSocketCallbacks = {}) =>
      new ACPWebSocketClient(config, callbacks),
  }
}
