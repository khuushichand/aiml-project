import { browser } from 'wxt/browser'
import { createSafeStorage } from '@/utils/safe-storage'
import { tldwRequest } from '@/services/tldw/request-core'
import type { PathOrUrl, AllowedMethodFor, UpperLower } from '@/services/tldw/openapi-guard'

export interface ApiSendPayload<P extends PathOrUrl = PathOrUrl, M extends AllowedMethodFor<P> = AllowedMethodFor<P>> {
  path: P
  method?: UpperLower<M>
  headers?: Record<string, string>
  body?: any
  noAuth?: boolean
  timeoutMs?: number
  responseType?: "json" | "text" | "arrayBuffer"
}

export interface ApiSendResponse<T = any> {
  ok: boolean
  status: number
  data?: T
  error?: string
  headers?: Record<string, string>
  retryAfterMs?: number | null
}

export async function apiSend<T = any, P extends PathOrUrl = PathOrUrl, M extends AllowedMethodFor<P> = AllowedMethodFor<P>>(
  payload: ApiSendPayload<P, M>
): Promise<ApiSendResponse<T>> {
  console.log('[API_SEND_DEBUG] apiSend called', {
    path: payload.path,
    method: payload.method,
    noAuth: payload.noAuth,
    hasRuntimeSendMessage: !!browser?.runtime?.sendMessage,
    hasRuntimeId: !!browser?.runtime?.id
  })

  try {
    // In web mode the wxt/browser shim provides sendMessage but no runtime.id.
    // Only use extension messaging when a real runtime is present.
    if (browser?.runtime?.sendMessage && browser?.runtime?.id) {
      console.log('[API_SEND_DEBUG] using extension messaging')
      const resp = await browser.runtime.sendMessage({ type: 'tldw:request', payload })
      console.log('[API_SEND_DEBUG] extension message response', { hasResp: !!resp, ok: resp?.ok, status: resp?.status })
      if (resp) {
        return resp as ApiSendResponse<T>
      }
    }
  } catch (err) {
    console.log('[API_SEND_DEBUG] extension message error', { error: String(err) })
    // fall through to direct request
  }
  console.log('[API_SEND_DEBUG] falling back to direct request')
  const storage = createSafeStorage()
  const config = await storage.get('tldwConfig').catch(() => null)
  console.log('[API_SEND_DEBUG] direct request config', { hasConfig: !!config, serverUrl: config?.serverUrl })
  return await tldwRequest(payload, {
    getConfig: () => Promise.resolve(config)
  })
}
