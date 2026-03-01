import { encode } from "gpt-tokenizer"
import type {
  ProgressResponse,
  TokenizeFileRequest,
  TokenizeRequest,
  TokenizeResponse
} from "../workers/tokenizer.worker"

type TokenizerMessage = TokenizeResponse | ProgressResponse
type MessageHandler = (payload: TokenizerMessage) => void

const estimateTokens = (text: string): number => {
  const normalized = String(text || "")
  const trimmed = normalized.trim()
  if (!trimmed) return 0
  try {
    return encode(trimmed).length
  } catch {
    return trimmed.split(/\s+/).length
  }
}

export class TokenizerWorker {
  private worker: Worker | null = null
  private handlers = new Map<string, MessageHandler>()
  private requestId = 0

  constructor() {
    this.initWorker()
  }

  private initWorker() {
    if (typeof Worker === "undefined") {
      this.worker = null
      return
    }

    try {
      this.worker = new Worker(
        new URL("../workers/tokenizer.worker.ts", import.meta.url),
        { type: "module" }
      )

      this.worker.onmessage = (event: MessageEvent<TokenizerMessage>) => {
        const payload = event.data
        const id = payload?.id
        if (!id) return
        const handler = this.handlers.get(id)
        if (!handler) return
        handler(payload)
        if ("tokenCount" in payload) {
          this.handlers.delete(id)
        }
      }
    } catch {
      this.worker = null
    }
  }

  async tokenize(text: string): Promise<number> {
    if (!this.worker) {
      return estimateTokens(text)
    }

    return await new Promise<number>((resolve, reject) => {
      const id = `single-${++this.requestId}`
      this.handlers.set(id, (payload) => {
        if ("tokenCount" in payload) {
          if (payload.error) {
            reject(new Error(payload.error))
            return
          }
          resolve(payload.tokenCount)
        }
      })

      const request: TokenizeRequest = {
        id,
        type: "single",
        text
      }
      this.worker!.postMessage(request)
    })
  }

  async tokenizeBatch(
    files: TokenizeFileRequest[],
    onProgress?: (progress: number, current: number, total: number) => void
  ): Promise<{
    totalTokens: number
    files: Array<{ path: string; tokenCount: number; lineCount: number }>
  }> {
    if (!this.worker) {
      const results = files.map((file) => ({
        path: file.path,
        tokenCount: estimateTokens(file.content),
        lineCount: String(file.content || "").split("\n").length
      }))
      return {
        totalTokens: results.reduce((sum, item) => sum + item.tokenCount, 0),
        files: results
      }
    }

    return await new Promise((resolve, reject) => {
      const id = `batch-${++this.requestId}`
      this.handlers.set(id, (payload) => {
        if ("progress" in payload) {
          onProgress?.(payload.progress, payload.current, payload.total)
          return
        }

        if (payload.error) {
          reject(new Error(payload.error))
          return
        }

        resolve({
          totalTokens: payload.tokenCount,
          files: payload.files ?? []
        })
      })

      const request: TokenizeRequest = {
        id,
        type: "batch",
        files
      }
      this.worker!.postMessage(request)
    })
  }

  terminate(): void {
    this.worker?.terminate()
    this.worker = null
    this.handlers.clear()
  }
}

let tokenizerWorkerInstance: TokenizerWorker | null = null

export const getTokenizerWorker = (): TokenizerWorker => {
  if (!tokenizerWorkerInstance) {
    tokenizerWorkerInstance = new TokenizerWorker()
  }
  return tokenizerWorkerInstance
}

export const terminateTokenizerWorker = (): void => {
  tokenizerWorkerInstance?.terminate()
  tokenizerWorkerInstance = null
}
